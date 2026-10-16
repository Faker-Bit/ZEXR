"use client";

import * as React from "react";
import { AdminShell, DataTable } from "@/components/admin/shell";
import { api } from "@/lib/api";
import type { AdminUser } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/lib/utils";
import { useToast } from "@/components/ui/toast";

type Row = Record<string, unknown>;

export function AdminTaxonomy() {
  const { toast } = useToast();
  const [tab, setTab] = React.useState<"categories" | "brands">("categories");
  const [rows, setRows] = React.useState<Row[]>([]);

  React.useEffect(() => {
    async function load() {
      try {
        setRows(tab === "categories" ? await api.adminCategories() : await api.adminBrands());
      } catch (error) {
        toast({ title: "Could not load taxonomy", tone: "error", description: String(error) });
      }
    }
    void load();
  }, [tab, toast]);

  return (
    <AdminShell
      title="Categories & brands"
      description="The taxonomy that drives navigation, search matching and facets."
      actions={
        <div className="flex gap-1">
          {(["categories", "brands"] as const).map((value) => (
            <Button
              key={value}
              onClick={() => setTab(value)}
              className={`h-8 rounded-lg border px-3 text-xs capitalize transition-colors ${
                tab === value
                  ? "border-primary/50 bg-primary/15 text-primary"
                  : "border-border text-muted-foreground hover:text-foreground"
              }`}
            >
              {value}
            </Button>
          ))}
        </div>
      }
    >
      {tab === "categories" ? (
        <DataTable<Row>
          columns={[
            {
              key: "name",
              label: "Category",
              render: (row) => (
                <div className="min-w-0">
                  <p className="font-medium">{String(row.name)}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    /{String(row.slug)} · {String(row.group_name ?? "—")}
                  </p>
                </div>
              ),
            },
            {
              key: "tagline",
              label: "Tagline",
              render: (row) => (
                <p className="max-w-sm truncate text-xs text-muted-foreground">
                  {String(row.tagline ?? "—")}
                </p>
              ),
            },
            {
              key: "offers",
              label: "Offers",
              className: "tabular-nums",
              render: (row) => String(row.offer_count ?? 0),
            },
            {
              key: "keywords",
              label: "Search keywords",
              render: (row) => (
                <p className="max-w-sm truncate text-[11px] text-muted-foreground">
                  {((row.keywords as string[]) ?? []).join(", ") || "—"}
                </p>
              ),
            },
          ]}
          rows={rows}
          empty="No categories."
        />
      ) : (
        <DataTable<Row>
          columns={[
            {
              key: "name",
              label: "Brand",
              render: (row) => (
                <div className="min-w-0">
                  <p className="font-medium">{String(row.name)}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {String(row.domain ?? "—")} · /{String(row.slug)}
                  </p>
                </div>
              ),
            },
            {
              key: "aliases",
              label: "Aliases",
              render: (row) => (
                <p className="max-w-sm truncate text-[11px] text-muted-foreground">
                  {((row.aliases as string[]) ?? []).join(", ") || "—"}
                </p>
              ),
            },
            {
              key: "offers",
              label: "Offers",
              className: "tabular-nums",
              render: (row) => String(row.offer_count ?? 0),
            },
            {
              key: "verified",
              label: "Verified",
              render: (row) => (row.is_verified ? "Yes" : "No"),
            },
          ]}
          rows={rows}
          empty="No brands."
        />
      )}

      <p className="mt-6 text-xs leading-relaxed text-muted-foreground">
        Adding a category or a brand needs no code change — the API, sitemap, navigation and search
        vocabulary all read from these rows. Aliases feed the search interpreter, so
        &ldquo;cloud hosting&rdquo; finds the right category without any keyword list in code.
      </p>
    </AdminShell>
  );
}

