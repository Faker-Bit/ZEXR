"""Email delivery + user notifications.

The platform writes to an `email_deliveries` outbox first so every message is
auditable, then hands off to the configured backend (`console`, `smtp`, or
`none`).  No card data is ever handled here — notifications only ever mention
offers, prices and links.
"""

from __future__ import annotations

import smtplib
from datetime import timedelta
from email.message import EmailMessage
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.db.base import utcnow
from app.models.enums import OfferStatus
from app.models.offer import Offer
from app.models.user import Alert, Bookmark, EmailDelivery, NewsletterSubscriber, User
from app.services.offers import OFFER_LOAD_OPTIONS, live_condition
from app.services.recommendations import matches_alert

log = get_logger("notifications")

BRAND_FOOTER = (
    "You get this because you saved or followed these offers on ZEXR Deal Hub.\n"
    "We never sell your data and we never ask for payment details."
)


def queue_email(
    session: Session,
    *,
    to_email: str,
    subject: str,
    template: str,
    payload: dict,
    user_id: str | None = None,
) -> EmailDelivery:
    delivery = EmailDelivery(
        user_id=user_id,
        to_email=to_email,
        subject=subject[:300],
        template=template,
        payload=payload,
        status="queued",
    )
    session.add(delivery)
    session.flush()
    _dispatch(delivery)
    return delivery


def _dispatch(delivery: EmailDelivery) -> None:
    backend = settings.email_backend
    if backend == "none":
        delivery.status = "suppressed"
        return
    body = render(delivery.template, delivery.payload or {})
    if backend == "console":
        log.info("email.console", to=delivery.to_email, subject=delivery.subject, body_preview=body[:200])
        delivery.status = "sent"
        delivery.sent_at = utcnow()
        return
    if backend == "smtp":
        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
                server.starttls()
                if settings.smtp_user:
                    server.login(settings.smtp_user, settings.smtp_password)
                message = EmailMessage()
                message["From"] = settings.email_from
                message["To"] = delivery.to_email
                message["Subject"] = delivery.subject
                message.set_content(body)
                server.send_message(message)
            delivery.status = "sent"
            delivery.sent_at = utcnow()
        except Exception as exc:
            log.warning("email.smtp_failed", to=delivery.to_email, error=str(exc))
            delivery.status = "failed"
            delivery.error = str(exc)[:500]
    else:
        delivery.status = "pending_backend"


# ------------------------------------------------------------------ render
def render(template: str, payload: dict) -> str:
    base = settings.site_url.rstrip("/")
    if template == "expiry_alert":
        offer = payload.get("offer", {})
        return (
            f"⏰ '{offer.get('title')}' expires in {payload.get('days_left', 'a few')} days\n\n"
            f"{offer.get('short_description', '')}\n\n"
            f"Claim it: {base}/offers/{offer.get('slug')}\n\n"
            f"{BRAND_FOOTER}"
        )
    if template == "weekly_digest":
        lines = [
            f"🧪 {payload.get('count', 0)} fresh deals verified in the last 7 days",
            "",
        ]
        for item in payload.get("offers", [])[:20]:
            lines.append(f"• {item['title']} — {item.get('summary', '')}")
            lines.append(f"  {base}/offers/{item['slug']}")
            lines.append("")
        lines.append(f"Explore everything: {base}/offers")
        lines.append("")
        lines.append(BRAND_FOOTER)
        return "\n".join(lines)
    if template == "alert_match":
        return (
            f"New match for your alert '{payload.get('label')}':\n\n"
            f"• {payload.get('title')}\n\n"
            f"Claim it: {base}/offers/{payload.get('slug')}\n\n{BRAND_FOOTER}"
        )
    return payload.get("body", "")


