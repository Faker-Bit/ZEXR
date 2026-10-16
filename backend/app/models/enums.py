"""Domain enumerations.

Kept in one module so new offer types / verification states can be added
without touching the schema migrations beyond a new enum value.
"""

from __future__ import annotations

import enum


class OfferType(str, enum.Enum):
    FREE = "free"                      # genuinely free, no catch
    FREE_TRIAL = "free_trial"          # time limited, converts to paid
    FREEMIUM = "freemium"              # free tier with paid upgrade
    FREE_CREDITS = "free_credits"      # $ / API / compute credits
    DISCOUNT = "discount"              # % or fixed amount off
    COUPON = "coupon"                  # code at checkout
    CASHBACK = "cashback"              # money back
    FREE_ALTERNATIVE = "free_alternative"  # free replacement for a paid tool


class OfferStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    PUBLISHED = "published"
    REJECTED = "rejected"
    EXPIRED = "expired"
    DISPUTED = "disputed"
    ARCHIVED = "archived"


class VerificationStatus(str, enum.Enum):
    UNVERIFIED = "unverified"
    NEEDS_MANUAL = "needs_manual"
    VERIFIED = "verified"
    FAILED = "failed"


class VerificationResult(str, enum.Enum):
    OK = "ok"
    REDIRECTED = "redirected"
    NOT_FOUND = "not_found"
    SERVER_ERROR = "server_error"
    BLOCKED = "blocked"
    PRICE_CHANGED = "price_changed"
    CONTENT_CHANGED = "content_changed"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"
    FAILED = "failed"


class UserRole(str, enum.Enum):
    USER = "user"
    REVIEWER = "reviewer"
    ADMIN = "admin"


class AuthProvider(str, enum.Enum):
    EMAIL = "email"
    GOOGLE = "google"
    GITHUB = "github"


class EligibilityType(str, enum.Enum):
    GLOBAL = "global"
    COUNTRIES = "countries"
    NEW_USERS = "new_users"
    STUDENTS = "students"
    AGE_18_PLUS = "age_18_plus"
    BUSINESS_EMAIL = "business_email"
    INVITE_ONLY = "invite_only"
    EXISTING_CUSTOMERS = "existing_customers"
    ANNUAL_BILLING = "annual_billing"
    PAYMENT_METHOD = "payment_method"
    PHONE_VERIFIED = "phone_verified"
    IDENTITY_VERIFIED = "identity_verified"


class SourceType(str, enum.Enum):
    RSS = "rss"
    JSON_API = "json_api"
    HTML_LISTING = "html_listing"
    AFFILIATE_API = "affiliate_api"
    PARTNER_API = "partner_api"
    MANUAL = "manual"
    SUBMISSION = "submission"


class SourceHealth(str, enum.Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILING = "failing"
    PAUSED = "paused"


class AlertKind(str, enum.Enum):
    CATEGORY = "category"
    BRAND = "brand"
    KEYWORD = "keyword"
    SAVED_EXPIRING = "saved_expiring"
    PRICE_DROP = "price_drop"
    ENDING_SOON = "ending_soon"
    WEEKLY_DIGEST = "weekly_digest"


class ReportReason(str, enum.Enum):
    EXPIRED = "expired"
    MISLEADING = "misleading"
    WRONG_PRICE = "wrong_price"
    BROKEN_LINK = "broken_link"
    FRAUD = "fraud"
    REGION_RESTRICTED = "region_restricted"
    DUPLICATE = "duplicate"
    OTHER = "other"


class ReportStatus(str, enum.Enum):
    OPEN = "open"
    TRIAGED = "triaged"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class DiscountKind(str, enum.Enum):
    PERCENT = "percent"
    FIXED = "fixed"
    FREE_MONTHS = "free_months"
    CREDIT = "credit"


class EventType(str, enum.Enum):
    PAGE_VIEW = "page_view"
    SEARCH = "search"
    OFFER_VIEW = "offer_view"
    OFFER_CLICK = "offer_click"
    BOOKMARK = "bookmark"
    SHARE = "share"
    REPORT = "report"
    NEWSLETTER_SIGNUP = "newsletter_signup"
    ADMIN_ACTION = "admin_action"

class SubscriptionPlan(str, enum.Enum):
    FREE = "free"
    PRO = "pro"


class SubscriptionStatus(str, enum.Enum):
    NONE = "none"
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    UNPAID = "unpaid"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    PAUSED = "paused"


class PaymentProvider(str, enum.Enum):
    NONE = "none"
    STRIPE = "stripe"
    RAZORPAY = "razorpay"
    MANUAL = "manual"


#: Statuses that can entitle a user to Pro, subject to the period check in
#: `app.services.billing.is_entitled`. ``past_due`` is included deliberately: a
#: card that failed but is still inside the grace window should not lose access
#: mid-month while the customer updates their details.
ENTITLING_STATUSES = frozenset(
    {
        SubscriptionStatus.ACTIVE.value,
        SubscriptionStatus.TRIALING.value,
        SubscriptionStatus.PAST_DUE.value,
    }
)