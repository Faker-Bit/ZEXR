"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  Boxes,
  ExternalLink,
  Flag,
  Gauge,
  Layers,
  Search,
  ServerCog,
  ShieldCheck,
  Tags,
  Users,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/admin", label: "Overview", icon: Gauge, exact: true },
  { href: "/admin/offers", label: "Offers", icon: Layers },
  { href: "/admin/review", label: "Review queue", icon: ShieldCheck },
  { href: "/admin/sources", label: "Sources & discovery", icon: ServerCog },
  { href: "/admin/taxonomy", label: "Categories & brands", icon: Tags },
  { href: "/admin/reports", label: "Reports", icon: Flag },
  { href: "/admin/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/admin/search-log", label: "Search log", icon: Search },
  { href: "/admin/users", label: "Users", icon: Users },
];

export function AdminNav({ className }: { className?: string }) {
  const pathname = usePathname();
  return (
    <nav className={cn("flex gap-1 overflow-x-auto lg:flex-col", className)}>
      {NAV.map((item) => {
        const active = item.exact ? pathname === item.href : pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "flex shrink-0 items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
              active
                ? "bg-primary/15 text-primary"
                : "text-muted-foreground hover:bg-accent hover:text-foreground",
            )}
          >
            <item.icon className="size-4" />
            {item.label}
          </Link>
        );
      })}
      <a
        href="/"
        target="_blank"
        rel="noopener noreferrer"
        className="mt-1 flex shrink-0 items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
      >
        <ExternalLink className="size-4" />
        View site
      </a>
    </nav>
  );
}

export function AdminShell({
  title,
  description,
  actions,
  children,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="container py-8">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-primary">
            Admin
          </p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">{title}</h1>
          {description ? (
            <p className="mt-1 text-sm text-muted-foreground">{description}</p>
          ) : null}
        </div>
        {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
      </div>
      {children}
    </div>
  );
}

export function StatCard({
  label,
  value,
  hint,
  tone = "default",
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
  tone?: "default" | "good" | "warn" | "bad";
}) {
  return (
    <div className="rounded-xl border border-border bg-card/60 p-4">
      <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p
        className={cn(
          "mt-1.5 text-2xl font-semibold tabular-nums",
          tone === "good" && "text-success",
          tone === "warn" && "text-warning",
          tone === "bad" && "text-destructive",
        )}
      >
        {value}
      </p>
      {hint ? <p className="mt-1 text-[11px] text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

export function DataTable<T>({
  columns,
  rows,
  empty = "Nothing here yet.",
}: {
  columns: { key: string; label: string; className?: string; render: (row: T) => React.ReactNode }[];
  rows: T[];
  empty?: string;
}) {
  if (!rows.length) {
    return <p className="py-10 text-center text-sm text-muted-foreground">{empty}</p>;
  }
  return (
    <div className="overflow-x-auto rounded-xl border border-border">
      <table className="w-full min-w-[640px] text-left text-sm">
        <thead className="bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            {columns.map((column) => (
              <th key={column.key} className={cn("px-4 py-2.5 font-medium", column.className)}>
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map((row, index) => (
            <tr key={index} className="hover:bg-accent/30">
              {columns.map((column) => (
                <td key={column.key} className={cn("px-4 py-3 align-middle", column.className)}>
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export { Boxes };