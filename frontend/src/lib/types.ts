/** Types mirroring the FastAPI response models. */

export type OfferType =
  | "free"
  | "free_trial"
  | "freemium"
  | "free_credits"
  | "discount"
  | "coupon"
  | "cashback"
  | "free_alternative";

export type OfferStatus =
  | "draft"
  | "pending_review"
  | "published"
  | "rejected"
  | "expired"
  | "disputed"
  | "archived";

export type VerificationStatus =
  | "unverified"
  | "needs_manual"
  | "verified"
  | "failed";

export type SortOption =
  | "relevance"
  | "newest"
  | "popular"
  | "savings"
  | "ending_soon"
  | "value"
  | "trending"
  | "price_asc"
  | "price_desc";

export interface CategoryBrief {
  id: string;
  slug: string;
  name: string;
  icon: string;
  color: string;
  tagline?: string | null;
  offer_count: number;
  live_offer_count: number;
}

export interface Category extends CategoryBrief {
  description?: string | null;
  group_name?: string | null;
  seo_title?: string | null;
  seo_description?: string | null;
  keywords: string[];
}

export interface BrandBrief {
  id: string;
  slug: string;
  name: string;
  domain?: string | null;
  logo_url?: string | null;
  accent_color?: string | null;
  is_verified: boolean;
  offer_count: number;
}

export interface CountryBrief {
  code: string;
  name: string;
  slug: string;
  flag_emoji?: string | null;
  currency: string;
  region?: string | null;
  offer_count: number;
}

export interface Price {
  currency: string;
  country_code?: string | null;
  original_price?: number | null;
  promo_price?: number | null;
  renewal_price?: number | null;
  billing_period?: string | null;
  is_available: boolean;
  captured_at?: string | null;
}

export interface EligibilityRule {
  rule: string;
  label: string;
  detail?: string | null;
  blocking: boolean;
  source_url?: string | null;
}

export interface VerificationEntry {
  id: string;
  result: string;
  http_status?: number | null;
  final_url?: string | null;
  checked_at: string;
  method: string;
  price_found?: number | null;
  original_price_found?: number | null;
  message?: string | null;
}

export interface Alternative {
  id: string;
  label: string;
  relation: string;
  external_name?: string | null;
  external_url?: string | null;
  note?: string | null;
}

export interface OfferCard {
  id: string;
  slug: string;
  title: string;
  short_description: string;
  offer_type: OfferType;
  status: OfferStatus;
  verification_status: VerificationStatus;

  category: CategoryBrief;
  brand?: BrandBrief | null;

  currency: string;
  original_price?: number | null;
  promo_price?: number | null;
  savings_value: number;
  savings_percent: number;
  billing_period?: string | null;
  trial_days?: number | null;
  credits_amount?: number | null;
  credits_unit?: string | null;

  is_global: boolean;
  requires_payment_method: boolean;
  requires_new_user: boolean;
  requires_student_id: boolean;
  requires_auto_renew?: boolean;
  is_affiliate?: boolean;
eligibility_types: string[];
  /** Short caveat shown on the card, e.g. a provider's reported free-tier terms. */
  eligibility_notes?: string | null;
  country_codes: string[];

  official_url: string;
  redemption_url: string;
  image_url?: string | null;
  is_sponsored: boolean;
  sponsor_name?: string | null;

  expires_at?: string | null;
  last_checked_at?: string | null;
  published_at?: string | null;
  days_remaining?: number | null;
  hours_remaining?: number | null;
  is_expired: boolean;
  is_verified: boolean;
  is_featured: boolean;
  is_handpicked: boolean;
  is_demo_data: boolean;
  is_genuinely_free: boolean;

  popularity_score: number;
  bookmark_count: number;
  click_count: number;

  display_prices: Price[];
  relevance?: number | null;
  matched_reason?: string | null;
  bookmarked: boolean;
}

export interface OfferDetail extends OfferCard {
  subtitle?: string | null;
  description: string;
  how_to_redeem: string[];
  fine_print?: string | null;
  features: string[];
  free_alternative_note?: string | null;
  ends_as_paid: boolean;
  renewal_price?: number | null;
  discount_kind?: string | null;
  discount_amount?: number | null;
  starts_at?: string | null;
  redemption_deadline?: string | null;
  eligibility_notes?: string | null;
  eligibility: EligibilityRule[];
  excluded_countries: string[];
  secondary_category_ids: string[];
  coupon_code?: string | null;
  is_disputed: boolean;
  discovery_confidence: number;
  source_name?: string | null;
  verifications: VerificationEntry[];
  alternatives: Alternative[];
  similar: OfferCard[];
  free_alternatives: OfferCard[];
}

