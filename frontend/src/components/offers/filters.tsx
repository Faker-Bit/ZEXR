"use client";

import * as React from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { SlidersHorizontal, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Accordion, Checkbox, Switch } from "@/components/ui/primitives";
import { Sheet } from "@/components/ui/overlays";
import { Input, Label } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import type { Category, CountryBrief, Facets, OfferTypeMeta } from "@/lib/types";

export interface DirectoryFilters {
  q: string;
  category: string[];
  brand: string[];
  type: string[];
  country_codes: string[];
  duration: string;
  min_trial_days: string;
  max_price: string;
  min_savings: string;
  requires_payment_method: boolean | null;
  requires_student_id: boolean;
  verified_only: boolean;
  global_only: boolean;
  ending_within_days: string;
  sort: string;
}

export const DEFAULT_FILTERS: DirectoryFilters = {
  q: "",
  category: [],
  brand: [],
  type: [],
  country_codes: [],
  duration: "",
  min_trial_days: "",
  max_price: "",
  min_savings: "",
  requires_payment_method: null,
  requires_student_id: false,
  verified_only: false,
  global_only: false,
  ending_within_days: "",
  sort: "relevance",
};

/** Read the active filters out of the query string. */
export function filtersFromParams(params: URLSearchParams): DirectoryFilters {
  const list = (key: string) =>
    params.getAll(key).flatMap((value) => value.split(",")).filter(Boolean);
  return {
    ...DEFAULT_FILTERS,
    q: params.get("q") ?? "",
    category: list("category"),
    brand: list("brand"),
    type: list("type"),
    country_codes: list("country") ?? list("country_codes"),
    duration: params.get("duration") ?? "",
    min_trial_days: params.get("min_trial_days") ?? "",
    max_price: params.get("max_price") ?? "",
    min_savings: params.get("min_savings") ?? "",
    requires_payment_method:
      params.get("requires_payment_method") === null
        ? null
        : params.get("requires_payment_method") === "true",
    requires_student_id: params.get("requires_student_id") === "true",
    verified_only: params.get("verified_only") === "true",
    global_only: params.get("global_only") === "true",
    ending_within_days: params.get("ending_within_days") ?? "",
    sort: params.get("sort") ?? "relevance",
  };
}

export function filtersToParams(filters: DirectoryFilters): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.q) params.set("q", filters.q);
  for (const key of ["category", "brand", "type", "country_codes"] as const) {
    for (const value of filters[key]) params.append(key, value);
  }
  for (const key of [
    "duration",
    "min_trial_days",
    "max_price",
    "min_savings",
    "ending_within_days",
  ] as const) {
    if (filters[key]) params.set(key, String(filters[key]));
  }
  if (filters.requires_payment_method !== null) {
    params.set("requires_payment_method", String(filters.requires_payment_method));
  }
  if (filters.requires_student_id) params.set("requires_student_id", "true");
  if (filters.verified_only) params.set("verified_only", "true");
  if (filters.global_only) params.set("global_only", "true");
  if (filters.sort && filters.sort !== "relevance") params.set("sort", filters.sort);
  return params;
}

export function countActiveFilters(filters: DirectoryFilters): number {
  return (
    filters.category.length +
    filters.brand.length +
    filters.type.length +
    filters.country_codes.length +
    (filters.duration ? 1 : 0) +
    (filters.min_trial_days ? 1 : 0) +
    (filters.max_price ? 1 : 0) +
    (filters.min_savings ? 1 : 0) +
    (filters.ending_within_days ? 1 : 0) +
    (filters.requires_payment_method !== null ? 1 : 0) +
    (filters.requires_student_id ? 1 : 0) +
    (filters.verified_only ? 1 : 0) +
    (filters.global_only ? 1 : 0)
  );
}

interface FilterPanelProps {
  categories: Category[];
  countries: CountryBrief[];
  offerTypes: OfferTypeMeta[];
  facets?: Facets | null;
}

