"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Loader2, Search, Sparkles, Tag, TrendingUp } from "lucide-react";
import { api } from "@/lib/api";
import type { SearchSuggestion } from "@/lib/types";
import { cn, labelForOfferType } from "@/lib/utils";

interface SearchBarProps {
  size?: "sm" | "lg";
  placeholder?: string;
  autoFocus?: boolean;
  defaultValue?: string;
  onSubmitted?: (query: string) => void;
  className?: string;
}

const EXAMPLES = [
  "30 days free VPN",
  "AI tools with free credits",
  "Free cloud hosting",
  "Free tools without a credit card",
];

/** The primary search experience: autocomplete, intent hints and typo recovery. */
export function SearchBar({
  size = "lg",
  placeholder = "Search deals, brands or tools…",
  autoFocus,
  defaultValue = "",
  onSubmitted,
  className,
}: SearchBarProps) {
  const router = useRouter();
  const [query, setQuery] = React.useState(defaultValue);
  const [suggestions, setSuggestions] = React.useState<SearchSuggestion[]>([]);
  const [open, setOpen] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  const [activeIndex, setActiveIndex] = React.useState(-1);
  const containerRef = React.useRef<HTMLDivElement>(null);
  const inputRef = React.useRef<HTMLInputElement>(null);

  // Debounced autocomplete — one request per pause, never per keystroke.
  React.useEffect(() => {
    const term = query.trim();
    if (term.length < 2) {
      setSuggestions([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      try {
        const results = await api.suggest(term, 8);
        setSuggestions(results);
        setActiveIndex(-1);
      } catch {
        setSuggestions([]);
      } finally {
        setLoading(false);
      }
    }, 180);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [query]);

  React.useEffect(() => {
    function onPointerDown(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  React.useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        inputRef.current?.focus();
        setOpen(true);
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const submit = React.useCallback(
    (value: string) => {
      const term = value.trim();
      if (!term) return;
      setOpen(false);
      inputRef.current?.blur();
      onSubmitted?.(term);
      router.push(`/search?q=${encodeURIComponent(term)}`);
    },
    [router, onSubmitted],
  );

  function onKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (!suggestions.length) {
      if (event.key === "Enter") submit(query);
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((index) => (index + 1) % suggestions.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((index) => (index <= 0 ? suggestions.length - 1 : index - 1));
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (activeIndex >= 0) {
        const picked = suggestions[activeIndex];
        if (picked.type === "category" && picked.slug) {
          setOpen(false);
          router.push(`/categories/${picked.slug}`);
          return;
        }
        if (picked.type === "brand" && picked.slug) {
          setOpen(false);
          router.push(`/offers?brand=${picked.slug}`);
          return;
        }
        if (picked.type === "offer" && picked.slug) {
          setOpen(false);
          router.push(`/offers/${picked.slug}`);
          return;
        }
        submit(picked.label);
        return;
      }
      submit(query);
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  }

  const showPanel = open && (query.trim().length > 0 || size === "lg");

  return (
    <div ref={containerRef} className={cn("relative w-full", className)}>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          submit(query);
        }}
        role="search"
      >
        <div
          className={cn(
            "relative flex items-center gap-2 rounded-xl border border-border bg-background/80 backdrop-blur transition-all",
            "focus-within:border-primary/50 focus-within:shadow-glow",
            size === "lg" ? "h-14 px-4" : "h-10 px-3",
          )}
        >
          {loading ? (
            <Loader2 className="size-4 shrink-0 animate-spin text-primary" />
          ) : (
            <Search className={cn("shrink-0 text-muted-foreground", size === "lg" && "size-5")} />
          )}
          <input
            ref={inputRef}
            type="search"
            value={query}
            autoFocus={autoFocus}
            onChange={(event) => {
              setQuery(event.target.value);
              setOpen(true);
            }}
            onFocus={() => setOpen(true)}
            onKeyDown={onKeyDown}
            placeholder={placeholder}
            aria-label="Search offers"
            aria-expanded={showPanel}
            aria-controls="search-suggestions"
            className={cn(
              "min-w-0 flex-1 bg-transparent outline-none placeholder:text-muted-foreground/70",
              size === "lg" ? "text-base" : "text-sm",
            )}
          />
          {query ? (
            <button
              type="button"
              onClick={() => {
                setQuery("");
                inputRef.current?.focus();
              }}
              className="rounded px-1 text-xs text-muted-foreground hover:text-foreground"
            >
              Clear
            </button>
          ) : null}
          <kbd className="hidden rounded border border-border bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground sm:inline-block">
            ⌘K
          </kbd>
          <button
            type="submit"
            className={cn(
              "hidden shrink-0 items-center gap-1.5 rounded-lg bg-primary px-4 font-medium text-primary-foreground transition-colors hover:bg-primary/90 sm:inline-flex",
              size === "lg" ? "h-10 text-sm" : "h-8 text-xs",
            )}
          >
            Search
            <ArrowRight className="size-3.5" />
          </button>
        </div>
      </form>

      <AnimatePresence>
        {showPanel ? (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.15 }}
            className="absolute inset-x-0 top-full z-50 mt-2 overflow-hidden rounded-xl border border-border bg-popover/97 shadow-2xl backdrop-blur"
          >
            {suggestions.length ? (
              <ul id="search-suggestions" className="max-h-[60vh] overflow-y-auto py-1.5">
                {suggestions.map((item, index) => (
                  <li key={`${item.type}-${item.id}`}>
                    <button
                      type="button"
                      onMouseEnter={() => setActiveIndex(index)}
                      onClick={() => {
                        if (item.type === "category" && item.slug) router.push(`/categories/${item.slug}`);
                        else if (item.type === "brand" && item.slug) router.push(`/offers?brand=${item.slug}`);
                        else if (item.type === "offer" && item.slug) router.push(`/offers/${item.slug}`);
                        else submit(item.label);
                        setOpen(false);
                      }}
                      className={cn(
                        "flex w-full items-center gap-3 px-3 py-2.5 text-left transition-colors",
                        activeIndex === index ? "bg-accent text-accent-foreground" : "hover:bg-accent/60",
                      )}
                    >
                      <SuggestionIcon type={item.type} offerType={item.offer_type ?? undefined} />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium">{item.label}</span>
                        {item.sublabel ? (
                          <span className="block truncate text-xs text-muted-foreground">
                            {item.sublabel}
                          </span>
                        ) : null}
                      </span>
                      <span className="shrink-0 text-[10px] uppercase tracking-wide text-muted-foreground">
                        {item.type}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="px-3 py-2.5">
                {loading ? (
                  <p className="text-xs text-muted-foreground">Searching…</p>
                ) : (
                  <>
                    <p className="mb-2 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                      <Sparkles className="size-3" />
                      Try one of these
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {EXAMPLES.map((example) => (
                        <button
                          key={example}
                          type="button"
                          onClick={() => {
                            setQuery(example);
                            submit(example);
                          }}
                          className="rounded-full border border-border bg-background px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
                        >
                          {example}
                        </button>
                      ))}
                    </div>
                  </>
                )}
              </div>
            )}
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}

function SuggestionIcon({
  type,
  offerType,
}: {
  type: SearchSuggestion["type"];
  offerType?: string;
}) {
  const base = "flex size-8 shrink-0 items-center justify-center rounded-lg border border-border bg-muted";
  if (type === "category") {
    return (
      <span className={base}>
        <Tag className="size-3.5 text-primary" />
      </span>
    );
  }
  if (type === "brand") {
    return (
      <span className={cn(base, "text-[10px] font-semibold uppercase")}>
        {offerType ? labelForOfferType(offerType).charAt(0) : "B"}
      </span>
    );
  }
  if (type === "query") {
    return (
      <span className={base}>
        <TrendingUp className="size-3.5 text-primary" />
      </span>
    );
  }
  return (
    <span className={base}>
      <Sparkles className="size-3.5 text-primary" />
    </span>
  );
}