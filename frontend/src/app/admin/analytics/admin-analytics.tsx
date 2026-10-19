"use client";

import * as React from "react";
import { BarChart3, Eye, TrendingUp, Users, Zap } from "lucide-react";
import { api } from "@/lib/api";
import { AdminShell } from "@/components/admin/shell";
import type { AnalyticsOverview, TopRow, TrendPoint } from "@/lib/types";

const RANGES = [7, 30, 90];

export function AdminAnalytics() {
  const [days, setDays] = React.useState(30);
  const [data, setData] = React.useState<AnalyticsOverview | null>(null);

  React.useEffect(() => {
    api.adminAnalytics(days).then(setData).catch(() => undefined);
  }, [days]);

  const totals = (series: TrendPoint[]) => series.reduce((sum, point) => sum + point.value, 0);

  return (
    <AdminShell
      title="Analytics"
      description="Traffic, conversion and verification quality."
      actions={
        <div className="flex gap-1">
          {RANGES.map((range) => (
            <button
              key={range}
              type="button"
              onClick={() => setDays(range)}
              className={`h-8 rounded-lg border px-3 text-xs transition-colors ${
                days === range
                  ? "border-primary/50 bg-primary/15 text-primary"
                  : "border-border text-muted-foreground hover:text-foreground"
              }`}
            >
              {range}d
            </button>
          ))}
        </div>
      }
    >
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric
          label="Page views"
          value={data ? data.page_view_total : null}
          hint="all time"
          icon={Eye}
        />
        <Metric
          label="Unique visitors"
          value={data ? data.unique_visitors_total : null}
          hint="distinct sessions"
          icon={Users}
        />
        <Metric label="Clicks" value={data ? totals(data.clicks) : null} />
        <Metric label="Offer views" value={data ? totals(data.views) : null} />
        <Metric label="Searches" value={data ? totals(data.searches) : null} />
        <Metric label="Signups" value={data ? totals(data.signups) : null} />
      </div>

      {data ? (
        <>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <Metric
              label="Click-through rate"
              value={`${(data.conversion_rate * 100).toFixed(1)}%`}
              hint="clicks ÷ views"
              icon={TrendingUp}
            />
            <Metric
              label="Clicks on verified offers"
              value={`${(data.click_to_verify_rate * 100).toFixed(1)}%`}
              icon={Zap}
            />
            <Metric
              label="Verification success"
              value={`${(data.verification_success_rate * 100).toFixed(1)}%`}
              icon={BarChart3}
            />
          </div>

          <div className="mt-6 grid gap-4 lg:grid-cols-2">
            <Chart title="Page views per day" series={data.page_views} />
            <Chart title="Unique visitors per day" series={data.unique_visitors} />
            <Chart title="Clicks per day" series={data.clicks} />
            <Chart title="Searches per day" series={data.searches} />
            <Chart title="Offer views per day" series={data.views} />
            <Chart title="New accounts per day" series={data.signups} />
          </div>

          <div className="mt-6 grid gap-4 lg:grid-cols-2">
            <Ranked
              title="Most visited pages"
              rows={data.top_paths}
              format={(row) => `${row.value}×`}
            />
            <Ranked title="Top categories" rows={data.top_categories} />
            <Ranked title="Top offers by clicks" rows={data.top_offers} />
            <Ranked
              title="Top searches"
              rows={data.top_searches}
              format={(row) => `${row.value}× · ${row.extra?.total_results ?? 0} results`}
            />
            <Ranked
              title="Zero-result searches"
              rows={data.zero_result_searches}
              format={(row) => `${row.value}×`}
            />
            <Ranked title="Top countries" rows={data.top_countries} />
          </div>
        </>
      ) : (
        <p className="py-16 text-center text-sm text-muted-foreground">Loading analytics…</p>
      )}
    </AdminShell>
  );
}

function Metric({
  label,
  value,
  hint,
  icon: Icon,
}: {
  label: string;
  value: number | string | null;
  hint?: string;
  icon?: React.ElementType;
}) {
  return (
    <div className="rounded-xl border border-border bg-card/60 p-4">
      <p className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {Icon ? <Icon className="size-3" /> : null}
        {label}
      </p>
      <p className="mt-1.5 text-2xl font-semibold tabular-nums">
        {value === null ? "—" : typeof value === "number" ? value.toLocaleString() : value}
      </p>
      {hint ? <p className="mt-1 text-[11px] text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

function Chart({ title, series }: { title: string; series: TrendPoint[] }) {
  const max = Math.max(1, ...series.map((point) => point.value));
  return (
    <div className="rounded-xl border border-border bg-card/50 p-4">
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </h3>
      <div className="flex h-28 items-end gap-[3px]">
        {series.map((point) => (
          <div
            key={point.day}
            title={`${point.day}: ${point.value}`}
            className="flex-1 rounded-t bg-primary/70 transition-colors hover:bg-primary"
            style={{ height: `${Math.max(2, (point.value / max) * 100)}%` }}
          />
        ))}
      </div>
    </div>
  );
}

function Ranked({
  title,
  rows,
  format,
}: {
  title: string;
  rows: TopRow[];
  format?: (row: TopRow) => string;
}) {
  return (
    <div className="rounded-xl border border-border bg-card/50 p-4">
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </h3>
      <ul className="space-y-1.5">
        {rows.slice(0, 8).map((row, index) => (
          <li key={`${row.label}-${index}`} className="flex items-center justify-between gap-3 text-sm">
            <span className="min-w-0 truncate">{row.label}</span>
            <span className="shrink-0 tabular-nums text-muted-foreground">
              {format ? format(row) : row.value.toLocaleString()}
            </span>
          </li>
        ))}
        {!rows.length ? <li className="text-sm text-muted-foreground">No data yet.</li> : null}
      </ul>
    </div>
  );
}
