import type { Metadata } from "next";
import Link from "next/link";
import { History } from "lucide-react";
import { api } from "@/lib/api";
import { pageMetadata } from "@/lib/seo";
import { OfferCard } from "@/components/offers/offer-card";
import { EmptyState } from "@/components/ui/empty-state";
import { Button } from "@/components/ui/button";

export const revalidate = 300;

export const metadata: Metadata = pageMetadata({
  title: "Recently expired offers",
  description:
    "Offers that have already ended, kept separate from live deals so you can spot what you missed and learn what to watch for next time.",
  path: "/expired",
});

export default async function ExpiredPage() {
  let offers: Awaited<ReturnType<typeof api.expired>> | null = null;
  try {
    offers = await api.expired(1, 36);
  } catch {
    offers = null;
  }

  return (
    <div className="container py-8">
      <header className="mb-8 max-w-2xl">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-warning/30 bg-warning/10 px-2.5 py-1 text-[11px] font-medium text-warning">
          <History className="size-3" />
          Archive
        </span>
        <h1 className="mt-3 text-2xl font-semibold tracking-tight sm:text-3xl">
          Recently expired offers
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          These offers are no longer claimable. They are kept here — clearly separated from live
          deals — so you can see what you missed and recognise the pattern next time.
        </p>
      </header>

      {offers && offers.items.length ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {offers.items.map((offer, index) => (
            <OfferCard key={offer.id} offer={offer} index={index} />
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<History className="size-5" />}
          title="Nothing has expired yet"
          description="Expired offers will appear here once their deadline passes."
          action={
            <Button asChild>
              <Link href="/offers">Browse live offers</Link>
            </Button>
          }
        />
      )}
    </div>
  );
}