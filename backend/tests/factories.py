"""Factory helpers so tests do not repeat boilerplate."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.base import utcnow
from app.models.enums import OfferStatus, OfferType, UserRole, VerificationStatus
from app.models.offer import Offer, OfferCountry, OfferEligibility
from app.models.taxonomy import Brand, Category, Country
from app.models.user import User

_CATEGORIES = [
    ("ai-tools", "AI Tools & AI Models", ["ai", "llm", "gpt", "model"]),
    ("vpn-security-privacy", "VPNs, Security & Privacy", ["vpn", "privacy", "proxy"]),
    ("cloud-hosting", "Cloud Hosting & Infrastructure", ["hosting", "cloud", "vps"]),
    ("software-productivity", "Software & Productivity", ["productivity", "notes"]),
    ("free-websites-utilities", "Free Websites & Online Utilities", ["utility", "converter"]),
    ("education-learning", "Education & Learning", ["learning", "courses", "students"]),
]

_BRANDS = [
    ("Proton", "proton.me", "vpn-security-privacy", ["protonvpn"]),
    ("Notion", "notion.so", "software-productivity", []),
    ("Replicate", "replicate.com", "ai-tools", []),
    ("DigitalOcean", "digitalocean.com", "cloud-hosting", ["digital ocean"]),
]

_COUNTRIES = [
    ("IN", "India", "India", "INR", "asia"),
    ("US", "United States", "United-States", "USD", "americas"),
    ("GB", "United Kingdom", "United-Kingdom", "GBP", "europe"),
    ("CA", "Canada", "Canada", "CAD", "americas"),
]


def seed_taxonomy(session: Session) -> dict[str, Category]:
    created: dict[str, Category] = {}
    for order, (slug, name, keywords) in enumerate(_CATEGORIES):
        category = Category(
            slug=slug,
            name=name,
            tagline=f"{name} deals",
            keywords=keywords,
            aliases=[],
            sort_order=order * 10,
        )
        session.add(category)
        created[slug] = category
    session.flush()
    return created


def seed_brands(session: Session, categories: dict[str, Category]) -> dict[str, Brand]:
    created: dict[str, Brand] = {}
    for name, domain, category_slug, aliases in _BRANDS:
        brand = Brand(
            name=name,
            slug=name.lower(),
            domain=domain,
            website_url=f"https://{domain}",
            aliases=aliases,
            category_id=categories[category_slug].id,
        )
        session.add(brand)
        created[name] = brand
    session.flush()
    return created


def seed_countries(session: Session) -> dict[str, Country]:
    created: dict[str, Country] = {}
    for code, name, slug, currency, region in _COUNTRIES:
        country = Country(code=code, name=name, slug=slug, currency=currency, region=region)
        session.add(country)
        created[code] = country
    session.flush()
    return created


def make_offer(
    session: Session,
    category: Category,
    *,
    brand: Brand | None = None,
    title: str = "Test offer",
    slug: str = "test-offer",
    offer_type: OfferType = OfferType.FREE_TRIAL,
    status: str = OfferStatus.PUBLISHED.value,
    verification: str = VerificationStatus.VERIFIED.value,
    original_price: float | None = 20.0,
    promo_price: float | None = 0.0,
    savings_percent: int = 100,
    savings_value: float = 20.0,
    trial_days: int | None = 30,
    expires_in_days: float | None = 20,
    is_global: bool = True,
    country_codes: tuple[str, ...] = (),
    requires_payment_method: bool = False,
    requires_new_user: bool = True,
    requires_student_id: bool = False,
    tags: list[str] | None = None,
    keywords: str = "",
    demo: bool = False,
    published_days_ago: int = 1,
    currency: str = "USD",
    is_genuinely_free: bool = False,
    is_featured: bool = False,
    is_handpicked: bool = False,
    coupon_code: str | None = None,
) -> Offer:
    now = utcnow()
    offer = Offer(
        slug=slug,
        title=title,
        short_description=keywords or f"Short description for {title}",
        description=f"Long form description for {title}. " * 8,
        category_id=category.id,
        brand_id=brand.id if brand else None,
        offer_type=offer_type.value,
        status=status,
        verification_status=verification,
        currency=currency,
        coupon_code=coupon_code,
        is_genuinely_free=is_genuinely_free,
        is_featured=is_featured,
        is_handpicked=is_handpicked,
        original_price=original_price,
        promo_price=promo_price,
        savings_value=savings_value,
        savings_percent=savings_percent,
        billing_period="monthly",
        trial_days=trial_days,
        starts_at=now - timedelta(days=published_days_ago + 5),
        expires_at=now + timedelta(days=expires_in_days) if expires_in_days is not None else None,
        published_at=now - timedelta(days=published_days_ago),
        is_global=is_global,
        requires_payment_method=requires_payment_method,
        requires_new_user=requires_new_user,
        requires_student_id=requires_student_id,
        eligibility_types=["new_users"] if requires_new_user else [],
        official_url=f"https://{brand.domain if brand else 'example.com'}/offer",
        how_to_redeem=["Step one", "Step two", "Step three"],
        tags=tags or [],
        popularity_score=10.0,
        quality_score=70.0,
        is_demo_data=demo,
    )
    session.add(offer)
    session.flush()

    for code in country_codes:
        session.add(
            OfferCountry(offer_id=offer.id, country_code=code, is_available=True)
        )
    if requires_student_id:
        session.add(
            OfferEligibility(offer_id=offer.id, rule="students", label="Students only", blocking=True)
        )
    session.flush()
    return offer


def make_user(
    session: Session,
    email: str = "tester@zexrdealhub.dev",
    *,
    role: str = UserRole.USER.value,
    password: str = "Passw0rdTest",
    country_code: str | None = "US",
    currency: str = "USD",
    interests: list[str] | None = None,
    email_notifications: bool = True,
) -> User:
    if country_code and not session.execute(
        select(Country.id).where(Country.code == country_code)
    ).first():
        session.add(
            Country(
                code=country_code,
                name=country_code,
                slug=country_code.lower(),
                currency=currency,
            )
        )
        session.flush()
    user = User(
        email=email,
        hashed_password=hash_password(password),
        display_name=email.split("@")[0],
        role=role,
        country_code=country_code,
        preferred_currency=currency,
        interests=interests or [],
        email_notifications=email_notifications,
    )
    session.add(user)
    session.flush()
    return user


def auth_headers(client, session: Session, user: User) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "Passw0rdTest"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}