# ------------------------------------------------------------- dispatchers
def notify_expiring_bookmarks(session: Session, days: int = 3) -> int:
    now = utcnow()
    horizon = now + timedelta(days=days)
    rows = session.execute(
        select(Bookmark, User, Offer)
        .join(User, Bookmark.user_id == User.id)
        .join(Offer, Bookmark.offer_id == Offer.id)
        .where(
            Bookmark.notify_on_expiry.is_(True),
            User.email_notifications.is_(True),
            User.is_active.is_(True),
            Offer.expires_at.isnot(None),
            Offer.expires_at > now,
            Offer.expires_at <= horizon,
            Offer.status == OfferStatus.PUBLISHED.value,
        )
    ).all()

    sent = 0
    for bookmark, user, offer in rows:
        already = session.execute(
            select(EmailDelivery.id).where(
                EmailDelivery.user_id == user.id,
                EmailDelivery.template == "expiry_alert",
                EmailDelivery.status == "sent",
                EmailDelivery.created_at > now - timedelta(days=1),
            )
        ).first()
        if already:
            continue
        queue_email(
            session,
            to_email=user.email,
            subject=f"Expiring soon: {offer.title}",
            template="expiry_alert",
            user_id=user.id,
            payload={
                "days_left": max(1, (offer.expires_at - now).days),
                "offer": {
                    "title": offer.title,
                    "slug": offer.slug,
                    "short_description": offer.short_description,
                },
            },
        )
        sent += 1
    return sent


def dispatch_alerts(session: Session, limit_per_alert: int = 3) -> dict:
    now = utcnow()
    alerts = session.execute(
        select(Alert).where(Alert.is_active.is_(True))
    ).scalars().all()

    matched = 0
    notified = 0
    for alert in alerts:
        user = session.get(User, alert.user_id)
        if user is None or not user.email_notifications or not user.is_active:
            continue

        stmt = (
            select(Offer)
            .options(*OFFER_LOAD_OPTIONS)
            .where(live_condition())
            .order_by(Offer.published_at.desc())
            .limit(200)
        )
        if alert.category_id:
            stmt = stmt.where(Offer.category_id == alert.category_id)
        if alert.brand_id:
            stmt = stmt.where(Offer.brand_id == alert.brand_id)

        offers = list(session.execute(stmt).scalars().unique().all())
        fresh = [
            offer
            for offer in offers
            if matches_alert(offer, alert)
            and offer.published_at
            and (now - offer.published_at) < timedelta(days=3)
        ]
        if not fresh:
            continue

        matched += len(fresh)
        for offer in fresh[:limit_per_alert]:
            queue_email(
                session,
                to_email=user.email,
                subject=f"New {alert.label}",
                template="alert_match",
                user_id=user.id,
                payload={
                    "label": alert.label,
                    "title": offer.title,
                    "slug": offer.slug,
                },
            )
            notified += 1
        alert.last_triggered_at = now

    return {"alerts": len(alerts), "matches": matched, "notifications": notified}


def send_weekly_digest(session: Session) -> int:
    since = utcnow() - timedelta(days=7)
    rows = session.execute(
        select(Offer)
        .options(*OFFER_LOAD_OPTIONS)
        .where(live_condition(), Offer.published_at.isnot(None), Offer.published_at >= since)
        .order_by(Offer.popularity_score.desc())
        .limit(20)
    ).scalars().unique().all()

    if not rows:
        return 0

    payload = {
        "count": len(rows),
        "offers": [
            {
                "title": offer.title,
                "slug": offer.slug,
                "summary": offer.short_description[:160],
            }
            for offer in rows
        ],
    }

    subscribers = session.execute(
        select(NewsletterSubscriber).where(
            NewsletterSubscriber.is_active.is_(True),
            NewsletterSubscriber.frequency.in_(["weekly", "daily"]),
        )
    ).scalars().all()

    sent = 0
    for subscriber in subscribers:
        queue_email(
            session,
            to_email=subscriber.email,
            subject=f"{len(rows)} new verified deals this week",
            template="weekly_digest",
            payload=payload,
        )
        sent += 1
    return sent


def subscribers_count(session: Session) -> int:
    return int(
        session.execute(
            select(func.count(NewsletterSubscriber.id)).where(
                NewsletterSubscriber.is_active.is_(True)
            )
        ).scalar()
        or 0
    )


def recent_deliveries(session: Session, limit: int = 50) -> Sequence[EmailDelivery]:
    return list(
        session.execute(
            select(EmailDelivery).order_by(EmailDelivery.created_at.desc()).limit(limit)
        )
        .scalars()
        .all()
    )
