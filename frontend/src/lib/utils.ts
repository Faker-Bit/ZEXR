import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Format a monetary value with the symbol for its currency. */
export function formatMoney(
  value: number | null | undefined,
  currency = "USD",
  options: { decimals?: boolean; compact?: boolean } = {},
): string {
  if (value === null || value === undefined) return "—";
  const symbols: Record<string, string> = {
    USD: "$", EUR: "€", GBP: "£", INR: "₹", CAD: "C$",
    AUD: "A$", JPY: "¥", SGD: "S$", HKD: "HK$", BRL: "R$",
    MXN: "Mex$", ZAR: "R", AED: "AED ", SEK: "kr", NOK: "kr",
    DKK: "kr", PLN: "zł", TRY: "₺", IDR: "Rp", PHP: "₱",
    THB: "฿", MYR: "RM", KRW: "₩", TWD: "NT$", NZD: "NZ$",
  };
  const symbol = symbols[currency.toUpperCase()] ?? `${currency.toUpperCase()} `;
  if (options.compact && Math.abs(value) >= 1000) {
    return `${symbol}${(value / 1000).toFixed(value >= 10000 ? 0 : 1)}k`;
  }
  const decimals = options.decimals ?? !Number.isInteger(value);
  const formatted = value.toLocaleString("en-US", {
    minimumFractionDigits: decimals ? 2 : 0,
    maximumFractionDigits: decimals ? 2 : 0,
  });
  return `${symbol}${formatted}`;
}

/** Compact number: 1.2k, 3.4M */
export function formatCompact(value: number): string {
  if (!Number.isFinite(value)) return "0";
  if (Math.abs(value) < 1000) return String(Math.round(value));
  if (Math.abs(value) < 1_000_000) return `${(value / 1000).toFixed(value < 10_000 ? 1 : 0)}k`;
  return `${(value / 1_000_000).toFixed(1)}M`;
}

/** "3 days ago" / "in 2 hours" */
export function relativeTime(value: string | Date | null | undefined): string {
  if (!value) return "never";
  const date = typeof value === "string" ? new Date(value) : value;
  const diff = date.getTime() - Date.now();
  const abs = Math.abs(diff);
  const minute = 60_000;
  const hour = 60 * minute;
  const day = 24 * hour;

  const formatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  if (abs < minute) return "just now";
  if (abs < hour) return formatter.format(Math.round(diff / minute), "minute");
  if (abs < day) return formatter.format(Math.round(diff / hour), "hour");
  if (abs < 30 * day) return formatter.format(Math.round(diff / day), "day");
  if (abs < 365 * day) return formatter.format(Math.round(diff / (30 * day)), "month");
  return formatter.format(Math.round(diff / (365 * day)), "year");
}