export interface QuotaMeta {
  limited: boolean;
  shown: number;
  limit: number | null;
  total: number;
  plan: "free" | "pro";
  is_pro: boolean;
  reason: string | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
  has_next: boolean;
  has_prev: boolean;
  /** Present on listings; describes any free-tier truncation. */
  meta?: QuotaMeta | null;
}

export interface FacetBucket {
  value: string;
  label: string;
  count: number;
  extra?: Record<string, unknown>;
}

export interface Facets {
  categories: FacetBucket[];
  brands: FacetBucket[];
  offer_types: FacetBucket[];
  countries: FacetBucket[];
  durations: FacetBucket[];
  max_savings: number;
  max_price?: number | null;
}

export interface ParsedIntent {
  raw: string;
  normalised: string;
  intent: string;
  offer_types: OfferType[];
  category_slugs: string[];
  brand_slugs: string[];
  keywords: string[];
  min_trial_days?: number | null;
  max_trial_days?: number | null;
  max_price?: number | null;
  min_price?: number | null;
  country_codes: string[];
  requires_payment_method?: boolean | null;
  ending_within_days?: number | null;
  explanation: string;
}

export interface SearchSuggestion {
  type: "offer" | "brand" | "category" | "query";
  id: string;
  label: string;
  sublabel?: string | null;
  slug?: string | null;
  logo_url?: string | null;
  icon?: string | null;
  offer_type?: OfferType | null;
  score: number;
}

export interface SearchResponse {
  query: string;
  intent: ParsedIntent;
  results: OfferCard[];
  suggestions: SearchSuggestion[];
  corrections: string[];
  facets: Record<string, Record<string, number>>;
  total: number;
  page: number;
  page_size: number;
  pages: number;
  took_ms: number;
  did_you_mean?: string | null;
  meta?: QuotaMeta | null;
}

export interface PlatformStats {
  total_offers: number;
  live_offers: number;
  verified_offers: number;
  free_offers: number;
  categories: number;
  total_savings: number;
  generated_at: string;
}

export interface HomeBundle {
  trending: OfferCard[];
  fresh: OfferCard[];
  ending_soon: OfferCard[];
  featured: OfferCard[];
  handpicked: OfferCard[];
  highest_value: OfferCard[];
  free_tools: OfferCard[];
  no_card: OfferCard[];
  popular: OfferCard[];
  stats: PlatformStats;
}

export interface User {
  id: string;
  email: string;
  display_name?: string | null;
  avatar_url?: string | null;
  role: "user" | "reviewer" | "admin";
  country_code?: string | null;
  preferred_currency: string;
  locale: string;
  interests: string[];
  email_notifications: boolean;
  newsletter_subscribed: boolean;
  is_active: boolean;
  created_at: string;
  bookmark_count: number;
  alert_count: number;
}

export interface Bookmark {
  id: string;
  offer_id: string;
  note?: string | null;
  notify_on_expiry: boolean;
  notify_on_price_drop: boolean;
  created_at: string;
  offer?: OfferCard | null;
}

export interface Alert {
  id: string;
  kind: string;
  label: string;
  query?: string | null;
  category_id?: string | null;
  brand_id?: string | null;
  filters: Record<string, unknown>;
  frequency: string;
  is_active: boolean;
  created_at: string;
  last_triggered_at?: string | null;
  match_count: number;
}

export interface OfferTypeMeta {
  value: OfferType;
  label: string;
  count: number;
}

export interface InterestTag {
  slug: string;
  label: string;
  icon: string;
  keywords: string[];
}

export interface Source {
  id: string;
  key: string;
  name: string;
  publisher: string;
  source_type: string;
  adapter?: string | null;
  homepage_url: string;
  feed_url?: string | null;
  api_docs_url?: string | null;
  is_active: boolean;
  respect_robots: boolean;
  requires_js: boolean;
  is_paywalled: boolean;
  rate_limit_per_hour: number;
  min_request_interval_seconds: number;
  cache_ttl_seconds: number;
  max_items: number;
  health: "healthy" | "degraded" | "failing" | "paused";
  trust_weight: number;
  license_note?: string | null;
  terms_url?: string | null;
  config: Record<string, unknown>;
  api_key_configured: boolean;
  last_run_at?: string | null;
  last_success_at?: string | null;
  consecutive_failures: number;
  total_items_seen: number;
  total_items_accepted: number;
  total_items_duplicate: number;
  total_items_rejected: number;
}

export interface DiscoveryCandidate {
  id: string;
  source_id: string;
  source_key?: string | null;
  source_url: string;
  raw_title: string;
  raw_description?: string | null;
  status: string;
  rejection_reason?: string | null;
  confidence: number;
  offer_id?: string | null;
  duplicate_of_id?: string | null;
  reviewed_at?: string | null;
  seen_at: string;
  parsed: ParsedOfferFields;
}

