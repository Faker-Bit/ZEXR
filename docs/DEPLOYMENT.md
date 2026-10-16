# Deployment

Everything needed to run ZEXR Deal Hub outside local development.

---

## 1. Prerequisites

| Component | Minimum | Notes |
| --- | --- | --- |
| PostgreSQL | 14+ | `pg_trgm` is recommended but not required — search uses portable SQL |
| Redis | 6+ | Cache, rate-limit store and Celery broker |
| Python | 3.11+ | Container image uses 3.13 |
| Node.js | 20+ | Container image uses 22 |

---

## 2. Configuration

Create a `.env` at the repository root from `.env.example`.

```bash
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(48))"
```

Required for production:

```dotenv
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=<generated>
POSTGRES_PASSWORD=<strong password>
DATABASE_URL=postgresql+psycopg://zexrdealhub:<password>@<host>:5432/zexrdealhub
REDIS_URL=redis://:<password>@<host>:6379/0
SITE_URL=https://your-domain.example
CORS_ORIGINS=https://your-domain.example
COOKIE_SECURE=true
```

Keep these at their safe defaults:

```dotenv
DISCOVERY_AUTO_PUBLISH=false   # everything discovered enters review
```

---

## 3. Schema

```bash
cd backend
alembic upgrade head
```

Seed the taxonomy (safe to run repeatedly). Skip demo offers in production:

```bash
python -m app.db.seed --no-demo --no-users
```

Then create the first admin:

```bash
python -c "
from app.db.session import SessionLocal
from app.models.user import User
from app.core.security import hash_password
from app.models.enums import UserRole

session = SessionLocal()
session.add(User(
    email='you@your-domain.example',
    hashed_password=hash_password('use-a-password-manager'),
    role=UserRole.ADMIN.value,
    email_verified=True,
))
session.commit()
print('admin created')
"
```

---

## 3b. Billing and webhooks

Billing is optional. With no provider keys set the site runs free-tier only and
the pricing page reports that no gateway is configured.

```bash
BILLING_ENABLED=true
BILLING_FREE_OFFER_LIMIT=12
BILLING_TRIAL_DAYS=7
BILLING_GRACE_DAYS=7

# Stripe
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRO_PRICE_ID=price_...

# Razorpay
RAZORPAY_KEY_ID=rzp_live_...
RAZORPAY_KEY_SECRET=...
RAZORPAY_WEBHOOK_SECRET=...
```

Register both webhooks — they must be reachable from the public internet:

```
POST https://api.example.com/api/v1/billing/webhook/stripe
POST https://api.example.com/api/v1/billing/webhook/razorpay
```

Stripe events: `customer.subscription.created|updated|deleted`.
Razorpay events: `subscription.activated|charged|halted|cancelled|completed|expired|paused`.

Webhook secrets are mandatory. An unsigned or replayed payload is rejected with
`400`, and Stripe signatures older than five minutes are refused outright.

Reconciliation is worth scheduling: providers occasionally drop a webhook, so a
periodic re-sync from the provider's own API keeps `subscriptions` honest. The
`current_period_end` check means a missed webhook downgrades access rather than
leaving it stuck on.

> `POST /api/v1/billing/dev-grant` is hard-blocked when `ENVIRONMENT=production`.
> Verify that before go-live.

---
## 4. Run

### Docker Compose

```bash
docker compose up --build -d
docker compose --profile tools run --rm migrate
```

Services: `web` (:3000), `api` (:8000), `postgres`, `redis`.

### Dedicated workers

Run Celery when you have more than one API replica, and turn off the in-process
scheduler so jobs are not scheduled twice:

```dotenv
SCHEDULER_ENABLED=false
```

```bash
docker compose --profile celery up -d worker beat
```

### Manual (systemd-style)

```bash
# API
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 --proxy-headers

# Worker
celery -A app.workers.celery_app.celery_app worker --loglevel=info --concurrency=4

# Beat
celery -A app.workers.celery_app.celery_app beat --loglevel=info

# Web
npm run build && npm run start
```

---

## 5. Reverse proxy and TLS

Terminate TLS in front of both tiers. The web tier must forward `/api/*` to the API, or the
`rewrites` rule in `next.config.mjs` will do it (set `API_INTERNAL_URL`).

```nginx
server {
  listen 443 ssl http2;
  server_name your-domain.example;

  ssl_certificate     /etc/letsencrypt/live/your-domain.example/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/your-domain.example/privkey.pem;

  client_max_body_size 2m;

  location /api/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Country-Code $http_cf_ipcountry;   # optional geo header
  }

  location / {
    proxy_pass http://127.0.0.1:3000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}
```

