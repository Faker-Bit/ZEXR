"""Auth + user schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import EmailStr, Field, field_validator

from app.models.enums import AlertKind, AuthProvider, UserRole
from app.schemas.common import ORMModel

MIN_PASSWORD_LENGTH = 8


def _password_strength(value: str) -> str:
    if len(value) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    if value.lower() == value or value.upper() == value:
        raise ValueError("Password must mix upper and lower case")
    if not any(ch.isdigit() for ch in value):
        raise ValueError("Password must contain a number")
    return value


class RegisterRequest(ORMModel):
    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=128)
    display_name: str | None = Field(default=None, max_length=120)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    preferred_currency: str = Field(default="USD", min_length=3, max_length=3)
    newsletter_opt_in: bool = False
    interests: list[str] = Field(default_factory=list)

    _check_password = field_validator("password")(_password_strength)

    @field_validator("preferred_currency")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()

    @field_validator("country_code")
    @classmethod
    def _upper_country(cls, v: str | None) -> str | None:
        return v.upper() if v else v


class LoginRequest(ORMModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class OAuthStartRequest(ORMModel):
    provider: AuthProvider = AuthProvider.GOOGLE
    redirect_uri: str | None = None


class OAuthCallbackRequest(ORMModel):
    provider: AuthProvider
    code: str
    redirect_uri: str | None = None
    state: str | None = None


class TokenPair(ORMModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UserOut"


class RefreshRequest(ORMModel):
    refresh_token: str


class UserOut(ORMModel):
    id: str
    email: EmailStr
    display_name: str | None = None
    avatar_url: str | None = None
    role: UserRole = UserRole.USER
    country_code: str | None = None
    preferred_currency: str = "USD"
    locale: str = "en"
    interests: list[str] = Field(default_factory=list)
    email_notifications: bool = True
    newsletter_subscribed: bool = False
    is_active: bool = True
    created_at: datetime
    bookmark_count: int = 0
    alert_count: int = 0


class UserUpdate(ORMModel):
    display_name: str | None = Field(default=None, max_length=120)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    preferred_currency: str | None = Field(default=None, min_length=3, max_length=3)
    locale: str | None = Field(default=None, max_length=12)
    interests: list[str] | None = None
    email_notifications: bool | None = None
    newsletter_subscribed: bool | None = None

    @field_validator("preferred_currency")
    @classmethod
    def _upper(cls, v: str | None) -> str | None:
        return v.upper() if v else v

    @field_validator("country_code")
    @classmethod
    def _upper_country(cls, v: str | None) -> str | None:
        return v.upper() if v else v


class PasswordChange(ORMModel):
    current_password: str
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=128)

    _check_password = field_validator("new_password")(_password_strength)


class BookmarkCreate(ORMModel):
    offer_id: str
    note: str | None = Field(default=None, max_length=500)
    notify_on_expiry: bool = True
    notify_on_price_drop: bool = True


class BookmarkOut(ORMModel):
    id: str
    offer_id: str
    note: str | None = None
    notify_on_expiry: bool = True
    notify_on_price_drop: bool = True
    created_at: datetime
    offer: "BookmarkOffer | None" = None


class BookmarkOffer(ORMModel):
    id: str
    slug: str
    title: str
    short_description: str
    offer_type: str
    official_url: str
    redemption_url: str = ""
    currency: str = "USD"
    promo_price: float | None = None
    original_price: float | None = None
    savings_percent: int = 0
    expires_at: datetime | None = None
    is_expired: bool = False
    image_url: str | None = None
    brand: "BrandMini | None" = None
    category: "CategoryMini | None" = None


class CategoryMini(ORMModel):
    id: str
    slug: str
    name: str
    icon: str = "tag"
    color: str = "lime"


class BrandMini(ORMModel):
    id: str
    slug: str
    name: str
    domain: str | None = None
    logo_url: str | None = None


class AlertUpsert(ORMModel):
    kind: AlertKind = AlertKind.CATEGORY
    label: str | None = Field(default=None, max_length=160)
    query: str | None = Field(default=None, max_length=240)
    category_id: str | None = None
    brand_id: str | None = None
    filters: dict = Field(default_factory=dict)
    frequency: str = Field(default="instant", pattern="^(instant|daily|weekly|never)$")
    is_active: bool = True


class AlertOut(ORMModel):
    id: str
    kind: AlertKind
    label: str
    query: str | None = None
    category_id: str | None = None
    brand_id: str | None = None
    filters: dict = Field(default_factory=dict)
    frequency: str = "instant"
    is_active: bool = True
    created_at: datetime
    last_triggered_at: datetime | None = None
    match_count: int = 0


class RecommendationRequest(ORMModel):
    interests: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    country_code: str | None = None
    currency: str | None = None
    limit: int = Field(default=12, ge=1, le=50)


class RecentViewOut(ORMModel):
    offer_id: str
    viewed_at: datetime
    offer: BookmarkOffer | None = None


class NewsletterSubscribe(ORMModel):
    email: EmailStr
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    interests: list[str] = Field(default_factory=list)
    frequency: str = Field(default="weekly", pattern="^(weekly|daily|instant)$")

    @field_validator("country_code")
    @classmethod
    def _upper_country(cls, v: str | None) -> str | None:
        return v.upper() if v else v


class NewsletterResult(ORMModel):
    ok: bool
    message: str
    already_subscribed: bool = False


class ReportCreate(ORMModel):
    offer_id: str | None = None
    reason: str = Field(pattern="^(expired|misleading|wrong_price|broken_link|fraud|region_restricted|duplicate|other)$")
    details: str | None = Field(default=None, max_length=2000)
    email: EmailStr | None = None


class ClickTrackResponse(ORMModel):
    redirect_url: str
    offer_slug: str
    is_affiliate: bool = False