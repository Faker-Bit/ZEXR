"use client";

import * as React from "react";

import { apiClient } from "@/lib/api";

interface TodayStats {
  page_views_today: number;
  visitors_today: number;
}

/**
 * Live visitor counter for the header.
 *
 * Fetches once on mount and then refreshes on an interval. Renders nothing at
 * all until it has data, so it never causes a layout shift on first paint, and
 * a failure just hides it - a broken counter must not break the header.
 */
export function VisitorCounter({ className }: { className?: string }) {
  const [stats, setStats] = React.useState<TodayStats | null>(null);

  React.useEffect(() => {
    let cancelled = false;

    const load = () => {
      // CLIENT_BASE already carries the /api/v1 prefix, and the interactions
      // router is mounted without a further prefix, so this resolves to
      // /api/v1/stats/today.
      apiClient<TodayStats>("/stats/today")
        .then((data) => {
          if (!cancelled && data) setStats(data);
        })
        .catch(() => undefined);
    };

    load();
    // Every 60s: high enough to feel live, low enough to stay quiet.
    const timer = window.setInterval(load, 60_000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  if (!stats) return null;

  return (
    <span
      className={
        "hidden items-center gap-1.5 rounded-full border border-border px-2.5 py-1 text-[11px] font-medium text-muted-foreground md:inline-flex " +
        (className ?? "")
      }
      title={`${stats.page_views_today} page views today`}
    >
      <span className="relative flex size-1.5">
        <span className="absolute inline-flex size-full animate-ping rounded-full bg-primary opacity-70" />
        <span className="relative inline-flex size-1.5 rounded-full bg-primary" />
      </span>
      {stats.visitors_today} online today
    </span>
  );
}