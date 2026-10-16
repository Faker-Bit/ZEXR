"""Database seeding: taxonomy, countries, brands, sources and DEMO offers.

Run with:

    python -m app.db.seed                # taxonomy + real public sources
    python -m app.db.seed --reset        # drop and rebuild everything
    python -m app.db.seed --demo-offers  # also add clearly-labelled DEMO offers
    python -m app.db.seed --no-users     # skip the operator accounts

Every offer created by ``--demo-offers`` is flagged ``is_demo_data=True``.  The
frontend renders a persistent "Demo data" badge for those rows and the API never
reports them as verified.  Real offers come from `app/discovery` + admin review.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete, func, select

from app.core.logging import get_logger
from app.core.security import hash_password, slugify
from app.db.base import utcnow
from app.db.session import SessionLocal
from app.models.enums import (
    DiscountKind,
    EligibilityType,
    OfferStatus,
    OfferType,
    SourceHealth,
    SourceType,
    UserRole,
    VerificationStatus,
)
from app.models.offer import (
    Offer,
    OfferAlternative,
    OfferCountry,
    OfferEligibility,
    OfferVerification,
)
from app.models.source import Source
from app.models.taxonomy import Brand, Category, Country
from app.models.user import User
from app.services import analytics
from app.services import search as search_service

log = get_logger("seed")

# --------------------------------------------------------------------- data
CATEGORIES: list[dict] = [
    {
        "slug": "ai-tools",
        "name": "AI Tools & AI Models",
        "tagline": "Free tiers, credits and trials for AI products",
        "description": (
            "Chatbots, image generators, developer AI APIs and productivity copilots with "
            "free usage tiers, trial credits or limited-time premium access."
        ),
        "icon": "sparkles",
        "color": "lime",
        "group_name": "Build",
        "sort_order": 10,
        "keywords": ["ai", "llm", "gpt", "machine learning", "chatbot", "image generation", "copilot", "model"],
        "aliases": ["artificial intelligence", "genai", "ml", "neural"],
        "seo_title": "Free AI tools, free credits and AI trials",
        "seo_description": "Find free AI tools, free API credits and free premium trials from verified AI providers.",
    },
    {
        "slug": "developer-tools-apis",
        "name": "Developer Tools & APIs",
        "tagline": "Ship faster with free tiers and credits",
        "description": "IDEs, CI platforms, error trackers, databases, auth providers and API gateways with free plans.",
        "icon": "code",
        "color": "indigo",
        "group_name": "Build",
        "sort_order": 20,
        "keywords": ["developer", "api", "sdk", "ide", "ci", "repository", "database", "testing"],
        "aliases": ["devtools", "programming", "engineering"],
        "seo_title": "Free developer tools and API credits",
        "seo_description": "Developer platforms with free tiers, free API credits and student-friendly plans.",
    },
    {
        "slug": "cloud-hosting",
        "name": "Cloud Hosting & Infrastructure",
        "tagline": "Free tiers and startup credits",
        "description": "Compute, storage, CDN and managed infrastructure providers offering free tiers and monthly credits.",
        "icon": "cloud",
        "color": "sky",
        "group_name": "Build",
        "sort_order": 30,
        "keywords": ["hosting", "cloud", "vps", "server", "cdn", "storage", "compute", "infrastructure"],
        "aliases": ["vps", "servers", "aws", "infrastructure"],
        "seo_title": "Free cloud hosting and free tier infrastructure",
        "seo_description": "Cloud hosting, VPS and CDN providers with free tiers and startup credits.",
    },
    {
        "slug": "software-productivity",
        "name": "Software & Productivity",
        "tagline": "Do more with less",
        "description": "Notes, project management, document editing, automation and collaboration tools with free plans.",
        "icon": "checklist",
        "color": "violet",
        "group_name": "Work",
        "sort_order": 40,
        "keywords": ["productivity", "notes", "tasks", "documents", "automation", "collaboration"],
        "aliases": ["office", "work", "productivity tools"],
        "seo_title": "Free productivity software and plan upgrades",
        "seo_description": "Free plans and free upgrades for notes, project management and office software.",
    },
    {
        "slug": "business-saas",
        "name": "Business & SaaS",
        "tagline": "Startup and small-team pricing",
        "description": "CRM, helpdesk, invoicing, HR and operations SaaS with startup programmes and free trials.",
        "icon": "briefcase",
        "color": "amber",
        "group_name": "Work",
        "sort_order": 50,
        "keywords": ["saas", "crm", "business", "startup", "team", "billing", "helpdesk", "hr"],
        "aliases": ["business software", "startup tools", "b2b"],
        "seo_title": "Free SaaS trials and startup deals",
        "seo_description": "Business software with free trials, startup pricing and team discounts.",
    },
    {
        "slug": "design-creative",
        "name": "Design & Creative Tools",
        "tagline": "Create without a subscription",
        "description": "Design, photo editing, video, 3D and audio tools with free tiers or free alternatives to paid suites.",
        "icon": "palette",
        "color": "pink",
        "group_name": "Create",
        "sort_order": 60,
        "keywords": ["design", "photo", "video", "audio", "3d", "illustration", "fonts", "creative"],
        "aliases": ["graphic design", "editing", "creative tools"],
        "seo_title": "Free design and creative tools",
        "seo_description": "Free design, photo, video and audio software plus free alternatives to paid suites.",
    },
    {
        "slug": "streaming-entertainment",
        "name": "Streaming & Entertainment",
        "tagline": "More shows, music and films",
        "description": "Video, music and audiobook services with free tiers, bundles and limited-time partner offers.",
        "icon": "play",
        "color": "rose",
        "group_name": "Live",
        "sort_order": 70,
        "keywords": ["streaming", "movies", "tv", "music", "audiobooks", "watch"],
        "aliases": ["entertainment", "video", "OTT"],
        "seo_title": "Free streaming trials and entertainment offers",
        "seo_description": "Free trials, bundles and promotional offers on streaming and music services.",
    },
    {
        "slug": "gaming",
        "name": "Gaming",
        "tagline": "Subscriptions, credits and store deals",
        "description": "Game pass subscriptions, store credit, in-game rewards and free-to-keep promotions.",
        "icon": "gamepad",
        "color": "emerald",
        "group_name": "Live",
        "sort_order": 80,
        "keywords": ["gaming", "games", "console", "xbox", "playstation", "steam", "esports"],
        "aliases": ["video games", "console"],
        "seo_title": "Free gaming subscriptions and store credit",
        "seo_description": "Gaming passes, free store credit and limited-time game promotions.",
    },
    {
        "slug": "vpn-security-privacy",
        "name": "VPNs, Security & Privacy",
        "tagline": "Browse privately for less",
        "description": "VPNs, password managers, antivirus and privacy tools with long free trials and free tiers.",
        "icon": "shield",
        "color": "teal",
        "group_name": "Protect",
        "sort_order": 90,
        "keywords": ["vpn", "privacy", "security", "antivirus", "password manager", "encryption"],
        "aliases": ["privacy tools", "security", "proxy"],
        "seo_title": "Free VPN trials and privacy tools",
        "seo_description": "VPNs, password managers and security tools with free trials and free tiers.",
    },
    {
        "slug": "finance-cashback",
        "name": "Finance & Cashback",
        "tagline": "Keep more of what you spend",
        "description": "Cashback cards, referral rewards, banking bonuses and shopping cashback programmes.",
        "icon": "wallet",
        "color": "lime",
        "group_name": "Save",
        "sort_order": 100,
        "keywords": ["cashback", "finance", "bank", "banking", "reward", "money", "savings"],
        "aliases": ["money", "banking", "cash back"],
        "seo_title": "Cashback offers and banking rewards",
        "seo_description": "Cashback cards, referral bonuses and shopping cashback you can claim today.",
    },
    {
        "slug": "shopping-fashion",
        "name": "Shopping & Fashion",
        "tagline": "Style for less",
        "description": "Apparel, footwear, accessories and marketplace offers with seasonal and student discounts.",
        "icon": "shopping-bag",
        "color": "fuchsia",
        "group_name": "Save",
        "sort_order": 110,
        "keywords": ["shopping", "fashion", "clothing", "shoes", "marketplace", "apparel"],
        "aliases": ["retail", "clothing", "ecommerce"],
        "seo_title": "Shopping and fashion deals",
        "seo_description": "Fashion, footwear and marketplace discounts with coupon codes.",
    },
    {
        "slug": "electronics",
        "name": "Electronics",
        "tagline": "Gadget deals and extended trials",
        "description": "Laptops, phones, audio and accessories plus manufacturer trade-in and student pricing.",
        "icon": "laptop",
        "color": "blue",
        "group_name": "Save",
        "sort_order": 120,
        "keywords": ["electronics", "laptop", "phone", "headphones", "gadgets", "hardware"],
        "aliases": ["gadgets", "hardware", "devices"],
        "seo_title": "Electronics deals and trade-in offers",
        "seo_description": "Laptop, phone and gadget deals plus manufacturer student pricing.",
    },
    {
        "slug": "food-delivery",
        "name": "Food & Delivery",
        "tagline": "Free delivery and meal credits",
        "description": "Food delivery, grocery and meal-kit services with first-order credits and free delivery windows.",
        "icon": "utensils",
        "color": "orange",
        "group_name": "Live",
        "sort_order": 130,
        "keywords": ["food", "delivery", "grocery", "restaurant", "meal", "coffee"],
        "aliases": ["meals", "takeaway", "groceries"],
        "seo_title": "Free food delivery credits and grocery deals",
        "seo_description": "First-order credits, free delivery and meal-kit discounts.",
    },
    {
        "slug": "travel-hotels",
        "name": "Travel & Hotels",
        "tagline": "Book smarter, travel further",
        "description": "Flight, hotel, eSIM and travel booking services with member prices, trial credits and rebates.",
        "icon": "plane",
        "color": "cyan",
        "group_name": "Save",
        "sort_order": 140,
        "keywords": ["travel", "hotel", "flight", "booking", "esim", "vacation", "car rental"],
        "aliases": ["flights", "hotels", "trips"],
        "seo_title": "Travel, hotel and flight deals",
        "seo_description": "Travel booking credits, hotel offers and eSIM promotions.",
    },
    {
        "slug": "education-learning",
        "name": "Education & Learning",
        "tagline": "Learn without paying",
        "description": "Course platforms, language apps and tutoring with free lessons, audit tracks and student pricing.",
        "icon": "graduation-cap",
        "color": "indigo",
        "group_name": "Work",
        "sort_order": 150,
        "keywords": ["education", "learning", "course", "courses", "language", "tutoring", "student"],
        "aliases": ["learning", "training", "students"],
        "seo_title": "Free online courses and student discounts",
        "seo_description": "Free course audits, language apps and student pricing on learning platforms.",
    },
    {
        "slug": "free-websites-utilities",
        "name": "Free Websites & Online Utilities",
        "tagline": "Genuinely free, no card needed",
        "description": "Websites that are free outright: converters, generators, validators, planners and open-source replacements.",
        "icon": "globe",
        "color": "slate",
        "group_name": "Free",
        "sort_order": 160,
        "keywords": ["free website", "utility", "converter", "generator", "tool", "online", "no card"],
        "aliases": ["utilities", "web tools", "free tools"],
        "seo_title": "Free online tools and utilities",
        "seo_description": "Genuinely free websites and online utilities that need no credit card.",
    },
]

COUNTRIES: list[tuple[str, str, str, str, str, str, int]] = [
    # code, name, flag, currency, region, group/slug, sort
    ("IN", "India", "🇮🇳", "INR", "Asia", "asia", 10),
    ("US", "United States", "🇺🇸", "USD", "Americas", "americas", 20),
    ("GB", "United Kingdom", "🇬🇧", "GBP", "Europe", "europe", 30),
    ("CA", "Canada", "🇨🇦", "CAD", "Americas", "americas", 40),
    ("AU", "Australia", "🇦🇺", "AUD", "Oceania", "oceania", 50),
    ("DE", "Germany", "🇩🇪", "EUR", "Europe", "europe", 60),
    ("FR", "France", "🇫🇷", "EUR", "Europe", "europe", 70),
    ("ES", "Spain", "🇪🇸", "EUR", "Europe", "europe", 80),
    ("IT", "Italy", "🇮🇹", "EUR", "Europe", "europe", 90),
    ("NL", "Netherlands", "🇳🇱", "EUR", "Europe", "europe", 100),
    ("SE", "Sweden", "🇸🇪", "SEK", "Europe", "europe", 110),
    ("PL", "Poland", "🇵🇱", "PLN", "Europe", "europe", 120),
    ("PT", "Portugal", "🇵🇹", "EUR", "Europe", "europe", 130),
    ("IE", "Ireland", "🇮🇪", "EUR", "Europe", "europe", 140),
    ("AE", "United Arab Emirates", "🇦🇪", "AED", "Middle East", "middle-east", 150),
    ("SA", "Saudi Arabia", "🇸🇦", "SAR", "Middle East", "middle-east", 160),
    ("SG", "Singapore", "🇸🇬", "SGD", "Asia", "asia", 170),
    ("MY", "Malaysia", "🇲🇾", "MYR", "Asia", "asia", 180),
    ("ID", "Indonesia", "🇮🇩", "IDR", "Asia", "asia", 190),
    ("TH", "Thailand", "🇹🇭", "THB", "Asia", "asia", 200),
    ("VN", "Vietnam", "🇻🇳", "VND", "Asia", "asia", 210),
    ("PH", "Philippines", "🇵🇭", "PHP", "Asia", "asia", 220),
    ("JP", "Japan", "🇯🇵", "JPY", "Asia", "asia", 230),
    ("KR", "South Korea", "🇰🇷", "KRW", "Asia", "asia", 240),
    ("CN", "China", "🇨🇳", "CNY", "Asia", "asia", 250),
    ("HK", "Hong Kong", "🇭🇰", "HKD", "Asia", "asia", 260),
    ("TW", "Taiwan", "🇹🇼", "TWD", "Asia", "asia", 270),
    ("BR", "Brazil", "🇧🇷", "BRL", "Americas", "americas", 280),
    ("MX", "Mexico", "🇲🇽", "MXN", "Americas", "americas", 290),
    ("AR", "Argentina", "🇦🇷", "ARS", "Americas", "americas", 300),
    ("CL", "Chile", "🇨🇱", "CLP", "Americas", "americas", 310),
    ("CO", "Colombia", "🇨🇴", "COP", "Americas", "americas", 320),
    ("ZA", "South Africa", "🇿🇦", "ZAR", "Africa", "africa", 330),
    ("NG", "Nigeria", "🇳🇬", "NGN", "Africa", "africa", 340),
    ("KE", "Kenya", "🇰🇪", "KES", "Africa", "africa", 350),
    ("EG", "Egypt", "🇪🇬", "EGP", "Africa", "africa", 360),
    ("IL", "Israel", "🇮🇱", "ILS", "Middle East", "middle-east", 370),
    ("TR", "Turkey", "🇹🇷", "TRY", "Europe", "europe", 380),
    ("UA", "Ukraine", "🇺🇦", "UAH", "Europe", "europe", 390),
    ("NZ", "New Zealand", "🇳🇿", "NZD", "Oceania", "oceania", 400),
]

BRANDS: list[dict] = [
    {"name": "OpenAI", "domain": "openai.com", "category": "ai-tools", "aliases": ["chatgpt", "gpt"]},
    {"name": "Anthropic", "domain": "anthropic.com", "category": "ai-tools", "aliases": ["claude"]},
    {"name": "Google Gemini", "domain": "gemini.google.com", "category": "ai-tools", "aliases": ["gemini", "bard"]},
    {"name": "Perplexity", "domain": "perplexity.ai", "category": "ai-tools", "aliases": ["perplexity ai"]},
    {"name": "Hugging Face", "domain": "huggingface.co", "category": "ai-tools", "aliases": ["hf"]},
    {"name": "Replicate", "domain": "replicate.com", "category": "ai-tools", "aliases": []},
    {"name": "ElevenLabs", "domain": "elevenlabs.io", "category": "ai-tools", "aliases": []},
    {"name": "Runway", "domain": "runwayml.com", "category": "ai-tools", "aliases": ["runway ml"]},
    {"name": "GitHub", "domain": "github.com", "category": "developer-tools-apis", "aliases": ["github copilot"]},
    {"name": "GitLab", "domain": "gitlab.com", "category": "developer-tools-apis", "aliases": []},
    {"name": "Vercel", "domain": "vercel.com", "category": "developer-tools-apis", "aliases": []},
    {"name": "Netlify", "domain": "netlify.com", "category": "developer-tools-apis", "aliases": []},
    {"name": "Sentry", "domain": "sentry.io", "category": "developer-tools-apis", "aliases": []},
    {"name": "Supabase", "domain": "supabase.com", "category": "developer-tools-apis", "aliases": []},
    {"name": "DigitalOcean", "domain": "digitalocean.com", "category": "cloud-hosting", "aliases": ["digital ocean"]},
    {"name": "Render", "domain": "render.com", "category": "cloud-hosting", "aliases": []},
    {"name": "Fly.io", "domain": "fly.io", "category": "cloud-hosting", "aliases": ["fly io"]},
    {"name": "Cloudflare", "domain": "cloudflare.com", "category": "cloud-hosting", "aliases": []},
    {"name": "Hetzner", "domain": "hetzner.com", "category": "cloud-hosting", "aliases": []},
    {"name": "Notion", "domain": "notion.so", "category": "software-productivity", "aliases": []},
    {"name": "Linear", "domain": "linear.app", "category": "software-productivity", "aliases": []},
    {"name": "Obsidian", "domain": "obsidian.md", "category": "software-productivity", "aliases": []},
    {"name": "Todoist", "domain": "todoist.com", "category": "software-productivity", "aliases": []},
    {"name": "Zapier", "domain": "zapier.com", "category": "software-productivity", "aliases": []},
    {"name": "Figma", "domain": "figma.com", "category": "design-creative", "aliases": []},
    {"name": "Canva", "domain": "canva.com", "category": "design-creative", "aliases": []},
    {"name": "Adobe", "domain": "adobe.com", "category": "design-creative", "aliases": ["creative cloud"]},
    {"name": "DaVinci Resolve", "domain": "blackmagicdesign.com", "category": "design-creative", "aliases": ["blackmagic"]},
    {"name": "GIMP", "domain": "gimp.org", "category": "design-creative", "aliases": []},
    {"name": "Inkscape", "domain": "inkscape.org", "category": "design-creative", "aliases": []},
    {"name": "Netflix", "domain": "netflix.com", "category": "streaming-entertainment", "aliases": []},
    {"name": "Spotify", "domain": "spotify.com", "category": "streaming-entertainment", "aliases": []},
    {"name": "YouTube", "domain": "youtube.com", "category": "streaming-entertainment", "aliases": ["youtube premium"]},
    {"name": "Disney+", "domain": "disneyplus.com", "category": "streaming-entertainment", "aliases": ["disney plus"]},
    {"name": "Xbox", "domain": "xbox.com", "category": "gaming", "aliases": ["game pass", "gamepass"]},
    {"name": "PlayStation", "domain": "playstation.com", "category": "gaming", "aliases": ["ps plus", "psn"]},
    {"name": "Epic Games", "domain": "epicgames.com", "category": "gaming", "aliases": ["epic games store"]},
    {"name": "Proton", "domain": "proton.me", "category": "vpn-security-privacy", "aliases": ["protonvpn", "proton vpn"]},
    {"name": "NordVPN", "domain": "nordvpn.com", "category": "vpn-security-privacy", "aliases": ["nord vpn"]},
    {"name": "1Password", "domain": "1password.com", "category": "vpn-security-privacy", "aliases": ["onepassword"]},
    {"name": "Bitwarden", "domain": "bitwarden.com", "category": "vpn-security-privacy", "aliases": []},
    {"name": "Mullvad", "domain": "mullvad.net", "category": "vpn-security-privacy", "aliases": []},
    {"name": "Rakuten", "domain": "rakuten.com", "category": "finance-cashback", "aliases": ["rakuten cashback"]},
    {"name": "Cashback World", "domain": "cashbackworld.com", "category": "finance-cashback", "aliases": []},
    {"name": "Swiggy", "domain": "swiggy.com", "category": "food-delivery", "aliases": []},
    {"name": "Zomato", "domain": "zomato.com", "category": "food-delivery", "aliases": ["eternal"]},
    {"name": "Uber Eats", "domain": "ubereats.com", "category": "food-delivery", "aliases": []},
    {"name": "Booking.com", "domain": "booking.com", "category": "travel-hotels", "aliases": ["booking com"]},
    {"name": "Airbnb", "domain": "airbnb.com", "category": "travel-hotels", "aliases": []},
    {"name": "Coursera", "domain": "coursera.org", "category": "education-learning", "aliases": []},
    {"name": "Duolingo", "domain": "duolingo.com", "category": "education-learning", "aliases": []},
    {"name": "Khan Academy", "domain": "khanacademy.org", "category": "education-learning", "aliases": []},
    {"name": "freeCodeCamp", "domain": "freecodecamp.org", "category": "education-learning", "aliases": []},
    {"name": "MuleSoft", "domain": "mulesoft.com", "category": "business-saas", "aliases": []},
    {"name": "HubSpot", "domain": "hubspot.com", "category": "business-saas", "aliases": []},
    {"name": "Trello", "domain": "trello.com", "category": "business-saas", "aliases": []},
    {"name": "Canva for Teams", "domain": "canva.com", "category": "design-creative", "aliases": []},
    {"name": "CloudConvert", "domain": "cloudconvert.com", "category": "free-websites-utilities", "aliases": []},
    {"name": "Squoosh", "domain": "squoosh.app", "category": "free-websites-utilities", "aliases": []},
    {"name": "Remove.bg", "domain": "remove.bg", "category": "free-websites-utilities", "aliases": []},
    {"name": "Photopea", "domain": "photopea.com", "category": "free-websites-utilities", "aliases": []},
    {"name": "TLDraw", "domain": "tldraw.com", "category": "free-websites-utilities", "aliases": []},
    {"name": "Excalidraw", "domain": "excalidraw.com", "category": "free-websites-utilities", "aliases": []},
    {"name": "AppVeyor", "domain": "appveyor.com", "category": "developer-tools-apis", "aliases": []},
    {"name": "JetBrains", "domain": "jetbrains.com", "category": "developer-tools-apis", "aliases": ["intellij"]},
    {"name": "Sublime Text", "domain": "sublimetext.com", "category": "developer-tools-apis", "aliases": []},
]

# Sources are *configurations*, not live feeds.  Each one points at a public,
# explicitly-published surface and carries its own crawl budget.  Nothing is
# fetched until an admin runs a sweep.
SOURCES: list[dict] = [
    {
        "key": "official-rss-partner",
        "name": "Partner offer RSS feed",
        "publisher": "ZEXR Deal Hub partnerships",
        "source_type": SourceType.RSS.value,
        "adapter": "rss",
        "homepage_url": "https://zexrdealhub.com/partners",
        "feed_url": "https://zexrdealhub.com/feeds/offers.xml",
        "config": {"max_items": 40},
        "trust_weight": 0.95,
        "license_note": "First-party feed published for syndication partners.",
        "is_active": False,
    },
    {
        "key": "affiliate-network-api",
        "name": "Affiliate network JSON API",
        "publisher": "Configured per deployment",
        "source_type": SourceType.AFFILIATE_API.value,
        "adapter": "json_api",
        "homepage_url": "https://example-network.com/docs/offers",
        "feed_url": "https://api.example-network.com/v1/offers",
        "api_key_env": "AFFILIATE_NETWORK_API_KEY",
        "config": {
            "url": "https://api.example-network.com/v1/offers",
            "auth": {"type": "header", "name": "X-Api-Key", "prefix": ""},
            "query": {"status": "active"},
            "items_path": "data",
            "fields": {
                "id": "id",
                "title": "name",
                "description": "description",
                "url": "landing_page",
                "offer_type": "type",
                "original_price": "pricing.original",
                "promo_price": "pricing.promo",
                "currency": "pricing.currency",
                "trial_days": "terms.trial_days",
                "expires_at": "terms.end_date",
                "coupon_code": "terms.code",
                "brand_name": "merchant.name",
                "category_slug": "category",
                "countries": "availability",
            },
        },
        "trust_weight": 0.8,
        "license_note": "Requires a commercial affiliate agreement and an API key.",
        "is_active": False,
    },
    {
        "key": "brand-offer-pages",
        "name": "Official brand offer pages",
        "publisher": "Individual vendors",
        "source_type": SourceType.HTML_LISTING.value,
        "adapter": "html_listing",
        "homepage_url": "https://example.com/offers",
        "feed_url": "https://example.com/offers",
        "config": {
            "list_url": "https://example.com/offers",
            "item_selector": "article.offer",
            "title_selector": "h3 a",
            "description_selector": "p",
            "require_text": ["free", "trial", "off"],
            "same_host_only": True,
            "max_items": 25,
        },
        "trust_weight": 0.7,
        "license_note": "Only used where the publisher exposes a public offers index.",
        "is_active": False,
    },
    {
        "key": "manual-intake",
        "name": "Manual intake",
        "publisher": "ZEXR Deal Hub editors",
        "source_type": SourceType.MANUAL.value,
        "adapter": "manual",
        "homepage_url": "https://zexrdealhub.com/admin/offers/new",
        "config": {},
        "trust_weight": 1.0,
        "license_note": "Editorially entered and manually verified.",
        "is_active": True,
    },
]

# ---------------------------------------------------------------- demo data
def _demo_offers() -> list[dict]:
    now = utcnow()

    def in_days(days: float) -> datetime:
        return now + timedelta(days=days)

    return [
        {
            "title": "ChatGPT Plus — 1 month free upgrade for new accounts",
            "brand": "OpenAI",
            "category": "ai-tools",
            "type": OfferType.FREE_TRIAL,
            "short": "Try the premium model tier free for a month before deciding whether to subscribe.",
            "desc": (
                "New accounts can trial the premium tier for one month. Cancelling before the trial ends "
                "means you are not charged. Availability varies by region and some features are excluded "
                "from the trial."
            ),
            "original": 20.0, "promo": 0.0, "currency": "USD", "period": "monthly",
            "trial_days": 30, "savings": 20.0, "percent": 100,
            "expires": in_days(18), "payment": True, "auto_renew": True,
            "new_user": True, "global": True,
            "steps": [
                "Open the official ChatGPT upgrade page.",
                "Sign in with (or create) an account that has never used a trial.",
                "Start the free trial and confirm your billing details if prompted.",
                "Set a calendar reminder to cancel before the trial ends.",
            ],
            "tags": ["ai", "chatbot", "upgrade"],
        },
        {
            "title": "Anthropic Claude — 3 months Pro at 40% off",
            "brand": "Anthropic",
            "category": "ai-tools",
            "type": OfferType.DISCOUNT,
            "short": "A partner discount on the Pro plan for new subscribers.",
            "desc": (
                "A partner promotion reducing the introductory price of the Pro plan for the first three "
                "billing cycles. Standard pricing resumes afterwards."
            ),
            "original": 20.0, "promo": 12.0, "currency": "USD", "period": "monthly",
            "renewal": 20.0, "trial_days": None, "savings": 8.0, "percent": 40,
            "expires": in_days(9), "payment": True, "auto_renew": True,
            "new_user": True, "global": True, "coupon": "CLAUDE40",
            "steps": [
                "Go to the official Anthropic console billing page.",
                "Start a new Pro subscription and apply the partner code if prompted.",
                "Confirm the discounted amount before the trial converts.",
            ],
            "tags": ["ai", "llm", "discount"],
        },
        {
            "title": "Google Gemini — 6 months of Google AI Pro free",
            "brand": "Google Gemini",
            "category": "ai-tools",
            "type": OfferType.FREE_TRIAL,
            "short": "Extended access to the premium AI tier bundled with storage benefits.",
            "desc": (
                "Eligible new subscribers receive an extended premium window. The offer bundles AI "
                "features with cloud storage; cancelling stops all of them at the end of the period."
            ),
            "original": 19.99, "promo": 0.0, "currency": "USD", "period": "monthly",
            "trial_days": 182, "savings": 119.94, "percent": 100,
            "expires": in_days(45), "payment": True, "auto_renew": True,
            "new_user": True, "global": True,
            "steps": [
                "Open the official offer page and check regional eligibility.",
                "Sign in with an eligible Google account.",
                "Activate the trial before the deadline shown on the page.",
            ],
            "tags": ["ai", "storage", "bundle"],
        },
        {
            "title": "Perplexity Pro — 3 months free for students",
            "brand": "Perplexity",
            "category": "ai-tools",
            "type": OfferType.FREE_TRIAL,
            "short": "Free premium research access with a verified student email.",
            "desc": (
                "Students with a valid institutional email can unlock Pro features at no cost for a "
                "limited period. Verification is handled by the provider."
            ),
            "original": 20.0, "promo": 0.0, "currency": "USD", "period": "monthly",
            "trial_days": 90, "savings": 60.0, "percent": 100,
            "expires": in_days(25), "payment": False, "student": True,
            "new_user": True, "global": True,
            "steps": [
                "Use a university email address when signing up.",
                "Complete the student verification step.",
                "Enable the free Pro window from your account settings.",
            ],
            "tags": ["ai", "students", "research"],
        },
        {
            "title": "Replicate — $5 free compute credit on signup",
            "brand": "Replicate",
            "category": "ai-tools",
            "type": OfferType.FREE_CREDITS,
            "short": "A small starter credit so you can run your first model without a card-on-file plan.",
            "desc": (
                "New accounts receive a one-time credit balance that can be spent running open models. "
                "The credit does not roll over and there is no card required."
            ),
            "original": None, "promo": None, "currency": "USD",
            "credits": 5.0, "credits_unit": "credit", "savings": 5.0, "percent": 100,
            "expires": None, "payment": False, "new_user": True, "global": True,
            "steps": [
                "Create an account on the official site.",
                "Open the billing page — the credit is applied automatically.",
                "Run a model; the credit is deducted from your balance.",
            ],
            "tags": ["ai", "credits", "api"],
        },
        {
            "title": "GitHub Copilot — 30-day free trial for individuals",
            "brand": "GitHub",
            "category": "developer-tools-apis",
            "type": OfferType.FREE_TRIAL,
            "short": "Full Copilot access for a month while you evaluate it in your editor.",
            "desc": (
                "Individual accounts can enable a 30-day trial of Copilot. Organisation seats are billed "
                "separately and are not included."
            ),
            "original": 10.0, "promo": 0.0, "currency": "USD", "period": "monthly",
            "trial_days": 30, "savings": 10.0, "percent": 100,
            "expires": in_days(60), "payment": True, "auto_renew": False,
            "new_user": True, "global": True,
            "steps": [
                "Go to your GitHub Settings → Copilot.",
                "Start the free trial.",
                "Install the extension in your IDE and sign in.",
            ],
            "tags": ["ai", "coding", "developer"],
        },
        {
            "title": "Hetzner Cloud — €4.15/month VPS entry plan",
            "brand": "Hetzner",
            "category": "cloud-hosting",
            "type": OfferType.DISCOUNT,
            "short": "Low-cost always-free-tier-sized servers billed monthly with no lock-in.",
            "desc": (
                "A small entry-level virtual machine suitable for side projects, staging and bots. "
                "Billed hourly with a monthly cap."
            ),
            "original": 6.0, "promo": 4.15, "currency": "EUR", "period": "monthly",
            "savings": 1.85, "percent": 31,
            "expires": None, "payment": True, "new_user": False, "global": True,
            "steps": ["Create an account and verify payment.", "Deploy a server from the Cloud console."],
            "tags": ["vps", "hosting", "cheap"],
        },
        {
            "title": "Render — free web service for side projects",
            "brand": "Render",
            "category": "cloud-hosting",
            "type": OfferType.FREEMIUM,
            "short": "A permanently free tier that sleeps when idle — ideal for demos and prototypes.",
            "desc": (
                "Free web services spin down after inactivity and restart on the next request. Cold "
                "starts can take up to a minute, so this is not suitable for production."
            ),
            "original": None, "promo": 0.0, "currency": "USD",
            "savings": 7.0, "percent": 100,
            "expires": None, "payment": False, "new_user": True, "global": True,
            "steps": ["Connect a Git repository.", "Choose 'Web Service' and pick the Free instance type."],
            "tags": ["hosting", "free tier", "paas"],
        },
        {
            "title": "Proton VPN — 30 days free on the Plus plan",
            "brand": "Proton",
            "category": "vpn-security-privacy",
            "type": OfferType.FREE_TRIAL,
            "short": "A month of the paid tier with money-back assurance rather than a card-on-file trial.",
            "desc": (
                "Proton offers a 30-day money-back window on annual plans, which functions like a free "
                "month. No card is required to start and you can cancel from your account."
            ),
            "original": 9.99, "promo": 0.0, "currency": "USD", "period": "monthly",
            "trial_days": 30, "savings": 9.99, "percent": 100,
            "expires": in_days(12), "payment": False, "new_user": False, "global": True,
            "steps": [
                "Subscribe to an annual plan on the official site.",
                "Request the money-back guarantee within 30 days.",
                "Receive the refund to your original payment method.",
            ],
            "tags": ["vpn", "privacy", "refund"],
        },
        {
            "title": "NordVPN — 3 extra months free on a 2-year plan",
            "brand": "NordVPN",
            "category": "vpn-security-privacy",
            "type": OfferType.DISCOUNT,
            "short": "Extend the subscription length at no extra cost during the promo window.",
            "desc": (
                "A limited-time bundle extension. The monthly-equivalent price effectively drops because "
                "the term is longer, but the total charge is unchanged."
            ),
            "original": 3.99, "promo": 2.99, "currency": "USD", "period": "monthly",
            "savings": 1.0, "percent": 25,
            "expires": in_days(5), "payment": True, "new_user": False, "global": True,
            "steps": ["Open the official pricing page.", "Choose the 2-year plan with the extended months."],
            "tags": ["vpn", "bundle"],
        },
        {
            "title": "Bitwarden Premium — $10 family discount per year",
            "brand": "Bitwarden",
            "category": "vpn-security-privacy",
            "type": OfferType.DISCOUNT,
            "short": "A discounted family plan covering up to six people.",
            "desc": "Family plans bundle vault sharing, unlimited devices and 2FA keys across members.",
            "original": 40.0, "promo": 30.0, "currency": "USD", "period": "yearly",
            "savings": 10.0, "percent": 25,
            "expires": None, "payment": True, "new_user": False, "global": True,
            "steps": ["Choose the Family plan at checkout."],
            "tags": ["password", "family"],
        },
        {
            "title": "Spotify Premium — 3 months for ₹0 with select cards",
            "brand": "Spotify",
            "category": "streaming-entertainment",
            "type": OfferType.FREE_TRIAL,
            "short": "India-only bank card offer giving three months of Premium at no cost.",
            "desc": (
                "Eligible Indian debit and credit cards unlock a three-month free Premium period. "
                "The offer is not available outside India and only one redemption per card is allowed."
            ),
            "original": 119.0, "promo": 0.0, "currency": "INR", "period": "monthly",
            "trial_days": 90, "savings": 357.0, "percent": 100,
            "expires": in_days(21), "payment": True, "auto_renew": True,
            "new_user": True, "countries": ["IN"], "global": False,
            "steps": [
                "Use an eligible Indian bank card.",
                "Subscribe to Individual Premium on the official page.",
                "The discount is applied automatically at checkout.",
            ],
            "tags": ["streaming", "music", "india"],
        },
        {
            "title": "Netflix Standard — first 3 months at ₹149",
            "brand": "Netflix",
            "category": "streaming-entertainment",
            "type": OfferType.FREE_TRIAL,
            "short": "Introductory pricing on the Standard plan for new subscribers in India.",
            "desc": (
                "New subscribers in India receive a reduced first billing period before reverting to "
                "standard pricing. The exact price and duration are set by Netflix at checkout."
            ),
            "original": 649.0, "promo": 149.0, "currency": "INR", "period": "monthly",
            "savings": 1500.0, "percent": 77,
            "expires": in_days(30), "payment": True, "auto_renew": True,
            "new_user": True, "countries": ["IN"], "global": False,
            "steps": ["Sign up for the Standard plan as a new user.", "Complete payment before the offer ends."],
            "tags": ["streaming", "india", "introductory"],
        },
        {
            "title": "Xbox Game Pass Ultimate — 3 months for new subscribers",
            "brand": "Xbox",
            "category": "gaming",
            "type": OfferType.FREE_TRIAL,
            "short": "Hundreds of games plus online multiplayer for a limited introductory period.",
            "desc": "New Game Pass Ultimate subscribers receive a discounted first billing period.",
            "original": 19.99, "promo": 7.99, "currency": "USD", "period": "monthly",
            "savings": 36.0, "percent": 60,
            "expires": in_days(14), "payment": True, "auto_renew": True,
            "new_user": True, "global": True,
            "steps": ["Sign in with a new Xbox account.", "Subscribe to Game Pass Ultimate."],
            "tags": ["gaming", "console", "subscription"],
        },
        {
            "title": "Epic Games Store — free game every week",
            "brand": "Epic Games",
            "category": "gaming",
            "type": OfferType.FREE,
            "short": "Genuinely free to keep, no subscription and no card required.",
            "desc": (
                "Epic releases a free game each week. Claiming adds the game to your account "
                "permanently — it is not a trial and does not expire."
            ),
            "original": None, "promo": 0.0, "currency": "USD",
            "savings": 0.0, "percent": 0, "genuinely_free": True, "ends_as_paid": False,
            "expires": None, "payment": False, "new_user": False, "global": True,
            "steps": ["Sign in to the Epic Games launcher.", "Open the store free games page and claim the title."],
            "tags": ["gaming", "free", "store"],
        },
        {
            "title": "Notion — free plan with unlimited pages",
            "brand": "Notion",
            "category": "software-productivity",
            "type": OfferType.FREEMIUM,
            "short": "The free tier is genuinely usable for individuals — no trial, no card.",
            "desc": "Personal use on the free plan is not time limited. Teams need a paid plan.",
            "original": None, "promo": 0.0, "currency": "USD",
            "savings": 10.0, "percent": 100, "genuinely_free": True, "ends_as_paid": False,
            "expires": None, "payment": False, "new_user": False, "global": True,
            "steps": ["Create an account and stay on the Free plan."],
            "tags": ["notes", "productivity", "free"],
        },
        {
            "title": "Obsidian — 25% off Sync & Publish add-on",
            "brand": "Obsidian",
            "category": "software-productivity",
            "type": OfferType.DISCOUNT,
            "short": "Discount applied to the optional sync add-on for existing users.",
            "desc": "The desktop app is free; this offer covers the optional Sync & Publish service.",
            "original": 4.0, "promo": 3.0, "currency": "USD", "period": "monthly",
            "savings": 1.0, "percent": 25,
            "expires": in_days(8), "payment": True, "new_user": False, "global": True,
            "steps": ["Open Settings → Sync in the Obsidian app.", "Purchase the add-on at the discount price."],
            "tags": ["notes", "sync"],
        },
        {
            "title": "Figma Professional — 3 months free for startups",
            "brand": "Figma",
            "category": "design-creative",
            "type": OfferType.FREE_TRIAL,
            "short": "Startup programme giving design teams extended paid features.",
            "desc": "Eligible early-stage companies can apply for an extended paid window on the Professional plan.",
            "original": 15.0, "promo": 0.0, "currency": "USD", "period": "monthly",
            "trial_days": 90, "savings": 45.0, "percent": 100,
            "expires": in_days(40), "payment": False, "new_user": True, "global": True,
            "steps": ["Apply through the official startup programme page.", "Wait for approval before the deadline."],
            "tags": ["design", "startup"],
        },
        {
            "title": "GIMP — free and open source, forever",
            "brand": "GIMP",
            "category": "design-creative",
            "type": OfferType.FREE_ALTERNATIVE,
            "short": "A capable free alternative to paid photo editors.",
            "desc": (
                "GIMP is free software released under a free licence. There is no trial, no upgrade "
                "prompt and no card requirement."
            ),
            "original": None, "promo": 0.0, "currency": "USD",
            "savings": 0.0, "percent": 0, "genuinely_free": True, "ends_as_paid": False,
            "expires": None, "payment": False, "new_user": False, "global": True,
            "steps": ["Download from the official site and install."],
            "tags": ["photo", "opensource", "alternative"],
        },
        {
            "title": "Photopea — free browser-based Photoshop alternative",
            "brand": "Photopea",
            "category": "free-websites-utilities",
            "type": OfferType.FREE_ALTERNATIVE,
            "short": "Full-featured image editing in the browser at no cost.",
            "desc": (
                "Photopea runs entirely in the browser and stores files locally. The free tier has a "
                "small ad placement; a paid plan removes it."
            ),
            "original": None, "promo": 0.0, "currency": "USD",
            "savings": 0.0, "percent": 0, "genuinely_free": True, "ends_as_paid": False,
            "expires": None, "payment": False, "new_user": False, "global": True,
            "steps": ["Open the site in a modern browser and start editing."],
            "tags": ["photo", "browser", "alternative"],
        },
        {
            "title": "Remove.bg — 10 free high-resolution exports per month",
            "brand": "Remove.bg",
            "category": "free-websites-utilities",
            "type": OfferType.FREEMIUM,
            "short": "Free tier with a monthly allowance of free background removals.",
            "desc": "Anonymous users get a limited number of free exports each month.",
            "original": 9.0, "promo": 0.0, "currency": "USD", "period": "monthly",
            "savings": 9.0, "percent": 100,
            "expires": None, "payment": False, "new_user": False, "global": True,
            "steps": ["Upload an image on the official site.", "Download the result before the free credits run out."],
            "tags": ["image", "free tier"],
        },
        {
            "title": "Swiggy — ₹150 first-order discount on selected restaurants",
            "brand": "Swiggy",
            "category": "food-delivery",
            "type": OfferType.COUPON,
            "short": "A limited first-order coupon on participating restaurants.",
            "desc": "Offer availability and the minimum order value vary by restaurant and time of day.",
            "original": None, "promo": 150.0, "currency": "INR",
            "coupon": "SWIGGYFIRST150",
            "savings": 150.0, "percent": 0,
            "expires": in_days(3), "payment": True, "new_user": True,
            "countries": ["IN"], "global": False,
            "steps": ["Open the app or website.", "Choose a participating restaurant and apply the code at checkout."],
            "tags": ["food", "india", "coupon"],
        },
        {
            "title": "Uber Eats — 30% off your first three orders",
            "brand": "Uber Eats",
            "category": "food-delivery",
            "type": OfferType.COUPON,
            "short": "A new-customer promotion across participating merchants.",
            "desc": "Offer terms, caps and participating merchants are set by the provider at checkout.",
            "original": None, "promo": None, "currency": "USD",
            "savings": 0.0, "percent": 30,
            "expires": in_days(6), "payment": True, "new_user": True, "global": True,
            "steps": ["Add the promotion from your account page.", "Apply it at checkout on a participating order."],
            "tags": ["food", "coupon"],
        },
        {
            "title": "Booking.com — €20 credit on stays over €300",
            "brand": "Booking.com",
            "category": "travel-hotels",
            "type": OfferType.FREE_CREDITS,
            "short": "A booking credit applied at checkout on qualifying reservations.",
            "desc": "The credit is applied automatically on eligible bookings made on the official site.",
            "original": None, "promo": 20.0, "currency": "EUR",
            "credits": 20.0, "credits_unit": "booking credit",
            "savings": 20.0, "percent": 0,
            "expires": in_days(20), "payment": True, "new_user": True, "global": True,
            "steps": ["Search for a qualifying stay.", "Apply the credit on the payment screen."],
            "tags": ["travel", "credit"],
        },
        {
            "title": "Coursera — audit every course free of charge",
            "brand": "Coursera",
            "category": "education-learning",
            "type": OfferType.FREE,
            "short": "Audit mode lets you take the full course content without paying.",
            "desc": (
                "Auditing gives access to lectures and readings. Graded assignments, certificates and "
                "peer review require payment."
            ),
            "original": None, "promo": 0.0, "currency": "USD",
            "savings": 0.0, "percent": 0, "genuinely_free": True, "ends_as_paid": False,
            "expires": None, "payment": False, "new_user": False, "global": True,
            "steps": ["Open a course page and choose 'Enroll for free' to audit."],
            "tags": ["education", "free", "courses"],
        },
        {
            "title": "Duolingo Super — 6 months free with an annual plan",
            "brand": "Duolingo",
            "category": "education-learning",
            "type": OfferType.FREE_TRIAL,
            "short": "Extended access to ad-free lessons and streak repair.",
            "desc": "Offer applies to new subscribers who pay annually.",
            "original": 6.99, "promo": 0.0, "currency": "USD", "period": "monthly",
            "trial_days": 182, "savings": 41.94, "percent": 100,
            "expires": in_days(16), "payment": True, "auto_renew": True,
            "new_user": True, "global": True,
            "steps": ["Start a Super trial on the official site.", "Choose the annual billing option."],
            "tags": ["education", "language"],
        },
        {
            "title": "Canva Pro — 90 days free, then 50% off for 3 months",
            "brand": "Canva",
            "category": "design-creative",
            "type": OfferType.FREE_TRIAL,
            "short": "Extended Pro access followed by a discounted period.",
            "desc": "The discount applies after the free window ends; cancel before then to avoid it.",
            "original": 14.99, "promo": 7.49, "currency": "USD", "period": "monthly",
            "trial_days": 90, "savings": 22.5, "percent": 50,
            "expires": in_days(11), "payment": True, "auto_renew": True,
            "new_user": True, "global": True,
            "steps": ["Start a Canva Pro trial.", "Set a reminder 85 days in to avoid the discounted period."],
            "tags": ["design", "trial"],
        },
        {
            "title": "Rakuten Cashback — ₹100 back on your first ₹1,000 spend",
            "brand": "Rakuten",
            "category": "finance-cashback",
            "type": OfferType.CASHBACK,
            "short": "Install the app, shop through it and get cashback after the purchase settles.",
            "desc": "Cashback is paid once the merchant confirms the order, typically within a few days.",
            "original": None, "promo": None, "currency": "INR",
            "savings": 100.0, "percent": 10,
            "expires": in_days(26), "payment": True, "new_user": True,
            "countries": ["IN"], "global": False,
            "steps": ["Sign in to the app.", "Activate cashback, then click through to the merchant to shop."],
            "tags": ["cashback", "india", "shopping"],
        },
        {
            "title": "JetBrains — 1 year free for students and teachers",
            "brand": "JetBrains",
            "category": "developer-tools-apis",
            "type": OfferType.FREE_TRIAL,
            "short": "A full year of every JetBrains IDE for verified educational accounts.",
            "desc": "Educational licences must be renewed annually and are limited to qualifying students.",
            "original": 228.9, "promo": 0.0, "currency": "USD", "period": "yearly",
            "trial_days": 365, "savings": 228.9, "percent": 100,
            "expires": in_days(75), "payment": False, "student": True,
            "new_user": False, "global": True,
            "steps": ["Apply with your .edu or institution email.", "Renew the licence each year to keep it."],
            "tags": ["ide", "students", "developer"],
        },
        {
            "title": "DigitalOcean — $200 credit for 12 months on the Starter plan",
            "brand": "DigitalOcean",
            "category": "cloud-hosting",
            "type": OfferType.FREE_CREDITS,
            "short": "A cloud credit allowance usable across droplets, spaces and managed services.",
            "desc": "The credit applies to the account as a promotional balance and expires with the plan.",
            "original": None, "promo": None, "currency": "USD",
            "credits": 200.0, "credits_unit": "cloud credit",
            "savings": 200.0, "percent": 0,
            "expires": in_days(90), "payment": True, "new_user": True, "global": True,
            "steps": ["Create an account and add payment details.", "Claim the credit from the billing section."],
            "tags": ["cloud", "credits", "vps"],
        },
        {
            "title": "Figma Community — free forever for individuals",
            "brand": "Figma",
            "category": "design-creative",
            "type": OfferType.FREE,
            "short": "Professional design tools at no cost for personal projects.",
            "desc": "The free Starter plan is unlimited for personal use and is not a trial.",
            "original": None, "promo": 0.0, "currency": "USD",
            "savings": 15.0, "percent": 100, "genuinely_free": True, "ends_as_paid": False,
            "expires": None, "payment": False, "new_user": False, "global": True,
            "steps": ["Create a free account and start a personal project."],
            "tags": ["design", "free", "forever"],
        },
        {
            "title": "Adobe Creative Cloud — 65% off the first year for students",
            "brand": "Adobe",
            "category": "design-creative",
            "type": OfferType.DISCOUNT,
            "short": "The long-running student price on the full Creative Cloud plan.",
            "desc": "Requires an eligible educational institution and annual auto-renewal at the student rate.",
            "original": 599.88, "promo": 209.96, "currency": "USD", "period": "yearly",
            "renewal": 263.76, "savings": 389.92, "percent": 65,
            "expires": in_days(200), "payment": True, "auto_renew": True,
            "student": True, "new_user": False, "global": True,
            "steps": ["Verify your student status on the official site.", "Subscribe to the student plan."],
            "tags": ["design", "students", "photoshop"],
        },
        {
            "title": "Linear — 60% off for 3 months on Team plan",
            "brand": "Linear",
            "category": "software-productivity",
            "type": OfferType.DISCOUNT,
            "short": "A discounted window on the team plan for new workspaces.",
            "desc": "Applies to new team subscriptions started during the promotion window.",
            "original": 8.0, "promo": 3.2, "currency": "USD", "period": "monthly",
            "savings": 14.4, "percent": 60,
            "expires": in_days(7), "payment": True, "auto_renew": True,
            "new_user": True, "global": True,
            "steps": ["Start a new team workspace and choose the Team plan."],
            "tags": ["productivity", "teams"],
        },
        {
            "title": "Excalidraw — free whiteboard, no account required",
            "brand": "Excalidraw",
            "category": "free-websites-utilities",
            "type": OfferType.FREE,
            "short": "A genuinely free collaborative whiteboard that works in the browser.",
            "desc": "No sign-up, no trial and no card. Files can be stored locally or in a free account.",
            "original": None, "promo": 0.0, "currency": "USD",
            "savings": 0.0, "percent": 0, "genuinely_free": True, "ends_as_paid": False,
            "expires": None, "payment": False, "new_user": False, "global": True,
            "steps": ["Open the site in a browser and start drawing."],
            "tags": ["whiteboard", "free", "collaboration"],
        },
        {
            "title": "Squoosh — free browser image compressor",
            "brand": "Squoosh",
            "category": "free-websites-utilities",
            "type": OfferType.FREE,
            "short": "Compress images entirely on-device without uploading anything.",
            "desc": "Runs locally in the browser, so images never leave your machine.",
            "original": None, "promo": 0.0, "currency": "USD",
            "savings": 0.0, "percent": 0, "genuinely_free": True, "ends_as_paid": False,
            "expires": None, "payment": False, "new_user": False, "global": True,
            "steps": ["Open the site, drop an image and download the result."],
            "tags": ["images", "privacy", "free"],
        },
    ]


# ------------------------------------------------------------------ helpers
def _seed_countries(session) -> dict[str, Country]:
    existing = {c.code: c for c in session.execute(select(Country)).scalars().all()}
    for code, name, flag, currency, region, _slug, order in COUNTRIES:
        if code in existing:
            continue
        row = Country(
            code=code,
            name=name,
            slug=name.lower().replace(" ", "-"),
            flag_emoji=flag,
            currency=currency,
            region=region,
            sort_order=order,
        )
        session.add(row)
        existing[code] = row
    session.flush()
    return existing


def _seed_categories(session) -> dict[str, Category]:
    existing = {c.slug: c for c in session.execute(select(Category)).scalars().all()}
    for spec in CATEGORIES:
        if spec["slug"] in existing:
            for key, value in spec.items():
                setattr(existing[spec["slug"]], key, value)
            continue
        row = Category(**spec)
        session.add(row)
        existing[spec["slug"]] = row
    session.flush()
    return existing


def _seed_brands(session, categories: dict[str, Category]) -> dict[str, Brand]:
    existing = {b.name: b for b in session.execute(select(Brand)).scalars().all()}
    for spec in BRANDS:
        category = categories.get(spec["category"])
        if spec["name"] in existing:
            continue
        row = Brand(
            name=spec["name"],
            slug=slugify(spec["name"]),
            domain=spec["domain"],
            website_url=f"https://{spec['domain']}",
            aliases=spec["aliases"],
            category_id=category.id if category else None,
            is_verified=False,
        )
        session.add(row)
        existing[spec["name"]] = row
    session.flush()
    return existing


def _seed_sources(session) -> dict[str, Source]:
    existing = {s.key: s for s in session.execute(select(Source)).scalars().all()}
    for spec in SOURCES:
        if spec["key"] in existing:
            continue
        row = Source(**spec)
        session.add(row)
        existing[spec["key"]] = row
    session.flush()
    return existing


def _seed_demo_offers(
    session,
    categories: dict[str, Category],
    brands: dict[str, Brand],
    countries: dict[str, Country],
    sources: dict[str, Source],
) -> int:
    created = 0
    for spec in _demo_offers():
        slug_base = f"{spec['brand']}-{spec['title']}"
        slug = slugify(slug_base)[:150].strip("-")
        if session.execute(select(Offer.id).where(Offer.slug == slug)).first():
            continue

        brand = brands.get(spec["brand"])
        category = categories.get(spec["category"])
        if category is None:
            continue

        offer = Offer(
            slug=slug,
            title=spec["title"],
            short_description=spec["short"],
            description=spec["desc"],
            category_id=category.id,
            brand_id=brand.id if brand else None,
            offer_type=spec["type"].value,
            tags=spec.get("tags", []),
            currency=spec["currency"],
            original_price=Decimal(str(spec["original"])) if spec.get("original") is not None else None,
            promo_price=Decimal(str(spec["promo"])) if spec.get("promo") is not None else None,
            savings_value=Decimal(str(spec.get("savings", 0))),
            savings_percent=int(spec.get("percent", 0)),
            billing_period=spec.get("period"),
            renewal_price=Decimal(str(spec["renewal"])) if spec.get("renewal") is not None else None,
            discount_kind=(
                DiscountKind.PERCENT.value
                if spec.get("percent") and spec["type"] is OfferType.DISCOUNT
                else None
            ),
            credits_amount=Decimal(str(spec["credits"])) if spec.get("credits") is not None else None,
            credits_unit=spec.get("credits_unit"),
            trial_days=spec.get("trial_days"),
            starts_at=utcnow() - timedelta(days=5),
            expires_at=spec.get("expires"),
            is_global=spec.get("global", True),
            requires_new_user=spec.get("new_user", True),
            requires_student_id=spec.get("student", False),
            requires_payment_method=spec.get("payment", False),
            requires_auto_renew=spec.get("auto_renew", False),
            eligibility_types=[
                e.value
                for e in (
                    [EligibilityType.NEW_USERS] if spec.get("new_user", True) else []
                )
                + ([EligibilityType.STUDENTS] if spec.get("student") else [])
                + (
                    [EligibilityType.COUNTRIES]
                    if not spec.get("global", True)
                    else [EligibilityType.GLOBAL]
                )
            ],
            how_to_redeem=spec.get("steps", []),
            fine_print=(
                "Availability, pricing and eligibility are set by the provider and can change at any "
                "time. Confirm on the official page before you pay anything."
            ),
            features=[spec["short"]],
            is_genuinely_free=spec.get("genuinely_free", False),
            ends_as_paid=spec.get("ends_as_paid", spec["type"] is not OfferType.FREE),
            official_url=(
                brand.website_url if brand and brand.website_url else "https://example.com/offer"
            ),
            coupon_code=spec.get("coupon"),
            status=OfferStatus.PUBLISHED.value,
            verification_status=VerificationStatus.UNVERIFIED.value,
            source_id=sources["manual-intake"].id,
            is_demo_data=True,
            discovery_confidence=1.0,
            published_at=utcnow() - timedelta(days=random_offset(spec["title"])),
            internal_notes="DEMO DATA — created by the seed script for local development only.",
            view_count=random_views(spec["title"]),
            click_count=random_views(spec["title"]) // 3,
            bookmark_count=random_views(spec["title"]) // 9,
        )
        session.add(offer)
        session.flush()

        for code in spec.get("countries", []):
            country = countries.get(code)
            if country:
                session.add(
                    OfferCountry(offer_id=offer.id, country_code=country.code, is_available=True)
                )

        for rule in offer.eligibility_types or []:
            session.add(
                OfferEligibility(
                    offer_id=offer.id,
                    rule=rule,
                    label=_eligibility_label(rule),
                    blocking=rule in (EligibilityType.STUDENTS.value, EligibilityType.COUNTRIES.value),
                    source_url=offer.official_url,
                )
            )

        session.add(
            OfferVerification(
                offer_id=offer.id,
                result="skipped",
                method="policy",
                message="Demo record — no live verification has been performed.",
                checked_at=utcnow(),
            )
        )

        analytics.recompute_quality(session, offer)
        analytics.recompute_popularity(session, offer)
        created += 1

    return created


def _eligibility_label(rule: str) -> str:
    return {
        "new_users": "New users only",
        "students": "Students only",
        "countries": "Available in selected countries only",
        "global": "Available worldwide",
        "payment_method": "Payment method required",
    }.get(rule, rule.replace("_", " ").title())


def random_offset(title: str) -> float:
    return float(sum(ord(c) for c in title) % 14) + 1


def random_views(title: str) -> int:
    return 120 + (sum(ord(c) for c in title) * 7) % 2400


def _seed_extras(session, sources: dict[str, Source]) -> None:
    """Free-alternative links + a couple of expired demo offers."""
    from app.models.enums import OfferStatus as _Status

    alternatives = [
        ("Adobe Creative Cloud — 65% off the first year for students", "GIMP — free and open source, forever", "alternative"),
        ("Canva Pro — 90 days free, then 50% off for 3 months", "Photopea — free browser-based Photoshop alternative", "alternative"),
        ("Notion — free plan with unlimited pages", "Obsidian — local-first markdown notes", "alternative"),
    ]
    for primary_title, alt_title, relation in alternatives:
        primary = session.execute(
            select(Offer).where(Offer.title == primary_title)
        ).scalars().first()
        alternative = session.execute(
            select(Offer).where(Offer.title == alt_title)
        ).scalars().first()
        if primary is None or alternative is None:
            continue
        exists = session.execute(
            select(OfferAlternative.id).where(
                OfferAlternative.offer_id == primary.id,
                OfferAlternative.related_offer_id == alternative.id,
            )
        ).first()
        if exists:
            continue
        session.add(
            OfferAlternative(
                offer_id=primary.id,
                related_offer_id=alternative.id,
                label="Free alternative",
                relation=relation,
                note=f"Use {alternative.brand.name if alternative.brand else 'this tool'} instead of paying.",
            )
        )

    # A couple of expired demo records so the "recently expired" rail has content.
    expired_specs = [
        (
            "CloudConvert Pro trial — expired",
            "A demonstration record for an offer that has already ended.",
            6,
        ),
        (
            "Headspace Plus 2 months free — expired",
            "A demonstration record for an offer that has already ended.",
            11,
        ),
    ]
    category = session.execute(
        select(Category).where(Category.slug == "free-websites-utilities")
    ).scalars().first()
    for title, short, days_ago in expired_specs:
        slug = slugify(title)
        if session.execute(select(Offer.id).where(Offer.slug == slug)).first():
            continue
        offer = Offer(
            slug=slug,
            title=title,
            short_description=short,
            description=short + " DEMO DATA.",
            category_id=category.id if category else None,
            offer_type=OfferType.FREE_TRIAL.value,
            currency="USD",
            promo_price=Decimal("0"),
            original_price=Decimal("19.99"),
            savings_value=Decimal("19.99"),
            savings_percent=100,
            trial_days=30,
            starts_at=utcnow() - timedelta(days=days_ago + 30),
            expires_at=utcnow() - timedelta(days=days_ago),
            status=_Status.EXPIRED.value,
            verification_status=VerificationStatus.NEEDS_MANUAL.value,
            published_at=utcnow() - timedelta(days=days_ago + 20),
            is_demo_data=True,
            source_id=sources["manual-intake"].id,
            official_url="https://example.com/offer",
            internal_notes="DEMO DATA — expired record used to illustrate the expired-offers view.",
        )
        session.add(offer)
        session.flush()
        analytics.recompute_quality(session, offer)


def _seed_users(session) -> None:
    if session.execute(select(func.count(User.id))).scalar():
        return
    session.add(
        User(
            email="admin@zexrdealhub.dev",
            hashed_password=hash_password("AdminPass123"),
            display_name="Demo Admin",
            role=UserRole.ADMIN.value,
            email_verified=True,
            country_code="IN",
            preferred_currency="INR",
            interests=["ai", "developer", "cloud"],
        )
    )
    session.add(
        User(
            email="reviewer@zexrdealhub.dev",
            hashed_password=hash_password("ReviewPass123"),
            display_name="Demo Reviewer",
            role=UserRole.REVIEWER.value,
            email_verified=True,
            preferred_currency="USD",
            interests=["design", "productivity"],
        )
    )
    session.add(
        User(
            email="user@zexrdealhub.dev",
            hashed_password=hash_password("UserPass123"),
            display_name="Demo User",
            role=UserRole.USER.value,
            email_verified=True,
            country_code="US",
            preferred_currency="USD",
            interests=["streaming", "gaming"],
        )
    )


# --------------------------------------------------------------------- CLI
def seed(session, *, demo: bool = True, demo_users: bool = True) -> dict:
    countries = _seed_countries(session)
    categories = _seed_categories(session)
    brands = _seed_brands(session, categories)
    sources = _seed_sources(session)

    created_offers = 0
    if demo:
        created_offers = _seed_demo_offers(session, categories, brands, countries, sources)
        _seed_extras(session, sources)
    if demo_users:
        _seed_users(session)

    for offer in session.execute(select(Offer)).scalars().unique().all():
        analytics.recompute_quality(session, offer)
        analytics.recompute_popularity(session, offer)

    session.commit()
    search_service.invalidate_vocabulary_cache()

    counts = {
        "countries": session.execute(select(func.count(Country.id))).scalar(),
        "categories": session.execute(select(func.count(Category.id))).scalar(),
        "brands": session.execute(select(func.count(Brand.id))).scalar(),
        "sources": session.execute(select(func.count(Source.id))).scalar(),
        "offers": session.execute(select(func.count(Offer.id))).scalar(),
        "demo_offers_created": created_offers,
        "users": session.execute(select(func.count(User.id))).scalar(),
    }
    return counts


# ---------------------------------------------------------------------------
# Schema management
#
# The schema is owned by Alembic.  Seeding deliberately does NOT call
# ``create_all``: that produces tables Alembic never stamped, after which
# ``alembic upgrade head`` fails with "table already exists" and
# ``alembic check`` reports "target database is not up to date".
# ---------------------------------------------------------------------------

MIGRATIONS_ROOT = Path(__file__).resolve().parents[2]


def _alembic_config():
    from alembic.config import Config

    cfg = Config(str(MIGRATIONS_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(MIGRATIONS_ROOT / "alembic"))
    return cfg


def upgrade_to_head() -> None:
    """Apply migrations up to head. A no-op when the database is already current."""
    from alembic import command

    command.upgrade(_alembic_config(), "head")


def downgrade_to_base() -> None:
    """Drop every managed table and clear the version stamp."""
    from alembic import command

    command.downgrade(_alembic_config(), "base")


def reset(session) -> None:
    """Drop and rebuild the schema through Alembic so version tracking stays correct."""
    log.warning("seed.reset_requested")
    downgrade_to_base()
    upgrade_to_head()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the ZEXR Deal Hub database")
    parser.add_argument(
        "--reset", action="store_true", help="Drop and recreate all tables first"
    )
    parser.add_argument(
        "--demo-offers",
        action="store_true",
        help="Also create clearly-labelled DEMO offers (off by default: prefer real discovered data)",
    )
    parser.add_argument("--no-users", action="store_true", help="Skip the demo accounts")
    parser.add_argument(
        "--no-sources",
        action="store_true",
        help="Skip installing the curated public deal sources",
    )
    parser.add_argument(
        "--no-providers",
        action="store_true",
        help="Skip importing the curated AI provider catalogue",
    )
    args = parser.parse_args()

    if args.reset:
        reset(None)
    else:
        upgrade_to_head()

    session = SessionLocal()
    try:
        if not args.no_sources:
            from app.discovery import catalog

            installed = catalog.install(session)
            print(
                f"Installed {len(installed['created'])} public source(s): "
                f"{', '.join(installed['created']) or 'none new'}"
            )
        counts = seed(session, demo=args.demo_offers, demo_users=not args.no_users)

        if not args.no_providers:
            from app.db.provider_catalog import import_catalogue

            catalogue = import_catalogue(session)
            print(
                f"AI provider catalogue: {catalogue['created']} new, "
                f"{catalogue['updated']} refreshed, {catalogue['skipped']} already verified"
            )
    finally:
        session.close()

    print("\nSeed complete:")
    for key, value in counts.items():
        print(f"  {key:22} {value}")
    print(
        "\nDemo accounts (development only):\n"
        "  admin@zexrdealhub.dev    / AdminPass123\n"
        "  reviewer@zexrdealhub.dev / ReviewPass123\n"
        "  user@zexrdealhub.dev     / UserPass123\n"
    )


if __name__ == "__main__":
    main()