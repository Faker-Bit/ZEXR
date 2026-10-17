import { cache } from "react";

import { api } from "@/lib/api";
import type { Category } from "@/lib/types";

/**
 * Category list, memoised for the lifetime of a single render.
 *
 * The root layout needs it for the header and footer on every page, and
 * /categories, /submit and /admin/offers/new each want it too. React's `cache`
 * collapses those into one request per render instead of one per consumer, and
 * it lives at module scope so every caller shares the same entry.
 *
 * Failures resolve to an empty list so a catalogue outage degrades the nav
 * rather than failing the whole page.
 */
export const loadCategories = cache(async (): Promise<Category[]> => {
  try {
    return await api.categories();
  } catch {
    return [];
  }
});