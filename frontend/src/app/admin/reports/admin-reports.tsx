"use client";

import * as React from "react";
import { Flag, Inbox } from "lucide-react";
import { AdminShell, DataTable } from "@/components/admin/shell";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import type { Report, Submission } from "@/lib/types";
import { cn, formatDateTime } from "@/lib/utils";

const STATUSES = ["open", "triaged", "resolved", "dismissed"];

export function AdminReports() {
  const { toast } = useToast();
  const [status, setStatus] = React.useState("open");
  const [reports, setReports] = React.useState<Report[]>([]);
  const [submissions, setSubmissions] = React.useState<Submission[]>([]);

  const load = React.useCallback(async () => {
    try {
      const [reportRows, submissionRows] = await Promise.all([
        api.adminReports(status || undefined),
        api.adminSubmissions("pending"),
      ]);
      setReports(reportRows);
      setSubmissions(submissionRows);
    } catch (error) {
      toast({ title: "Could not load reports", tone: "error", description: String(error) });
    }
  }, [status, toast]);

  React.useEffect(() => {
    void load();
  }, [load]);

  async function resolve(report: Report, next: string, markDisputed: boolean) {
    try {
      await api.resolveReport(report.id, {
        status: next,
        resolution_note: next === "dismissed" ? "Not an issue" : "Verified against the official page",
        mark_offer_disputed: markDisputed,
      });
      toast({ title: `Report ${next}`, tone: "success" });
      await load();
    } catch (error) {
      toast({ title: "Update failed", tone: "error", description: String(error) });
    }
  }

  return (
    <AdminShell
      title="Reports & submissions"
      description="Community flags and deal submissions awaiting review."
      actions={
        <div className="flex gap-1">
          {STATUSES.map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setStatus(value)}
              className={cn(
                "h-8 rounded-lg border px-3 text-xs capitalize transition-colors",
                status === value
                  ? "border-primary/50 bg-primary/15 text-primary"
                  : "border-border text-muted-foreground hover:text-foreground",
              )}
            >
              {value}
            </button>
          ))}
        </div>
      }
    >
      <DataTable<Report>
        columns={[
          {
            key: "offer",
            label: "Offer",
            render: (row) => (
              <div className="min-w-0">
                <p className="truncate font-medium">{row.offer_title ?? "Offer removed"}</p>
                <p className="text-xs text-muted-foreground">
                  {row.reporter_email ?? "anonymous"} · {formatDateTime(row.created_at)}
                </p>
              </div>
            ),
          },
          {
            key: "reason",
            label: "Reason",
            className: "whitespace-nowrap",
            render: (row) => (
              <span className="inline-flex rounded-full bg-warning/15 px-2 py-0.5 text-[10px] font-semibold uppercase text-warning">
                {row.reason.replace("_", " ")}
              </span>
            ),
          },
          {
            key: "details",
            label: "Details",
            render: (row) => (
              <p className="max-w-sm truncate text-xs text-muted-foreground">
                {row.details ?? "—"}
              </p>
            ),
          },
          {
            key: "actions",
            label: "",
            className: "whitespace-nowrap",
            render: (row) =>
              row.status === "open" || row.status === "triaged" ? (
                <div className="flex gap-1">
                  <Button size="xs" onClick={() => resolve(row, "resolved", true)}>
                    Resolve + dispute
                  </Button>
                  <Button size="xs" variant="outline" onClick={() => resolve(row, "dismissed", false)}>
                    Dismiss
                  </Button>
                </div>
              ) : (
                <span className="text-[11px] capitalize text-muted-foreground">{row.status}</span>
              ),
          },
        ]}
        rows={reports}
        empty="No reports in this state."
      />

      <section className="mt-8">
        <h2 className="mb-3 flex items-center gap-1.5 text-sm font-semibold">
          <Inbox className="size-4 text-primary" />
          Pending submissions ({submissions.length})
        </h2>
        <DataTable<Submission>
          columns={[
            {
              key: "title",
              label: "Submission",
              render: (row) => (
                <div className="min-w-0">
                  <p className="truncate font-medium">{row.title}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {row.brand_name ?? "unknown brand"} · {row.submitter_email ?? "anonymous"}
                  </p>
                </div>
              ),
            },
            {
              key: "url",
              label: "Official page",
              render: (row) => (
                <a
                  href={row.official_url}
                  target="_blank"
                  rel="noopener noreferrer nofollow"
                  className="text-xs text-primary hover:underline"
                >
                  {row.official_url}
                </a>
              ),
            },
            {
              key: "notes",
              label: "Notes",
              render: (row) => (
                <p className="max-w-xs truncate text-xs text-muted-foreground">{row.notes ?? "—"}</p>
              ),
            },
          ]}
          rows={submissions}
          empty="No pending submissions."
        />
      </section>

      <p className="mt-6 flex items-center gap-1.5 text-xs text-muted-foreground">
        <Flag className="size-3" />
        Resolving with &ldquo;dispute&rdquo; removes the offer from all public listings immediately.
      </p>
    </AdminShell>
  );
}