import type { Metadata } from "next";
import Link from "next/link";
import { api } from "@/lib/api";
import { pageMetadata } from "@/lib/seo";
import { CategoryGrid } from "@/components/home/newsletter";
import { Button } from "@/components/ui/button";

export const revalidate = 600;

export const metadata: Metadata = pageMetadata({
  title: "All categories — free deals by topic",
  description:
    "Browse ZEXR Deal Hub by category: AI tools, developer APIs, cloud hosting, VPNs, streaming, gaming, shopping, education, design and free online utilities.",
  path: "/categories",
});

const ICONS: Record<string, string> = {
  sparkles: "AI Tools",
  code: "Developer Tools",
  cloud: "Cloud Hosting",
  shield: "VPN & Privacy",
  play: "Streaming",
  gamepad: "Gaming",
  wallet: "Finance",
  "shopping-bag": "Shopping",
  laptop: "Electronics",
  utensils: "Food",
  plane: "Travel",
  "graduation-cap": "Education",
  palette: "Design",
  briefcase: "Business",
  checklist: "Productivity",
  globe: "Free Utilities",
};

export default async function CategoriesPage() {
  let categories: Awaited<ReturnType<typeof api.categories>> = [];
  try {
    categories = await api.categories();
  } catch {
    categories = [];
  }

  const groups = new Map<string, typeof categories>();
  for (const category of categories) {
    const key = category.group_name ?? "Browse";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(category);
  }

  const totalOffers = categories.reduce((sum, category) => sum + category.offer_count, 0);

  return (
    <div className="container py-8">
      <header className="mb-8 max-w-2xl">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">All categories</h1>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          {categories.length} categories covering {totalOffers.toLocaleString()} live offers. New
          categories can be added without changing the data model — the taxonomy is driven by
          configuration.
        </p>
      </header>

      {[...groups.entries()].map(([group, items]) => (
        <section key={group} className="mb-10">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            {group}
          </h2>
          <div className="space-y-2.5">
            {items.map((category) => (
              <Link
                key={category.slug}
                href={`/categories/${category.slug}`}
                className="flex flex-col gap-1.5 rounded-xl border border-border bg-card/50 p-4 transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:bg-accent/30 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0">
                  <h3 className="flex items-center gap-2 text-sm font-semibold">
                    {category.name}
                    <span className="text-[10px] font-normal uppercase tracking-wide text-muted-foreground">
                      {ICONS[category.icon] ?? category.group_name}
                    </span>
                  </h3>
                  {category.tagline ? (
                    <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                      {category.tagline}
                    </p>
                  ) : null}
                </div>
                <span className="shrink-0 rounded-full border border-border bg-background/60 px-2.5 py-1 text-xs tabular-nums text-muted-foreground">
                  {category.offer_count} offers
                </span>
              </Link>
            ))}
          </div>
        </section>
      ))}

      <section className="mt-10">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Jump to a topic
        </h2>
        <CategoryGrid categories={categories.filter((category) => category.offer_count > 0)} />
      </section>

      <div className="mt-10">
        <Button asChild variant="outline">
          <Link href="/submit">Missing a category or an offer? Tell us →</Link>
        </Button>
      </div>
    </div>
  );
}