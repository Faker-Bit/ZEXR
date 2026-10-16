# Architecture and data model

---

## 1. Why this shape

The platform has one hard requirement that shapes everything else: **a deal that is wrong is worse
than a deal that is missing.** So the system is built so that uncertainty is visible rather than
smoothed over.

Three consequences run through the whole design:

1. **Extraction never guesses.** A missing price stays `None`. Confidence is recorded, and
   low-confidence items are stored as rejected candidates rather than published.
2. **Verification states are explicit.** `verified`, `needs_manual`, `unverified`, `failed` are
   distinct and are rendered distinctly on every card.
3. **Discovery is never automatic by default.** `DISCOVERY_AUTO_PUBLISH` defaults to `false`;
   discovered offers land in a human review queue as `pending_review` / `needs_manual`.

---

## 2. Request flow

```
Browser
  │
  │  Next.js (App Router)
  │    server components ──► apiServer()  ──► http://api:8000/api/v1/...
  │    client components ──► apiClient()  ──► /api/v1/...  (same-origin, proxied)
  ▼
FastAPI
  routers ──► services ──► SQLAlchemy ──► PostgreSQL
                 │             │
                 │             └──► cache (Redis, in-process fallback)
                 └──► structured logging, rate limiting
  ▲
  │
Background (in-process scheduler, or Celery + beat)
  ├─ discover   ──► polite crawler ──► adapters ──► normaliser ──► dedupe ──► review queue
  ├─ verify     ──► HTTP check ──► fingerprint + price comparison ──► status transitions
  ├─ expire     ──► past-deadline offers leave the live set
  ├─ trending   ──► 7-day click ranking
  └─ notify     ──► outbox ──► console / SMTP
```

---

## 3. Data model

```
countries ──┬─< brands
            ├─< users ──┬─< bookmarks >── offers
            │           ├─< alerts
            │           ├─< recent_views
            │           └─< reports >─── offers
            └─< offer_countries >──── offers

categories ──< offers ──┬─< offer_prices        (per-market pricing)
                         ├─< offer_countries    (availability)
                         ├─< offer_eligibility  (rules)
                         ├─< offer_verifications (audit trail)
                         ├─< offer_alternatives  (free alternatives)
                         └─< offers (duplicates)

sources ──┬─< source_runs
          ├─< discovery_candidates
          └─< offers

events · daily_stats · search_query_logs   (analytics)
oauth_accounts · newsletter_subscribers · email_deliveries · submissions
```

### Design notes

**`offers.status`** and **`offers.verification_status`** are separate axes. Status answers *"is this
in the live set?"*; verification answers *"do we know it is true, and how do we know?"* — an offer can
be published but unverified (manually entered, not yet swept).

**`offer_verifications` is append-only.** The detail page renders the real history instead of a
single badge, which is the whole point of building verification into the product.

**`offer_prices` + `country_codes`** let a single offer carry region-specific pricing while the base
row holds the source currency. The API converts to the viewer's currency at read time and omits the
figure entirely when no rate exists for the pair.

**`discovery_candidates` is the audit log for discovery.** Every scraped item lands here — accepted,
rejected or duplicate — with the raw payload. That makes "why does this offer exist?" answerable
without re-running the crawl.

**`sources.config` is JSON.** A new partner API, RSS feed or HTML listing is a row, not a migration.

**Alembic owns the schema.** Models are the single source of truth and `0001_initial.py` is generated
from them, so `alembic check` reports zero drift. Seeding never calls `create_all` — tables built that
way carry no version stamp and break the next migration.

---

## 4. Offer lifecycle

```
                discovery / submission
                         │
                         ▼
                   DRAFT ──────────► REJECTED
                         │
                         ▼
                 PENDING_REVIEW        ← every discovered offer starts here
                         │
          ┌──────────────┼───────────────┐
          ▼              ▼               ▼
      PUBLISHED      DISPUTED         EXPIRED  ← deadline passed, or repeated 404s
          │
          └─ price / content drift ──► DISPUTED (removed from public listings)
```

Verification states are orthogonal and independent of the above:

```
UNVERIFIED ──► NEEDS_MANUAL ──► VERIFIED
     │                │
     └────────────────┴──► FAILED (transient: timeout, 5xx)
```

### Rules encoded in the code

| Rule | Where |
| --- | --- |
| Expired / disputed / duplicate offers never appear in live listings | `services/offers.py: live_condition` |
| A page that no longer contains the offer's fingerprint terms is *changed*, not *verified* | `services/verification.py: evaluate_offer` |
| Repeated 404/410 moves an offer to expired | `services/verification.py: _record` |
| Sources needing JavaScript or a login are skipped, never scraped around | `discovery/base.py`, `discovery/adapters/html_listing.py` |
| Items below the confidence threshold are stored rejected, not published | `discovery/runner.py: MIN_CONFIDENCE` |
| Prices only appear in the response when a real value exists for that pair | `services/serializers.py: _localised_prices` |

---

## 5. Search design

The interpreter (`services/search.py`) is deliberately conservative:

- It only maps words onto taxonomy that **exists in the database** (categories, brands, countries,
  their aliases and keywords).
- A bare "free" does **not** constrain `offer_type` — most good results are trials and credits that
  merely include something free.
- Multi-word brand aliases (`"proton vpn"`) are matched as phrases, never as single tokens, so the
  word "vpn" still resolves to the VPN category.
- Expansion terms boost ranking but are not *required*, so synonym expansion can never empty a
  result set on its own.
- If a query returns nothing and a corrected spelling returns something, the corrected results are
  served and the correction is reported to the user.

Relevance is a single portable SQL expression weighted across title, brand, category, description,
tags and coupon code, with boosts for verification, quality, popularity and savings — identical
behaviour on PostgreSQL and SQLite.

---

## 6. Trust model

| Signal | Source | Shown to users |
| --- | --- | --- |
| Verified | Successful HTTP check with matching fingerprint | Green badge + last-checked time |
| Needs manual | Source needs JS/login, or cannot be reached | Grey badge + explanation |
| Demo | Seeded sample data | Amber badge, never marked verified |
| Disputed | Report or drift detection | Warning banner, removed from live listings |
| Expired | Deadline passed or repeated failure | Archived in its own section |

Every one of these is enforced in the query layer, so a stale status cannot leak into a listing by
accident.

---

## 7. Performance

- Eager loading (`selectinload`) for card relationships; no N+1 on grid pages.
- Cursor-free pagination with a count over a subquery.
- Redis-backed caching for homepage and taxonomy payloads, with an in-process fallback.
- `AbortSignal.timeout` on every fetch so a slow API degrades to an empty state instead of hanging.
- Background work (verification, discovery, analytics) never blocks a request.
- Composite indexes on the filter axes (`status × expires_at`, `category × status`, `type × status`,
  `verification × last_checked_at`).

---

## 8. Security

- bcrypt password hashing (PBKDF2 fallback if the bcrypt wheel is unavailable).
- JWT access + refresh tokens; the access token is also set as an `httpOnly` cookie.
- Role guards on every admin route (`user` / `reviewer` / `admin`), enforced server-side — the
  client-side gate is UX only.
- Rate limits on auth, search, writes, reports and submissions.
- The crawler refuses non-http(s) schemes, loopback, link-local and private-range hosts.
- No payment data is ever stored or transmitted — the platform has no payment integration at all.