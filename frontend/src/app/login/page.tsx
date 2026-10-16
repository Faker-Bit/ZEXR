import type { Metadata } from "next";
import Link from "next/link";
import { AdminLoginForm } from "./auth-form";
import { pageMetadata } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "Admin sign in",
  description: "Sign in to the ZEXR Deal Hub moderation console.",
  path: "/login",
  noindex: true,
});

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string }>;
}) {
  const params = await searchParams;
  // Only same-site paths: an open redirect here would be a phishing primitive.
  const next = params.next && params.next.startsWith("/") ? params.next : "/admin";

  return (
    <div className="container flex min-h-[70vh] items-center justify-center py-12">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <h1 className="text-2xl font-semibold tracking-tight">Admin sign in</h1>
          <p className="mt-1.5 text-sm text-muted-foreground">
            For moderators and reviewers. Everyone else can browse the whole catalogue without an
            account.
          </p>
        </div>
        <AdminLoginForm nextPath={next} />
        <p className="mt-6 text-center text-sm text-muted-foreground">
          Just looking for deals?{" "}
          <Link
            href="/offers"
            className="font-medium text-primary underline-offset-4 hover:underline"
          >
            Browse the directory
          </Link>
        </p>
      </div>
    </div>
  );
}