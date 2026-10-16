"use client";

import * as React from "react";
import Link from "next/link";
import { TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function ErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  React.useEffect(() => {
    // Surface the failure for debugging without leaking internals to the UI.
    console.error("ZEXR Deal Hub route error:", error);
  }, [error]);

  return (
    <div className="container flex min-h-[60vh] items-center justify-center py-16">
      <div className="max-w-md text-center">
        <TriangleAlert className="mx-auto size-10 text-warning" />
        <h1 className="mt-4 text-2xl font-semibold tracking-tight">This page could not load</h1>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          The content service did not respond in time. This is usually temporary — the offers
          themselves are unaffected.
        </p>
        {error.digest ? (
          <p className="mt-2 font-mono text-[11px] text-muted-foreground">ref: {error.digest}</p>
        ) : null}
        <div className="mt-6 flex justify-center gap-2">
          <Button onClick={reset}>Try again</Button>
          <Button asChild variant="outline">
            <Link href="/">Go home</Link>
          </Button>
        </div>
      </div>
    </div>
  );
}