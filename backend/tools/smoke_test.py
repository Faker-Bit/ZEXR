"""End-to-end API smoke test against a running server (development helper)."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000/api/v1"


def get(path: str, token: str | None = None):
    req = urllib.request.Request(BASE + path)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.status, json.loads(response.read() or "null")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or "null")


def post(path: str, payload: dict | None = None, token: str | None = None):
    data = json.dumps(payload or {}).encode()
    req = urllib.request.Request(BASE + path, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.status, json.loads(response.read() or "null")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or "null")


def patch(path: str, payload: dict, token: str):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(BASE + path, data=data, method="PATCH")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.status, json.loads(response.read() or "null")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or "null")


def delete(path: str, token: str):
    req = urllib.request.Request(BASE + path, method="DELETE")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read()
            return response.status, json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        body = exc.read()
        return exc.code, json.loads(body) if body else None


CHECKS: list[tuple[str, str, object]] = []


def check(name: str, ok: bool, detail: object = "") -> None:
    CHECKS.append((name, "PASS" if ok else "FAIL", detail))


def main() -> int:
    status, health = get("/health")
    check("health", status == 200 and health["status"] == "ok", health.get("database"))

    status, home = get("/home?limit=4")
    check("home bundle", status == 200 and len(home["trending"]) > 0,
          f"trending={len(home.get('trending', []))} live={home.get('stats', {}).get('live_offers')}")

    status, cats = get("/categories")
    check("categories", status == 200 and len(cats) == 16, len(cats))
    first_cat = cats[0]["slug"]

    status, cat_offers = get(f"/categories/{first_cat}/offers?page_size=3")
    check("category offers", status == 200 and isinstance(cat_offers, list), first_cat)

    status, directory = get("/offers?page_size=5&sort=popular")
    check("directory", status == 200 and directory["total"] > 0, directory.get("total"))

    status, filters = get("/offers?type=free_trial&verified_only=false&page_size=5")
    check("filtered directory", status == 200 and filters["total"] > 0, filters.get("total"))

    status, ending = get("/offers?ending_within_days=14&page_size=5")
    check("ending soon filter", status == 200, ending.get("total"))

    status, facets = get("/offers/facets")
    check("facets", status == 200 and len(facets["offer_types"]) > 0, len(facets.get("offer_types", [])))

    status, searches = [
        get("/search?q=30%20days%20free%20vpn"),
        get("/search?q=ai%20tools%20with%20free%20credits"),
        get("/search?q=free%20cloud%20hosting"),
        get("/search?q=best%20software%20discounts"),
        get("/search?q=free%20premium%20tools%20without%20a%20credit%20card"),
    ][0]
    # These exercise the intent parser across the categories the *live* corpus
    # actually covers. The imported public datasets are developer/AI-focused
    # (see app/discovery/catalog.py), so consumer queries like "free vpn" or
    # "software discounts" would return nothing until a consumer source is added
    # — asserting on those would make this suite fail for a data reason.
    for query in [
        "ai%20tools%20with%20free%20credits",
        "free%20cloud%20hosting",
        "free%20premium%20tools%20without%20a%20credit%20card",
        "free%20api%20credits",
        "developer%20tools",
    ]:
        status, payload = get(f"/search?q={query}")
        check(f"search {urllib.request.unquote(query)[:28]}",
              status == 200 and payload["total"] > 0, payload.get("total"))

    status, typo = get("/search?q=cheap%20cloud%20hostng")
    check("typo tolerance", status == 200 and typo["total"] > 0,
          typo.get("did_you_mean"))

    status, suggest = get("/search/suggest?q=not")
    check("autocomplete", status == 200 and len(suggest) > 0, len(suggest))

    status, collection = get("/collections/ending-soon?limit=4")
    check("collection", status == 200 and isinstance(collection, list), len(collection))

    status, stats = get("/platform/stats")
    check("platform stats", status == 200 and stats["live_offers"] > 0, stats.get("live_offers"))

    status, detail_list = get("/offers?page_size=1")
    slug = detail_list["items"][0]["slug"]
    status, detail = get(f"/offers/{slug}")
    check("offer detail", status == 200 and detail["slug"] == slug,
          f"similar={len(detail.get('similar', []))}")

    status, history = get(f"/offers/{slug}/verification")
    check("verification history", status == 200 and "history" in history,
          len(history.get("history", [])))

    status, availability = get(f"/search/availability?slug={slug}")
    check("availability", status == 200 and "countries" in availability, availability.get("is_global"))

    status, payload = post("/auth/login", {"email": "user@zexrdealhub.dev", "password": "UserPass123"})
    check("login", status == 200 and "access_token" in payload, payload.get("detail"))
    token = payload.get("access_token", "")

    status, me = get("/auth/me", token)
    check("profile", status == 200 and me["email"] == "user@zexrdealhub.dev", me.get("role"))

    offer_id = detail_list["items"][0]["id"]
    status, bookmark = post("/me/bookmarks", {"offer_id": offer_id}, token)
    check("bookmark create", status == 201, bookmark.get("id"))

    status, bookmarks = get("/me/bookmarks", token)
    check("bookmark list", status == 200 and len(bookmarks) >= 1, len(bookmarks))

    status, checked = get(f"/me/bookmarks/check?offer_ids={offer_id}", token)
    check("bookmark check", status == 200 and offer_id in checked["bookmarked"], checked)

    status, alert = post("/me/alerts", {"kind": "category", "category_id": cats[0]["id"]}, token)
    check("alert create", status == 201, alert.get("match_count"))

    status, alerts = get("/me/alerts", token)
    check("alert list", status == 200 and len(alerts) >= 1, len(alerts))

    status, recs = post("/me/recommendations", {"limit": 4, "interests": ["ai"]}, token)
    check("recommendations", status == 200 and len(recs) >= 1, len(recs))

    status, newsletter = post("/newsletter", {"email": "smoke@example.com", "interests": ["ai"]})
    check("newsletter", status == 200 and newsletter["ok"], newsletter.get("message"))

    status, report = post("/reports", {"offer_id": offer_id, "reason": "other", "details": "smoke"}, token)
    check("report", status == 201, report.get("detail"))

    status, unsub = post("/auth/logout", {})
    check("logout", status == 200, None)

    # ---------------------------------------------------------------- admin
    status, admin_login = post("/auth/login", {"email": "admin@zexrdealhub.dev", "password": "AdminPass123"})
    admin_token = admin_login.get("access_token", "")
    check("admin login", status == 200 and bool(admin_token))

    status, forbidden = get("/admin/stats")
    check("admin requires auth", status in (401, 403), status)

    status, admin_stats = get("/admin/stats", admin_token)
    check("admin stats", status == 200 and admin_stats["total_offers"] > 0,
          f"live={admin_stats.get('live_offers')} sources={admin_stats.get('total_sources')}")

    status, analytics = get("/admin/analytics?days=30", admin_token)
    check("admin analytics", status == 200, len(analytics.get("top_categories", [])))

    status, admin_offers = get("/admin/offers?page_size=3", admin_token)
    check("admin offers", status == 200 and len(admin_offers["items"]) > 0, admin_offers.get("total"))

    status, sources = get("/admin/sources", admin_token)
    check("admin sources", status == 200 and len(sources) >= 4, len(sources))

    status, candidates = get("/admin/candidates", admin_token)
    check("admin candidates", status == 200, candidates.get("total"))

    status, dupes = get("/admin/duplicates", admin_token)
    check("admin duplicates", status == 200, len(dupes))

    status, jobs = get("/admin/jobs", admin_token)
    check("admin jobs", status == 200 and len(jobs) >= 5, len(jobs))

    status, admin_cats = get("/admin/categories", admin_token)
    check("admin categories", status == 200 and len(admin_cats) == 16, len(admin_cats))

    status, reports = get("/admin/reports", admin_token)
    check("admin reports", status == 200 and len(reports) >= 1, len(reports))

    status, users = get("/admin/users", admin_token)
    check("admin users", status == 200 and len(users) >= 3, len(users))

    # Every moderation transition below runs against an offer this test owns.
    # Reaching into `admin_offers["items"][0]` instead would publish and feature
    # a *real* offer, and — once the leftovers piled up — one of its own
    # previously created rows.
    status, created = post(
        "/admin/offers",
        {
            "title": "Smoke test offer from the admin API",
            "short_description": "Created by the automated smoke test to prove the write path works.",
            "description": "Created by the API smoke test and deleted again before it finishes.",
            "category_id": cats[0]["id"],
            "offer_type": "free_trial",
            "currency": "USD",
            "trial_days": 14,
            "official_url": "https://example.com/smoke-offer",
            "status": "pending_review",
            "verification_status": "unverified",
        },
        admin_token,
    )
    check("admin create offer", status == 201, created.get("slug"))

    if status == 201:
        offer_id = created["id"]
        status, changed = patch(
            f"/admin/offers/{offer_id}/status",
            {"status": "published", "is_featured": True},
            admin_token,
        )
        check("admin status change", status == 200 and changed.get("status") == "published",
              changed.get("status"))

        status, readback = get(f"/admin/offers/{offer_id}", admin_token)
        check("admin read back", status == 200, readback.get("slug"))

        status, _ = patch(
            f"/admin/offers/{offer_id}/status", {"status": "rejected"}, admin_token
        )
        status, _ = delete(f"/admin/offers/{offer_id}", admin_token)
        check("admin delete offer (cleanup)", status in (200, 204), status)
    else:
        check("admin status change", False, "create failed")
        check("admin read back", False, "create failed")
        check("admin delete offer (cleanup)", False, "create failed")

    print()
    failures = 0
    for name, status_text, detail in CHECKS:
        flag = "OK  " if status_text == "PASS" else "FAIL"
        if status_text != "PASS":
            failures += 1
        print(f"[{flag}] {name:<44} {detail}")
    print(f"\n{len(CHECKS) - failures}/{len(CHECKS)} checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())