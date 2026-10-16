"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowRight, Check, Mail, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import type { InterestTag } from "@/lib/types";
import { cn } from "@/lib/utils";

export function NewsletterCta({ interests = [] }: { interests?: InterestTag[] }) {
  const [email, setEmail] = React.useState("");
  const [selected, setSelected] = React.useState<string[]>([]);
  const [status, setStatus] = React.useState<"idle" | "loading" | "done">("idle");
  const { toast } = useToast();

  async function subscribe(event: React.FormEvent) {
    event.preventDefault();
    if (!email) return;
    setStatus("loading");
    try {
      const result = await api.subscribeNewsletter({
        email,
        interests: selected,
        frequency: "weekly",
      });
      setStatus("done");
      toast({
        title: result.already_subscribed ? "Already on the list" : "You're subscribed",
        description: result.message,
        tone: "success",
      });
    } catch (error) {
      setStatus("idle");
      toast({
        title: "Could not subscribe",
        description: error instanceof Error ? error.message : "Please try again.",
        tone: "error",
      });
    }
  }

  return (
    <section className="relative overflow-hidden rounded-2xl border border-primary/25 bg-gradient-to-br from-primary/[0.13] via-card to-card p-6 sm:p-8">
      <div
        className="pointer-events-none absolute -right-20 -top-24 size-72 rounded-full bg-primary/20 blur-3xl"
        aria-hidden
      />
      <div className="relative grid gap-6 lg:grid-cols-[1.2fr_1fr] lg:items-center">
        <div>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-primary/30 bg-primary/10 px-2.5 py-1 text-[11px] font-medium text-primary">
            <Mail className="size-3" />
            Deal digest
          </span>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight">
            Get the best deals before they expire
          </h2>
          <p className="mt-2 max-w-lg text-sm leading-relaxed text-muted-foreground">
            One short email a week: new trials, limited-time credits and the offers about to end.
            Unsubscribe in one click, and we never ask for payment details.
          </p>
          <div className="mt-4 flex items-center gap-2 text-xs text-muted-foreground">
            <ShieldCheck className="size-3.5 text-primary" />
            No spam · no affiliate spam · unsubscribe anytime
          </div>
        </div>

        <div>
          <form onSubmit={subscribe} className="space-y-3">
            <div className="flex flex-col gap-2 sm:flex-row">
              <Input
                type="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@example.com"
                aria-label="Email address"
                className="h-11 flex-1"
                disabled={status === "done"}
              />
              <Button type="submit" size="lg" disabled={status === "loading" || status === "done"}>
                {status === "done" ? (
                  <>
                    <Check className="size-4" /> Subscribed
                  </>
                ) : status === "loading" ? (
                  "Subscribing…"
                ) : (
                  <>
                    Subscribe <ArrowRight className="size-4" />
                  </>
                )}
              </Button>
            </div>

            {interests.length ? (
              <div className="flex flex-wrap gap-1.5">
                {interests.slice(0, 8).map((interest) => {
                  const active = selected.includes(interest.slug);
                  return (
                    <button
                      key={interest.slug}
                      type="button"
                      onClick={() =>
                        setSelected((current) =>
                          active
                            ? current.filter((item) => item !== interest.slug)
                            : [...current, interest.slug],
                        )
                      }
                      className={cn(
                        "rounded-full border px-2.5 py-1 text-xs transition-colors",
                        active
                          ? "border-primary/50 bg-primary/15 text-primary"
                          : "border-border text-muted-foreground hover:text-foreground",
                      )}
                    >
                      {interest.label}
                    </button>
                  );
                })}
              </div>
            ) : null}
          </form>
        </div>
      </div>
    </section>
  );
}

export function TrustStrip() {
  const items = [
    {
      icon: ShieldCheck,
      title: "Automatic re-checking",
      body: "Every offer is re-verified against its official page on a schedule. Broken links and price changes surface automatically.",
    },
    {
      icon: Check,
      title: "Eligibility up front",
      body: "Country limits, student requirements, new-user rules and whether a card is needed are shown before you click.",
    },
    {
      icon: ArrowRight,
      title: "Free vs free trial",
      body: "We label genuinely free products separately from trials that silently convert into a paid subscription.",
    },
  ];
  return (
    <section className="grid gap-4 sm:grid-cols-3">
      {items.map((item) => (
        <div key={item.title} className="rounded-xl border border-border bg-card/60 p-5">
          <item.icon className="size-5 text-primary" />
          <h3 className="mt-3 text-sm font-semibold">{item.title}</h3>
          <p className="mt-1.5 text-[13px] leading-relaxed text-muted-foreground">{item.body}</p>
        </div>
      ))}
    </section>
  );
}

export function CategoryGrid({
  categories,
}: {
  categories: { slug: string; name: string; tagline?: string | null; offer_count: number }[];
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {categories.map((category) => (
        <Link
          key={category.slug}
          href={`/categories/${category.slug}`}
          className="group flex items-start justify-between gap-3 rounded-xl border border-border bg-card/60 p-4 transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:bg-accent/40"
        >
          <div className="min-w-0">
            <h3 className="truncate text-sm font-semibold transition-colors group-hover:text-primary">
              {category.name}
            </h3>
            {category.tagline ? (
              <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-muted-foreground">
                {category.tagline}
              </p>
            ) : null}
          </div>
          <span className="shrink-0 rounded-full border border-border bg-background/60 px-2 py-0.5 text-[11px] tabular-nums text-muted-foreground">
            {category.offer_count}
          </span>
        </Link>
      ))}
    </div>
  );
}