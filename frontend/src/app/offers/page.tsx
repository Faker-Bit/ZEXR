import type { Metadata } from "next";
import { Suspense } from "react";
import { api } from "@/lib/api";
import { pageMetadata, jsonLd, breadcrumbSchema } from "@/lib/seo";
import { DirectoryClient } from "./directory-client";

export const metadata: Metadata = pageMetadata({
  title: "All offers — browse every free trial, discount and free credit",
  description:
    "Search and filter every verified offer: free trials, discounts, coupon codes, free credits and genuinely free tools. Filter by country, duration, eligibility and whether a card is needed.",
  path: "/offers",
});

export default async function OffersPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const query: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined) continue;
    query[key] = Array.isArray(value) ? value : String(value).split(",").filter(Boolean);
    if (typeof value === "string" && !value.includes(",")) query[key] = value;
  }
  query.page_size = 24;

  const [offersResult, categoriesResult, countriesResult, typesResult] = await Promise.allSettled([
    api.offers(query),
    api.categories(),
    api.countries(),
    api.offerTypes(),
  ]);

  const offers =
    offersResult.status === "fulfilled"
      ? offersResult.value
      : { items: [], total: 0, page: 1, page_size: 24, pages: 1, has_next: false, has_prev: false };
  const categories = categoriesResult.status === "fulfilled" ? categoriesResult.value : [];
  const countries = countriesResult.status === "fulfilled" ? countriesResult.value : [];
  const offerTypes = typesResult.status === "fulfilled" ? typesResult.value : [];

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={jsonLd(
          breadcrumbSchema([
            { name: "Home", path: "/" },
            { name: "Offers", path: "/offers" },
          ]),
        )}
      />
      <div className="container py-8 sm:py-10">
        <header className="mb-6">
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">All offers</h1>
          <p className="mt-1.5 text-sm text-muted-foreground">
            {offers.total.toLocaleString()} active offers. Every card shows whether a payment method is
            needed, where it works and when we last checked it.
          </p>
        </header>

        <Suspense fallback={<DirectorySkeleton />}>
          <DirectoryClient
            initialPage={offers}
            categories={categories}
            countries={countries}
            offerTypes={offerTypes}
          />
        </Suspense>
      </div>
    </>
  );
}

function DirectorySkeleton() {
  return (
    <div className="grid gap-6 lg:grid-cols-[240px_1fr]">
      <div className="hidden space-y-3 lg:block">
        {Array.from({ length: 6 }).map((_, index) => (
          <div key={index} className="skeleton h-10 rounded-lg" />
        ))}
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 6 }).map((_, index) => (
          <div key={index} className="skeleton h-56 rounded-xl" />
        ))}
      </div>
    </div>
  );
}