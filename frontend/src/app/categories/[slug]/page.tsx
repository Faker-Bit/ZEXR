import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowRight } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { breadcrumbSchema, faqSchema, jsonLd, pageMetadata } from "@/lib/seo";
import { OfferCard } from "@/components/offers/offer-card";
import { Button } from "@/components/ui/button";

export const revalidate = 600;

/** True only when the API said the resource genuinely does not exist. */
function isNotFound(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404;
}

/**
 * Shown when the API is unreachable rather than the category being missing.
 * Keeps the page a soft-503 instead of a hard 404 so a transient outage does
 * not look like the category disappeared.
 */
function CategoryUnavailable({ slug }: { slug: string }) {
  return (
    <main id="main" className="container flex min-h-[60vh] flex-col items-center justify-center py-16 text-center">
      <h1 className="text-2xl font-semibold tracking-tight">Temporarily unavailable</h1>
      <p className="mt-2 max-w-md text-sm leading-relaxed text-muted-foreground">
        We couldn&apos;t reach the deal catalogue just now. This page is intact — please try again
        in a moment.
      </p>
      <div className="mt-6 flex gap-2">
        <Button asChild>
          <Link href="/offers">Browse all offers</Link>
        </Button>
        <Button asChild variant="outline">
          <Link href="/categories">All categories</Link>
        </Button>
      </div>
      <p className="sr-only">{slug}</p>
    </main>
  );
}

export async function generateStaticParams() {
  try {
    const categories = await api.categories();
    return categories.map((category) => ({ slug: category.slug }));
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
    const category = await api.category(slug);
    return pageMetadata({
      title: category.seo_title ?? `${category.name} — free offers, trials and discounts`,
      description:
        category.seo_description ??
        category.tagline ??
        `Browse ${category.offer_count} ${category.name.toLowerCase()} offers with eligibility and verification details.`,
      path: `/categories/${category.slug}`,
    });
  } catch {
    return pageMetadata({
      title: "Category not found",
      description: "This category does not exist.",
      path: `/categories/${slug}`,
      noindex: true,
    });
  }
}

export default async function CategoryPage({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { slug } = await params;
  const query = await searchParams;

  let category;
  let offers;
  try {
    category = await api.category(slug);
    offers = await api.categoryOffers(slug, 48);
  } catch (error) {
    // Only a genuine "no such category" is a 404. A transient API outage must
    // not turn every category page into a hard 404 — that is indistinguishable
    // from the category disappearing, and search engines de-index accordingly.
    // A network failure gets a temporary-unavailable page instead.
    if (isNotFound(error)) notFound();
    return <CategoryUnavailable slug={slug} />;
  }

  // Optional type filter applied client-side via the shared directory controls.
  const typeFilter = typeof query.type === "string" ? query.type : "";
  const filtered = typeFilter
    ? offers.filter((offer) => offer.offer_type === typeFilter)
    : offers;

  const grouped = new Map<string, typeof filtered>();
  for (const offer of filtered) {
    const key = offer.brand?.name ?? "Independent tools";
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key)!.push(offer);
  }

  const faq = [
    {
      question: `What is included in ${category.name}?`,
      answer:
        category.description ??
        `This page lists every ${category.name.toLowerCase()} offer currently tracked by ZEXR Deal Hub, with eligibility and verification status for each one.`,
    },
    {
      question: `How many ${category.name} offers are available?`,
      answer: `There are currently ${category.offer_count} active offers in ${category.name}. Expired ones move to the recently-expired page.`,
    },
    {
      question: "Are these offers verified?",
      answer:
        "Each offer shows whether it was verified automatically against its official page and when. Anything that cannot be checked automatically is labelled as needing manual verification.",
    },
  ];

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={jsonLd([
          breadcrumbSchema([
            { name: "Home", path: "/" },
            { name: "Categories", path: "/categories" },
            { name: category.name, path: `/categories/${category.slug}` },
          ]),
          faqSchema(faq),
        ])}
      />

      <div className="container py-8">
        <nav className="mb-4 flex items-center gap-1.5 text-xs text-muted-foreground">
          <Link href="/" className="hover:text-foreground">
            Home
          </Link>
          <span>/</span>
          <Link href="/categories" className="hover:text-foreground">
            Categories
          </Link>
          <span>/</span>
          <span className="text-foreground">{category.name}</span>
        </nav>

        <header className="mb-8 max-w-3xl">
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{category.name}</h1>
          {category.tagline ? (
            <p className="mt-1.5 text-base text-muted-foreground">{category.tagline}</p>
          ) : null}
          {category.description ? (
            <p className="mt-3 text-[15px] leading-relaxed text-foreground/85">
              {category.description}
            </p>
          ) : null}
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span className="rounded-full border border-border px-2.5 py-1 text-xs text-muted-foreground">
              {category.offer_count} live offers
            </span>
            {category.group_name ? (
              <span className="rounded-full border border-border px-2.5 py-1 text-xs text-muted-foreground">
                {category.group_name}
              </span>
            ) : null}
            <Button asChild size="sm" variant="ghost">
              <Link href={`/offers?category=${category.slug}`}>
                Open in directory
                <ArrowRight className="size-3.5" />
              </Link>
            </Button>
          </div>
        </header>

        {filtered.length ? (
          <>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {filtered.map((offer, index) => (
                <OfferCard key={offer.id} offer={offer} index={index} />
              ))}
            </div>

            <section className="mt-12">
              <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                Browse by brand
              </h2>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {[...grouped.entries()].map(([brand, items]) => (
                  <Link
                    key={brand}
                    href={`/offers?brand=${items[0].brand?.slug ?? ""}`}
                    className="flex items-center justify-between gap-2 rounded-lg border border-border bg-card/50 px-3 py-2.5 text-sm transition-colors hover:border-primary/40 hover:bg-accent/40"
                  >
                    <span className="truncate">{brand}</span>
                    <span className="text-xs tabular-nums text-muted-foreground">{items.length}</span>
                  </Link>
                ))}
              </div>
            </section>
          </>
        ) : (
          <div className="rounded-2xl border border-dashed border-border bg-card/40 px-6 py-14 text-center">
            <h2 className="text-base font-semibold">No live offers here yet</h2>
            <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-muted-foreground">
              This category is being filled. In the meantime, browse the full directory or tell us
              about an offer we are missing.
            </p>
            <div className="mt-5 flex justify-center gap-2">
              <Button asChild>
                <Link href="/offers">Browse all offers</Link>
              </Button>
              <Button asChild variant="outline">
                <Link href="/submit">Submit a deal</Link>
              </Button>
            </div>
          </div>
        )}

        <section className="mt-14 rounded-2xl border border-border bg-card/50 p-6">
          <h2 className="text-sm font-semibold">About this category</h2>
          <p className="mt-2 text-[13px] leading-relaxed text-muted-foreground">
            ZEXR Deal Hub re-checks every listing in {category.name} on a rolling schedule. When a page
            disappears, a price moves or the offer silently ends, the listing is flagged and either
            corrected or moved to the expired page. Nothing is marked verified unless we reached the
            official page ourselves.
          </p>
          {category.keywords?.length ? (
            <p className="mt-3 text-xs text-muted-foreground">
              Also indexed under: {category.keywords.join(", ")}
            </p>
          ) : null}
        </section>
      </div>
    </>
  );
}
