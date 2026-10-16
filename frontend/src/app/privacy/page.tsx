import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata({
  title: "Privacy policy",
  description:
    "What data ZEXR Deal Hub collects, why, how long it is kept, and what we never collect.",
  path: "/privacy",
});

const SECTIONS = [
  {
    title: "What we collect",
    body: "If you create an account: your email address, an optional display name, your country and preferred currency, and your notification preferences. If you use the site without an account: anonymised analytics such as searches, page views and which offers you click.",
  },
  {
    title: "What we never collect",
    body: "Payment card numbers, bank details, government identifiers, passwords for third-party services, or any document you upload to a provider. Claiming an offer happens on the provider's own site and we have no visibility into it.",
  },
  {
    title: "Cookies",
    body: "We use a single session cookie to keep you signed in, and a local storage entry to remember your colour theme. Analytics use a first-party session id so that clicks can be attributed to a visit without identifying you.",
  },
  {
    title: "Third parties",
    body: "Clicking 'Claim' takes you to an external provider whose own privacy policy then applies. We do not control how those providers handle your data and we do not receive anything they collect.",
  },
  {
    title: "Retention",
    body: "Account data is kept until you ask us to delete it. Raw analytics events are rolled up into daily aggregates and then removed. Verification history is kept for auditability and pruned automatically after a set period.",
  },
  {
    title: "Your rights",
    body: "You can request a copy of your data or ask for your account to be deleted. Contact us and we will action it; deletion removes your bookmarks, alerts and profile.",
  },
];

export default function PrivacyPage() {
  return (
    <div className="container max-w-3xl py-10">
      <h1 className="text-3xl font-semibold tracking-tight">Privacy policy</h1>
      <p className="mt-3 text-sm text-muted-foreground">
        Last updated when this platform was built. Written to be read, not to be skimmed.
      </p>
      <div className="mt-8 space-y-6">
        {SECTIONS.map((section) => (
          <section key={section.title}>
            <h2 className="text-lg font-semibold tracking-tight">{section.title}</h2>
            <p className="mt-2 text-[15px] leading-relaxed text-foreground/85">{section.body}</p>
          </section>
        ))}
      </div>
    </div>
  );
}