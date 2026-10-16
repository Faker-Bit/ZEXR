"""Management CLI for the ZEXR Deal Hub API.

    python -m app.cli seed                 # seed taxonomy + demo data
    python -m app.cli seed --reset         # drop, recreate and seed
    python -m app.cli migrate              # alembic upgrade head
    python -m app.cli verify [--limit 50]  # run a verification sweep now
    python -m app.cli discover [--force]   # run one discovery sweep now
    python -m app.cli expire               # expire finished offers
    python -m app.cli trending             # recompute trending ranks
    python -m app.cli rollup               # roll events into daily stats
    python -m app.cli stats                # print a catalogue snapshot
"""

from __future__ import annotations

import argparse
import json

from app.db.base import Base
from app.db.session import SessionLocal, engine


def cmd_seed(args: argparse.Namespace) -> int:
    from app.db.seed import seed

    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        if args.reset:
            Base.metadata.drop_all(bind=engine)
            Base.metadata.create_all(bind=engine)
        counts = seed(session, demo=not args.no_demo, demo_users=not args.no_users)
    finally:
        session.close()
    print(json.dumps(counts, indent=2))
    return 0


def cmd_migrate(args: argparse.Namespace) -> int:
    from alembic import command
    from alembic.config import Config

    config = Config("alembic.ini")
    command.upgrade(config, args.revision)
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    from app.services.verification import run_verification_sweep

    session = SessionLocal()
    try:
        result = run_verification_sweep(
            session, limit=args.limit, only_stale=not args.all_offers
        )
        session.commit()
    finally:
        session.close()
    print(json.dumps(result.model_dump(mode="json"), indent=2, default=str))
    return 0


def cmd_discover(args: argparse.Namespace) -> int:
    from app.discovery.runner import run_sweep

    session = SessionLocal()
    try:
        result = run_sweep(
            session,
            source_keys=[args.source] if args.source else None,
            force=args.force,
            max_sources=args.max_sources,
        )
        session.commit()
    finally:
        session.close()
    print(json.dumps(result.model_dump(mode="json"), indent=2, default=str))
    return 0


def cmd_sources(args: argparse.Namespace) -> int:
    """List or install the curated public deal datasets."""
    from app.discovery import catalog

    if args.action == "list":
        for entry in catalog.describe():
            print(f"{entry['key']:22} {entry['source_type']:10} {entry['name']}")
            print(f"{'':22} {entry['license_note']}")
            print(f"{'':22} {entry['feed_url']}")
            print()
        return 0

    session = SessionLocal()
    try:
        result = catalog.install(session, keys=[args.source] if args.source else None)
        session.commit()
    finally:
        session.close()
    print(json.dumps(result, indent=2))
    return 0


def cmd_auth_doctor(args: argparse.Namespace) -> int:
    """Report exactly what is missing for email, Google and GitHub sign-in.

    Exists because "sign-in is not configured" is a useless error to debug
    against: this prints the precise keys, where to get them, and the redirect
    URI that has to match the provider console character for character.
    """
    from app.core.config import settings

    redirect = settings.oauth_redirect_uri
    lines: list[str] = []

    def row(label: str, ok: bool, detail: str) -> None:
        lines.append(f"  [{'ok ' if ok else 'MISSING'}] {label:<22} {detail}")

    lines.append("")
    lines.append("Email sign-in")
    row("EMAIL_ENABLED", True, "always available")

    lines.append("")
    lines.append(f"Google sign-in — redirect URI must be exactly: {redirect}")
    row("GOOGLE_CLIENT_ID", bool(settings.google_client_id),
        "console.cloud.google.com/apis/credentials → OAuth client ID (Web application)")
    row("GOOGLE_CLIENT_SECRET", bool(settings.google_client_secret),
        "shown on the same credentials page")

    lines.append("")
    lines.append(f"GitHub sign-in — redirect URI must be exactly: {redirect}")
    row("GITHUB_CLIENT_ID", bool(settings.github_client_id),
        "github.com/settings/developers → OAuth Apps → New OAuth App")
    row("GITHUB_CLIENT_SECRET", bool(settings.github_client_secret),
        "shown on the same OAuth App page")

    google_ok = bool(settings.google_client_id and settings.google_client_secret)
    github_ok = bool(settings.github_client_id and settings.github_client_secret)
    lines.append("")
    lines.append("Result")
    lines.append(f"  Google  {'ready' if google_ok else 'not configured'}")
    lines.append(f"  GitHub  {'ready' if github_ok else 'not configured'}")
    if google_ok or github_ok:
        lines.append("")
        lines.append("  Restart the API, then check GET /api/v1/auth/providers")
    else:
        lines.append("")
        lines.append("  Add the keys above to backend/.env, restart the API, then re-run:")
        lines.append("      python -m app.cli auth doctor")
    lines.append("")

    print("\n".join(lines))
    return 0


