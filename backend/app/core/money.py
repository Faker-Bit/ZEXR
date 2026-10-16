"""Money helpers, currency metadata and FX conversion."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.core.config import settings

CURRENCY_SYMBOLS: dict[str, str] = {
    "USD": "$", "EUR": "€", "GBP": "£", "INR": "₹", "CAD": "C$",
    "AUD": "A$", "JPY": "¥", "CNY": "¥", "SGD": "S$", "HKD": "HK$",
    "BRL": "R$", "MXN": "Mex$", "ZAR": "R", "AED": "AED ", "SEK": "kr",
    "NOK": "kr", "DKK": "kr", "PLN": "zł", "TRY": "₺", "IDR": "Rp",
    "PHP": "₱", "THB": "฿", "MYR": "RM", "KRW": "₩", "TWD": "NT$",
    "NZD": "NZ$", "ILS": "₪", "UAH": "₴", "RON": "lei", "CZK": "Kč",
}

# Static reference rates (units of currency per 1 USD).  Refreshed by a
# scheduled job when an FX provider is configured; the platform never invents a
# conversion for a pair it does not have a rate for.
USD_RATES: dict[str, float] = {
    "USD": 1.0, "EUR": 0.92, "GBP": 0.79, "INR": 83.5, "CAD": 1.36,
    "AUD": 1.52, "JPY": 151.0, "CNY": 7.24, "SGD": 1.35, "HKD": 7.81,
    "BRL": 5.05, "MXN": 17.1, "ZAR": 18.4, "AED": 3.67, "SEK": 10.5,
    "NOK": 10.7, "DKK": 6.87, "PLN": 3.98, "TRY": 32.3, "IDR": 16200.0,
    "PHP": 56.2, "THB": 36.4, "MYR": 4.72, "KRW": 1338.0, "TWD": 32.1,
    "NZD": 1.65, "ILS": 3.68, "UAH": 39.5, "RON": 4.58, "CZK": 23.1,
}

DEFAULT_CURRENCY = "USD"


def symbol_for(currency: str) -> str:
    return CURRENCY_SYMBOLS.get(currency.upper(), f"{currency.upper()} ")


def convert(amount: float | Decimal | None, source: str, target: str) -> float | None:
    """Convert between currencies using USD as the pivot. None if unknown pair."""
    if amount is None:
        return None
    src = (source or DEFAULT_CURRENCY).upper()
    dst = (target or DEFAULT_CURRENCY).upper()
    if src == dst:
        return round(float(amount), 2)
    src_rate = USD_RATES.get(src)
    dst_rate = USD_RATES.get(dst)
    if not src_rate or not dst_rate:
        return None
    value = float(amount) / src_rate * dst_rate
    return round(value, 2)


def round_money(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def savings_percent(original: float | None, promo: float | None) -> int | None:
    if not original or promo is None:
        return None
    if original <= 0 or promo >= original:
        return 0
    return int(round((1 - promo / original) * 100))


def format_money(value: float | None, currency: str = DEFAULT_CURRENCY) -> str:
    if value is None:
        return "—"
    code = currency.upper()
    sym = symbol_for(code)
    if value >= 1000:
        return f"{sym}{value:,.0f}"
    return f"{sym}{value:,.2f}".replace(".00", "")


def billing_label(billing_period: str | None) -> str:
    return {
        "monthly": "per month",
        "yearly": "per year",
        "annual": "per year",
        "lifetime": "one-time",
        "weekly": "per week",
    }.get((billing_period or "").lower(), "")


def public_currency(currency: str | None) -> str:
    return (currency or DEFAULT_CURRENCY).upper()


def default_currency() -> str:
    return DEFAULT_CURRENCY


def site_url(path: str = "") -> str:
    base = settings.site_url.rstrip("/")
    if not path:
        return base
    return f"{base}/{path.lstrip('/')}"