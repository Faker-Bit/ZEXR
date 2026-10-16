import type {
  Alert,
  AnalyticsOverview,
  Bookmark,
  Category,
  CountryBrief,
  DashboardStats,
  DiscoveryCandidate,
  DiscoverySweepResult,
  Facets,
  HomeBundle,
  InterestTag,
  OfferCard,
  OfferDetail,
  OfferTypeMeta,
  Page,
  ParsedIntent,
  PlatformStats,
  Report,
  SearchResponse,
  SearchSuggestion,
  Source,
  Submission,
  User,
  VerificationSweepResult,
} from "./types";

/**
 * Typed client for the ZEXR Deal Hub API.
 *
 * Server components call `apiServer` (absolute URL, no cookies).
 * Client components call `apiClient` (same-origin `/api` proxy, forwards the
 * session cookie so authenticated endpoints work without a token in JS).
 */

const SERVER_BASE =
  process.env.API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";
const CLIENT_BASE =
  process.env.NEXT_PUBLIC_API_PREFIX?.replace(/\/$/, "") ?? "/api/v1";

/**
 * Never let a slow or unavailable backend hang a page render. Rendering a
 * friendly empty state is always better than a stalled request.
 */
const SERVER_TIMEOUT_MS = Number(process.env.API_TIMEOUT_MS ?? 6000);
const CLIENT_TIMEOUT_MS = Number(process.env.API_CLIENT_TIMEOUT_MS ?? 12000);

export class ApiError extends Error {
  status: number;
  details?: unknown;

