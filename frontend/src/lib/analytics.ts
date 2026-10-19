"use client";

/**
 * First-party page-view tracking.
 *
 * Design constraints, in order:
 *
 * 1. Never affect the page. Everything here is best-effort, runs after the page
 *    is interactive, and swallows its own errors. A tracker that can break a
 *    render is worse than no tracker.
 * 2. No fingerprinting. The only identifier is a random id in localStorage.
 *    No fingerprinting of IP, user agent, canvas or fonts is combined with it,
 *    so "unique visitors" means unique browser profiles, not unique people.
 *    This matches what the privacy page already promises.
 * 3. Cheap. One small request per navigation, sent with sendBeacon where
 *    available so it survives the page being unloaded.
 */

const SESSION_KEY = "zexr_sid";
const LAST_PATH_KEY = "zexr_last_path";
const BEACON_URL = "/api/v1/events";

/** Admin browsing is not a public page view and would inflate the number. */
function isExcluded(path: string): boolean {
  return (
    path.startsWith("/admin") ||
    path.startsWith("/login") ||
    path.startsWith("/_next") ||
    path.startsWith("/api")
  );
}

function readSessionId(): string | null {
  try {
    const existing = window.localStorage.getItem(SESSION_KEY);
    if (existing) return existing;
    // crypto.randomUUID needs a secure context; localhost qualifies, plain
    // http on a LAN host does not, hence the fallback.
    const id =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
    window.localStorage.setItem(SESSION_KEY, id);
    return id;
  } catch {
    // Private mode or storage disabled. Tracking is optional, so give up
    // quietly rather than reporting an error to the user.
    return null;
  }
}

/** Record one page view for `path`. Safe to call unconditionally. */
export function trackPageView(path: string): void {
  if (typeof window === "undefined") return;
  if (isExcluded(path)) return;

  // Suppress a repeat of the same path. App Router remounts on refresh and on
  // some navigations, and counting each one would double the figure.
  try {
    if (window.localStorage.getItem(LAST_PATH_KEY) === path) return;
    window.localStorage.setItem(LAST_PATH_KEY, path);
  } catch {
    /* storage unavailable; still record the view */
  }

  const sid = readSessionId();
  if (!sid) return;

  const query = new URLSearchParams({
    event: "page_view",
    path: path.slice(0, 500),
    sid,
  });
  const url = `${BEACON_URL}?${query.toString()}`;

  // sendBeacon is fire-and-forget and is not subject to the usual 6-connection
  // per-origin cap, which matters on a page that is also loading offers.
  try {
    if (navigator.sendBeacon) {
      navigator.sendBeacon(url);
      return;
    }
  } catch {
    /* fall through to fetch */
  }

  try {
    void fetch(url, {
      method: "POST",
      credentials: "include",
      keepalive: true,
      cache: "no-store",
    }).catch(() => undefined);
  } catch {
    /* never surface tracking failures */
  }
}