export function FilterPanel({
  filters,
  onChange,
  categories,
  countries,
  offerTypes,
  facets,
  className,
}: FilterPanelProps & { filters: DirectoryFilters; onChange: (next: DirectoryFilters) => void; className?: string }) {
  const set = React.useCallback(
    (patch: Partial<DirectoryFilters>) => onChange({ ...filters, ...patch }),
    [filters, onChange],
  );

  const toggleIn = (key: "category" | "brand" | "type" | "country_codes", value: string) => {
    const current = filters[key];
    set({
      [key]: current.includes(value)
        ? current.filter((item) => item !== value)
        : [...current, value],
    } as Partial<DirectoryFilters>);
  };

  return (
    <div className={cn("space-y-1", className)}>
      <Accordion title="Offer type" defaultOpen badge={filters.type.length ? <Badge>{filters.type.length}</Badge> : null}>
        <div className="space-y-2.5">
          {offerTypes.map((type) => (
            <Checkbox
              key={type.value}
              id={`type-${type.value}`}
              checked={filters.type.includes(type.value)}
              onCheckedChange={() => toggleIn("type", type.value)}
              label={type.label}
              count={type.count}
            />
          ))}
        </div>
      </Accordion>

      <Accordion title="Category" defaultOpen badge={filters.category.length ? <Badge>{filters.category.length}</Badge> : null}>
        <div className="max-h-64 space-y-2.5 overflow-y-auto pr-1">
          {categories
            .filter((category) => category.offer_count > 0 || filters.category.includes(category.slug))
            .map((category) => (
              <Checkbox
                key={category.slug}
                id={`cat-${category.slug}`}
                checked={filters.category.includes(category.slug)}
                onCheckedChange={() => toggleIn("category", category.slug)}
                label={category.name}
                count={category.offer_count}
              />
            ))}
        </div>
      </Accordion>

      <Accordion title="Price &amp; duration">
        <div className="space-y-4">
          <div>
            <Label htmlFor="max_price">Maximum price</Label>
            <div className="mt-1.5 flex items-center gap-2">
              <Input
                id="max_price"
                type="number"
                min={0}
                inputMode="decimal"
                placeholder="Any"
                value={filters.max_price}
                onChange={(event) => set({ max_price: event.target.value })}
                className="h-9"
              />
              <div className="flex gap-1">
                {[0, 5, 10, 25].map((value) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => set({ max_price: value === 0 ? "" : String(value) })}
                    className={cn(
                      "rounded-md border px-1.5 py-1 text-[11px] transition-colors",
                      filters.max_price === String(value)
                        ? "border-primary/50 bg-primary/10 text-primary"
                        : "border-border text-muted-foreground hover:text-foreground",
                    )}
                  >
                    {value === 0 ? "Free" : `$${value}`}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div>
            <Label htmlFor="min_trial_days">Minimum trial length</Label>
            <div className="mt-1.5 flex flex-wrap gap-1">
              {["", "7", "14", "30", "90", "182"].map((value) => (
                <button
                  key={value || "any"}
                  type="button"
                  onClick={() => set({ min_trial_days: value })}
                  className={cn(
                    "rounded-md border px-2 py-1 text-[11px] transition-colors",
                    filters.min_trial_days === value
                      ? "border-primary/50 bg-primary/10 text-primary"
                      : "border-border text-muted-foreground hover:text-foreground",
                  )}
                >
                  {value ? `${value}d+` : "Any"}
                </button>
              ))}
            </div>
          </div>
        </div>
      </Accordion>

      <Accordion title="Availability" defaultOpen>
        <div className="space-y-3">
          <ToggleRow
            id="global_only"
            label="Worldwide only"
            checked={filters.global_only}
            onChange={(value) => set({ global_only: value })}
          />
          <ToggleRow
            id="no_card"
            label="No credit card required"
            checked={filters.requires_payment_method === false}
            onChange={(value) => set({ requires_payment_method: value ? false : null })}
          />
          <ToggleRow
            id="with_card"
            label="Credit card required"
            checked={filters.requires_payment_method === true}
            onChange={(value) => set({ requires_payment_method: value ? true : null })}
          />
          <ToggleRow
            id="students"
            label="Students only"
            checked={filters.requires_student_id}
            onChange={(value) => set({ requires_student_id: value })}
          />
          <ToggleRow
            id="verified"
            label="Verified only"
            checked={filters.verified_only}
            onChange={(value) => set({ verified_only: value })}
          />
        </div>
      </Accordion>

      <Accordion title="Ending soon">
        <div className="flex flex-wrap gap-1">
          {["", "1", "3", "7", "30"].map((value) => (
            <button
              key={value || "any"}
              type="button"
              onClick={() => set({ ending_within_days: value })}
              className={cn(
                "rounded-md border px-2 py-1 text-[11px] transition-colors",
                filters.ending_within_days === value
                  ? "border-primary/50 bg-primary/10 text-primary"
                  : "border-border text-muted-foreground hover:text-foreground",
              )}
            >
              {value ? `Within ${value}d` : "Any time"}
            </button>
          ))}
        </div>
      </Accordion>

      <Accordion title="Country" badge={filters.country_codes.length ? <Badge>{filters.country_codes.length}</Badge> : null}>
        <div className="max-h-56 space-y-2.5 overflow-y-auto pr-1">
          {countries.slice(0, 40).map((country) => (
            <Checkbox
              key={country.code}
              id={`country-${country.code}`}
              checked={filters.country_codes.includes(country.code)}
              onCheckedChange={() => toggleIn("country_codes", country.code)}
              label={
                <span className="flex items-center gap-1.5">
                  <span aria-hidden>{country.flag_emoji}</span>
                  {country.name}
                </span>
              }
            />
          ))}
        </div>
      </Accordion>
    </div>
  );
}

function ToggleRow({
  id,
  label,
  checked,
  onChange,
}: {
  id: string;
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <Label htmlFor={id} className="cursor-pointer text-[13px] font-normal text-foreground/85">
        {label}
      </Label>
      <Switch id={id} checked={checked} onCheckedChange={onChange} />
    </div>
  );
}

function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-full bg-primary/15 px-1.5 py-0.5 text-[10px] font-semibold text-primary">
      {children}
    </span>
  );
}

