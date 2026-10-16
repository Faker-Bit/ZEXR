"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { Compass, Flame, Sparkles, Wand2 } from "lucide-react";
import { api } from "@/lib/api";
import { EmptyState } from "@/components/ui/empty-state";
import { OfferCard, OfferCardSkeleton } from "@/components/offers/offer-card";
import { SearchBar } from "@/components/site/search-bar";
import { Badge } from "@/components/ui/badge";
import type {
  Category,
  CountryBrief,
OfferCard as OfferCardType,
    OfferTypeMeta,
    Page,
    ParsedIntent,
    QuotaMeta,
  } from "@/lib/types";
import { labelForOfferType } from "@/lib/utils";

interface SearchPageClientProps {
  initialOffers: Page<OfferCardType> | null;
  categories: Category[];
  countries: CountryBrief[];
  offerTypes: OfferTypeMeta[];
  trending: { query: string; searches: number; results: number }[];
}

interface SearchState {
  query: string;
  intent: ParsedIntent | null;
  results: OfferCardType[];
  total: number;
  page: number;
  pages: number;
  didYouMean: string | null;
  meta: QuotaMeta | null;
  tookMs: number;
}

const SUGGESTED = [
  "30 days free VPN",
  "AI tools with free credits",
  "Free cloud hosting",
  "Best software discounts",
  "Free premium tools without a credit card",
  "India only offers",
  "Cashback on shopping",
  "Free alternatives to Photoshop",
];