  constructor(message: string, status: number, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
}

function buildQuery(params: Record<string, unknown> = {}): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) {
      for (const item of value) {
        if (item !== undefined && item !== null && item !== "") search.append(key, String(item));
      }
    } else {
      search.append(key, String(value));
    }
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = response.statusText;
    let extra: unknown;
    try {
      const body = await response.json();
      detail = body?.detail ?? detail;
      extra = body?.errors ?? body;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(detail, response.status, extra);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** Server-side fetch: absolute backend URL, revalidated every 60s. */
export async function apiServer<T>(
  path: string,
  options: RequestInit & { revalidate?: number; tags?: string[] } = {},
): Promise<T> {
  const { revalidate = 60, tags, ...init } = options;
  const response = await fetch(`${SERVER_BASE}/api/v1${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
    cache: init.cache ?? (init.method && init.method !== "GET" ? "no-store" : undefined),
    next: { revalidate, tags },
    signal: AbortSignal.timeout(SERVER_TIMEOUT_MS),
  });
  return parse<T>(response);
}

/** Client-side fetch: same-origin proxy, cookies included. */
export async function apiClient<T>(
  path: string,
  options: RequestInit & { params?: Record<string, unknown> } = {},
): Promise<T> {
  const { params, ...init } = options;
  const response = await fetch(`${CLIENT_BASE}${path}${buildQuery(params)}`, {
    ...init,
    credentials: "include",
    cache: "no-store",
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
    signal: AbortSignal.timeout(CLIENT_TIMEOUT_MS),
  });
  return parse<T>(response);
}

export interface OfferQuery extends Record<string, unknown> {
  q?: string;
  category?: string[];
  brand?: string[];
  type?: string[];
  country_codes?: string[];
  currencies?: string[];
  min_savings?: number;
  max_price?: number;
  min_trial_days?: number;
  duration?: string;
  requires_payment_method?: boolean;
  requires_student_id?: boolean;
  new_users_only?: boolean;
  verified_only?: boolean;
  global_only?: boolean;
  ending_within_days?: number;
  sort?: string;
  page?: number;
  page_size?: number;
}

export const api = {
  // ---------------------------------------------------------------- public
  home: (limit = 8) => apiServer<HomeBundle>(`/home${buildQuery({ limit })}`, { revalidate: 60 }),
  platformStats: () => apiServer<PlatformStats>("/platform/stats", { revalidate: 120 }),
  categories: () => apiServer<Category[]>("/categories", { revalidate: 600 }),
  category: (slug: string) => apiServer<Category>(`/categories/${slug}`, { revalidate: 600 }),
  categoryOffers: (slug: string, pageSize = 24) =>
    apiServer<OfferCard[]>(`/categories/${slug}/offers${buildQuery({ page_size: pageSize })}`, {
      revalidate: 60,
    }),
  brands: (params: Record<string, unknown> = {}) =>
    apiClient<unknown[]>("/brands", { params }),
  countries: () => apiClient<CountryBrief[]>("/countries"),
  currencies: () =>
    apiClient<{ base: string; currencies: { code: string; symbol: string; per_usd: number }[] }>(
      "/currencies",
    ),
  offerTypes: () => apiClient<OfferTypeMeta[]>("/offer-types"),
  interests: () => apiClient<InterestTag[]>("/interests"),

  offers: (params: OfferQuery = {}) =>
    apiServer<Page<OfferCard>>(`/offers${buildQuery(params as Record<string, unknown>)}`, {
      revalidate: 30,
    }),
  facets: (params: Record<string, unknown> = {}) =>
    apiClient<Facets>(`/offers/facets${buildQuery(params)}`),
  offer: (slug: string) => apiServer<OfferDetail>(`/offers/${slug}`, { revalidate: 60 }),
  offerVerification: (slug: string) =>
    apiClient<{ verification_status: string; last_checked_at?: string | null; history: unknown[] }>(
      `/offers/${slug}/verification`,
    ),
  expired: (page = 1, pageSize = 24) =>
    apiServer<Page<OfferCard>>(`/expired${buildQuery({ page, page_size: pageSize })}`, {
      revalidate: 300,
    }),
  collection: (name: string, limit = 12) =>
    apiServer<OfferCard[]>(`/collections/${name}${buildQuery({ limit })}`, { revalidate: 120 }),

  // ---------------------------------------------------------------- search
  search: (params: OfferQuery & { sort?: string }) =>
    apiClient<SearchResponse>(`/search${buildQuery(params as Record<string, unknown>)}`),
  suggest: (q: string, limit = 8) =>
    apiClient<SearchSuggestion[]>(`/search/suggest${buildQuery({ q, limit })}`),
  parseIntent: (q: string) => apiClient<ParsedIntent>(`/search/parse${buildQuery({ q })}`),
  trendingSearches: (limit = 12) => apiClient<{ query: string; searches: number; results: number }[]>(
    `/search/trending${buildQuery({ limit })}`,
  ),

  // ------------------------------------------------------------------ auth
  // No public accounts: browsing is open. These exist for the admin console.
  login: (payload: { email: string; password: string }) =>
    apiClient<{ access_token: string; user: User }>("/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  logout: () => apiClient<{ ok: boolean }>("/auth/logout", { method: "POST" }),
  me: () => apiClient<User>("/auth/me"),
  providers: () =>
    apiClient<{ providers: { id: string; label: string; enabled: boolean }[] }>("/auth/providers"),

  // --------------------------------------------------------------- account
  updateProfile: (payload: Record<string, unknown>) =>
    apiClient<User>("/me", { method: "PATCH", body: JSON.stringify(payload) }),
  changePassword: (payload: { current_password: string; new_password: string }) =>
    apiClient<{ detail: string }>("/me/password", { method: "POST", body: JSON.stringify(payload) }),
  bookmarks: (page = 1) => apiClient<Bookmark[]>(`/me/bookmarks${buildQuery({ page })}`),
  addBookmark: (offerId: string) =>
    apiClient<Bookmark>("/me/bookmarks", { method: "POST", body: JSON.stringify({ offer_id: offerId }) }),
  removeBookmark: (offerId: string) =>
    apiClient<void>(`/me/bookmarks/${offerId}`, { method: "DELETE" }),
  checkBookmarks: (offerIds: string[]) =>
    apiClient<{ bookmarked: string[] }>(`/me/bookmarks/check${buildQuery({ offer_ids: offerIds })}`),
  recent: (limit = 12) => apiClient<OfferCard[]>(`/me/recent${buildQuery({ limit })}`),
  clearRecent: () => apiClient<void>("/me/recent", { method: "DELETE" }),
  alerts: () => apiClient<Alert[]>("/me/alerts"),
  createAlert: (payload: Record<string, unknown>) =>
    apiClient<Alert>("/me/alerts", { method: "POST", body: JSON.stringify(payload) }),
  updateAlert: (id: string, payload: Record<string, unknown>) =>
    apiClient<Alert>(`/me/alerts/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteAlert: (id: string) => apiClient<void>(`/me/alerts/${id}`, { method: "DELETE" }),
  recommendations: (payload: Record<string, unknown>) =>
    apiClient<OfferCard[]>("/me/recommendations", { method: "POST", body: JSON.stringify(payload) }),

  // ---------------------------------------------------------- interaction
  trackEvent: (event: string, params: Record<string, unknown> = {}) =>
    apiClient<{ ok: boolean }>(`/events${buildQuery({ event, ...params })}`, { method: "POST" }),
  report: (payload: Record<string, unknown>) =>
    apiClient<{ detail: string }>("/reports", { method: "POST", body: JSON.stringify(payload) }),
  subscribeNewsletter: (payload: Record<string, unknown>) =>
    apiClient<{ ok: boolean; message: string; already_subscribed: boolean }>("/newsletter", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  submitOffer: (params: Record<string, unknown>) =>
    apiClient<{ detail: string }>(`/submit${buildQuery(params)}`, { method: "POST" }),

  // ----------------------------------------------------------------- admin
  adminStats: () => apiClient<DashboardStats>("/admin/stats"),
  adminAnalytics: (days = 30) => apiClient<AnalyticsOverview>(`/admin/analytics${buildQuery({ days })}`),
  adminOffers: (params: Record<string, unknown> = {}) =>
    apiClient<Page<import("./types").AdminOfferRow>>(`/admin/offers${buildQuery(params)}`),
  adminOffer: (id: string) => apiClient<OfferDetail>(`/admin/offers/${id}`),
  createOffer: (payload: Record<string, unknown>) =>
    apiClient<OfferDetail>("/admin/offers", { method: "POST", body: JSON.stringify(payload) }),
  updateOffer: (id: string, payload: Record<string, unknown>) =>
    apiClient<OfferDetail>(`/admin/offers/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  changeOfferStatus: (id: string, payload: Record<string, unknown>) =>
    apiClient<OfferDetail>(`/admin/offers/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  bulkOfferAction: (offerIds: string[], action: string, reason?: string) =>
    apiClient<{ ok: boolean; affected: number }>("/admin/offers/bulk", {
      method: "POST",
      body: JSON.stringify({ offer_ids: offerIds, action, reason }),
    }),
  deleteOffer: (id: string) => apiClient<void>(`/admin/offers/${id}`, { method: "DELETE" }),
  verifyOffer: (id: string) =>
    apiClient<VerificationSweepResult>(`/admin/offers/${id}/verify`, { method: "POST" }),
  verifySweep: (params: Record<string, unknown> = {}) =>
    apiClient<VerificationSweepResult>(`/admin/verify/sweep${buildQuery(params)}`, {
      method: "POST",
    }),
  duplicates: () =>
    apiClient<{
      primary: { id: string; slug: string; title: string; status: string; official_url: string };
      duplicate: { id: string; slug: string; title: string; status: string; official_url: string };
      similarity: number;
    }[]>("/admin/duplicates"),
  mergeDuplicates: (keepId: string, dropId: string) =>
    apiClient<{ ok: boolean; kept: string }>(`/admin/duplicates/merge${buildQuery({ keep_id: keepId, drop_id: dropId })}`, {
      method: "POST",
    }),

  adminSources: () => apiClient<Source[]>("/admin/sources"),
  runSource: (id: string) =>
    apiClient<Record<string, unknown>>(`/admin/sources/${id}/run`, { method: "POST" }),
  discoverSweep: (params: Record<string, unknown> = {}) =>
    apiClient<DiscoverySweepResult>(`/admin/discover/sweep${buildQuery(params)}`, { method: "POST" }),
  candidates: (params: Record<string, unknown> = {}) =>
    apiClient<Page<DiscoveryCandidate>>(`/admin/candidates${buildQuery(params)}`),
  decideCandidate: (id: string, action: string, reason?: string) =>
    apiClient<{ ok: boolean }>(`/admin/candidates/${id}/decision`, {
      method: "POST",
      body: JSON.stringify({ action, reason }),
    }),

  adminCategories: () => apiClient<Record<string, unknown>[]>("/admin/categories"),
  adminBrands: () => apiClient<Record<string, unknown>[]>("/admin/brands"),
  adminUsers: (q?: string) =>
    apiClient<import("./types").AdminUser[]>(`/admin/users${buildQuery({ q })}`),
  changeUserRole: (id: string, payload: Record<string, unknown>) =>
    apiClient<import("./types").AdminUser>(`/admin/users/${id}/role`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  adminReports: (status?: string) =>
    apiClient<Report[]>(`/admin/reports${buildQuery({ status_filter: status })}`),
  resolveReport: (id: string, payload: Record<string, unknown>) =>
    apiClient<Report>(`/admin/reports/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  adminSubmissions: (status?: string) =>
    apiClient<Submission[]>(`/admin/submissions${buildQuery({ status_filter: status })}`),
  jobs: () => apiClient<import("./types").ScheduledJob[]>("/admin/jobs"),
  runExpiry: () =>
    apiClient<{ ok: boolean; expired: number }>("/admin/maintenance/expiry", { method: "POST" }),
  runTrending: () =>
    apiClient<{ ok: boolean }>("/admin/maintenance/trending", { method: "POST" }),
  searchLog: (params: Record<string, unknown> = {}) =>
    apiClient<Record<string, unknown>[]>(`/admin/search-log${buildQuery(params)}`),
  health: () => apiClient<Record<string, unknown>>("/health"),
};

/** Outbound click URL - goes through the API so conversions are tracked. */
export function claimUrl(offer: Pick<OfferCard, "slug">, sessionId?: string): string {
  return `/api/v1/go/${offer.slug}${buildQuery({ sid: sessionId })}`;
}

export const SERVER_API_BASE = SERVER_BASE;