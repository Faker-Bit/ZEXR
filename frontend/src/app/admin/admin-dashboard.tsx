"use client";

import * as React from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowUpRight,
  Boxes,
  Clock,
  Play,
  RefreshCw,
  ServerCog,
  ShieldCheck,
  Users,
} from "lucide-react";
import { AdminShell, StatCard } from "@/components/admin/shell";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import type { DashboardStats, ScheduledJob } from "@/lib/types";
import { formatDateTime, formatRelativeSafe } from "@/lib/utils";

export function AdminOverview() {
  const { toast } = useToast();
  const [stats, setStats] = React.useState<DashboardStats | null>(null);
  const [jobs, setJobs] = React.useState<ScheduledJob[]>([]);
  const [busy, setBusy] = React.useState<string | null>(null);
  const [sweep, setSweep] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    try {
      const [statsResult, jobsResult] = await Promise.all([api.adminStats(), api.jobs()]);
      setStats(statsResult);
      setJobs(jobsResult);
    } catch (error) {
      toast({ title: "Could not load dashboard", tone: "error", description: String(error) });
    }
  }, [toast]);

  React.useEffect(() => {
    void load();
  }, [load]);

  async function run(name: string, fn: () => Promise<unknown>, label: string) {
    setBusy(name);
    try {
      const result = (await fn()) as Record<string, unknown>;
      setSweep(`${label}: ${JSON.stringify(result)}`);
      toast({ title: `${label} finished`, tone: "success" });
      await load();
    } catch (error) {
      toast({ title: `${label} failed`, tone: "error", description: String(error) });
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <AdminShell
        title="Overview"
        description="Catalogue health, verification queue and background jobs."
        actions={
          <>
            <Button variant="outline" size="sm" onClick={() => void load()}>
              <RefreshCw className="size-3.5" />
              Refresh
            </Button>
            <Button
              size="sm"
              disabled={busy === "verify"}
              onClick={() => run("verify", () => api.verifySweep({ limit: 25 }), "Verification sweep")}
            >
              <ShieldCheck className="size-3.5" />
              Run verification
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={busy === "discover"}
              onClick={() => run("discover", () => api.discoverSweep({ max_sources: 5 }), "Discovery sweep")}
            >
              <ServerCog className="size-3.5" />
              Run discovery
            </Button>
          </>
        }
      >
        {sweep ? (
          <p className="mb-4 truncate rounded-lg border border-border bg-muted/40 px-3 py-2 font-mono text-[11px] text-muted-foreground">
            {sweep}
          </p>
        ) : null}

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Live offers" value={stats?.live_offers ?? "—"} hint={`${stats?.total_offers ?? 0} total rows`} />
          <StatCard
            label="Verified"
            value={stats?.verified_offers ?? "—"}
            tone="good"
            hint="Reached the official page"
          />
          <StatCard
            label="Pending review"
            value={stats?.pending_review ?? "—"}
            tone={stats?.pending_review ? "warn" : "default"}
            hint="Discovered but unpublished"
          />
          <StatCard
            label="Disputed"
            value={stats?.disputed_offers ?? "—"}
            tone={stats?.disputed_offers ? "bad" : "default"}
            hint="Held out of live results"
          />
          <StatCard label="Expired" value={stats?.expired_offers ?? "—"} />
          <StatCard label="Demo records" value={stats?.demo_offers ?? "—"} hint="Flagged, never verified" />
          <StatCard
            label="Sources"
            value={`${stats?.active_sources ?? 0}/${stats?.total_sources ?? 0}`}
            tone={stats?.failing_sources ? "bad" : "default"}
            hint={`${stats?.failing_sources ?? 0} failing`}
          />
          <StatCard
            label="Open reports"
            value={stats?.open_reports ?? "—"}
            tone={stats?.open_reports ? "warn" : "default"}
            hint="Community flags"
          />
          <StatCard label="Users" value={stats?.total_users ?? "—"} hint={`${stats?.new_users_7d ?? 0} new this week`} />
          <StatCard label="Clicks (7d)" value={stats?.clicks_7d ?? "—"} />
          <StatCard label="Searches (7d)" value={stats?.searches_7d ?? "—"} />
          <StatCard label="Newsletter" value={stats?.newsletter_subs ?? "—"} />
        </div>

        {stats ? (
          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            <QuickLink
              href="/admin/review"
              icon={AlertTriangle}
              label="Review queue"
              value={`${stats.pending_candidates} candidates`}
            />
            <QuickLink
              href="/admin/offers"
              icon={Boxes}
              label="Offers"
              value={`${stats.total_offers} rows`}
            />
            <QuickLink
              href="/admin/users"
              icon={Users}
              label="Users"
              value={`${stats.total_users} accounts`}
            />
          </div>
        ) : null}

        <section className="mt-8">
          <h2 className="mb-3 text-sm font-semibold">Scheduled jobs</h2>
          <div className="grid gap-2 sm:grid-cols-2">
            {jobs.map((job) => (
              <div key={job.name} className="rounded-xl border border-border bg-card/50 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium capitalize">{job.name}</p>
                    <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
                      {job.description}
                    </p>
                  </div>
                  <span
                    className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ${
                      job.enabled ? "bg-success/15 text-success" : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {job.enabled ? job.schedule : "disabled"}
                  </span>
                </div>
                <p className="mt-2 flex items-center gap-1 text-[11px] text-muted-foreground">
                  <Clock className="size-3" />
                  Last run {formatRelativeSafe(job.last_run_at)}
                </p>
              </div>
            ))}
          </div>
        </section>

        <section className="mt-8 flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={busy === "expiry"}
            onClick={() => run("expiry", () => api.runExpiry(), "Expire finished offers")}
          >
            Expire finished offers
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={busy === "trending"}
            onClick={() => run("trending", () => api.runTrending(), "Recompute trending")}
          >
            <Play className="size-3.5" />
            Recompute trending
          </Button>
          {stats ? (
            <p className="self-center text-xs text-muted-foreground">
              Snapshot generated {formatDateTime(stats.generated_at)}
            </p>
          ) : null}
        </section>
      </AdminShell>
    </>
  );
}

function QuickLink({
  href,
  icon: Icon,
  label,
  value,
}: {
  href: string;
  icon: React.ElementType;
  label: string;
  value: string;
}) {
  return (
    <Link
      href={href}
      className="group flex items-center justify-between gap-2 rounded-xl border border-border bg-card/50 p-4 transition-colors hover:border-primary/40 hover:bg-accent/30"
    >
      <div className="flex items-center gap-2.5">
        <Icon className="size-4 text-primary" />
        <div>
          <p className="text-sm font-medium">{label}</p>
          <p className="text-xs text-muted-foreground">{value}</p>
        </div>
      </div>
      <ArrowUpRight className="size-4 text-muted-foreground transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
    </Link>
  );
}