/** Values lifted straight from a discovery payload by the adapters. */
export interface ParsedOfferFields {
  offer_type?: string;
  promo_price?: number;
  original_price?: number;
  currency?: string;
  trial_days?: number;
  expires_at?: string;
  coupon_code?: string;
  eligibility?: string[];
  [key: string]: unknown;
}

export interface DashboardStats {
  total_offers: number;
  live_offers: number;
  expired_offers: number;
  pending_review: number;
  verified_offers: number;
  disputed_offers: number;
  demo_offers: number;
  total_categories: number;
  total_brands: number;
  total_sources: number;
  active_sources: number;
  failing_sources: number;
  total_users: number;
  new_users_7d: number;
  total_bookmarks: number;
  open_reports: number;
  pending_candidates: number;
  clicks_7d: number;
  views_7d: number;
  searches_7d: number;
  newsletter_subs: number;
  sponsored_offers: number;
  avg_savings_percent: number;
  generated_at: string;
}

export interface TrendPoint {
  day: string;
  value: number;
}

export interface TopRow {
  label: string;
  slug?: string | null;
  id?: string | null;
  value: number;
  extra?: Record<string, unknown>;
}

export interface AnalyticsOverview {
  range_days: number;
  clicks: TrendPoint[];
  views: TrendPoint[];
  searches: TrendPoint[];
  signups: TrendPoint[];
  top_categories: TopRow[];
  top_offers: TopRow[];
  top_countries: TopRow[];
  top_searches: TopRow[];
  zero_result_searches: TopRow[];
  conversion_rate: number;
  click_to_verify_rate: number;
  verification_success_rate: number;
}

export interface VerificationSweepResult {
  checked: number;
  ok: number;
  changed: number;
  broken: number;
  expired: number;
  failed: number;
  skipped: number;
  details: Record<string, unknown>[];
}

export interface DiscoverySweepResult {
  sources_checked: number;
  sources_skipped: number;
  items_seen: number;
  items_created: number;
  items_updated: number;
  items_duplicate: number;
  items_rejected: number;
  details: Record<string, unknown>[];
}

export interface AdminOfferRow extends OfferCard {
  source_key?: string | null;
  duplicate_of_id?: string | null;
  created_at: string;
  consecutive_failures: number;
  discovery_confidence: number;
}

export interface Report {
  id: string;
  offer_id?: string | null;
  offer_title?: string | null;
  reason: string;
  details?: string | null;
  status: string;
  reporter_email?: string | null;
  created_at: string;
  resolved_at?: string | null;
  resolution_note?: string | null;
}

export interface Submission {
  id: string;
  title: string;
  brand_name?: string | null;
  official_url: string;
  category_slug?: string | null;
  offer_type?: string | null;
  notes?: string | null;
  submitter_email?: string | null;
  status: string;
  created_at: string;
  created_offer_id?: string | null;
}

export interface AdminUser {
  id: string;
  email: string;
  display_name?: string | null;
  role: string;
  country_code?: string | null;
  preferred_currency: string;
  is_active: boolean;
  is_banned: boolean;
  created_at: string;
  last_login_at?: string | null;
  bookmark_count: number;
}

export interface ScheduledJob {
  name: string;
  schedule: string;
  enabled: boolean;
  last_run_at?: string | null;
  next_run_at?: string | null;
  description: string;
}

/* ----------------------------------------------------------------- billing */

export type SubscriptionPlan = "free" | "pro";

export interface PlanOut {
  id: SubscriptionPlan;
  name: string;
  price_monthly: number;
  price_monthly_inr?: number | null;
  currency: string;
  features: string[];
  highlighted: boolean;
}

export interface ProviderOut {
  id: "stripe" | "razorpay";
  label: string;
  configured: boolean;
  currency: string;
  amount: number;
  publishable_key: string | null;
}

export interface PlansOut {
  plans: PlanOut[];
  providers: ProviderOut[];
  trial_days: number;
  billing_enabled: boolean;
  any_provider_configured: boolean;
}

export interface SubscriptionOut {
  provider: string;
  status: string;
  plan: string;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  trial_end: string | null;
  notes: string | null;
}

export interface BillingStatus {
  plan: SubscriptionPlan;
  is_pro: boolean;
  result_limit: number | null;
  features: string[];
  reason: string | null;
  status: string;
  provider: string;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  subscription: SubscriptionOut;
}

export interface CheckoutResult {
  ok: boolean;
  provider: string;
  error?: string | null;
  session_id?: string | null;
  order_id?: string | null;
  checkout_url?: string | null;
  publishable_key?: string | null;
  amount: number;
  currency: string;
}