import type { Metadata } from "next";
import { Suspense } from "react";
import { SearchPageClient } from "./search-client";
import { api } from "@/lib/api";
import { loadCategories } from "@/lib/categories";

export const metadata: Metadata = {
  title: "Search deals",
  description:
    "Search free trials, free credits, discounts and free tools by brand, category, price or country.",
  robots: { index: false, follow: true },
};

export default async function SearchPage({
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

  const [offersResult, categoriesResult, countriesResult, typesResult, trendingResult] =
    await Promise.allSettled([
      api.offers(query),
      loadCategories(),
      api.countries(),
      api.offerTypes(),
      api.trendingSearches(10),
    ]);

  return (
    <div className="container py-8">
      <Suspense fallback={<div className="skeleton h-40 rounded-xl" />}>
        <SearchPageClient
          initialOffers={
            offersResult.status === "fulfilled" ? offersResult.value : null
          }
          categories={categoriesResult.status === "fulfilled" ? categoriesResult.value : []}
          countries={countriesResult.status === "fulfilled" ? countriesResult.value : []}
          offerTypes={typesResult.status === "fulfilled" ? typesResult.value : []}
          trending={trendingResult.status === "fulfilled" ? trendingResult.value : []}
        />
      </Suspense>
    </div>
  );
}
