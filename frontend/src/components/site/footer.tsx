import Link from "next/link";
import { ExternalLink, ShieldCheck, Sparkles } from "lucide-react";
import { Logo } from "./logo";
import type { Category } from "@/lib/types";

const FOOTER_GROUPS = [
  {
    title: "Explore",
    links: [
      { href: "/offers", label: "All offers" },
      { href: "/offers?type=free", label: "Genuinely free" },
      { href: "/offers?type=free_trial", label: "Free trials" },
      { href: "/offers?type=free_credits", label: "Free credits" },
      { href: "/offers?type=coupon", label: "Coupon codes" },
      { href: "/offers?ending_within_days=3", label: "Ending soon" },
    ],
  },
  {
    title: "Popular categories",
    links: [
      { href: "/categories/ai-tools", label: "AI tools" },
      { href: "/categories/software-productivity", label: "Software" },
      { href: "/categories/cloud-hosting", label: "Cloud hosting" },
      { href: "/categories/vpn-security-privacy", label: "VPNs & privacy" },
      { href: "/categories/streaming-entertainment", label: "Streaming" },
      { href: "/categories/education-learning", label: "Learning" },
    ],
  },
  {
    title: "Platform",
    links: [
      { href: "/how-it-works", label: "How verification works" },
      { href: "/trust-and-safety", label: "Trust & safety" },
      { href: "/submit", label: "Submit a deal" },
      { href: "/expired", label: "Recently expired" },
      { href: "/about", label: "About" },
    ],
  },
  {
    title: "Legal",
    links: [
      { href: "/privacy", label: "Privacy" },
      { href: "/terms", label: "Terms" },
      { href: "/affiliate-disclosure", label: "Affiliate disclosure" },
    ],
  },
];

export function Footer({ categories }: { categories: Category[] }) {
  const year = new Date().getFullYear();
  const topCategories = categories.filter((category) => category.offer_count > 0).slice(0, 10);

  return (
    <footer className="mt-20 border-t border-border bg-card/30">
      <div className="container py-12">
        <div className="grid gap-10 lg:grid-cols-[1.4fr_2.6fr]">
          <div>
            <Logo />
            <p className="mt-4 max-w-sm text-sm leading-relaxed text-muted-foreground">
              A global, continuously verified catalogue of free trials, discounts, free credits and
              genuinely free tools — with eligibility details spelled out before you click.
            </p>
            <div className="mt-5 flex items-start gap-2.5 rounded-lg border border-border bg-background/60 p-3">
              <ShieldCheck className="mt-0.5 size-4 shrink-0 text-primary" />
              <p className="text-xs leading-relaxed text-muted-foreground">
                We never fabricate an offer. Anything we cannot check automatically is labelled
                <span className="mx-1 font-medium text-foreground">needs manual verification</span>
                instead of being presented as verified.
              </p>
            </div>
          </div>

          <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {FOOTER_GROUPS.map((group) => (
              <div key={group.title}>
                <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                  {group.title}
                </h2>
                <ul className="space-y-2">
                  {group.links.map((link) => (
                    <li key={link.href}>
                      <Link
                        href={link.href}
                        className="text-sm text-foreground/80 transition-colors hover:text-primary"
                      >
                        {link.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        {topCategories.length ? (
          <div className="mt-10 border-t border-border pt-6">
            <h2 className="mb-3 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
              <Sparkles className="size-3" />
              Trending categories
            </h2>
            <div className="flex flex-wrap gap-1.5">
              {topCategories.map((category) => (
                <Link
                  key={category.slug}
                  href={`/categories/${category.slug}`}
                  className="rounded-full border border-border px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
                >
                  {category.name}
                  <span className="ml-1.5 tabular-nums text-foreground/60">
                    {category.offer_count}
                  </span>
                </Link>
              ))}
            </div>
          </div>
        ) : null}
      </div>

      <div className="border-t border-border">
        <div className="container flex flex-col items-start justify-between gap-3 py-5 text-xs text-muted-foreground sm:flex-row sm:items-center">
          <p>
            © {year} ZEXR Deal Hub. Demo content is clearly labelled and never presented as a live
            verified offer.
          </p>
          <div className="flex flex-wrap items-center gap-4">
            <Link href="/trust-and-safety" className="hover:text-foreground">
              Verification policy
            </Link>
            <Link href="/affiliate-disclosure" className="hover:text-foreground">
              How we make money
            </Link>
            <a
              href="https://github.com"
              target="_blank"
              rel="noopener noreferrer nofollow"
              className="inline-flex items-center gap-1 hover:text-foreground"
            >
              Open source <ExternalLink className="size-3" />
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}