export function formatDate(value: string | Date | null | undefined): string {
  if (!value) return "—";
  const date = typeof value === "string" ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

export function formatDateTime(value: string | Date | null | undefined): string {
  if (!value) return "—";
  const date = typeof value === "string" ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Countdown label for an expiry date. */
export function expiryLabel(offer: {
  expires_at?: string | null;
  days_remaining?: number | null;
  hours_remaining?: number | null;
  is_expired?: boolean;
}): { label: string; tone: "urgent" | "soon" | "normal" } {
  if (offer.is_expired) return { label: "Expired", tone: "urgent" };
  const expires = offer.expires_at ? new Date(offer.expires_at).getTime() : null;
  if (!expires) return { label: "Ongoing", tone: "normal" };

  const diff = expires - Date.now();
  if (diff <= 0) return { label: "Expired", tone: "urgent" };
  const hours = diff / 3_600_000;
  if (hours < 24) {
    const whole = Math.max(1, Math.floor(hours));
    return { label: `${whole}h left`, tone: "urgent" };
  }
  const days = Math.floor(diff / 86_400_000);
  if (days <= 3) return { label: `${days}d left`, tone: "urgent" };
  if (days <= 14) return { label: `${days} days left`, tone: "soon" };
  return { label: `${days} days left`, tone: "normal" };
}

const PERIOD_SUFFIX: Record<string, string> = {
  monthly: "/mo",
  yearly: "/yr",
  annual: "/yr",
  weekly: "/wk",
  lifetime: "",
};

export function priceLine(offer: {
  promo_price?: number | null;
  original_price?: number | null;
  billing_period?: string | null;
  currency?: string;
  credits_amount?: number | null;
  credits_unit?: string | null;
  is_genuinely_free?: boolean;
  offer_type?: string;
}): string {
  const currency = offer.currency ?? "USD";
  if (offer.credits_amount) {
    return `${formatMoney(offer.credits_amount, currency)} ${offer.credits_unit || "credit"}`;
  }
  if (offer.promo_price === 0) return "Free";
  if (offer.promo_price === null || offer.promo_price === undefined) {
    if (offer.is_genuinely_free || offer.offer_type === "free") return "Free";
    if (offer.offer_type === "coupon") return "Coupon";
    if (offer.offer_type === "cashback") return "Cashback";
    return "Price on site";
  }
  const suffix = PERIOD_SUFFIX[(offer.billing_period ?? "").toLowerCase()] ?? "";
  return `${formatMoney(offer.promo_price, currency)}${suffix}`;
}

/** SSR-safe relative time (avoids hydration mismatch between server & client). */
export function formatRelativeSafe(value: string | Date | null | undefined): string {
  if (!value) return "recently";
  const date = typeof value === "string" ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) return "recently";
  const diff = date.getTime() - Date.now();
  const abs = Math.abs(diff);
  const minute = 60_000;
  const hour = 60 * minute;
  const day = 24 * hour;

  if (abs < minute) return "just now";
  if (abs < hour) return `${Math.max(1, Math.round(abs / minute))}m ago`;
  if (abs < day) return `${Math.max(1, Math.round(abs / hour))}h ago`;
  if (abs < 30 * day) return `${Math.max(1, Math.round(abs / day))}d ago`;
  if (abs < 365 * day) return `${Math.max(1, Math.round(abs / (30 * day)))}mo ago`;
  return `${Math.max(1, Math.round(abs / (365 * day)))}y ago`;
}

export const OFFER_TYPE_LABELS: Record<string, string> = {
  free: "Free",
  free_trial: "Free trial",
  freemium: "Freemium",
  free_credits: "Free credits",
  discount: "Discount",
  coupon: "Coupon",
  cashback: "Cashback",
  free_alternative: "Free alternative",
};

export const ELIGIBILITY_LABELS: Record<string, string> = {
  new_users: "New users only",
  global: "Worldwide",
  countries: "Selected countries",
  students: "Students only",
  age_18_plus: "18+ only",
  business_email: "Business email",
  invite_only: "Invite only",
  existing_customers: "Existing customers",
  annual_billing: "Annual billing",
  payment_method: "Card required",
  phone_verified: "Phone required",
  identity_verified: "ID required",
};

export function labelForOfferType(value: string): string {
  return OFFER_TYPE_LABELS[value] ?? value.replace(/_/g, " ");
}

export function labelForEligibility(value: string): string {
  return ELIGIBILITY_LABELS[value] ?? value.replace(/_/g, " ");
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join("");
}

export function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

/** Deterministic accent for a brand so avatars stay stable without assets. */
export function brandAccent(seed: string): string {
  let hash = 0;
  for (let i = 0; i < seed.length; i += 1) {
    hash = (hash << 5) - hash + seed.charCodeAt(i);
    hash |= 0;
  }
  const hue = Math.abs(hash) % 360;
  return `hsl(${hue} 62% 52%)`;
}

export function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export function isSafeExternal(url: string): boolean {
  return /^https?:\/\//i.test(url);
}

export function pluralise(count: number, singular: string, plural?: string): string {
  return `${count.toLocaleString()} ${count === 1 ? singular : plural ?? `${singular}s`}`;
}