"use client";

import * as React from "react";
import { usePathname, useSearchParams } from "next/navigation";

import { trackPageView } from "@/lib/analytics";

/**
 * Fires a page view on every client-side navigation.
 *
 * Mounted once in the root layout and renders nothing. Tracking is deferred
 * until after the page is interactive so the request never competes with
 * loading content, and it is keyed on the pathname only - query strings are
 * excluded so sorting or paginating the same page is one view, not twenty.
 */
export function PageViewTracker() {
  const pathname = usePathname();
  const searchParams = useSearchParams();

  React.useEffect(() => {
    if (!pathname) return;
    // Defer past the current task so first paint is never waiting on this.
    const timer = window.setTimeout(() => trackPageView(pathname), 0);
    return () => window.clearTimeout(timer);
    // searchParams is read so a query-string-only change still re-evaluates,
    // but it is deliberately not part of the recorded path.
  }, [pathname, searchParams]);

  return null;
}