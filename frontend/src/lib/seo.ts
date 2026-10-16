import type { Metadata } from "next";

const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000").replace(/\/$/, "");
const DEFAULT_TITLE = "ZEXR Deal Hub — Find the Best Deals. Unlock More for Less.";
const DEFAULT_DESCRIPTION =
  "Discover verified free trials, premium offers, discounts, free credits and free online tools from across the internet — for everyone, anywhere.";

/** Site-wide defaults. Dark-first with a light option. */
export const siteMetadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: DEFAULT_TITLE,
    template: "%s · ZEXR Deal Hub",
  },
  description: DEFAULT_DESCRIPTION,
  applicationName: "ZEXR Deal Hub",
  keywords: [
    "free trials",
    "free credits",
    "discounts",
    "deals",
    "coupon codes",
    "free software",
    "free alternatives",
    "student discounts",
    "cashback",
    "limited time offers",
  ],
  authors: [{ name: "ZEXR Deal Hub" }],
  creator: "ZEXR Deal Hub",
  publisher: "ZEXR Deal Hub",
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    url: SITE_URL,
    siteName: "ZEXR Deal Hub",
    title: DEFAULT_TITLE,
    description: DEFAULT_DESCRIPTION,
  },
  twitter: {
    card: "summary_large_image",
    title: DEFAULT_TITLE,
    description: DEFAULT_DESCRIPTION,
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true, "max-image-preview": "large" },
  },
  category: "shopping",
};

export function absoluteUrl(path = "/"): string {
  return `${SITE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

export function pageMetadata(options: {
  title: string;
  description: string;
  path: string;
  image?: string;
  type?: "website" | "article";
  noindex?: boolean;
}): Metadata {
  const url = absoluteUrl(options.path);
  return {
    title: options.title,
    description: options.description,
    alternates: { canonical: url },
    robots: options.noindex ? { index: false, follow: false } : undefined,
    openGraph: {
      title: options.title,
      description: options.description,
      url,
      type: options.type ?? "website",
      siteName: "ZEXR Deal Hub",
      images: options.image ? [absoluteUrl(options.image)] : undefined,
    },
    twitter: {
      card: "summary_large_image",
      title: options.title,
      description: options.description,
    },
  };
}

/**
 * JSON-LD helper.
 *
 * Only types that follow search-engine guidelines are emitted; anything that
 * would be speculative (invented ratings, fake reviews, prices we cannot verify)
 * is deliberately left out.
 */
export function jsonLd(data: Record<string, unknown> | Record<string, unknown>[]) {
  return {
    __html: JSON.stringify(data, (_key, value) =>
      value === null || value === undefined ? undefined : value,
    ).replace(/</g, "\\u003c"),
  };
}

export const ORGANISATION_SCHEMA = {
  "@context": "https://schema.org",
  "@type": "Organization",
  name: "ZEXR Deal Hub",
  url: SITE_URL,
  logo: absoluteUrl("/logo.png"),
  description: DEFAULT_DESCRIPTION,
  sameAs: [],
};

export function websiteSchema() {
  return {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: "ZEXR Deal Hub",
    url: SITE_URL,
    description: DEFAULT_DESCRIPTION,
    potentialAction: {
      "@type": "SearchAction",
      target: {
        "@type": "EntryPoint",
        urlTemplate: absoluteUrl("/search?q={search_term_string}"),
      },
      "query-input": "required name=search_term_string",
    },
  };
}

export function breadcrumbSchema(items: { name: string; path: string }[]) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: item.name,
      item: absoluteUrl(item.path),
    })),
  };
}

/**
 * Offer schema.
 *
 * `priceSpecification` is only emitted when the platform actually holds a
 * verified price; speculative values are omitted rather than guessed.
 */
export function offerSchema(offer: {
  title: string;
  description: string;
  url: string;
  category?: string;
  brand?: string | null;
  original_price?: number | null;
  promo_price?: number | null;
  currency?: string;
  expires_at?: string | null;
  is_verified?: boolean;
  eligibility?: string[];
}) {
  const base: Record<string, unknown> = {
    "@context": "https://schema.org",
    "@type": "Offer",
    name: offer.title,
    description: offer.description,
    url: absoluteUrl(`/offers/${offer.url.split("/").pop()}`),
    itemOffered: {
      "@type": "Service",
      name: offer.title,
      description: offer.description,
      category: offer.category,
      brand: offer.brand ? { "@type": "Brand", name: offer.brand } : undefined,
    },
    availability: "https://schema.org/InStock",
    eligibleRegion: {
      "@type": "Place",
      name: "Worldwide",
    },
    priceValidUntil: offer.expires_at ?? undefined,
  };

  if (typeof offer.promo_price === "number") {
    base.priceSpecification = {
      "@type": "PriceSpecification",
      price: offer.promo_price,
      priceCurrency: offer.currency ?? "USD",
      valueAddedTaxIncluded: false,
    };
    if (typeof offer.original_price === "number") {
      (base.priceSpecification as Record<string, unknown>).priceValidUntil = undefined;
    }
  }
  return base;
}

export function faqSchema(entries: { question: string; answer: string }[]) {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: entries.map((entry) => ({
      "@type": "Question",
      name: entry.question,
      acceptedAnswer: { "@type": "Answer", text: entry.answer },
    })),
  };
}