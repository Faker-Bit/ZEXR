import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider, THEME_INIT_SCRIPT } from "@/components/site/theme";
import { ToastProvider } from "@/components/ui/toast";
import { AuthProvider } from "@/components/site/auth-provider";
import { Header } from "@/components/site/header";
import { Footer } from "@/components/site/footer";
import { api } from "@/lib/api";
import { siteMetadata, jsonLd, websiteSchema, ORGANISATION_SCHEMA } from "@/lib/seo";
import type { Category } from "@/lib/types";

export const metadata: Metadata = siteMetadata;

export const viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#08090b" },
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
  ],
};

/**
 * Categories are needed by the header, footer and most pages. Fetched once per
 * request with revalidation so taxonomy edits appear quickly without hammering
 * the API.
 */
async function loadCategories(): Promise<Category[]> {
  try {
    return await api.categories();
  } catch {
    return [];
  }
}

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const categories = await loadCategories();

  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={jsonLd([websiteSchema(), ORGANISATION_SCHEMA])}
        />
      </head>
      <body className="min-h-dvh bg-background font-sans">
        <ThemeProvider>
          <ToastProvider>
            <AuthProvider>
              <a
                href="#main"
                className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[200] focus:rounded-lg focus:bg-primary focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-primary-foreground"
              >
                Skip to content
              </a>
              <Header categories={categories} />
              <main id="main" className="min-h-[60vh]">
                {children}
              </main>
              <Footer categories={categories} />
            </AuthProvider>
          </ToastProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}