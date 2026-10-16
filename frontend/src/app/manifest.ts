import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "ZEXR Deal Hub — verified free trials, discounts and free tools",
    short_name: "ZEXR Deal Hub",
    description:
      "Discover verified free trials, free credits, discounts and genuinely free online tools.",
    start_url: "/",
    display: "standalone",
    background_color: "#08090b",
    theme_color: "#a3e635",
    categories: ["shopping", "productivity", "utilities"],
    icons: [
      {
        src: "/icon.svg",
        sizes: "any",
        type: "image/svg+xml",
      },
    ],
  };
}