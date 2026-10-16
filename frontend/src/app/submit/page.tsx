import type { Metadata } from "next";
import { api } from "@/lib/api";
import { pageMetadata } from "@/lib/seo";
import { SubmitForm } from "./submit-form";

export const metadata: Metadata = pageMetadata({
  title: "Submit a deal",
  description:
    "Tell us about an offer. A human reviewer verifies it against the official page before it is published.",
  path: "/submit",
});

export default async function SubmitPage() {
  let categories: Awaited<ReturnType<typeof api.categories>> = [];
  try {
    categories = await api.categories();
  } catch {
    categories = [];
  }

  return (
    <div className="container max-w-3xl py-8">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Submit a deal</h1>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          We only publish offers we can confirm on the provider&rsquo;s own page. Tell us what you
          found and a reviewer will check the terms, eligibility and deadline before it goes live.
        </p>
      </header>

      <SubmitForm categories={categories} />

      <section className="mt-8 rounded-2xl border border-border bg-card/40 p-5">
        <h2 className="text-sm font-semibold">What happens next</h2>
        <ol className="mt-3 space-y-2 text-[13px] leading-relaxed text-muted-foreground">
          <li>1. A reviewer opens the official page you linked.</li>
          <li>2. We confirm the price, the trial length and the eligibility rules.</li>
          <li>3. The offer is published and then re-checked automatically on a schedule.</li>
          <li>4. If the page disappears or the terms change, the offer is flagged or expired.</li>
        </ol>
      </section>
    </div>
  );
}