Sending an `X-Country-Code` header makes the API personalise availability and currency from the
first request — worth enabling if you sit behind Cloudflare or a CDN that exposes geo headers.

---

## 6. Scheduled jobs

| Job | Default cadence | What it does |
| --- | --- | --- |
| `verify` | every 60 min | Re-checks published offers; flags price/content changes |
| `discover` | every 4 h | Polls active sources and stages new candidates |
| `expiry` | every 15 min | Moves past-deadline offers out of live results |
| `trending` | every 30 min | Recomputes `trending_rank` from the last 7 days |
| `rollup` | every 12 h | Aggregates raw events into `daily_stats` |
| `alerts` | every 3 h | Saved-offer expiry emails and alert matching |
| `digest` | twice daily | Weekly newsletter digest |

Tune the verify cadence with `VERIFY_INTERVAL_HOURS`. Run any job by hand:

```bash
python -m app.cli verify --limit 100
python -m app.cli discover --force
python -m app.cli expire
python -m app.cli stats
```

---

## 7. Email

Alerts and digests are written to an `email_deliveries` outbox first, then dispatched. Configure:

```dotenv
EMAIL_BACKEND=smtp
SMTP_HOST=smtp.provider.example
SMTP_PORT=587
SMTP_USER=...
SMTP_PASSWORD=...
EMAIL_FROM=no-reply@your-domain.example
```

`EMAIL_BACKEND=console` logs the message body instead — useful for testing.
`EMAIL_BACKEND=none` records it without sending.

---

## 8. Observability

- `GET /api/v1/health` — database, cache and scheduler status. Use it as the container health check.
- Logs are structured (structlog). In production they are emitted as JSON.
- The admin overview surfaces catalogue health, the review queue size, source health and
  verification success rate.

Ship logs to your aggregator by pointing `STDOUT` at it, or switch the console renderer for
`ENVIRONMENT=development`.

---

## 8b. Subscriptions

Copy the billing block from `.env.example` into the environment and fill in
whichever gateway you use. Both are optional; with neither configured the pricing
page reports that billing is unavailable and everything stays on the free tier.

### Stripe

```bash
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_PRO_PRICE_ID=price_...        # a recurring monthly price
STRIPE_WEBHOOK_SECRET=whsec_...
```

Register the webhook endpoint and copy its signing secret:

```
https://your-domain.example/api/v1/billing/webhook/stripe
  events: customer.subscription.created|updated|deleted
```

### Razorpay

```bash
RAZORPAY_KEY_ID=rzp_live_...
RAZORPAY_KEY_SECRET=...
RAZORPAY_PRO_PLAN_ID=plan_...
RAZORPAY_WEBHOOK_SECRET=<from dashboard>
```

```
https://your-domain.example/api/v1/billing/webhook/razorpay
  events: subscription.activated | subscription.charged |
          subscription.halted | subscription.cancelled |
          subscription.completed | subscription.expired
```

### Verify before going live

```bash
curl -s localhost:8000/api/v1/billing/plans | jq '.providers'
# configured: true means the key + price/plan id are both present

# local smoke test without touching a gateway
curl -X POST localhost:8000/api/v1/billing/dev-grant \
  -H "Authorization: Bearer $TOKEN" -d '{"days":1}' -H 'Content-Type: application/json'
```

Confirm `dev-grant` is refused in production — it is gated on `ENVIRONMENT=production`.
Both webhook endpoints return **400** on a bad signature; never disable that check.

---
## 9. Backups

Back up PostgreSQL:

```bash
pg_dump -Fc -U zexrdealhub zexrdealhub > zexrdealhub-$(date +%F).dump
pg_restore -d zexrdealhub --clean zexrdealhub-$(date +%F).dump
```

The `offers`, `offer_verifications` and `events` tables are the ones that matter. Verification
history older than 120 days is pruned automatically by the `purge-verifications` Celery task.

---

## 10. Going live checklist

- [ ] `SECRET_KEY` is long, random and unique to this deployment
- [ ] `DEBUG=false`, `ENVIRONMENT=production`
- [ ] `CORS_ORIGINS` contains only your real origins
- [ ] `COOKIE_SECURE=true` and TLS terminates in front of both tiers
- [ ] `alembic upgrade head` applied; demo accounts removed
- [ ] Webhook endpoints registered and signing secrets set (if billing enabled)
- [ ] `SITE_URL` set correctly (canonical URLs, sitemap, JSON-LD)
- [ ] Exactly one scheduler (in-process **or** Celery beat)
- [ ] `DISCOVERY_AUTO_PUBLISH=false`
- [ ] SMTP configured and a test digest delivered
- [ ] Backups scheduled and a restore rehearsed
- [ ] Rate limits reviewed (`RATE_LIMIT_*`)