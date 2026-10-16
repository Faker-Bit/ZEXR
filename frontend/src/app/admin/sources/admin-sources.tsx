"use client";

import * as React from "react";
import { Play, Radio, ServerCog, ShieldAlert } from "lucide-react";
import { AdminShell, DataTable } from "@/components/admin/shell";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import type { DiscoverySweepResult, Source } from "@/lib/types";
import { cn, formatRelativeSafe } from "@/lib/utils";

const HEALTH_TONES: Record<string, string> = {
  healthy: "bg-success/15 text-success",
  degraded: "bg-warning/15 text-warning",
  failing: "bg-destructive/15 text-destructive",
  paused: "bg-muted text-muted-foreground",
};

export function AdminSources() {
  const { toast } = useToast();
  const [sources, setSources] = React.useState<Source[]>([]);
  const [running, setRunning] = React.useState<string | null>(null);
  const [sweepResult, setSweepResult] = React.useState<DiscoverySweepResult | null>(null);
  const [log, setLog] = React.useState<string[]>([]);

  const load = React.useCallback(async () => {
    try {
      setSources(await api.adminSources());
    } catch (error) {
      toast({ title: "Could not load sources", tone: "error", description: String(error) });
    }
  }, [toast]);

  React.useEffect(() => {
    void load();
  }, [load]);

  async function runSource(source: Source) {
    setRunning(source.id);
    setLog((current) => [`Running ${source.key}…`, ...current].slice(0, 8));
    try {
      const result = await api.runSource(source.id);
      setLog((current) => [`${source.key}: ${JSON.stringify(result)}`, ...current].slice(0, 8));
      toast({ title: `${source.name} run finished`, tone: "success" });
      await load();
    } catch (error) {
      setLog((current) => [`${source.key}: ERROR ${String(error)}`, ...current].slice(0, 8));
      toast({ title: "Source run failed", tone: "error", description: String(error) });
    } finally {
      setRunning(null);
    }
  }

  async function runSweep() {
    setRunning("sweep");
    try {
      const result = await api.discoverSweep({ max_sources: 10 });
      setSweepResult(result);
      setLog((current) => [`sweep: ${JSON.stringify(result)}`, ...current].slice(0, 8));
      toast({
        title: `Checked ${result.sources_checked} source(s)`,
        description: `${result.items_created} created, ${result.items_duplicate} duplicates, ${result.items_rejected} rejected`,
        tone: "success",
      });
      await load();
    } catch (error) {
      toast({ title: "Discovery sweep failed", tone: "error", description: String(error) });
    } finally {
      setRunning(null);
    }
  }

  return (
    <AdminShell
      title="Sources & discovery"
      description="Permitted upstreams, their crawl budgets, and the results of each run."
      actions={
        <Button size="sm" onClick={runSweep} disabled={running === "sweep"}>
          <Play className="size-3.5" />
          {running === "sweep" ? "Running…" : "Run discovery sweep"}
        </Button>
      }
    >
      {sweepResult ? (
        <div className="mb-4 grid gap-3 sm:grid-cols-5">
          {[
            { label: "Sources checked", value: sweepResult.sources_checked },
            { label: "Skipped", value: sweepResult.sources_skipped },
            { label: "Items seen", value: sweepResult.items_seen },
            { label: "Created", value: sweepResult.items_created },
            { label: "Rejected", value: sweepResult.items_rejected },
          ].map((item) => (
            <div key={item.label} className="rounded-lg border border-border bg-card/50 p-3">
              <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{item.label}</p>
              <p className="mt-1 text-xl font-semibold tabular-nums">{item.value}</p>
            </div>
          ))}
        </div>
      ) : null}

      <DataTable<Source>
        columns={[
          {
            key: "name",
            label: "Source",
            render: (row) => (
              <div className="min-w-0">
                <p className="font-medium">{row.name}</p>
                <p className="truncate text-xs text-muted-foreground">
                  {row.key} · {row.publisher} · {row.source_type}
                  {row.adapter ? ` / ${row.adapter}` : ""}
                </p>
              </div>
            ),
          },
          {
            key: "policy",
            label: "Crawl policy",
            className: "whitespace-nowrap text-xs",
            render: (row) => (
              <div className="space-y-0.5">
                <p>
                  {row.rate_limit_per_hour}/h · min {row.min_request_interval_seconds}s apart
                </p>
                <p className="text-muted-foreground">
                  robots: {row.respect_robots ? "respected" : "ignored"}
                </p>
                {row.requires_js ? (
                  <p className="text-warning">requires JS — never fetched</p>
                ) : null}
                {row.is_paywalled ? (
                  <p className="text-warning">behind login/paywall — never fetched</p>
                ) : null}
              </div>
            ),
          },
          {
            key: "health",
            label: "Health",
            className: "whitespace-nowrap",
            render: (row) => (
              <div className="space-y-1">
                <span
                  className={cn(
                    "inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase",
                    HEALTH_TONES[row.health] ?? "bg-muted text-muted-foreground",
                  )}
                >
                  {row.health}
                </span>
                <p className="text-[11px] text-muted-foreground">
                  {formatRelativeSafe(row.last_success_at)}
                </p>
                {!row.is_active ? (
                  <p className="text-[11px] text-muted-foreground">inactive</p>
                ) : null}
              </div>
            ),
          },
          {
            key: "stats",
            label: "Totals",
            className: "whitespace-nowrap text-xs tabular-nums text-muted-foreground",
            render: (row) => (
              <div>
                <p>seen {row.total_items_seen}</p>
                <p>accepted {row.total_items_accepted}</p>
                <p>dupes {row.total_items_duplicate}</p>
                <p>rejected {row.total_items_rejected}</p>
              </div>
            ),
          },
          {
            key: "actions",
            label: "",
            className: "whitespace-nowrap",
            render: (row) => (
              <Button
                size="xs"
                variant="outline"
                disabled={running === row.id || !row.is_active}
                onClick={() => runSource(row)}
              >
                <Radio className="size-3" />
                Run
              </Button>
            ),
          },
        ]}
        rows={sources}
        empty="No sources configured."
      />

      {log.length ? (
        <section className="mt-6">
          <h2 className="mb-2 text-sm font-semibold">Run log</h2>
          <pre className="max-h-64 overflow-auto rounded-lg border border-border bg-muted/40 p-3 font-mono text-[11px] leading-relaxed text-muted-foreground">
            {log.join("\n")}
          </pre>
        </section>
      ) : null}

      <div className="mt-6 flex items-start gap-2 rounded-lg border border-border bg-card/50 p-3">
        <ShieldAlert className="mt-0.5 size-4 shrink-0 text-primary" />
        <p className="text-xs leading-relaxed text-muted-foreground">
          Adding a source never requires a code change: the adapter and field mapping live in the
          source&rsquo;s JSON config. Sources that need JavaScript or a login are flagged and skipped
          — the platform will not work around access controls.
        </p>
      </div>

      <p className="mt-4 flex items-center gap-1.5 text-xs text-muted-foreground">
        <ServerCog className="size-3" />
        API keys are read from the environment variable named in <code>api_key_env</code>, never
        stored in the database.
      </p>
    </AdminShell>
  );
}