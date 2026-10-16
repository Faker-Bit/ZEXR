import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Clock3, Flame, Gem, ShieldCheck, Sparkles, Wallet } from "lucide-react";
import { Hero, OfferRail, SectionHeader } from "@/components/home/hero";
import {
  CategoryGrid,
  NewsletterCta,
  TrustStrip,
} from "@/components/home/newsletter";
import { OfferCard } from "@/components/offers/offer-card";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { jsonLd, pageMetadata } from "@/lib/seo";
import { formatCompact, formatMoney, pluralise } from "@/lib/utils";
import type { HomeBundle, OfferCard as OfferCardType } from "@/lib/types";

export const revalidate = 120;

export const metadata: Metadata = pageMetadata({
  title: "Find the Best Deals. Unlock More for Less.",
  description:
    "Verified free trials, discounts, free credits and genuinely free online tools for everyone — with eligibility, renewal price and last-checked date on every offer.",
  path: "/",
});

function rail(items: OfferCardType[]) {
  if (!items.length) return null;
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {items.slice(0, 8).map((offer, index) => (
        <OfferCard key={offer.id} offer={offer} index={index} />
      ))}
    </div>
  );
}

export default async function HomePage() {
  let bundle: HomeBundle | null = null;
  let categories: Awaited<ReturnType<typeof api.categories>> = [];
  let interests: Awaited<ReturnType<typeof api.interests>> = [];

  const [homeResult, categoriesResult, interestsResult] = await Promise.allSettled([
    api.home(8),
    api.categories(),
    api.interests(),
  ]);
  if (homeResult.status === "fulfilled") bundle = homeResult.value;
  if (categoriesResult.status === "fulfilled") categories = categoriesResult.value;
  if (interestsResult.status === "fulfilled") interests = interestsResult.value;

  const stats = bundle?.stats;
  const popularCategories = categories.filter((category) => category.offer_count > 0);
  const trendingSearches = await safeTrending();

  const faq = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: [
      {
        "@type": "Question",
        name: "Is ZEXR Deal Hub free to use?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "Partly. Browsing, searching and saving offers is free, and the free plan never expires — it shows the first 12 offers in any listing. Pro removes that cap and adds price-drop and expiry alerts. We may also earn a commission when you claim an offer through an affiliate link, which never costs you extra and is always labelled.",
        },
      },
      {
        "@type": "Question",
        name: "How do you verify offers?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "Each offer links to the official page and is re-checked on a schedule. We record the HTTP result, the price found on the page and the time of the check. Anything we cannot check automatically is labelled as needing manual verification instead of being marked verified.",
        },
      },
      {
        "@type": "Question",
        name: "What is the difference between free and free trial?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "A genuinely free product costs nothing and does not convert into a subscription. A free trial gives full access for a limited period and then starts charging unless you cancel. Every offer states which one it is.",
        },
      },
      {
        "@type": "Question",
        name: "Do offers work in my country?",
        acceptedAnswer: {
          "@type": "Answer",
          text: "Each offer lists the countries it is available in, or is marked worldwide. Regional restrictions are always shown before you click through.",
        },
      },
    ],
  };

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={jsonLd(faq)} />

      <Hero stats={stats ? { ...stats, categories: stats.categories } : undefined} />

      <div className="container space-y-14 py-12 sm:space-y-16 sm:py-16">
        {trendingSearches.length ? (
          <section aria-label="Trending searches">
            <div className="flex flex-wrap items-center gap-2">
              <span className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                <Flame className="size-3.5 text-warning" />
                Trending:
              </span>
              {trendingSearches.slice(0, 8).map((item) => (
                <Link
                  key={item.query}
                  href={`/search?q=${encodeURIComponent(item.query)}`}
                  className="rounded-full border border-border px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:border-primary/40 hover:text-primary"
                >
                  {item.query}
                </Link>
              ))}
            </div>
          </section>
        ) : null}

        {bundle ? (
          <>
            <section>
              <SectionHeader
                eyebrow="Right now"
                title="Trending deals"
                description="What people are claiming this week, ranked by verified clicks."
                href="/offers?sort=trending"
              />
              {rail(bundle.trending)}
            </section>

            <section>
              <SectionHeader
                eyebrow="Ending soon"
                title="Grab these before they expire"
                description="Offers with a deadline inside the next few days."
                href="/offers?ending_within_days=7&sort=ending_soon"
              />
              {bundle.ending_soon.length ? (
                <OfferRail>
                  {bundle.ending_soon.map((offer, index) => (
                    <div key={offer.id} className="w-[280px] shrink-0 snap-start sm:w-[320px]">
                      <OfferCard offer={offer} index={index} />
                    </div>
                  ))}
                </OfferRail>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Nothing is expiring in the next few days right now.
                </p>
              )}
            </section>

            <section>
              <SectionHeader
                eyebrow="Highest value"
                title="Biggest verified savings"
                description="Free upgrades and large credits that cost nothing to claim."
                href="/offers?sort=savings"
              />
              {rail(bundle.highest_value)}
            </section>

            <section>
              <SectionHeader
                eyebrow="Genuinely free"
                title="Free forever, no card required"
                description="Products that cost nothing and do not turn into a subscription."
                href="/offers?type=free"
              />
              {rail(bundle.free_tools)}
            </section>

            {bundle.no_card.length ? (
              <section>
                <SectionHeader
                  eyebrow="No strings"
                  title="Free without a credit card"
                  description="Start these without entering payment details."
                  href="/offers?requires_payment_method=false"
                />
                {rail(bundle.no_card)}
              </section>
            ) : null}

            <section>
              <SectionHeader
                eyebrow="Just added"
                title="Fresh offers"
                description="Discovered and reviewed in the last few days."
                href="/offers?sort=newest"
              />
              {rail(bundle.fresh)}
              <div className="mt-5">
                <Button asChild variant="outline">
                  <Link href="/offers?sort=newest">
                    See everything new
                    <ArrowRight className="size-4" />
                  </Link>
                </Button>
              </div>
            </section>
          </>
        ) : (
          <EmptyBackendNotice />
        )}

        {popularCategories.length ? (
          <section>
            <SectionHeader
              eyebrow="Browse"
              title="Popular categories"
              description="Sixteen curated buckets covering AI, developer tools, cloud, privacy, streaming, shopping and more."
              href="/categories"
              actionLabel="All categories"
            />
            <CategoryGrid categories={popularCategories.slice(0, 9)} />
          </section>
        ) : null}

        <TrustStrip />

        {stats ? (
          <section className="rounded-2xl border border-border bg-card/50 p-6 sm:p-8">
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
              <Stat
                icon={<Sparkles className="size-4" />}
                value={formatCompact(stats.live_offers)}
                label="Live offers tracked"
              />
              <Stat
                icon={<ShieldCheck className="size-4" />}
                value={formatCompact(stats.verified_offers)}
                label="Verified automatically"
              />
              <Stat
                icon={<Wallet className="size-4" />}
                value={formatMoney(stats.total_savings, "USD", { compact: true })}
                label="Total savings listed"
              />
              <Stat
                icon={<Gem className="size-4" />}
                value={formatCompact(stats.free_offers)}
                label="Genuinely free products"
              />
            </div>
            <p className="mt-5 text-xs leading-relaxed text-muted-foreground">
              Figures update continuously as offers are discovered, re-verified and expired. They
              describe the catalogue — not your personal savings.
            </p>
          </section>
        ) : null}

        <NewsletterCta interests={interests} />

        {bundle?.ending_soon.length ? (
          <section>
            <SectionHeader
              eyebrow="Don't miss out"
              title="Deadlines within 48 hours"
              actionLabel="All ending soon"
              href="/offers?ending_within_days=2&sort=ending_soon"
            />
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {bundle.ending_soon.slice(0, 4).map((offer, index) => (
                <div key={offer.id} className="relative">
                  <Clock3 className="absolute -top-1.5 -right-1.5 z-10 size-4 rounded-full bg-warning/20 text-warning" />
                  <OfferCard offer={offer} index={index} compact />
                </div>
              ))}
            </div>
          </section>
        ) : null}
      </div>
    </>
  );
}

function Stat({ icon, value, label }: { icon: React.ReactNode; value: string; label: string }) {
  return (
    <div>
      <div className="flex items-center gap-2 text-primary">
        {icon}
        <span className="text-2xl font-semibold tabular-nums">{value}</span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">{label}</p>
    </div>
  );
}

function EmptyBackendNotice() {
  return (
    <div className="rounded-2xl border border-dashed border-border bg-card/40 px-6 py-14 text-center">
      <h2 className="text-base font-semibold">No offers loaded yet</h2>
      <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-muted-foreground">
        The API did not respond. Start the backend with{" "}
        <code className="rounded bg-muted px-1.5 py-0.5 text-xs">uvicorn app.main:app</code> and seed it
        with <code className="rounded bg-muted px-1.5 py-0.5 text-xs">python -m app.db.seed</code>.
      </p>
    </div>
  );
}

async function safeTrending() {
  try {
    const rows = await api.trendingSearches(10);
    return rows.filter((row) => row.searches > 0);
  } catch {
    return [];
  }
}

export { pluralise };