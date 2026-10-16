import Link from "next/link";
import { Eye, FileWarning, Flag, Lock, Scale, ShieldCheck } from "lucide-react";
import { pageMetadata } from "@/lib/seo";
import { Button } from "@/components/ui/button";

export const metadata = pageMetadata({
  title: "Trust & safety",
  description:
    "How ZEXR Deal Hub handles affiliate disclosure, sponsored placements, user data, payment information and fraudulent listings.",
  path: "/trust-and-safety",
});

const PRINCIPLES = [
  {
    icon: ShieldCheck,
    title: "No invented offers",
    body: "Every listing traces back to a real page on a provider's own domain. We do not generate discounts, prices, trial lengths or codes that we have not seen in the source.",
  },
  {
    icon: Eye,
    title: "Regional honesty",
    body: "An offer that only works in India is labelled India-only, with the exact regions listed. We never describe a regionally limited offer as universally available.",
  },
  {
    icon: Scale,
    title: "Free vs free trial",
    body: "A product that costs nothing forever is marked genuinely free. A trial that converts into a paid subscription is labelled as such, including the renewal price when we know it.",
  },
  {
    icon: Lock,
    title: "We never touch your money",
    body: "ZEXR Deal Hub has no payment processing and never asks for card details. Claiming an offer happens entirely on the provider's site.",
  },
  {
    icon: FileWarning,
    title: "Clear affiliate disclosure",
    body: "Some outbound links are affiliate links and may earn us a commission at no extra cost to you. Sponsored placements are badged. Neither changes organic ranking order.",
  },
  {
    icon: Flag,
    title: "Report anything",
    body: "Expired, misleading, regional or fraudulent listings can be reported from any offer page. Reports are triaged by a human and surfaced in the admin queue.",
  },
];

export default function TrustPage() {
  return (
    <div className="container max-w-4xl py-10">
      <header className="mb-10">
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Trust &amp; safety</h1>
        <p className="mt-3 text-base leading-relaxed text-muted-foreground">
          A platform that helps people save money has an obligation to be accurate about where the
          money is saved, and honest about how we are paid.
        </p>
      </header>

      <div className="mb-12 grid gap-4 sm:grid-cols-2">
        {PRINCIPLES.map((principle) => (
          <div key={principle.title} className="rounded-xl border border-border bg-card/50 p-5">
            <principle.icon className="size-5 text-primary" />
            <h2 className="mt-3 text-sm font-semibold">{principle.title}</h2>
            <p className="mt-1.5 text-[13px] leading-relaxed text-muted-foreground">
              {principle.body}
            </p>
          </div>
        ))}
      </div>

      <section className="mb-10 rounded-2xl border border-border bg-card/40 p-6">
        <h2 className="text-base font-semibold">Data we hold</h2>
        <ul className="mt-3 space-y-2 text-[13px] leading-relaxed text-muted-foreground">
          <li>
            <strong className="text-foreground">Account data:</strong> email, display name,
            country, preferred currency and notification preferences.
          </li>
          <li>
            <strong className="text-foreground">Interaction data:</strong> searches, offer views and
            claim clicks, used to rank results and detect abuse.
          </li>
          <li>
            <strong className="text-foreground">Never collected:</strong> payment card numbers,
            bank credentials, or any document you might upload to a provider. Those go directly to
            the provider.
          </li>
        </ul>
        <p className="mt-3 text-xs text-muted-foreground">
          See the <Link href="/privacy" className="text-primary hover:underline">privacy policy</Link>{" "}
          for the full detail.
        </p>
      </section>

      <Button asChild variant="outline">
        <Link href="/how-it-works">Read the verification policy →</Link>
      </Button>
    </div>
  );
}