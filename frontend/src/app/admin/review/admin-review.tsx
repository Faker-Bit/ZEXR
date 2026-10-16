"use client";

import * as React from "react";
import Link from "next/link";
import { Check, ExternalLink, Inbox, X } from "lucide-react";
import { AdminShell, DataTable } from "@/components/admin/shell";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import type { DiscoveryCandidate, Page } from "@/lib/types";
import { cn, formatMoney, formatRelativeSafe } from "@/lib/utils";

const STATUS_FILTERS = ["pending", "accepted", "rejected", "duplicate"];

export function AdminReview() {
  const { toast } = useToast();
  const [status, setStatus] = React.useState("pending");
  const [page, setPage] = React.useState(1);
  const [result, setResult] = React.useState<Page<DiscoveryCandidate> | null>(null);
  const [loading, setLoading] = React.useState(true);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      setResult(await api.candidates({ status: status || undefined, page, page_size: 25 }));
    } catch (error) {
      toast({ title: "Could not load candidates", tone: "error", description: String(error) });
    } finally {
      setLoading(false);
    }
  }, [status, page, toast]);

  React.useEffect(() => {
    void load();
  }, [load]);

  async function decide(candidate: DiscoveryCandidate, action: string) {
    try {
      await api.decideCandidate(candidate.id, action);
      toast({
        title:
          action === "approve"
            ? "Offer created as pending_review"
            : action === "reject"
              ? "Candidate rejected"
              : "Marked as duplicate",
        tone: "success",
      });
      await load();
    } catch (error) {
      toast({ title: "Decision failed", tone: "error", description: String(error) });
    }
  }

  return (
    <AdminShell
      title="Review queue"
      description="Raw items found by discovery. Nothing is published until a reviewer approves it."
      actions={
        <div className="flex gap-1">
          {STATUS_FILTERS.map((value) => (
            <Button
              key={value}
              size="xs"
              variant={status === value ? "default" : "outline"}
              onClick={() => {
                setStatus(value);
                setPage(1);
              }}
            >
              {value}
            </Button>
          ))}
        </div>
      }
    >
      <DataTable<DiscoveryCandidate>
        columns={[
          {
            key: "title",
            label: "Discovered item",
            render: (row) => (
              <div className="min-w-0">
                <a
                  href={row.source_url}
                  target="_blank"
                  rel="noopener noreferrer nofollow"
                  className="inline-flex items-center gap-1 font-medium hover:text-primary"
                >
                  {row.raw_title}
                  <ExternalLink className="size-3 text-muted-foreground" />
                </a>
                <p className="truncate text-xs text-muted-foreground">
                  {row.source_key ?? "unknown source"} · {row.source_url}
                </p>
              </div>
            ),
          },
          {
            key: "parsed",
            label: "Parsed",
            className: "whitespace-nowrap text-xs",
            render: (row) => {
              const parsed = row.parsed ?? {};
              return (
                <div className="space-y-0.5">
                  <span className="inline-flex rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium">
                    {parsed.offer_type ?? row.status}
                  </span>
                  {parsed.promo_price !== undefined && parsed.promo_price !== null ? (
                    <span className="block tabular-nums text-muted-foreground">
                      {formatMoney(parsed.promo_price, parsed.currency ?? "USD")}
                      {parsed.original_price ? (
                        <span className="line-through"> {formatMoney(parsed.original_price, parsed.currency)}</span>
                      ) : null}
                    </span>
                  ) : (
                    <span className="block text-muted-foreground">no price</span>
                  )}
                  {parsed.trial_days ? (
                    <span className="block text-muted-foreground">{parsed.trial_days}d trial</span>
                  ) : null}
                  {(parsed.eligibility ?? []).length ? (
                    <span className="block text-muted-foreground">
                      {(parsed.eligibility ?? []).join(", ")}
                    </span>
                  ) : null}
                </div>
              );
            },
          },
          {
            key: "confidence",
            label: "Confidence",
            className: "whitespace-nowrap",
            render: (row) => (
              <div className="w-24">
                <div className="mb-1 flex items-center justify-between text-[11px] tabular-nums">
                  <span>{Math.round((row.confidence ?? 0) * 100)}%</span>
                </div>
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className={cn(
                      "h-full rounded-full",
                      row.confidence >= 0.75
                        ? "bg-success"
                        : row.confidence >= 0.55
                          ? "bg-warning"
                          : "bg-destructive",
                    )}
                    style={{ width: `${Math.round((row.confidence ?? 0) * 100)}%` }}
                  />
                </div>
              </div>
            ),
          },
          {
            key: "status",
            label: "Status",
            className: "whitespace-nowrap text-xs",
            render: (row) => (
              <div>
                <span
                  className={cn(
                    "inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase",
                    row.status === "accepted"
                      ? "bg-success/15 text-success"
                      : row.status === "rejected"
                        ? "bg-destructive/15 text-destructive"
                        : row.status === "duplicate"
                          ? "bg-muted text-muted-foreground"
                          : "bg-warning/15 text-warning",
                  )}
                >
                  {row.status}
                </span>
                {row.rejection_reason ? (
                  <p className="mt-1 max-w-[16rem] truncate text-[11px] text-muted-foreground">
                    {row.rejection_reason}
                  </p>
                ) : null}
              </div>
            ),
          },
          {
            key: "actions",
            label: "",
            className: "whitespace-nowrap",
            render: (row) =>
              row.status === "pending" ? (
                <div className="flex gap-1">
                  <Button size="xs" onClick={() => decide(row, "approve")}>
                    <Check className="size-3" /> Approve
                  </Button>
                  <Button size="xs" variant="outline" onClick={() => decide(row, "reject")}>
                    <X className="size-3" /> Reject
                  </Button>
                  <Button size="xs" variant="ghost" onClick={() => decide(row, "duplicate")}>
                    Dup
                  </Button>
                </div>
              ) : (
                <span className="text-[11px] text-muted-foreground">
                  {formatRelativeSafe(row.reviewed_at)}
                </span>
              ),
          },
        ]}
        rows={result?.items ?? []}
        empty={loading ? "Loading…" : "Queue is empty — run a discovery sweep from Sources."}
      />

      {result && result.pages > 1 ? (
        <nav className="mt-4 flex items-center justify-between text-sm">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => setPage((current) => current - 1)}
            className="rounded-lg border border-border px-3 py-1.5 disabled:opacity-40"
          >
            Previous
          </button>
          <span className="text-muted-foreground">
            Page {page} of {result.pages} · {result.total} candidates
          </span>
          <button
            type="button"
            disabled={page >= result.pages}
            onClick={() => setPage((current) => current + 1)}
            className="rounded-lg border border-border px-3 py-1.5 disabled:opacity-40"
          >
            Next
          </button>
        </nav>
      ) : null}

      <div className="mt-6 flex items-start gap-2 rounded-lg border border-border bg-card/50 p-3">
        <Inbox className="mt-0.5 size-4 shrink-0 text-primary" />
        <p className="text-xs leading-relaxed text-muted-foreground">
          Candidates below the confidence threshold are stored as rejected rather than published. That
          is intentional: low-confidence extraction is a data-quality problem, not something to hide.
          Approving a candidate creates a draft offer in{" "}
          <span className="font-medium text-foreground">pending_review</span> with verification
          status <span className="font-medium text-foreground">needs_manual</span>.
        </p>
      </div>

      <p className="mt-4 text-xs">
        <Link href="/admin/sources" className="text-primary hover:underline">
          Manage sources and run discovery →
        </Link>
      </p>
    </AdminShell>
  );
}