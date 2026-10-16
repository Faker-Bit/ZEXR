"use client";

import * as React from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  ArrowRight,
  BadgeCheck,
  Clock3,
  CreditCard,
  Gift,
  Globe2,
  Sparkles,
  Tag,
  TrendingUp,
} from "lucide-react";
import { SearchBar } from "@/components/site/search-bar";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const QUICK_FILTERS = [
  { label: "Free", value: "free", href: "/offers?type=free", icon: Gift },
  { label: "Free trial", value: "free_trial", href: "/offers?type=free_trial", icon: Clock3 },
  { label: "Under $10", value: "under10", href: "/offers?max_price=10", icon: Tag },
  { label: "Discounts", value: "discount", href: "/offers?type=discount", icon: BadgeCheck },
  { label: "Free credits", value: "free_credits", href: "/offers?type=free_credits", icon: CreditCard },
  { label: "Ending soon", value: "ending", href: "/offers?ending_within_days=3", icon: TrendingUp },
  { label: "New offers", value: "new", href: "/offers?sort=newest", icon: Sparkles },
  { label: "Worldwide", value: "global", href: "/offers?global_only=true", icon: Globe2 },
];

export function Hero({
  stats,
}: {
  stats?: { live_offers: number; verified_offers: number; categories: number };
}) {
  return (
    <section className="relative overflow-hidden border-b border-border bg-noise">
      <div className="pointer-events-none absolute inset-0 bg-grid" aria-hidden />
      <div
        className="pointer-events-none absolute left-1/2 top-[-18rem] size-[46rem] -translate-x-1/2 rounded-full bg-primary/[0.11] blur-[110px]"
        aria-hidden
      />

      <div className="container relative py-14 sm:py-20 lg:py-24">
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          className="mx-auto max-w-3xl text-center"
        >
          <span className="inline-flex items-center gap-1.5 rounded-full border border-primary/25 bg-primary/10 px-3 py-1 text-[11px] font-medium text-primary">
            <span className="relative flex size-1.5">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-primary opacity-70" />
              <span className="relative inline-flex size-1.5 rounded-full bg-primary" />
            </span>
            Automatically verified · {stats?.live_offers ?? "—"} live offers
          </span>

          <h1 className="mt-6 text-balance text-4xl font-semibold leading-[1.08] tracking-tight sm:text-5xl lg:text-6xl">
            Find the Best Deals.{" "}
            <span className="text-gradient">Unlock More for Less.</span>
          </h1>

          <p className="mx-auto mt-5 max-w-2xl text-pretty text-base leading-relaxed text-muted-foreground sm:text-lg">
            Discover free trials, premium offers, discounts, and hidden savings from across the
            internet — with eligibility, renewal price and verification date on every single offer.
          </p>

          <div className="mx-auto mt-8 max-w-2xl">
            <SearchBar size="lg" />
          </div>

          <div className="mt-7">
            <div className="scrollbar-none flex flex-wrap items-center justify-center gap-1.5">
              <span className="mr-1 text-xs text-muted-foreground">Quick filters</span>
              {QUICK_FILTERS.map((filter) => (
                <Link
                  key={filter.value}
                  href={filter.href}
                  className={cn(
                    "group inline-flex items-center gap-1.5 rounded-full border border-border bg-background/60 px-3 py-1.5 text-xs font-medium transition-all",
                    "hover:border-primary/40 hover:bg-primary/10 hover:text-primary",
                  )}
                >
                  <filter.icon className="size-3.5" />
                  {filter.label}
                </Link>
              ))}
            </div>
          </div>
        </motion.div>

        <div className="mx-auto mt-12 grid max-w-4xl grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { label: "Live offers", value: stats?.live_offers },
            { label: "Verified by us", value: stats?.verified_offers },
            { label: "Categories", value: stats?.categories },
            { label: "Countries covered", value: 40 },
          ].map((item, index) => (
            <motion.div
              key={item.label}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.15 + index * 0.05, duration: 0.4 }}
              className="rounded-xl border border-border bg-card/60 px-4 py-3 text-center backdrop-blur"
            >
              <p className="text-xl font-semibold tabular-nums">
                {item.value === undefined ? "—" : item.value.toLocaleString()}
              </p>
              <p className="mt-0.5 text-[11px] text-muted-foreground">{item.label}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

export function SectionHeader({
  eyebrow,
  title,
  description,
  href,
  actionLabel = "View all",
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  href?: string;
  actionLabel?: string;
}) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        {eyebrow ? (
          <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-primary">
            {eyebrow}
          </p>
        ) : null}
        <h2 className="text-xl font-semibold tracking-tight sm:text-2xl">{title}</h2>
        {description ? (
          <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-muted-foreground">
            {description}
          </p>
        ) : null}
      </div>
      {href ? (
        <Button asChild variant="ghost" size="sm">
          <Link href={href}>
            {actionLabel}
            <ArrowRight className="size-3.5" />
          </Link>
        </Button>
      ) : null}
    </div>
  );
}

/** Horizontal scroller for rails of offers. */
export function OfferRail({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "scrollbar-none -mx-4 flex snap-x snap-mandatory gap-3 overflow-x-auto px-4 pb-2 sm:mx-0 sm:px-0",
        className,
      )}
    >
      {children}
    </div>
  );
}