# ZEXR Deal Hub

**Find the Best Deals. Unlock More for Less.**

A production-ready deals discovery platform for **everyone, everywhere** — free trials, premium
offers, discounts, free credits, coupon codes, free software and genuinely free alternatives to paid
tools. Built for global audiences from day one, with country filters and local currency display.

The defining feature is not the UI: it is **automatic discovery and verification**. A background
worker reads permitted sources, extracts only what is literally written in them, and re-checks every
listing against the provider's own page on a schedule. Anything we cannot verify automatically is
labelled *needs manual verification* — it is never dressed up as confirmed.

```
Next.js 16 (App Router, TypeScript, Tailwind, shadcn-style, Framer Motion)
        │
        ▼
FastAPI (async-ready, SQLAlchemy 2.1, Alembic, Celery + Redis)
        │
        ▼
PostgreSQL  (SQLite for local development)
```

---

## Table of contents

- [Highlights](#highlights)
- [Repository layout](#repository-layout)
- [Quick start](#quick-start)
- [Docker](#docker)
- [Configuration](#configuration)
- [Demo data](#demo-data)
- [How verification works](#how-verification-works)
- [How discovery works](#how-discovery-works)
- [Search](#search)
- [API reference](#api-reference)
- [Testing](#testing)
- [Deployment](#deployment)
- [Trust, safety and monetisation](#trust-safety-and-monetisation)
- [Extending](#extending)

---

## Branding

The product is **ZEXR Deal Hub**.

- Wordmark: `ZEXR` in white + `DEAL HUB` in a green gradient, tagline
  *Freebies · Discounts · Premium*.
- Colours: lime/neon green (`#a3e635` primary, `#22c55e` deep green) on near-black.
- App icon: `frontend/public/icon.svg`.
- Full artwork: drop the exported PNG at **`frontend/public/logo.png`**. Until that
  file exists the header renders an inline SVG "Z" mark, so nothing looks broken.
  See `frontend/README-LOGO.txt`.

Key strings live in one place each: `app_name` in `backend/app/core/config.py`, and
`DEFAULT_TITLE` / `siteName` in `frontend/src/lib/seo.ts`.

### Demo accounts

```
admin@zexrdealhub.dev    / AdminPass123
reviewer@zexrdealhub.dev / ReviewPass123
user@zexrdealhub.dev     / UserPass123
```

---
## Highlights

| Area | What is built |
| --- | --- |
| **Discovery** | robots.txt-aware polite crawler, per-source and per-host rate limits, conditional GETs, exponential backoff with `Retry-After`, feed/API/HTML adapters, fingerprint + similarity dedupe, review queue. Nothing is auto-published. |
| **Verification** | Scheduled re-checks that record HTTP status, redirect target, price found and content fingerprint. Distinguishes *verified*, *needs manual*, *price changed*, *disputed* and *expired*. |
| **Search** | Intent parsing (`"30 days free vpn"` → category + duration + no-card), synonym expansion, taxonomy-driven vocabulary, portable SQL relevance scoring, autocomplete, typo tolerance with auto-correction. |
| **Directory** | 16 categories, filters for type, category, brand, country, currency, duration, savings, price, eligibility, card requirement and expiry, 9 sort orders, pagination, facets. |
| **Accounts** | Email + OAuth, bookmarks, expiry alerts, category follows, recently viewed, interest-based recommendations, country/currency preferences. Browsing never requires an account. |
| **Admin** | Offer moderation with bulk actions, review queue, source management with crawl policies, taxonomy, reports, submissions, users/roles, analytics and search-log. |
| **Platform** | Structured logging, rate limiting, caching, migrations, 141 automated tests, Docker, CI-ready. |

---

## Repository layout

```
zexrdealhub/
├── backend/
│   ├── app/
│   │   ├── api/v1/            # FastAPI routers (offers, search, auth, users, admin, …)
│   │   ├── core/              # config, security, logging, cache, rate limit, money
│   │   ├── db/                # declarative base, session, seed
│   │   ├── discovery/         # crawler, adapters, normaliser, dedupe, runner
│   │   ├── models/            # SQLAlchemy models + enums
│   │   ├── schemas/           # Pydantic request/response models
│   │   ├── services/          # offers, search, verification, analytics, notifications
│   │   └── workers/           # Celery app, tasks, in-process scheduler
│   ├── alembic/versions/      # migrations
│   ├── tests/                 # pytest suite
│   └── tools/smoke_test.py    # end-to-end API check against a running server
├── frontend/
│   └── src/
│       ├── app/               # App Router pages (public, account, admin, SEO routes)
│       ├── components/        # ui kit, site chrome, offer cards, admin shell
│       └── lib/               # API client, types, SEO helpers, formatting
├── docker-compose.yml
└── .env.example
```

---

## Quick start

**Prerequisites:** Python 3.11+, Node.js 20+.

### 1. Backend

```bash
cd backend
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate

pip install -r requirements-dev.txt
cp .env.example .env          # Windows: copy .env.example .env

# Local development uses SQLite and an in-process scheduler — no infra needed.
python -m app.db.seed         # taxonomy + real public deal sources
uvicorn app.main:app --reload
```

The API is now on <http://localhost:8000> and its interactive docs on
<http://localhost:8000/docs>.

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local   # Windows: copy .env.example .env.local

npm run dev
```

The site is now on <http://localhost:3000>.

### Demo accounts

| Role | Email | Password | Can do |
| --- | --- | --- | --- |
| Admin | `admin@zexrdealhub.dev` | `AdminPass123` | Everything, including deletion and role changes |
| Reviewer | `reviewer@zexrdealhub.dev` | `ReviewPass123` | Moderate and review, but not delete |
| User | `user@zexrdealhub.dev` | `UserPass123` | Bookmarks, alerts, recommendations |

> **Demo data is demo data.** Every seeded offer is flagged `is_demo_data`, rendered with a visible
> *Demo* badge, never marked verified, and excluded from the "verified" collections. It exists to
> exercise the UI and is never presented as a live, claimable offer.

---

## Docker

```bash
cp .env.example .env          # set SECRET_KEY and POSTGRES_PASSWORD

docker compose up --build -d                        # web + api + postgres + redis
docker compose --profile tools run --rm migrate     # alembic upgrade head
docker compose --profile tools run --rm seed        # optional demo content
```

Then visit <http://localhost:3000>.

To run discovery and verification in dedicated workers instead of inside the API process:

```bash
docker compose --profile celery up -d worker beat
# and set SCHEDULER_ENABLED=false in .env so jobs are not scheduled twice
```

---

## Configuration

Both tiers read from environment variables. Full templates:

- [`backend/.env.example`](backend/.env.example)
- [`frontend/.env.example`](frontend/.env.example)
- [`.env.example`](.env.example) (docker compose)

The settings you are most likely to change:

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./zexrdealhub.db` | PostgreSQL via `postgresql+psycopg://…` in production |
| `SECRET_KEY` | random | JWT signing — **must** be set explicitly in production |
| `DISCOVERY_ENABLED` | `true` | Master switch; when false the crawler refuses all outbound requests |
| `DISCOVERY_AUTO_PUBLISH` | `false` | Keep `false`. Discovered offers should enter the review queue |
| `VERIFY_INTERVAL_HOURS` | `12` | How often a published offer is re-checked |
| `SCHEDULER_ENABLED` | `true` | Disable when Celery beat owns the schedule |
| `CORS_ORIGINS` | localhost | Comma-separated allowed origins |

Source credentials are never stored in the database. Each source row names an **environment
variable** in `api_key_env`; the crawler reads it at request time.

---

## Real deal sources (no demo data required)

The platform ships with **three real, permissively-licensed public datasets** already wired up.
`python -m app.db.seed` installs them and `python -m app.cli discover` pulls real offers from them.

```bash
python -m app.cli sources list        # what is available, with licence + attribution
python -m app.cli sources install     # create/update the `sources` rows
python -m app.cli discover --force    # fetch and stage offers for review
```

| Source | Licence | What it gives |
| --- | --- | --- |
| [FreeTokens](https://github.com/luongnv89/freetokens) | MIT | ~250 hand-checked AI / developer credit offers, with real vendor URLs |
| [DevCheap](https://github.com/hasitpbhatt/devcheap) | MIT | ~230 developer deals, free tiers and promos, with real vendor URLs |
| [Steam specials](https://store.steampowered.com/api/featuredcategories) | Valve Web API terms | Current store discounts with real prices, converted from minor units |

Selection rules every entry in `app/discovery/catalog.py` must satisfy:

1. **Permissive licence** — MIT/Apache/CC/public-domain only. Datasets with unclear terms are
   deliberately excluded even when the data looks attractive.
2. **robots.txt permits it** — and the fetcher re-checks robots on every request, so a host that
   tightens its policy later simply stops being crawled.
3. **Direct vendor URLs** — not the aggregator's own landing page. Verification checks the vendor
   page, so an aggregator URL would make every verification meaningless.
4. **Structured payloads** — JSON/JSONL over HTTPS rather than scraping HTML.

Imported offers land in `pending_review` and are **never auto-published**. Bulk-publish them from
the admin review queue once you have eyeballed a sample.

### Coverage caveat, stated plainly

The three sources above are developer- and AI-focused, so the imported catalogue is heavily
weighted that way. Consumer categories (VPNs, food delivery, shopping, electronics) start empty
and need a consumer-oriented source before they can rank for anything. This is a data-coverage
limit, not a search bug — `free ai tools` returns 140+ hits while `free vpn` returns none because
there are no VPN offers, not because the query is broken.

---

## Demo data

Demo offers are **off by default**. The real sources above are what populate the catalogue; use
`--demo-offers` only when you need placeholder content (offline UI work, demos, load testing).

```bash
python -m app.db.seed                  # taxonomy + real public sources (no demo offers)
python -m app.db.seed --reset          # drop and rebuild everything
python -m app.db.seed --demo-offers    # additionally add clearly-labelled DEMO offers
python -m app.db.seed --no-users       # skip the operator accounts
python -m app.db.seed --no-sources     # skip installing the curated public sources
```

Every offer created by `--demo-offers` is flagged `is_demo_data=True`, badged in the UI, excluded
from "verified" collections, and never counted as real data.

### Schema management

**Alembic owns the schema. Seeding never calls `create_all`.** That distinction matters: tables built by
`create_all` are never stamped in `alembic_version`, so the next `alembic upgrade head` dies with
"table already exists" and `alembic check` reports "target database is not up to date".

`app.db.seed` therefore runs `alembic upgrade head` itself (a no-op when already current) and
`--reset` goes `downgrade base` → `upgrade head`. Working rules:

```bash
python -m alembic upgrade head              # apply
python -m alembic downgrade -1              # roll back one revision
python -m alembic check                     # must report "No new upgrade operations detected"

python -m alembic revision --autogenerate -m "add xyz"   # after changing app/models/*
```

`alembic/check` is clean against the committed migration, so any future diff it reports is genuine
model drift rather than pre-existing noise. `alembic/env.py` reads `DATABASE_URL` from application
settings, so migrations always target the same database as the app.

---

## Gaming: free-to-keep games and deep Steam discounts

A dedicated /gaming page fed by two robots-permitted Steam endpoints:

| Source | What it returns |
| --- | --- |
| Steam search, `maxprice=free&specials=1` | Games currently **free to keep** during the promotion window |
| Steam search, `discounts=80,85,90,95,100` | Games at 80% off or deeper |
| Steam `featuredcategories` | The everyday specials carousel with real USD prices |

`ash
python -m app.cli sources list                # see all feeds
python -m app.cli discover --source steam-free-keep --force
python -m app.cli discover --source steam-deep-discounts --force
`

Prices, discount percentages and store links come from the storefront itself, so a card cannot
claim a discount the store does not show. Anything promoted as free to keep is marked
`offer_type=free` with `promo_price=0`.

**Epic Games is deliberately not scraped.** `store.epicgames.com` returns **403** on
`robots.txt`, and this project does not crawl a site that blocks automated access. Adding Epic
needs either a data licence or a first-party feed.

---

## How verification works

```
 ┌────────────┐   schedule    ┌──────────────┐   pass    ┌──────────────┐
 │ published  │ ────────────▶ │ HTTP check   │ ─────────▶ │  verified    │
 │   offers   │  every 12h    │ + fingerprint│            │ + last_checked│
 └────────────┘               └──────────────┘            └──────────────┘
        │                              │
        │                              ├─ blocked / anti-bot  ─▶ needs_manual
        │                              ├─ page changed       ─▶ needs_manual + disputed
        │                              ├─ price drift        ─▶ disputed
        │                              └─ 404 / 410 ×3       ─▶ expired
        │
        └─ deadline passed ─────────────────────────────────▶ expired (archived)
```

The non-negotiable rule: **an offer is only marked verified when we actually reached the provider's
page and its fingerprint terms were still present.** Sources that need JavaScript, a login or a
paywall are never fetched at all — those offers are labelled for manual review instead.

Every check appends to `offer_verifications`, which is why the offer page can show full history
rather than a single "verified ✓".

---

## How discovery works

```
 source row (DB)
     │  respects robots.txt · per-source rate limit · per-host budget · backoff
     ▼
 adapter: rss | json_api | html_listing | affiliate_api | partner_api
     ▼
 normaliser: classify type · extract prices/duration/coupon/eligibility/countries
     │        (missing fields stay None — nothing is invented)
     ▼
 dedupe: canonical URL → fingerprint → title similarity
     │
     ├─ duplicate → merge fresh info, keep one listing
     ├─ confidence < 0.55 → stored as a rejected candidate
     └─ accepted → Offer(status=pending_review, verification=needs_manual)
                      ▼
                  admin review queue
```

Adapters are configuration-driven. A new partner API needs a `sources` row — no code change, no
migration:

```json
{
  "url": "https://partner.example.com/v2/offers",
  "auth": {"type": "header", "name": "X-Api-Key"},
  "query": {"status": "active"},
  "items_path": "data.offers",
  "url_template": "https://partner.example.com/offer/{id}",
  "price_divisor": 100,
  "offer_type": "discount",
  "fields": {
    "id": "id", "title": "name", "url": "landing_page",
    "offer_type": "promotion.type", "original_price": "pricing.list",
    "promo_price": "pricing.sale", "currency": "pricing.currency",
    "trial_days": "terms.trial_days", "expires_at": "terms.end_date",
    "coupon_code": "terms.code", "brand_name": "merchant.name",
    "category_slug": "category", "countries": "availability"
  }
}
```

`"format": "jsonl"` (or `ndjson`) switches the payload to newline-delimited JSON, which is how most
static open datasets on GitHub ship. Three options handle payloads that don't fit the common shape:

| Option | Purpose |
| --- | --- |
| `url_template` | Build the canonical URL from row fields, e.g. `{id}` — used for store APIs that omit links |
| `price_divisor` | Convert minor units to major, e.g. `100` when the API quotes `599` for `$5.99` |
| `offer_type` | A constant type for feeds whose items are all one kind (a "specials" carousel is all discounts) |

Custom adapters can be registered at runtime with
`app.discovery.registry.register("my_adapter", MyAdapter)`.

---

## Search

The interpreter is grounded entirely in rows that exist in the database. If it mis-parses a query it
degrades to plain keyword search — it can never invent a category or a brand.

| Query | Interpreted as |
| --- | --- |
| `30 days free vpn` | category `vpn-security-privacy`, `min_trial_days=30` |
| `ai tools with free credits` | category `ai-tools`, type `free_credits` |
| `free cloud hosting` | category `cloud-hosting` (no type filter — "free" alone is too weak to restrict) |
| `best software discounts` | type `discount`, keyword `software` |
| `free premium tools without a credit card` | `requires_payment_method=false` |
| `free student discount` | `discount`, plus a `students` eligibility match |
| `cheap cloud hostng` | auto-corrected to `cheap cloud hosting` |

Ranking is a portable SQL expression weighted across title, brand, category, description, tags and
coupon code, with boosts for verification, quality, popularity and savings. The same code path runs
on PostgreSQL and on the SQLite development database.

---

## API reference

Interactive documentation is served at `/docs` in development. Overview:

### Public

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Liveness + dependency check |
| `GET` | `/api/v1/home` | Homepage bundle in one round trip |
| `GET` | `/api/v1/offers` | Directory with the full filter surface |
| `GET` | `/api/v1/offers/facets` | Facet counts for the active query |
| `GET` | `/api/v1/offers/{slug}` | Full offer detail |
| `GET` | `/api/v1/offers/{slug}/verification` | Verification history |
| `GET` | `/api/v1/collections/{name}` | Curated rails (`trending`, `ending-soon`, `free`, …) |
| `GET` | `/api/v1/expired` | Recently expired archive |
| `GET` | `/api/v1/platform/stats` | Public counters |
| `GET` | `/api/v1/search` | Search with intent parsing and facets |
| `GET` | `/api/v1/search/suggest` | Autocomplete |
| `GET` | `/api/v1/search/parse` | Inspect how a query is interpreted |
| `GET` | `/api/v1/categories`, `/brands`, `/countries`, `/currencies` | Taxonomy |
| `GET` | `/api/v1/go/{slug}` | Tracked claim redirect |

### Account

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/v1/auth/register`, `/login`, `/refresh`, `/logout` | Sessions |
| `GET` | `/api/v1/auth/me` | Current profile |
| `GET/POST/PATCH` | `/api/v1/me` | Profile and preferences |
| `GET/POST/DELETE` | `/api/v1/me/bookmarks` | Saved offers |
| `GET/POST/PATCH/DELETE` | `/api/v1/me/alerts` | Alerts |
| `POST` | `/api/v1/me/recommendations` | Interest-based picks |
| `POST` | `/api/v1/newsletter`, `/reports`, `/submit`, `/events` | Interaction |

### Admin (role-protected)

`/api/v1/admin/` — dashboard, offers (create/update/bulk/status/delete), verify + verify sweep,
duplicates + merge, sources + runs, discovery sweep, candidates + decisions, categories, brands,
users + roles, reports, submissions, jobs, maintenance, search log.

---

### AI model API provider catalogue

A hand-curated list of AI model providers, gateways and self-hosted runtimes —
**60 entries** covering gateways (OpenRouter, Eden AI, Portkey, Cloudflare AI
Gateway…), hosted providers (Google AI Studio, Groq, Cerebras, Groq, NVIDIA NIM,
Mistral, Together, Fireworks, xAI, AI21…) and self-hosted runtimes (Ollama,
vLLM, llama.cpp, SGLang, LM Studio).

```bash
python -m app.cli providers            # list all 60 with their labels
python -m app.cli providers import     # import (idempotent)
python -m app.db.seed                  # includes it by default
```

**These are reported claims, not verified facts.** Each entry records the
originating label, and `CHECK` — meaning "free access reported but unconfirmed" —
is the most common one, because free tiers change weekly. Every imported row is
stored as:

| Field | Value | Why |
| --- | --- | --- |
| `verification_status` | `needs_manual` | Never marked verified — it is a claim from a docs page, not an automated check of a live offer URL |
| `eligibility_notes` | The vendor's wording | Rendered on the card behind a "Reported:" prefix |
| `internal_notes` | Full provenance | Label, type and the caveat |

Offers already verified from a live source are **skipped**, not overwritten. The
UI shows the reported access level so a documented claim is never mistaken for
something we confirmed.

---
## Testing

```bash
cd backend
pytest -q                                   # 124 unit + integration tests
python tools/smoke_test.py                  # 46 end-to-end checks against a running server

cd ../frontend
npm run typecheck
npm run build
```

The suite covers the public API, filters, currency conversion, search intent parsing, typo
tolerance, the discovery adapters and crawler safety rules, price normalisation, dedupe,
verification outcomes, analytics, notifications, authorisation boundaries and admin workflows.

---

## Deployment

### Checklist

1. Set a strong `SECRET_KEY` and `POSTGRES_PASSWORD`.
2. Point `DATABASE_URL` at PostgreSQL and run `alembic upgrade head`.
3. Set `ENVIRONMENT=production`, `DEBUG=false`, `COOKIE_SECURE=true`.
4. Set `CORS_ORIGINS` to your real site origin (no wildcards).
5. Configure `EMAIL_BACKEND=smtp` if you want real expiry alerts.
6. Keep `DISCOVERY_AUTO_PUBLISH=false`.
7. Choose one scheduler: in-process (`SCHEDULER_ENABLED=true`) **or** Celery beat — not both.
8. Add a real admin account and remove the seeded demo users.
9. Terminate TLS in front of both tiers.

### Scaling notes

- The API is stateless; scale horizontally behind a load balancer.
- Enable `SCHEDULER_ENABLED=false` and run `worker` + `beat` when you run more than one API replica.
- Redis backs the cache, rate limiter and Celery broker. Without it the API falls back to an
  in-process cache and the limiter becomes per-instance, which is fine for development only.
- Set `SITE_URL` correctly — canonical URLs, the sitemap and JSON-LD all derive from it.

---

## Trust, safety and monetisation

- **No invented offers.** Every listing links to the provider's own domain and traces back to a
  source we are permitted to read.
- **No fabricated verification.** Unverifiable listings are labelled, never marked verified.
- **Regional honesty.** Country availability is explicit on every card and detail page.
- **Free ≠ free trial.** Permanently free products are marked separately from trials that convert,
  including the renewal price where it is known.
- **Affiliate disclosure.** Affiliate links are tracked per offer and disclosed. Sponsored
  placements are badged and never outrank organic results.
- **No payment data, ever.** The platform has no payment processing and never asks for card details.
- **Reporting.** Any offer can be flagged; reports immediately mark it disputed and remove it from
  public listings until resolved.

---

## Extending

**Add a category** — insert a row; navigation, sitemap, facets and the search vocabulary all follow.

**Add a brand** — insert a row with `aliases`; those aliases feed query interpretation.

**Add a source** — insert a `sources` row with its adapter and JSON field map. No code change.

**Write a custom adapter** — subclass `SourceAdapter`, implement `fetch`/`parse`, register it:

```python
from app.discovery.adapters.base import AdapterContext, AdapterOutcome, SourceAdapter
from app.discovery.registry import register

class MyAdapter(SourceAdapter):
    name = "my_adapter"
    def fetch(self, ctx): ...
    def parse(self, ctx) -> AdapterOutcome: ...

register("my_adapter", MyAdapter)
```

**Add a scheduled job** — add a `JobSpec` to `app/workers/scheduler.py` and a matching entry in the
Celery beat schedule.

---

## Licence

Provided as a reference implementation. Add your own licence before using commercially.