const SORT_OPTIONS = [
  { value: "relevance", label: "Best match" },
  { value: "newest", label: "Newest first" },
  { value: "trending", label: "Trending" },
  { value: "popular", label: "Most claimed" },
  { value: "savings", label: "Highest savings" },
  { value: "value", label: "Best value" },
  { value: "ending_soon", label: "Ending soon" },
  { value: "price_asc", label: "Price: low to high" },
  { value: "price_desc", label: "Price: high to low" },
];

export function SortSelect({
  value,
  onChange,
  className,
}: {
  value: string;
  onChange: (value: string) => void;
  className?: string;
}) {
  return (
    <select
      value={value}
      onChange={(event) => onChange(event.target.value)}
      aria-label="Sort results"
      className={cn(
        "h-9 rounded-lg border border-border bg-background px-3 text-sm outline-none transition-colors hover:border-primary/40 focus:border-primary/60",
        className,
      )}
    >
      {SORT_OPTIONS.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
}

/** Mobile drawer trigger + panel. */
export function MobileFilters(props: FilterPanelProps & { filters: DirectoryFilters; onChange: (next: DirectoryFilters) => void }) {
  const [open, setOpen] = React.useState(false);
  const active = countActiveFilters(props.filters);

  return (
    <>
      <Button variant="outline" size="sm" onClick={() => setOpen(true)} className="lg:hidden">
        <SlidersHorizontal className="size-3.5" />
        Filters
        {active ? (
          <span className="rounded-full bg-primary px-1.5 text-[10px] font-semibold text-primary-foreground">
            {active}
          </span>
        ) : null}
      </Button>
      <Sheet open={open} onClose={() => setOpen(false)} title="Filters" side="left">
        <div className="p-4">
          <FilterPanel {...props} />
          <Button className="mt-4 w-full" onClick={() => setOpen(false)}>
            Show results
          </Button>
        </div>
      </Sheet>
    </>
  );
}

/** Chips summarising the active filters, each removable. */
export function ActiveFilterChips({
  filters,
  labels,
  onChange,
}: {
  filters: DirectoryFilters;
  labels: { categories: Record<string, string>; types: Record<string, string>; countries: Record<string, string> };
  onChange: (next: DirectoryFilters) => void;
}) {
  const chips: { key: string; text: string; clear: () => void }[] = [];

  for (const slug of filters.category) {
    chips.push({
      key: `cat-${slug}`,
      text: labels.categories[slug] ?? slug,
      clear: () => onChange({ ...filters, category: filters.category.filter((item) => item !== slug) }),
    });
  }
  for (const type of filters.type) {
    chips.push({
      key: `type-${type}`,
      text: labels.types[type] ?? type,
      clear: () => onChange({ ...filters, type: filters.type.filter((item) => item !== type) }),
    });
  }
  for (const code of filters.country_codes) {
    chips.push({
      key: `country-${code}`,
      text: labels.countries[code] ?? code,
      clear: () =>
        onChange({
          ...filters,
          country_codes: filters.country_codes.filter((item) => item !== code),
        }),
    });
  }
  if (filters.verified_only) {
    chips.push({ key: "verified", text: "Verified only", clear: () => onChange({ ...filters, verified_only: false }) });
  }
  if (filters.global_only) {
    chips.push({ key: "global", text: "Worldwide", clear: () => onChange({ ...filters, global_only: false }) });
  }
  if (filters.requires_payment_method !== null) {
    chips.push({
      key: "card",
      text: filters.requires_payment_method ? "Card required" : "No card needed",
      clear: () => onChange({ ...filters, requires_payment_method: null }),
    });
  }
  if (filters.requires_student_id) {
    chips.push({ key: "student", text: "Students only", clear: () => onChange({ ...filters, requires_student_id: false }) });
  }
  if (filters.max_price) {
    chips.push({ key: "max", text: `Under $${filters.max_price}`, clear: () => onChange({ ...filters, max_price: "" }) });
  }
  if (filters.min_trial_days) {
    chips.push({
      key: "trial",
      text: `${filters.min_trial_days}+ days`,
      clear: () => onChange({ ...filters, min_trial_days: "" }),
    });
  }
  if (filters.ending_within_days) {
    chips.push({
      key: "ending",
      text: `Ends within ${filters.ending_within_days}d`,
      clear: () => onChange({ ...filters, ending_within_days: "" }),
    });
  }
  if (filters.duration) {
    chips.push({ key: "duration", text: filters.duration, clear: () => onChange({ ...filters, duration: "" }) });
  }

  if (!chips.length) return null;

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {chips.map((chip) => (
        <button
          key={chip.key}
          type="button"
          onClick={chip.clear}
          className="group inline-flex items-center gap-1 rounded-full border border-border bg-background/70 px-2.5 py-1 text-xs text-foreground/85 transition-colors hover:border-destructive/40 hover:text-destructive"
        >
          {chip.text}
          <X className="size-3 opacity-50 group-hover:opacity-100" />
        </button>
      ))}
      <button
        type="button"
        onClick={() => onChange({ ...DEFAULT_FILTERS, q: filters.q, sort: filters.sort })}
        className="px-2 py-1 text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
      >
        Clear all
      </button>
    </div>
  );
}