import type { MetadataRoute } from "next";
import { api } from "@/lib/api";

const BASE = (process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000").replace(/\/$/, "");

export const revalidate = 3600;

/**
 * Sitemap.
 *
 * Only canonical, indexable pages are listed. Offer URLs use their real
 * pathname; expired offers are excluded so stale content does not compete with
 * live listings in search results.
 */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date();

  const staticRoutes: MetadataRoute.Sitemap = [
    { url: `${BASE}/`, lastModified: now, changeFrequency: "hourly", priority: 1 },
    { url: `${BASE}/offers`, lastModified: now, changeFrequency: "hourly", priority: 0.9 },
    { url: `${BASE}/categories`, lastModified: now, changeFrequency: "daily", priority: 0.8 },
    { url: `${BASE}/expired`, lastModified: now, changeFrequency: "daily", priority: 0.3 },
    { url: `${BASE}/how-it-works`, lastModified: now, changeFrequency: "monthly", priority: 0.5 },
    { url: `${BASE}/trust-and-safety`, lastModified: now, changeFrequency: "monthly", priority: 0.5 },
    { url: `${BASE}/about`, lastModified: now, changeFrequency: "monthly", priority: 0.4 },
    { url: `${BASE}/affiliate-disclosure`, lastModified: now, changeFrequency: "monthly", priority: 0.3 },
    { url: `${BASE}/privacy`, lastModified: now, changeFrequency: "yearly", priority: 0.2 },
    { url: `${BASE}/terms`, lastModified: now, changeFrequency: "yearly", priority: 0.2 },
  ];

  const [categoriesResult, offersResult] = await Promise.allSettled([
    api.categories(),
    api.offers({ page_size: 100, sort: "popular" }),
  ]);

  const categories =
    categoriesResult.status === "fulfilled" && categoriesResult.value.length
      ? categoriesResult.value.map((category) => ({
          url: `${BASE}/categories/${category.slug}`,
          lastModified: now,
          changeFrequency: "daily" as const,
          priority: category.offer_count > 0 ? 0.8 : 0.4,
        }))
      : [];

  const offers =
    offersResult.status === "fulfilled" && offersResult.value.items.length
      ? offersResult.value.items.map((offer) => ({
          url: `${BASE}/offers/${offer.slug}`,
          lastModified: offer.last_checked_at ? new Date(offer.last_checked_at) : now,
          changeFrequency: "daily" as const,
          priority: 0.7,
        }))
      : [];

  return [...staticRoutes, ...categories, ...offers];
}