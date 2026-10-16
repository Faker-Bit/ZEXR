import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  ArrowLeft,
  BadgeCheck,
  CalendarClock,
  CircleAlert,
  CreditCard,
  ExternalLink,
  Globe2,
  History,
  ListChecks,
  ShieldCheck,
  Tag,
  TriangleAlert,
  UserPlus,
} from "lucide-react";
import { api } from "@/lib/api";
import { breadcrumbSchema, jsonLd, offerSchema, pageMetadata } from "@/lib/seo";
import { OfferDetailView } from "./detail-client";
import { OfferCard } from "@/components/offers/offer-card";
import { SectionHeader } from "@/components/home/hero";
import { Badge } from "@/components/ui/badge";
import { cn, formatDate, formatMoney, labelForEligibility, labelForOfferType } from "@/lib/utils";

export const revalidate = 300;

export async function generateStaticParams() {
  try {
    const page = await api.offers({ page_size: 50, sort: "popular" });
    return page.items.map((offer) => ({ slug: offer.slug }));
  } catch {
    return [];
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  try {
    const offer = await api.offer(slug);
    return pageMetadata({
      title: offer.title,
      description: offer.short_description.slice(0, 160),
      path: `/offers/${offer.slug}`,
      type: "article",
    });
  } catch {
    return pageMetadata({
      title: "Offer not found",
      description: "This offer is no longer available.",
      path: `/offers/${slug}`,
      noindex: true,
    });
  }
}

export default async function OfferPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  let offer;
  try {
    offer = await api.offer(slug);
  } catch {
    notFound();
  }

  const schema = offerSchema({
    title: offer.title,
    description: offer.short_description,
    url: `/offers/${offer.slug}`,
    category: offer.category.name,
    brand: offer.brand?.name ?? null,
    original_price: offer.original_price,
    promo_price: offer.promo_price,
    currency: offer.currency,
    expires_at: offer.expires_at ?? undefined,
    is_verified: offer.is_verified,
  });

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={jsonLd([
          schema,
          breadcrumbSchema([
            { name: "Home", path: "/" },
            { name: "Offers", path: "/offers" },
            { name: offer.category.name, path: `/categories/${offer.category.slug}` },
            { name: offer.title, path: `/offers/${offer.slug}` },
          ]),
        ])}
      />

      <div className="container py-6 sm:py-8">
        <Link
          href="/offers"
          className="mb-5 inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-3.5" />
          Back to all offers
        </Link>

        <div className="grid gap-8 lg:grid-cols-[1fr_360px]">
          <article className="min-w-0">
            <header>
              <div className="flex flex-wrap items-center gap-2">
                <Badge>{labelForOfferType(offer.offer_type)}</Badge>
                <Link
                  href={`/categories/${offer.category.slug}`}
                  className="text-xs text-muted-foreground hover:text-primary"
                >
                  {offer.category.name}
                </Link>
                {offer.brand ? (
                  <>
                    <span className="text-muted-foreground/40">·</span>
                    <Link
                      href={`/offers?brand=${offer.brand.slug}`}
                      className="text-xs text-muted-foreground hover:text-primary"
                    >
                      {offer.brand.name}
                    </Link>
                  </>
                ) : null}
              </div>

              <h1 className="mt-3 text-2xl font-semibold leading-tight tracking-tight sm:text-3xl">
                {offer.title}
              </h1>
              {offer.subtitle ? (
                <p className="mt-2 text-base text-muted-foreground">{offer.subtitle}</p>
              ) : null}
            </header>

            {offer.is_demo_data ? (
              <div className="mt-5 flex items-start gap-2.5 rounded-xl border border-warning/40 bg-warning/10 p-4">
                <TriangleAlert className="mt-0.5 size-4 shrink-0 text-warning" />
                <div>
                  <p className="text-sm font-medium text-warning">Demo data</p>
                  <p className="mt-0.5 text-[13px] leading-relaxed text-warning/90">
                    This record is development sample data. It is never marked as verified and must
                    not be treated as a live, claimable offer.
                  </p>
                </div>
              </div>
            ) : null}

            {offer.is_disputed ? (
              <div className="mt-5 flex items-start gap-2.5 rounded-xl border border-destructive/40 bg-destructive/10 p-4">
                <CircleAlert className="mt-0.5 size-4 shrink-0 text-destructive" />
                <div>
                  <p className="text-sm font-medium text-destructive">Under review</p>
                  <p className="mt-0.5 text-[13px] leading-relaxed">
                    Our last automated check found something that did not match. A human reviewer is
                    looking at it — treat the details below with caution.
                  </p>
                </div>
              </div>
            ) : null}

            <section className="mt-6">
              <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                What you get
              </h2>
              <p className="whitespace-pre-line text-[15px] leading-relaxed">{offer.description}</p>
            </section>

            {offer.features.length ? (
              <section className="mt-6">
                <h2 className="mb-2.5 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                  Highlights
                </h2>
                <ul className="grid gap-2 sm:grid-cols-2">
                  {offer.features.map((feature) => (
                    <li key={feature} className="flex items-start gap-2 text-sm">
                      <BadgeCheck className="mt-0.5 size-4 shrink-0 text-primary" />
                      <span className="text-foreground/90">{feature}</span>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}

            {offer.how_to_redeem.length ? (
              <section className="mt-7">
                <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                  How to claim it
                </h2>
                <ol className="space-y-3">
                  {offer.how_to_redeem.map((step, index) => (
                    <li key={step} className="flex gap-3">
                      <span className="flex size-6 shrink-0 items-center justify-center rounded-full border border-primary/40 bg-primary/10 text-[11px] font-semibold text-primary">
                        {index + 1}
                      </span>
                      <span className="text-[15px] leading-relaxed text-foreground/90">{step}</span>
                    </li>
                  ))}
                </ol>
              </section>
            ) : null}

            <section className="mt-7 grid gap-4 sm:grid-cols-2">
              <InfoCard title="Eligibility" icon={<ListChecks className="size-4" />}>
                <ul className="space-y-1.5">
                  {offer.eligibility.length ? (
                    offer.eligibility.map((rule) => (
                      <li key={rule.rule} className="flex items-start gap-2">
                        <span
                          className={cn(
                            "mt-1.5 size-1.5 shrink-0 rounded-full",
                            rule.blocking ? "bg-warning" : "bg-primary",
                          )}
                        />
                        <span>
                          <span className="font-medium">{rule.label}</span>
                          {rule.detail ? (
                            <span className="block text-xs text-muted-foreground">{rule.detail}</span>
                          ) : null}
                        </span>
                      </li>
                    ))
                  ) : (
                    <li className="text-muted-foreground">No special eligibility requirements listed.</li>
                  )}
                  {offer.eligibility_notes ? (
                    <li className="text-xs leading-relaxed text-muted-foreground">
                      {offer.eligibility_notes}
                    </li>
                  ) : null}
                </ul>
              </InfoCard>

              <InfoCard title="Where it works" icon={<Globe2 className="size-4" />}>
                <p className="text-sm">
                  {offer.is_global
                    ? "Available worldwide."
                    : `Limited to: ${offer.country_codes.length} listed regions.`}
                </p>
                {offer.country_codes.length ? (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {offer.country_codes.map((code) => (
                      <span
                        key={code}
                        className="rounded-md border border-border bg-background/60 px-1.5 py-0.5 text-[11px] text-muted-foreground"
                      >
                        {code}
                      </span>
                    ))}
                  </div>
                ) : null}
                {offer.excluded_countries.length ? (
                  <p className="mt-2 text-xs text-warning">
                    Not available in: {offer.excluded_countries.join(", ")}
                  </p>
                ) : null}
              </InfoCard>

              <InfoCard title="Payment & renewal" icon={<CreditCard className="size-4" />}>
                <ul className="space-y-1.5 text-sm">
                  <li className="flex items-center justify-between gap-2">
                    <span className="text-muted-foreground">Payment method</span>
                    <span className={offer.requires_payment_method ? "text-warning" : "text-primary"}>
                      {offer.requires_payment_method ? "Required" : "Not required"}
                    </span>
                  </li>
                  <li className="flex items-center justify-between gap-2">
                    <span className="text-muted-foreground">Auto-renews</span>
                    <span>{offer.requires_auto_renew ? "Yes — cancel before the deadline" : "No"}</span>
                  </li>
                  {offer.renewal_price ? (
                    <li className="flex items-center justify-between gap-2">
                      <span className="text-muted-foreground">Price after trial</span>
                      <span>{formatMoney(offer.renewal_price, offer.currency)}</span>
                    </li>
                  ) : null}
                  <li className="flex items-center justify-between gap-2">
                    <span className="text-muted-foreground">Genuinely free</span>
                    <span className={offer.is_genuinely_free ? "text-primary" : ""}>
                      {offer.is_genuinely_free ? "Yes — no conversion" : "No — becomes paid"}
                    </span>
                  </li>
                </ul>
              </InfoCard>

              <InfoCard title="Validity" icon={<CalendarClock className="size-4" />}>
                <ul className="space-y-1.5 text-sm">
                  {offer.starts_at ? (
                    <li className="flex items-center justify-between gap-2">
                      <span className="text-muted-foreground">Started</span>
                      <span>{formatDate(offer.starts_at)}</span>
                    </li>
                  ) : null}
                  <li className="flex items-center justify-between gap-2">
                    <span className="text-muted-foreground">Expires</span>
                    <span className={offer.days_remaining !== null && (offer.days_remaining ?? 99) <= 7 ? "text-warning" : ""}>
                      {offer.expires_at ? formatDate(offer.expires_at) : "Ongoing"}
                    </span>
                  </li>
                  {offer.redemption_deadline ? (
                    <li className="flex items-center justify-between gap-2">
                      <span className="text-muted-foreground">Redeem by</span>
                      <span>{formatDate(offer.redemption_deadline)}</span>
                    </li>
                  ) : null}
                  {offer.trial_days ? (
                    <li className="flex items-center justify-between gap-2">
                      <span className="text-muted-foreground">Trial length</span>
                      <span>{offer.trial_days} days</span>
                    </li>
                  ) : null}
                </ul>
              </InfoCard>
            </section>

            {offer.coupon_code ? (
              <section className="mt-7 rounded-xl border border-dashed border-primary/40 bg-primary/[0.06] p-4">
                <h2 className="flex items-center gap-1.5 text-sm font-semibold">
                  <Tag className="size-4 text-primary" />
                  Coupon code
                </h2>
                <p className="mt-2 font-mono text-xl font-semibold tracking-[0.18em]">
                  {offer.coupon_code}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Enter this on the official page at checkout. We cannot guarantee third-party code
                  validity.
                </p>
              </section>
            ) : null}

            {offer.fine_print ? (
              <section className="mt-7">
                <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                  Fine print
                </h2>
                <p className="text-[13px] leading-relaxed text-muted-foreground">{offer.fine_print}</p>
              </section>
            ) : null}

            {offer.verifications.length ? (
              <section className="mt-7">
                <h2 className="mb-3 flex items-center gap-1.5 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                  <History className="size-3.5" />
                  Verification history
                </h2>
                <div className="overflow-hidden rounded-xl border border-border">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-muted/50 text-muted-foreground">
                      <tr>
                        <th className="px-3 py-2 font-medium">Checked</th>
                        <th className="px-3 py-2 font-medium">Result</th>
                        <th className="px-3 py-2 font-medium">HTTP</th>
                        <th className="px-3 py-2 font-medium">Note</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {offer.verifications.slice(0, 8).map((entry) => (
                        <tr key={entry.id}>
                          <td className="whitespace-nowrap px-3 py-2">{formatDate(entry.checked_at)}</td>
                          <td className="px-3 py-2">
                            <span
                              className={cn(
                                "inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-medium",
                                entry.result === "ok" || entry.result === "redirected"
                                  ? "bg-success/15 text-success"
                                  : entry.result === "skipped"
                                    ? "bg-muted text-muted-foreground"
                                    : "bg-warning/15 text-warning",
                              )}
                            >
                              {entry.result.replace(/_/g, " ")}
                            </span>
                          </td>
                          <td className="px-3 py-2 tabular-nums text-muted-foreground">
                            {entry.http_status ?? "—"}
                          </td>
                          <td className="max-w-xs truncate px-3 py-2 text-muted-foreground">
                            {entry.message ?? "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="mt-2 text-xs text-muted-foreground">
                  {offer.source_name ? `Discovered via ${offer.source_name}. ` : ""}
                  Confidence score {Math.round(offer.discovery_confidence * 100)}%.
                </p>
              </section>
            ) : null}

            {offer.alternatives.length ? (
              <section className="mt-7">
                <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                  Related alternatives
                </h2>
                <ul className="space-y-2">
                  {offer.alternatives.map((alt) => (
                    <li key={alt.id}>
                      <a
                        href={alt.external_url ?? "#"}
                        target="_blank"
                        rel="noopener noreferrer nofollow"
                        className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2.5 text-sm transition-colors hover:border-primary/40 hover:bg-accent/40"
                      >
                        <span>
                          <span className="font-medium">{alt.external_name ?? alt.label}</span>
                          {alt.note ? (
                            <span className="block text-xs text-muted-foreground">{alt.note}</span>
                          ) : null}
                        </span>
                        <ExternalLink className="size-3.5 shrink-0 text-muted-foreground" />
                      </a>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
          </article>

          {/* Sticky claim panel */}
          <aside className="lg:sticky lg:top-24 lg:self-start">
            <OfferDetailView offer={offer} />

            <div className="mt-4 rounded-xl border border-border bg-card/60 p-4">
              <h2 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <ShieldCheck className="size-3.5" />
                Trust signals
              </h2>
              <ul className="mt-2.5 space-y-2 text-xs text-muted-foreground">
                <li className="flex items-start gap-2">
                  <BadgeCheck className="mt-0.5 size-3.5 shrink-0 text-primary" />
                  Links point to the official page, never to a mirror.
                </li>
                <li className="flex items-start gap-2">
                  <UserPlus className="mt-0.5 size-3.5 shrink-0 text-primary" />
                  We never ask for payment details — you claim directly with the provider.
                </li>
                <li className="flex items-start gap-2">
                  <CalendarClock className="mt-0.5 size-3.5 shrink-0 text-primary" />
                  Expiry and last-checked timestamps are stored for every offer.
                </li>
              </ul>
            </div>
          </aside>
        </div>

        {offer.free_alternatives.length ? (
          <section className="mt-14">
            <SectionHeader
              eyebrow="Pay nothing"
              title="Genuinely free alternatives"
              description={`Free options in ${offer.category.name} that do not convert into a subscription.`}
              href={`/categories/${offer.category.slug}?type=free`}
            />
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {offer.free_alternatives.map((alternative, index) => (
                <OfferCard key={alternative.id} offer={alternative} index={index} compact />
              ))}
            </div>
          </section>
        ) : null}

        {offer.similar.length ? (
          <section className="mt-14">
            <SectionHeader
              eyebrow="You might also like"
              title="Similar offers"
              href={`/categories/${offer.category.slug}`}
            />
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {offer.similar.map((similar, index) => (
                <OfferCard key={similar.id} offer={similar} index={index} compact />
              ))}
            </div>
          </section>
        ) : null}

        <section className="mt-14 rounded-2xl border border-border bg-card/50 p-6">
          <h2 className="text-sm font-semibold">Eligibility on this offer, in plain language</h2>
          <ul className="mt-3 grid gap-2 text-[13px] text-muted-foreground sm:grid-cols-2">
            <li>
              <span className="font-medium text-foreground">Where:</span>{" "}
              {offer.is_global ? "worldwide" : `limited to ${offer.country_codes.join(", ") || "selected regions"}`}.
            </li>
            <li>
              <span className="font-medium text-foreground">Who:</span>{" "}
              {offer.requires_student_id
                ? "students with valid ID"
                : offer.requires_new_user
                  ? "new users only"
                  : "anyone"}.
            </li>
            <li>
              <span className="font-medium text-foreground">Card:</span>{" "}
              {offer.requires_payment_method ? "required to start" : "not required"}.
            </li>
            <li>
              <span className="font-medium text-foreground">Length:</span>{" "}
              {offer.trial_days ? `${offer.trial_days} days` : offer.expires_at ? `until ${formatDate(offer.expires_at)}` : "ongoing"}.
            </li>
            <li>
              <span className="font-medium text-foreground">Then:</span>{" "}
              {offer.is_genuinely_free ? "stays free" : "you must cancel before it charges"}.
            </li>
            <li>
              <span className="font-medium text-foreground">Status:</span>{" "}
              {offer.is_verified ? "verified automatically" : "not automatically verified — confirm on the official page"}.
            </li>
          </ul>
          <p className="mt-4 text-xs text-muted-foreground">
            Types recorded for this offer:{" "}
            {(offer.eligibility_types.length ? offer.eligibility_types : ["global"]).map(labelForEligibility).join(", ")}.
          </p>
        </section>
      </div>
    </>
  );
}

function InfoCard({
  title,
  icon,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-border bg-card/50 p-4">
      <h3 className="mb-2.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {icon}
        {title}
      </h3>
      {children}
    </div>
  );
}