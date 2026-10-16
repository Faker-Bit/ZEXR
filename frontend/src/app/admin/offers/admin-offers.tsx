"use client";

import * as React from "react";
import Link from "next/link";
import {
  Check,
  Copy,
  Eye,
  Search,
  ShieldCheck,
  Star,
  Trash2,
  TriangleAlert,
  X,
} from "lucide-react";
import { AdminShell, DataTable } from "@/components/admin/shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import type { AdminOfferRow, OfferCard } from "@/lib/types";
import { cn, formatDateTime, formatMoney, formatRelativeSafe } from "@/lib/utils";

const STATUS_TONES: Record<string, string> = {
  published: "bg-success/15 text-success",
  pending_review: "bg-warning/15 text-warning",
  disputed: "bg-destructive/15 text-destructive",
  expired: "bg-muted text-muted-foreground",
  draft: "bg-muted text-muted-foreground",
  rejected: "bg-muted text-muted-foreground",
  archived: "bg-muted text-muted-foreground",
};

export function AdminOffers() {
  const { toast } = useToast();
  const [rows, setRows] = React.useState<OfferCard[] | AdminOfferRow[]>([]);
  const [total, setTotal] = React.useState(0);
  const [page, setPage] = React.useState(1);
  const [status, setStatus] = React.useState("");
  const [query, setQuery] = React.useState("");
  const [selected, setSelected] = React.useState<string[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [duplicates, setDuplicates] = React.useState<
    { primary: { id: string; title: string; slug: string }; duplicate: { id: string; title: string; slug: string }; similarity: number }[]
  >([]);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const result = await api.adminOffers({
        page,
        page_size: 25,
        status: status || undefined,
        q: query || undefined,
      });
      setRows(result.items);
      setTotal(result.total);
    } catch (error) {
      toast({ title: "Could not load offers", tone: "error", description: String(error) });
    } finally {
      setLoading(false);
    }
  }, [page, status, query, toast]);

  React.useEffect(() => {
    void load();
  }, [load]);

  React.useEffect(() => {
    api.duplicates().then(setDuplicates).catch(() => undefined);
  }, []);

  async function bulk(action: string) {
    if (!selected.length) return;
    try {
      const result = await api.bulkOfferAction(selected, action);
      toast({ title: `${result.affected} offers updated`, tone: "success" });
      setSelected([]);
      await load();
    } catch (error) {
      toast({ title: "Bulk action failed", tone: "error", description: String(error) });
    }
  }

  async function setOfferStatus(id: string, next: string) {
    try {
      await api.changeOfferStatus(id, { status: next });
      toast({ title: `Offer ${next.replace("_", " ")}`, tone: "success" });
      await load();
    } catch (error) {
      toast({ title: "Update failed", tone: "error", description: String(error) });
    }
  }

  async function verifyOne(id: string) {
    try {
      const result = await api.verifyOffer(id);
      toast({
        title: `Checked ${result.checked} offer(s)`,
        description: `ok: ${result.ok}, changed: ${result.changed}, broken: ${result.broken}, skipped: ${result.skipped}`,
        tone: "success",
      });
      await load();
    } catch (error) {
      toast({ title: "Verification failed", tone: "error", description: String(error) });
    }
  }

  async function merge(keepId: string, dropId: string) {
    try {
      await api.mergeDuplicates(keepId, dropId);
      toast({ title: "Merged", tone: "success" });
      setDuplicates(await api.duplicates());
      await load();
    } catch (error) {
      toast({ title: "Merge failed", tone: "error", description: String(error) });
    }
  }

  return (
    <AdminShell
      title="Offers"
      description={`${total} records. Bulk moderate, verify individually and merge duplicates.`}
      actions={
        <>
          <Button variant="outline" size="sm" onClick={() => void load()}>
            Refresh
          </Button>
          <Button asChild size="sm">
            <Link href="/admin/offers/new">New offer</Link>
          </Button>
        </>
      }
    >
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative min-w-[220px] flex-1">
          <Search className="absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(1);
            }}
            placeholder="Search title or description…"
            className="pl-9"
          />
        </div>
        <select
          value={status}
          onChange={(event) => {
            setStatus(event.target.value);
            setPage(1);
          }}
          className="h-10 rounded-lg border border-input bg-background px-3 text-sm"
        >
          <option value="">All statuses</option>
          {["published", "pending_review", "disputed", "expired", "draft", "rejected", "archived"].map(
            (value) => (
              <option key={value} value={value}>
                {value.replace("_", " ")}
              </option>
            ),
          )}
        </select>
      </div>

      {selected.length ? (
        <div className="mb-3 flex flex-wrap items-center gap-2 rounded-lg border border-primary/30 bg-primary/10 px-3 py-2">
          <span className="text-xs font-medium text-primary">{selected.length} selected</span>
          <Button size="xs" variant="outline" onClick={() => bulk("publish")}>
            <Check className="size-3" /> Publish
          </Button>
          <Button size="xs" variant="outline" onClick={() => bulk("feature")}>
            <Star className="size-3" /> Feature
          </Button>
          <Button size="xs" variant="outline" onClick={() => bulk("verify")}>
            <ShieldCheck className="size-3" /> Mark verified
          </Button>
          <Button size="xs" variant="outline" onClick={() => bulk("expire")}>
            Expire
          </Button>
          <Button size="xs" variant="outline" onClick={() => bulk("archive")}>
            Archive
          </Button>
          <Button size="xs" variant="outline" onClick={() => setSelected([])}>
            <X className="size-3" /> Clear
          </Button>
        </div>
      ) : null}

      <DataTable<AdminOfferRow>
        columns={[
          {
            key: "select",
            label: "",
            className: "w-8",
            render: (row) => (
              <input
                type="checkbox"
                checked={selected.includes(row.id)}
                onChange={(event) =>
                  setSelected((current) =>
                    event.target.checked
                      ? [...current, row.id]
                      : current.filter((id) => id !== row.id),
                  )
                }
                className="size-3.5 accent-lime-500"
              />
            ),
          },
          {
            key: "title",
            label: "Offer",
            render: (row) => (
              <div className="min-w-0">
                <Link
                  href={`/offers/${row.slug}`}
                  target="_blank"
                  className="font-medium hover:text-primary"
                >
                  {row.title}
                </Link>
                <p className="truncate text-xs text-muted-foreground">
                  {row.brand?.name ?? "—"} · {row.category.name} · {row.offer_type}
                </p>
              </div>
            ),
          },
          {
            key: "price",
            label: "Price",
            className: "whitespace-nowrap",
            render: (row) => (
              <span className="tabular-nums">
                {formatMoney(row.promo_price, row.currency)} /{" "}
                <span className="text-muted-foreground line-through">
                  {formatMoney(row.original_price, row.currency)}
                </span>
              </span>
            ),
          },
          {
            key: "status",
            label: "Status",
            className: "whitespace-nowrap",
            render: (row) => (
              <div className="space-y-1">
                <span
                  className={cn(
                    "inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase",
                    STATUS_TONES[row.status] ?? "bg-muted text-muted-foreground",
                  )}
                >
                  {row.status.replace("_", " ")}
                </span>
                {row.is_demo_data ? (
                  <span className="block text-[10px] text-warning">demo</span>
                ) : null}
                {row.verification_status !== "verified" ? (
                  <span className="block text-[10px] text-muted-foreground">
                    {row.verification_status}
                  </span>
                ) : null}
              </div>
            ),
          },
          {
            key: "checked",
            label: "Last checked",
            className: "whitespace-nowrap text-xs text-muted-foreground",
            render: (row) => (
              <>
                {formatRelativeSafe(row.last_checked_at)}
                {row.consecutive_failures > 0 ? (
                  <span className="block text-[10px] text-destructive">
                    {row.consecutive_failures} failures
                  </span>
                ) : null}
              </>
            ),
          },
          {
            key: "actions",
            label: "Actions",
            className: "whitespace-nowrap",
            render: (row) => (
              <div className="flex items-center gap-1">
                <Button size="xs" variant="ghost" onClick={() => verifyOne(row.id)} title="Verify now">
                  <ShieldCheck className="size-3" />
                </Button>
                {row.status !== "published" ? (
                  <Button size="xs" variant="ghost" onClick={() => setOfferStatus(row.id, "published")}>
                    Publish
                  </Button>
                ) : (
                  <Button size="xs" variant="ghost" onClick={() => setOfferStatus(row.id, "disputed")}>
                    Dispute
                  </Button>
                )}
                <Button
                  size="xs"
                  variant="ghost"
                  onClick={async () => {
                    if (!window.confirm("Delete this offer permanently?")) return;
                    await api.deleteOffer(row.id);
                    await load();
                  }}
                  className="text-destructive"
                  title="Delete"
                >
                  <Trash2 className="size-3" />
                </Button>
              </div>
            ),
          },
        ]}
        rows={rows as AdminOfferRow[]}
        empty={loading ? "Loading…" : "No offers match those filters."}
      />

      {total > 25 ? (
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
            Page {page} of {Math.ceil(total / 25)}
          </span>
          <button
            type="button"
            disabled={page * 25 >= total}
            onClick={() => setPage((current) => current + 1)}
            className="rounded-lg border border-border px-3 py-1.5 disabled:opacity-40"
          >
            Next
          </button>
        </nav>
      ) : null}

      {duplicates.length ? (
        <section className="mt-10">
          <h2 className="mb-3 flex items-center gap-1.5 text-sm font-semibold">
            <Copy className="size-4 text-warning" />
            Possible duplicates
          </h2>
          <div className="space-y-2">
            {duplicates.map((pair) => (
              <div
                key={`${pair.primary.id}-${pair.duplicate.id}`}
                className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-card/50 px-3 py-2.5"
              >
                <div className="min-w-0 text-sm">
                  <p className="truncate font-medium">{pair.primary.title}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    ≈ {pair.duplicate.title} · {Math.round(pair.similarity * 100)}% similar
                  </p>
                </div>
                <div className="flex gap-1.5">
                  <Button size="xs" variant="outline" onClick={() => merge(pair.primary.id, pair.duplicate.id)}>
                    <Copy className="size-3" /> Merge
                  </Button>
                  <Button size="xs" variant="ghost" asChild>
                    <Link href={`/offers/${pair.duplicate.slug}`} target="_blank">
                      <Eye className="size-3" />
                    </Link>
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {rows.some((row) => row.status === "disputed") ? (
        <p className="mt-6 flex items-center gap-1.5 text-xs text-muted-foreground">
          <TriangleAlert className="size-3" />
          Disputed offers are excluded from all public listings until resolved.
        </p>
      ) : null}

      <p className="mt-6 text-xs text-muted-foreground">
        Last refreshed {formatDateTime(new Date().toISOString())}.
      </p>
    </AdminShell>
  );
}