export function AdminSearchLog() {
  const [rows, setRows] = React.useState<Row[]>([]);
  const [zeroOnly, setZeroOnly] = React.useState(false);

  React.useEffect(() => {
    api.searchLog({ limit: 60, zero_only: zeroOnly }).then(setRows).catch(() => undefined);
  }, [zeroOnly]);

  return (
    <AdminShell
      title="Search log"
      description="What people searched for, and where we returned nothing."
      actions={
        <label className="flex items-center gap-2 text-xs text-muted-foreground">
          <input
            type="checkbox"
            checked={zeroOnly}
            onChange={(event) => setZeroOnly(event.target.checked)}
            className="size-3.5 accent-lime-500"
          />
          Zero results only
        </label>
      }
    >
      <DataTable<Row>
        columns={[
          {
            key: "query",
            label: "Query",
            render: (row) => <span className="font-medium">{String(row.query ?? "")}</span>,
          },
          {
            key: "intent",
            label: "Intent",
            render: (row) => (
              <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium uppercase">
                {String(row.intent ?? "—")}
              </span>
            ),
          },
          {
            key: "results",
            label: "Results",
            className: "tabular-nums",
            render: (row) => (
              <span className={row.zero_results ? "text-destructive" : ""}>
                {String(row.result_count ?? 0)}
              </span>
            ),
          },
          {
            key: "took",
            label: "Took",
            className: "whitespace-nowrap tabular-nums text-muted-foreground",
            render: (row) => `${Number(row.took_ms ?? 0).toFixed(0)} ms`,
          },
          {
            key: "country",
            label: "Country",
            className: "whitespace-nowrap text-muted-foreground",
            render: (row) => String(row.country ?? "—"),
          },
        ]}
        rows={rows}
        empty="No searches logged yet."
      />
      <p className="mt-4 text-xs text-muted-foreground">
        Zero-result queries are the clearest signal that a category, alias or source is missing.
        {formatDate(new Date().toISOString()) && ""}
      </p>
    </AdminShell>
  );
}

export function AdminUsers() {
  const { toast } = useToast();
  const [users, setUsers] = React.useState<AdminUser[]>([]);

  const load = React.useCallback(async () => {
    try {
      setUsers(await api.adminUsers());
    } catch (error) {
      toast({ title: "Could not load users", tone: "error", description: String(error) });
    }
  }, [toast]);

  React.useEffect(() => {
    void load();
  }, [load]);

  async function changeRole(user: AdminUser, role: string) {
    try {
      await api.changeUserRole(user.id, { role });
      toast({ title: `${user.email} is now ${role}`, tone: "success" });
      await load();
    } catch (error) {
      toast({ title: "Role change failed", tone: "error", description: String(error) });
    }
  }

  return (
    <AdminShell title="Users" description="Accounts, roles and moderation state.">
      <DataTable<AdminUser>
        columns={[
          {
            key: "email",
            label: "Account",
            render: (row) => (
              <div className="min-w-0">
                <p className="truncate font-medium">{row.email}</p>
                <p className="truncate text-xs text-muted-foreground">
                  {row.display_name ?? "—"} · joined {formatDate(row.created_at)}
                </p>
              </div>
            ),
          },
          {
            key: "locale",
            label: "Preferences",
            className: "whitespace-nowrap text-xs text-muted-foreground",
            render: (row) => `${row.country_code ?? "—"} · ${row.preferred_currency}`,
          },
          {
            key: "bookmarks",
            label: "Saved",
            className: "tabular-nums",
            render: (row) => String(row.bookmark_count),
          },
          {
            key: "role",
            label: "Role",
            className: "whitespace-nowrap",
            render: (row) => (
              <select
                value={row.role}
                onChange={(event) => changeRole(row, event.target.value)}
                className="h-8 rounded-md border border-input bg-background px-2 text-xs"
              >
                <option value="user">user</option>
                <option value="reviewer">reviewer</option>
                <option value="admin">admin</option>
              </select>
            ),
          },
          {
            key: "state",
            label: "State",
            className: "whitespace-nowrap text-xs",
            render: (row) => (
              <span className={row.is_banned ? "text-destructive" : "text-muted-foreground"}>
                {row.is_banned ? "banned" : row.is_active ? "active" : "inactive"}
              </span>
            ),
          },
        ]}
        rows={users}
        empty="No users."
      />
      <p className="mt-4 text-xs text-muted-foreground">
        Role changes are enforced server-side and recorded as admin actions. You cannot demote your
        own account.
      </p>
    </AdminShell>
  );
}
