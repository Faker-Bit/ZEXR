"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { LogIn } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/components/site/auth-provider";
import { api } from "@/lib/api";

/**
 * Sign-in form for the **admin** console only.
 *
 * The public site has no accounts: browsing, searching and reading every offer
 * is open, so there is nothing to sign up for. Admin/reviewer roles still need
 * an identity, and that is what this page is for.
 */
export function AdminLoginForm({ nextPath = "/admin" }: { nextPath?: string }) {
  const router = useRouter();
  const { setUser } = useAuth();
  const { toast } = useToast();

  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const result = await api.login({ email, password });
      if (!result.user) throw new Error("Could not sign in");
      setUser(result.user);
      toast({ title: "Signed in", tone: "success" });
      router.push(nextPath);
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Sign-in failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor="admin-email">Email</Label>
        <Input
          id="admin-email"
          type="email"
          autoComplete="username"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="admin@zexrdealhub.dev"
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="admin-password">Password</Label>
        <Input
          id="admin-password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </div>

      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}

      <Button type="submit" className="w-full" disabled={submitting}>
        <LogIn className="size-4" />
        {submitting ? "Signing in…" : "Sign in to admin"}
      </Button>
    </form>
  );
}