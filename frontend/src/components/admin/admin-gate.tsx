"use client";

import * as React from "react";
import Link from "next/link";
import { useAuth } from "@/components/site/auth-provider";
import { AdminNav } from "@/components/admin/shell";

/**
 * Admin gate.
 *
 * The API enforces role-based access on every admin route; this is only a UX
 * layer so non-admins get a clear message instead of a wall of failed fetches.
 */
export function AdminGate({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();

  if (loading) {
    return <div className="container py-10"><div className="skeleton h-72 rounded-xl" /></div>;
  }

  if (!user || (user.role !== "admin" && user.role !== "reviewer")) {
    return (
      <div className="container flex min-h-[60vh] items-center justify-center py-16">
        <div className="max-w-sm text-center">
          <h1 className="text-xl font-semibold tracking-tight">Admin access required</h1>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
            Sign in with an account that has the admin or reviewer role. Every admin endpoint is
            authorised server-side — this page only avoids pointless requests.
          </p>
          <Link
            href="/login?next=/admin"
            className="mt-5 inline-flex h-10 items-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground"
          >
            Sign in
          </Link>
          <p className="mt-4 text-xs text-muted-foreground">
            Development accounts: <code>admin@zexrdealhub.dev</code> ·{" "}
            <code>reviewer@zexrdealhub.dev</code>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="container py-8">
      <div className="grid gap-6 lg:grid-cols-[210px_1fr]">
        <aside className="lg:sticky lg:top-24 lg:self-start">
          <AdminNav />
        </aside>
        <div className="min-w-0">{children}</div>
      </div>
    </div>
  );
}