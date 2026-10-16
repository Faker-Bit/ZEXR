import Link from "next/link";
import {
  ArrowRight,
  Ban,
  CheckCircle2,
  FileSearch,
  Flag,
  Lock,
  RefreshCw,
  Scale,
  ShieldCheck,
  Tags,
} from "lucide-react";
import { pageMetadata } from "@/lib/seo";
import { Button } from "@/components/ui/button";

export const metadata = pageMetadata({
  title: "How verification works",
  description:
    "How ZEXR Deal Hub discovers, verifies and expires offers: HTTP checks, price comparison, eligibility extraction, anti-bot detection and human review.",
  path: "/how-it-works",
});

const STEPS = [
  {
    icon: FileSearch,
    title: "Discovery",
    body: "A background worker reads permitted sources — official RSS feeds, partner and affiliate APIs, and public offer index pages. robots.txt is always honoured, request rates are capped per source and per host, and nothing that requires JavaScript or a login is ever fetched.",
  },
  {
    icon: Tags,
    title: "Normalisation",
    body: "Each item is classified (free, free trial, free credits, discount, coupon, cashback, free alternative). Prices, durations, coupon codes and eligibility rules are only extracted when they appear verbatim in the source. Anything missing stays missing — we never fill in a guess.",
  },
  {
    icon: RefreshCw,
    title: "Verification",
    body: "We re-open the official page on a schedule. A successful fetch must also contain the offer's own fingerprint terms, otherwise it is treated as changed rather than verified. Prices are compared against what we recorded, and only material differences are flagged.",
  },
  {
    icon: CheckCircle2,
    title: "Trust labelling",
    body: "An offer is only marked verified when we actually reached the page. Anything we cannot check automatically is labelled 'needs manual verification' — we never dress up an unverified listing as a confirmed deal.",
  },
  {
    icon: Ban,
    title: "Expiry",
    body: "Offers past their deadline move to the recently-expired archive automatically. Repeated link failures move a listing to expired and it stops appearing in search and on category pages.",
  },
  {
    icon: Flag,
    title: "Community review",
    body: "Anyone can report an expired, misleading or fraudulent listing. Reports mark the offer as disputed, which pulls it out of the 'live' set until a reviewer resolves it.",
  },
];

const STATES = [
  { name: "Verified", tone: "success", body: "We reached the official page and the content still matches." },
  { name: "Needs manual verification", tone: "muted", body: "Could not check automatically (login, paywall or JavaScript). A human confirms it." },
  { name: "Unverified", tone: "muted", body: "Newly discovered or submitted. Never labelled as confirmed." },
  { name: "Disputed", tone: "warning", body: "A report or an automated check found a mismatch. Removed from live results." },
  { name: "Expired", tone: "destructive", body: "Past its deadline, or repeatedly unreachable. Archived separately from live deals." },
];

export default function HowItWorksPage() {
  return (
    <div className="container max-w-4xl py-10">
      <header className="mb-10">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-primary/25 bg-primary/10 px-2.5 py-1 text-[11px] font-medium text-primary">
          <ShieldCheck className="size-3" />
          Verification policy
        </span>
        <h1 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
          How verification works
        </h1>
        <p className="mt-3 text-base leading-relaxed text-muted-foreground">
          A deals site lives or dies on trust. This page documents exactly what we check, what we
          refuse to guess, and how an offer moves through its lifecycle.
        </p>
      </header>

      <section className="mb-12 space-y-4">
        {STEPS.map((step, index) => (
          <div key={step.title} className="flex gap-4 rounded-xl border border-border bg-card/50 p-5">
            <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/15">
              <step.icon className="size-4 text-primary" />
            </div>
            <div>
              <h2 className="text-sm font-semibold">
                <span className="mr-1.5 text-primary">{index + 1}.</span>
                {step.title}
              </h2>
              <p className="mt-1.5 text-[13px] leading-relaxed text-muted-foreground">{step.body}</p>
            </div>
          </div>
        ))}
      </section>

      <section className="mb-12">
        <h2 className="mb-4 text-lg font-semibold tracking-tight">What each status means</h2>
        <div className="overflow-hidden rounded-xl border border-border">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-4 py-2.5 font-medium">Status</th>
                <th className="px-4 py-2.5 font-medium">Meaning</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {STATES.map((state) => (
                <tr key={state.name}>
                  <td className="whitespace-nowrap px-4 py-3">
                    <span
                      className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                        state.tone === "success"
                          ? "bg-success/15 text-success"
                          : state.tone === "warning"
                            ? "bg-warning/15 text-warning"
                            : state.tone === "destructive"
                              ? "bg-destructive/15 text-destructive"
                              : "bg-muted text-muted-foreground"
                      }`}
                    >
                      {state.name}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{state.body}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mb-12 grid gap-4 sm:grid-cols-2">
        <div className="rounded-xl border border-border bg-card/50 p-5">
          <Lock className="size-5 text-primary" />
          <h3 className="mt-3 text-sm font-semibold">We never bypass anything</h3>
          <p className="mt-1.5 text-[13px] leading-relaxed text-muted-foreground">
            No logins, no CAPTCHAs, no paywalls, no rate-limit evasion. If a page is not openly
            available, the offer is labelled for manual verification instead of being scraped around.
          </p>
        </div>
        <div className="rounded-xl border border-border bg-card/50 p-5">
          <Scale className="size-5 text-primary" />
          <h3 className="mt-3 text-sm font-semibold">Sponsored is labelled</h3>
          <p className="mt-1.5 text-[13px] leading-relaxed text-muted-foreground">
            Paid placements carry a visible <em>Sponsored</em> badge and always keep the same position
            in ranking logic. Commission never buys a better position.
          </p>
        </div>
      </section>

      <section className="rounded-2xl border border-primary/25 bg-primary/[0.06] p-6">
        <h2 className="text-base font-semibold">See something wrong?</h2>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          Every offer page has a report button. Reports mark the listing as disputed immediately and
          queue it for human review — they are never ignored.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button asChild>
            <Link href="/offers">Browse live offers</Link>
          </Button>
          <Button asChild variant="outline">
            <Link href="/trust-and-safety">
              Trust &amp; safety
              <ArrowRight className="size-4" />
            </Link>
          </Button>
        </div>
      </section>
    </div>
  );
}