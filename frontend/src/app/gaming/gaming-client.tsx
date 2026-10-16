"use client";

import * as React from "react";
import Link from "next/link";
import { Gamepad2, Flame, Gift, Percent } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { OfferCard } from "@/components/offers/offer-card";
import type { OfferCard as OfferCardType } from "@/lib/types";

function money(value: number | null | undefined) {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

export function GamingClient({
  freeGames,
  deepDeals,
  totalFree,
  totalDeep,
  catalogueTotal,
}: {
  freeGames: OfferCardType[];
  deepDeals: OfferCardType[];
  totalFree: number;
  totalDeep: number;
  catalogueTotal: number;
}) {
  return (
    <div className="mt-10 space-y-14">
      <section aria-labelledby="free-heading">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2
              id="free-heading"
              className="flex items-center gap-2 text-xl font-semibold tracking-tight"
            >
              <Gift className="size-5 text-primary" />
              Free to keep right now
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Add them to your Steam library before the promotion ends.
            </p>
          </div>
          <Badge variant="success" size="sm">
            {totalFree} free
          </Badge>
        </div>

        <div className="mt-5">
          {freeGames.length ? (
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {freeGames.map((game, index) => (
                <OfferCard key={game.id} offer={game} index={index} />
              ))}
            </div>
          ) : (
            <EmptyState
              icon={<Gift className="size-5" />}
              title="No free promotions right now"
              description="Steam hands out free games most weeks — check back, or browse every deal meanwhile."
            />
          )}
        </div>
      </section>

      <section aria-labelledby="deep-heading">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2
              id="deep-heading"
              className="flex items-center gap-2 text-xl font-semibold tracking-tight"
            >
              <Flame className="size-5 text-primary" />
              Discounts of 50% and deeper
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {catalogueTotal} game deals tracked · {totalDeep} at half price or less.
            </p>
          </div>
          <Button asChild variant="outline" size="sm">
            <Link href="/categories/gaming">
              <Percent className="size-3.5" />
              All gaming deals
            </Link>
          </Button>
        </div>

        <div className="mt-5">
          {deepDeals.length ? (
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {deepDeals.map((game, index) => (
                <OfferCard key={game.id} offer={game} index={index} />
              ))}
            </div>
          ) : (
            <EmptyState
              icon={<Gamepad2 className="size-5" />}
              title="No deep discounts tracked yet"
              description="The Steam specials feed refreshes through discovery — run `python -m app.cli discover` to pull the current sale."
            />
          )}
        </div>
      </section>

      <section className="rounded-2xl border border-border bg-card/40 p-6">
        <h2 className="text-sm font-semibold">Where this data comes from</h2>
        <ul className="mt-3 space-y-1.5 text-sm text-muted-foreground">
          <li>
            <strong className="font-medium text-foreground">Free games</strong> — Steam&rsquo;s store
            search filtered to free promotions, refreshed on a rolling schedule.
          </li>
          <li>
            <strong className="font-medium text-foreground">Discounts</strong> — the Steam specials
            feed, with the price shown on every card taken from the store itself.
          </li>
          <li>
            Prices are in <strong className="font-medium text-foreground">USD</strong> and reflect
            the US storefront. Regional pricing and taxes vary.
          </li>
        </ul>
        <p className="mt-3 text-xs text-muted-foreground">
          Steam will only keep a free promotion for a limited window. Always confirm on the store
          page before relying on the price.
        </p>
      </section>
    </div>
  );
}