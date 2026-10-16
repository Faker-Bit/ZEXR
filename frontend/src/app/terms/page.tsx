import Link from "next/link";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata({
  title: "Terms of use",
  description: "The terms that apply when you browse ZEXR Deal Hub and claim an offer.",
  path: "/terms",
});

const SECTIONS = [
  {
    title: "Information, not advice",
    body: "ZEXR Deal Hub lists publicly available promotional offers to help you discover them faster. We are not a party to any contract you enter with a provider. Prices, terms and eligibility are set by the provider and can change at any moment — always confirm on the official page before you pay.",
  },
  {
    title: "Verification limits",
    body: "A 'verified' label means our automated check reached the official page and the content still matched at that moment. It is not a guarantee that an offer will still be available when you click. Anything we cannot check automatically is labelled as needing manual verification.",
  },
  {
    title: "No warranty",
    body: "The site is provided 'as is'. We correct mistakes as fast as we find them, but we make no warranty that any offer is accurate, available, or suitable for your purposes.",
  },
  {
    title: "Acceptable use",
    body: "Do not attempt to scrape the site at a rate that degrades it for others, bypass rate limits, or use the platform to distribute deceptive or fraudulent listings. Submissions that misrepresent an offer may be removed.",
  },
  {
    title: "Affiliate links",
    body: "Some outbound links are affiliate links and may earn us a commission at no extra cost to you. Sponsored placements are labelled. See the affiliate disclosure for the full detail.",
  },
  {
    title: "Your account",
    body: "You are responsible for keeping your credentials secure. You can delete your account at any time; deleting it removes your bookmarks, alerts and profile.",
  },
  {
    title: "Liability",
    body: "To the extent permitted by law, ZEXR Deal Hub is not liable for losses arising from relying on information published here, including losses from an offer that ends or changes without notice.",
  },
];

export default function TermsPage() {
  return (
    <div className="container max-w-3xl py-10">
      <h1 className="text-3xl font-semibold tracking-tight">Terms of use</h1>
      <div className="mt-8 space-y-6">
        {SECTIONS.map((section) => (
          <section key={section.title}>
            <h2 className="text-lg font-semibold tracking-tight">{section.title}</h2>
            <p className="mt-2 text-[15px] leading-relaxed text-foreground/85">{section.body}</p>
          </section>
        ))}
      </div>
      <p className="mt-10 text-sm text-muted-foreground">
        See also our{" "}
        <Link href="/trust-and-safety" className="text-primary hover:underline">
          trust &amp; safety
        </Link>{" "}
        and{" "}
        <Link href="/affiliate-disclosure" className="text-primary hover:underline">
          affiliate disclosure
        </Link>{" "}
        pages.
      </p>
    </div>
  );
}