export function SearchPageClient({
  initialOffers,
  categories,
  countries,
  offerTypes,
  trending,
}: SearchPageClientProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialQuery = searchParams.get("q") ?? "";

  const [state, setState] = React.useState<SearchState>({
    query: initialQuery,
    intent: null,
    results: initialOffers?.items ?? [],
    total: initialOffers?.total ?? 0,
    page: initialOffers?.page ?? 1,
pages: initialOffers?.pages ?? 1,
    didYouMean: null,
    meta: initialOffers?.meta ?? null,
    tookMs: 0,
  });
  const [loading, setLoading] = React.useState(false);
  const [sort, setSort] = React.useState("relevance");
  const [typeFilter, setTypeFilter] = React.useState<string[]>([]);
  const [categoryFilter, setCategoryFilter] = React.useState<string[]>([]);
  const [countryFilter, setCountryFilter] = React.useState<string[]>([]);
  const [bookmarks, setBookmarks] = React.useState<Record<string, boolean>>({});
  const firstRender = React.useRef(true);

  const run = React.useCallback(async (query: string, pageNumber: number) => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const response = await api.search({
        q: query,
        sort,
        type: typeFilter,
        category: categoryFilter,
        country_codes: countryFilter,
        page: pageNumber,
        page_size: 24,
      });
      setState({
        query: query,
        intent: response.intent,
        results: response.results,
        total: response.total,
        page: response.page,
        pages: response.pages,
        didYouMean: response.did_you_mean ?? null,
    meta: response.meta ?? null,
        tookMs: response.took_ms,
      });
      router.replace(`/search?q=${encodeURIComponent(query)}`, { scroll: false });
    } catch {
      /* keep previous results */
    } finally {
      setLoading(false);
    }
  }, [sort, typeFilter, categoryFilter, countryFilter, router]);

  React.useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      if (initialQuery) void run(initialQuery, 1);
      return;
    }
    void run(state.query, 1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sort, typeFilter, categoryFilter, countryFilter]);

  const items = state.results.map((offer) => ({
    ...offer,
    bookmarked: bookmarks[offer.id] ?? offer.bookmarked,
  }));

  return (
    <div className="space-y-6">
      <header>
        <h1 className="sr-only">Search</h1>
        <SearchBar
          size="lg"
          defaultValue={state.query}
          onSubmitted={(value) => {
            setState((current) => ({ ...current, query: value }));
            void run(value, 1);
          }}
        />
      </header>

      {!state.query && !items.length ? (
        <EmptyState
          icon={<Wand2 className="size-5" />}
          title="What are you looking to save on?"
          description="Describe it the way you would to a friend — we understand free trials, credits, discounts, countries and student discounts."
          action={
            <div className="flex flex-wrap justify-center gap-1.5">
              {SUGGESTED.map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => {
                    setState((current) => ({ ...current, query: item }));
                    void run(item, 1);
                  }}
                  className="rounded-full border border-border px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:border-primary/40 hover:text-primary"
                >
                  {item}
                </button>
              ))}
            </div>
          }
        />
      ) : null}

      {trending.length && !state.query ? (
        <section className="rounded-xl border border-border bg-card/50 p-4">
          <h2 className="mb-2.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            <Flame className="size-3.5 text-warning" />
            Trending searches
          </h2>
          <div className="flex flex-wrap gap-1.5">
            {trending.map((item) => (
              <button
                key={item.query}
                type="button"
                onClick={() => {
                  setState((current) => ({ ...current, query: item.query }));
                  void run(item.query, 1);
                }}
                className="rounded-full border border-border px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
              >
                {item.query}
                <span className="ml-1.5 tabular-nums text-foreground/50">{item.searches}</span>
              </button>
            ))}
          </div>
        </section>
      ) : null}

      <AnimatePresence mode="wait">
        {state.intent ? (
          <motion.div
            key="intent"
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="flex flex-wrap items-center gap-2 rounded-lg border border-primary/25 bg-primary/[0.07] px-3 py-2"
          >
            <Sparkles className="size-3.5 shrink-0 text-primary" />
            <p className="flex-1 text-xs leading-relaxed text-foreground/85">
              {state.intent.explanation || `Showing ${state.total.toLocaleString()} offers.`}
            </p>
            {state.intent.offer_types.map((type) => (
              <Badge key={type}>{labelForOfferType(type)}</Badge>
            ))}
            {state.intent.category_slugs.map((slug) => {
              const category = categories.find((item) => item.slug === slug);
              return <Badge key={slug} variant="outline">{category?.name ?? slug}</Badge>;
            })}
            {state.intent.min_trial_days ? (
              <Badge variant="outline">{state.intent.min_trial_days}+ days</Badge>
            ) : null}
            {state.intent.max_price ? (
              <Badge variant="outline">under {state.intent.max_price}</Badge>
            ) : null}
            {state.intent.requires_payment_method === false ? (
              <Badge variant="success">No card needed</Badge>
            ) : null}
            <span className="text-[11px] tabular-nums text-muted-foreground">
              {state.tookMs}ms
            </span>
          </motion.div>
        ) : null}
      </AnimatePresence>

      {state.didYouMean ? (
        <p className="text-sm text-muted-foreground">
          Showing results for{" "}
          <button
            type="button"
            onClick={() => {
              setState((current) => ({ ...current, query: state.didYouMean! }));
              void run(state.didYouMean!, 1);
            }}
            className="font-medium text-primary underline-offset-2 hover:underline"
          >
            {state.didYouMean}
          </button>
          .{" "}
          <Link
            href={`/search?q=${encodeURIComponent(state.query)}`}
            className="underline-offset-2 hover:underline"
          >
            Search instead
          </Link>
          .
        </p>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
        <aside className="space-y-4">
          <div>
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Offer type
            </h2>
            <div className="flex flex-wrap gap-1.5 lg:flex-col lg:items-start">
              {offerTypes.map((type) => {
                const active = typeFilter.includes(type.value);
                return (
                  <button
                    key={type.value}
                    type="button"
                    onClick={() =>
                      setTypeFilter((current) =>
                        active
                          ? current.filter((item) => item !== type.value)
                          : [...current, type.value],
                      )
                    }
                    className={`rounded-full border px-2.5 py-1 text-xs transition-colors ${
                      active
                        ? "border-primary/50 bg-primary/15 text-primary"
                        : "border-border text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {type.label}
                    <span className="ml-1 tabular-nums opacity-60">{type.count}</span>
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Category
            </h2>
            <div className="flex flex-wrap gap-1.5 lg:flex-col lg:items-start">
              {categories
                .filter((category) => category.offer_count > 0)
                .slice(0, 10)
                .map((category) => {
                  const active = categoryFilter.includes(category.slug);
                  return (
                    <button
                      key={category.slug}
                      type="button"
                      onClick={() =>
                        setCategoryFilter((current) =>
                          active
                            ? current.filter((item) => item !== category.slug)
                            : [...current, category.slug],
                        )
                      }
                      className={`text-left text-xs transition-colors ${
                        active ? "text-primary" : "text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      {category.name}
                    </button>
                  );
                })}
            </div>
          </div>

          <div>
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Country
            </h2>
            <div className="flex flex-wrap gap-1.5">
              {countries.slice(0, 10).map((country) => {
                const active = countryFilter.includes(country.code);
                return (
                  <button
                    key={country.code}
                    type="button"
                    title={country.name}
                    onClick={() =>
                      setCountryFilter((current) =>
                        active
                          ? current.filter((item) => item !== country.code)
                          : [...current, country.code],
                      )
                    }
                    className={`rounded-md border px-1.5 py-0.5 text-xs transition-colors ${
                      active
                        ? "border-primary/50 bg-primary/15"
                        : "border-border hover:border-primary/40"
                    }`}
                  >
                    <span aria-hidden>{country.flag_emoji}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </aside>

        <div>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm text-muted-foreground">
              {loading ? "Searching…" : `${state.total.toLocaleString()} results`}
            </p>
            <select
              value={sort}
              onChange={(event) => setSort(event.target.value)}
              aria-label="Sort results"
              className="h-9 rounded-lg border border-border bg-background px-3 text-sm outline-none"
            >
              <option value="relevance">Best match</option>
              <option value="newest">Newest</option>
              <option value="popular">Most claimed</option>
              <option value="savings">Highest savings</option>
              <option value="ending_soon">Ending soon</option>
            </select>
          </div>

          {items.length === 0 ? (
            <EmptyState
              icon={<Compass className="size-5" />}
              title="Nothing matched that search"
              description="Try fewer words, a broader category, or one of the suggested searches above."
            />
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {loading && !items.length
                ? Array.from({ length: 6 }).map((_, index) => (
                    <OfferCardSkeleton key={index} />
                  ))
                : items.map((offer, index) => (
                    <OfferCard
                      key={offer.id}
                      offer={offer}
                      index={index}
                      onBookmarkChange={(id, value) =>
                        setBookmarks((current) => ({ ...current, [id]: value }))
                      }
                    />
                  ))}
            </div>
          )}

          {state.pages > 1 ? (
            <nav className="mt-8 flex justify-center gap-1.5" aria-label="Pagination">
              <button
                type="button"
                disabled={state.page <= 1}
                onClick={() => run(state.query, state.page - 1)}
                className="h-9 rounded-lg border border-border px-3 text-sm text-muted-foreground disabled:opacity-40"
              >
                Previous
              </button>
              <span className="flex h-9 items-center px-3 text-sm text-muted-foreground">
                {state.page} / {state.pages}
              </span>
              <button
                type="button"
                disabled={state.page >= state.pages}
                onClick={() => run(state.query, state.page + 1)}
                className="h-9 rounded-lg border border-border px-3 text-sm text-muted-foreground disabled:opacity-40"
              >
                Next
              </button>
            </nav>
          ) : null}
        </div>
      </div>
    </div>
  );
}