def cmd_providers(args: argparse.Namespace) -> int:
    """List or import the curated AI provider catalogue."""
    from app.db.provider_catalog import CATALOGUE, import_catalogue

    if args.action == "list":
        for entry in CATALOGUE:
            print(f"{entry.access:<8} {entry.label:<10} {entry.name}")
        print(f"\n{len(CATALOGUE)} entries")
        return 0

    session = SessionLocal()
    try:
        result = import_catalogue(session)
        session.commit()
    finally:
        session.close()
    print(json.dumps(result, indent=2))
    return 0


def cmd_expire(args: argparse.Namespace) -> int:
    from app.services.verification import expire_finished_offers

    session = SessionLocal()
    try:
        count = expire_finished_offers(session)
        session.commit()
    finally:
        session.close()
    print(f"expired {count} offer(s)")
    return 0


def cmd_trending(args: argparse.Namespace) -> int:
    from app.services.analytics import bump_trending

    session = SessionLocal()
    try:
        bump_trending(session)
        session.commit()
    finally:
        session.close()
    print("trending ranks recomputed")
    return 0


def cmd_rollup(args: argparse.Namespace) -> int:
    from app.services.analytics import rollup_events

    session = SessionLocal()
    try:
        moved = rollup_events(session, days=args.days)
        session.commit()
    finally:
        session.close()
    print(f"rolled up {moved} events")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    from app.services.analytics import dashboard_stats

    session = SessionLocal()
    try:
        stats = dashboard_stats(session)
    finally:
        session.close()
    print(json.dumps(stats.model_dump(mode="json"), indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="app.cli", description="ZEXR Deal Hub management CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    seed = sub.add_parser("seed", help="seed taxonomy and demo data")
    seed.add_argument("--reset", action="store_true", help="drop all tables first")
    seed.add_argument("--no-demo", action="store_true")
    seed.add_argument("--no-users", action="store_true")
    seed.set_defaults(func=cmd_seed)

    migrate = sub.add_parser("migrate", help="run alembic migrations")
    migrate.add_argument("--revision", default="head")
    migrate.set_defaults(func=cmd_migrate)

    verify = sub.add_parser("verify", help="re-check offer pages")
    verify.add_argument("--limit", type=int, default=50)
    verify.add_argument("--all-offers", action="store_true", help="ignore staleness")
    verify.set_defaults(func=cmd_verify)

    discover = sub.add_parser("discover", help="poll configured sources")
    discover.add_argument("--source", help="single source key")
    discover.add_argument("--force", action="store_true", help="ignore the throttle")
    discover.add_argument("--max-sources", type=int, default=10)
    discover.set_defaults(func=cmd_discover)

    sources = sub.add_parser(
        "sources", help="list or install curated public deal datasets"
    )
    sources.add_argument(
        "action", nargs="?", default="list", choices=["list", "install"]
    )
    sources.add_argument("--source", help="install only this source key")
    sources.set_defaults(func=cmd_sources)

    auth = sub.add_parser("auth", help="check sign-in configuration")
    auth.add_argument("action", nargs="?", default="doctor", choices=["doctor"])
    auth.set_defaults(func=cmd_auth_doctor)

    providers = sub.add_parser(
        "providers", help="curated AI model API provider catalogue"
    )
    providers.add_argument(
        "action", nargs="?", default="list", choices=["list", "import"]
    )
    providers.set_defaults(func=cmd_providers)

    expire = sub.add_parser("expire", help="expire offers past their deadline")
    expire.set_defaults(func=cmd_expire)

    trending = sub.add_parser("trending", help="recompute trending ranks")
    trending.set_defaults(func=cmd_trending)

    rollup = sub.add_parser("rollup", help="roll raw events into daily stats")
    rollup.add_argument("--days", type=int, default=1)
    rollup.set_defaults(func=cmd_rollup)

    stats = sub.add_parser("stats", help="print catalogue statistics")
    stats.set_defaults(func=cmd_stats)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())