import type { Metadata } from "next";

import { api } from "@/lib/api";
import { pageMetadata } from "@/lib/seo";
import { GamingClient } from "./gaming-client";

export const revalidate = 600;

export const metadata: Metadata = pageMetadata({
  title: "Free games and big Steam discounts",
  description:
    "Games you can keep for nothing right now, plus the deepest Steam discounts — real prices, refreshed from the Steam store.",
  path: "/gaming",
});

export default async function GamingPage() {
  let freeGames: Awaited<ReturnType<typeof api.categoryOffers>> = [];
  let deepDeals: Awaited<ReturnType<typeof api.offers>> | null = null;

  try {
    freeGames = await api.categoryOffers("gaming", 24);
  } catch {
    freeGames = [];
  }

  try {
deepDeals = await api.offers({
        category: ["gaming"],
        sort: "savings",
        page_size: 36,
      });
  } catch {
    deepDeals = null;
  }

  const free = freeGames.filter(
    (offer) => offer.promo_price === 0 || offer.is_genuinely_free,
  );
  const deep = (deepDeals?.items ?? []).filter((offer) => offer.savings_percent >= 50);

  return (
    <main id="main" className="container py-10 sm:py-14">
      <header className="max-w-2xl">
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
          Free games &amp; big discounts
        </h1>
        <p className="mt-3 text-base leading-relaxed text-muted-foreground">
          Pulled straight from the Steam store with real prices. Games marked free are{" "}
          <strong className="font-medium text-foreground">free to keep</strong> during the
          promotion window, not just free to try.
        </p>
      </header>

      <GamingClient
        freeGames={free.slice(0, 12)}
        deepDeals={deep.slice(0, 24)}
        totalFree={free.length}
        totalDeep={deep.length}
        catalogueTotal={deepDeals?.total ?? 0}
      />
    </main>
  );
}