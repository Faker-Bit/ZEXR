import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata({
  title: "Affiliate disclosure",
  description:
    "How ZEXR Deal Hub makes money: affiliate commissions, sponsored placements and premium alerts — and what they never buy.",
  path: "/affiliate-disclosure",
});

export default function AffiliatePage() {
  return (
    <div className="container max-w-3xl py-10">
      <h1 className="text-3xl font-semibold tracking-tight">How ZEXR Deal Hub makes money</h1>
      <p className="mt-4 text-base leading-relaxed text-muted-foreground">
        ZEXR Deal Hub is free to browse and free to use. There is no premium tier that unlocks better
        results, and no way to pay for a higher position.
      </p>

      <h2 className="mt-8 text-lg font-semibold tracking-tight">Affiliate commissions</h2>
      <p className="mt-3 text-[15px] leading-relaxed text-foreground/85">
        Many provider programmes pay a commission when you reach their site through an affiliate link
        and make a purchase. When an offer link is an affiliate link, the claim button still takes
        you to the provider&rsquo;s own official page — your price is not affected, and we never add
        a fee. Affiliate status is stored per offer and surfaced in the link metadata.
      </p>

      <h2 className="mt-8 text-lg font-semibold tracking-tight">Sponsored placements</h2>
      <p className="mt-3 text-[15px] leading-relaxed text-foreground/85">
        Occasionally a provider pays for a placement. Sponsored offers are badged{" "}
        <span className="rounded-full bg-primary/15 px-2 py-0.5 text-xs font-semibold text-primary">
          Sponsored
        </span>{" "}
        on the card and on the offer page. Sponsored content is never allowed to outrank organic
        results in our sorting, and it is never presented as independently verified.
      </p>

      <h2 className="mt-8 text-lg font-semibold tracking-tight">Premium alerts (planned)</h2>
      <p className="mt-3 text-[15px] leading-relaxed text-foreground/85">
        We intend to offer a paid tier that sends more frequent notifications for a much larger
        catalogue. The hard rule for that tier: it will only ever change{" "}
        <em>how often you hear from us</em> — never which offers you see, how they are ranked, or
        how they are verified.
      </p>

      <h2 className="mt-8 text-lg font-semibold tracking-tight">What we will never do</h2>
      <ul className="mt-3 space-y-2 text-[15px] leading-relaxed text-foreground/85">
        <li>Sell placement in search results or on category pages.</li>
        <li>Accept payment to remove a negative report or a disputed listing.</li>
        <li>Label an unverified offer as verified.</li>
        <li>Hide that a link is an affiliate link.</li>
      </ul>

      <p className="mt-8 text-sm text-muted-foreground">
        Questions about a specific link? Use the report button on the offer page and mention
        &ldquo;affiliate&rdquo; in the details.
      </p>
    </div>
  );
}