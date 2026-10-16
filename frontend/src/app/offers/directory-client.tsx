"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { EmptyState } from "@/components/ui/empty-state";
import { OfferCard, OfferCardSkeleton } from "@/components/offers/offer-card";
import {
  ActiveFilterChips,
  FilterPanel,
  MobileFilters,
  SortSelect,
  countActiveFilters,
  filtersFromParams,
  filtersToParams,
  DEFAULT_FILTERS,
  type DirectoryFilters,
} from "@/components/offers/filters";
import type { Category, CountryBrief, OfferCard as OfferCardType, OfferTypeMeta, Page } from "@/lib/types";

interface DirectoryClientProps {
  initialPage: Page<OfferCardType>;
  categories: Category[];
  countries: CountryBrief[];
  offerTypes: OfferTypeMeta[];
}

/** Client-side directory: filters, sorting and pagination over the live API. */
export function DirectoryClient({
  initialPage,
  categories,
  countries,
  offerTypes,
}: DirectoryClientProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [page, setPage] = React.useState(initialPage);
  const [loading, setLoading] = React.useState(false);
  const [filters, setFilters] = React.useState<DirectoryFilters>(() =>
    filtersFromParams(new URLSearchParams(searchParams.toString())),
  );
  const [bookmarks, setBookmarks] = React.useState<Record<string, boolean>>({});
  const [pageNumber, setPageNumber] = React.useState(initialPage.page);
  const firstRender = React.useRef(true);

  const labels = React.useMemo(
    () => ({
      categories: Object.fromEntries(categories.map((item) => [item.slug, item.name])),
      types: Object.fromEntries(offerTypes.map((item) => [item.value, item.label])),
      countries: Object.fromEntries(countries.map((item) => [item.code, item.name])),
    }),
    [categories, offerTypes, countries],
  );

  const load = React.useCallback(async (active: DirectoryFilters, nextPage: number) => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = {};
      for (const [key, value] of Object.entries(active)) {
        if (value === "" || value === null || value === false) continue;
        if (Array.isArray(value) && !value.length) continue;
        params[key] = value;
      }
      params.page = nextPage;
      params.page_size = 24;
      if (!active.q && active.sort === "relevance") params.sort = "popular";
      const result = await api.offers(params);
      setPage(result);
      setPageNumber(nextPage);
    } catch {
      /* keep the previous page visible */
    } finally {
      setLoading(false);
    }
  }, []);

  // Debounce navigation so typing in a filter box does not spam the router.
  React.useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    const timer = window.setTimeout(() => {
      const params = filtersToParams(filters);
      if (!params.toString()) router.replace("/offers");
      else router.replace(`/offers?${params.toString()}`, { scroll: false });
      void load(filters, 1);
    }, 220);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters, load]);

  // Respond to browser back/forward by re-reading the URL.
  React.useEffect(() => {
    const handler = () => {
      setFilters(filtersFromParams(new URLSearchParams(window.location.search)));
    };
    window.addEventListener("popstate", handler);
    return () => window.removeEventListener("popstate", handler);
  }, []);

  const items = page.items.map((offer) => ({
    ...offer,
    bookmarked: bookmarks[offer.id] ?? offer.bookmarked,
  }));

  return (
    <div className="grid gap-6 lg:grid-cols-[248px_1fr]">
      <aside className="hidden lg:block">
        <div className="sticky top-24 max-h-[calc(100dvh-7rem)] overflow-y-auto pr-1">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold">Filters</h2>
            {countActiveFilters(filters) ? (
              <button
                type="button"
                onClick={() => setFilters({ ...DEFAULT_FILTERS, sort: filters.sort })}
                className="text-xs text-muted-foreground hover:text-foreground"
              >
                Reset
              </button>
            ) : null}
          </div>
          <FilterPanel
            filters={filters}
            onChange={setFilters}
            categories={categories}
            countries={countries}
            offerTypes={offerTypes}
          />
        </div>
      </aside>

      <div>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-muted-foreground">
            {loading ? "Updating…" : `${page.total.toLocaleString()} offers`}
          </p>
          <div className="flex items-center gap-2">
            <MobileFilters
              filters={filters}
              onChange={setFilters}
              categories={categories}
              countries={countries}
              offerTypes={offerTypes}
            />
            <SortSelect
              value={filters.sort}
              onChange={(value) => setFilters({ ...filters, sort: value })}
            />
          </div>
        </div>

        <div className="mb-4">
          <ActiveFilterChips filters={filters} labels={labels} onChange={setFilters} />
        </div>

        {items.length === 0 ? (
          <EmptyState
            title="No offers match those filters"
            description="Try removing a filter, widening the country list, or searching for something broader."
            action={
              <button
                type="button"
                onClick={() => setFilters({ ...DEFAULT_FILTERS, q: filters.q })}
                className="inline-flex h-10 items-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground"
              >
                Clear filters
              </button>
            }
          />
        ) : (
          <div
            className={`grid gap-3 transition-opacity sm:grid-cols-2 xl:grid-cols-3 ${
              loading ? "opacity-60" : "opacity-100"
            }`}
          >
            {loading && page.items.length === 0
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

        {page.pages > 1 ? (
          <nav className="mt-8 flex items-center justify-center gap-1.5" aria-label="Pagination">
            <PaginationButton
              disabled={!page.has_prev}
              onClick={() => load(filters, pageNumber - 1)}
              label="Previous"
            />
            {Array.from({ length: Math.min(page.pages, 7) }).map((_, index) => {
              const start = Math.max(1, Math.min(pageNumber - 3, page.pages - 6));
              const value = start + index;
              if (value > page.pages) return null;
              const active = value === pageNumber;
              return (
                <button
                  key={value}
                  type="button"
                  onClick={() => load(filters, value)}
                  aria-current={active ? "page" : undefined}
                  className={`h-9 min-w-9 rounded-lg border px-3 text-sm transition-colors ${
                    active
                      ? "border-primary/50 bg-primary/15 text-primary"
                      : "border-border text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {value}
                </button>
              );
            })}
            <PaginationButton
              disabled={!page.has_next}
              onClick={() => load(filters, pageNumber + 1)}
              label="Next"
            />
          </nav>
        ) : null}

        <p className="mt-6 text-xs leading-relaxed text-muted-foreground">
          Showing offer types:{" "}
          {offerTypes.map((type) => type.label).join(", ") || "all"}.
        </p>
      </div>
    </div>
  );
}

function PaginationButton({
  children,
  disabled,
  onClick,
  label,
}: {
  children?: React.ReactNode;
  disabled: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      aria-label={label}
      className="h-9 rounded-lg border border-border px-3 text-sm text-muted-foreground transition-colors hover:text-foreground disabled:opacity-40"
    >
      {children ?? label}
    </button>
  );
}
