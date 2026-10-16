import Link from "next/link";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata({
  title: "About ZEXR Deal Hub",
  description:
    "ZEXR Deal Hub is a global catalogue of verified free trials, discounts, free credits and genuinely free online tools.",
  path: "/about",
});

export default function AboutPage() {
  return (
    <div className="container max-w-3xl py-10">
      <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">About ZEXR Deal Hub</h1>
      <p className="mt-4 text-base leading-relaxed text-muted-foreground">
        ZEXR Deal Hub exists because finding a good deal online is genuinely hard work. Offers are
        buried in marketing pages, they expire quietly, they only work in some countries, and the
        difference between &ldquo;free for 30 days&rdquo; and &ldquo;free forever&rdquo; is easy to
        miss until you are already being charged.
      </p>

      <h2 className="mt-8 text-lg font-semibold tracking-tight">What we do differently</h2>
      <div className="mt-3 space-y-4 text-[15px] leading-relaxed text-foreground/85">
        <p>
          Most deal sites are hand-maintained lists. Ours is a pipeline: a background worker reads
          permitted sources, a normaliser extracts only what is actually written in the source, a
          duplicate check merges what we already have, and a verification job re-opens the official
          page on a schedule.
        </p>
        <p>
          That matters for the reader. When an offer disappears, it leaves the live set instead of
          lingering as bad advice. When a price moves, the listing is flagged for review rather than
          quietly updated to something we cannot prove.
        </p>
        <p>
          The rule we hold ourselves to is simple:{" "}
          <strong className="text-foreground">
            if we cannot check it, we do not claim we checked it.
          </strong>
        </p>
      </div>

      <h2 className="mt-10 text-lg font-semibold tracking-tight">Built for everyone, everywhere</h2>
      <p className="mt-3 text-[15px] leading-relaxed text-foreground/85">
        The site works for anyone, in any country, in their own currency. Every offer states where
        it works, who can claim it, whether a payment method is required, what it costs after the
        free period, and when we last checked the page. Regional limits are shown up front, not
        discovered after you have already entered your details on someone else&rsquo;s website.
      </p>

      <h2 className="mt-10 text-lg font-semibold tracking-tight">Get involved</h2>
      <ul className="mt-3 space-y-2 text-[15px] text-foreground/85">
        <li>
          <Link href="/submit" className="text-primary underline-offset-4 hover:underline">
            Submit an offer
          </Link>{" "}
          — a reviewer checks it against the official page before publication.
        </li>
        <li>
          <Link href="/how-it-works" className="text-primary underline-offset-4 hover:underline">
            Read how verification works
          </Link>
          .
        </li>
        <li>
          <Link href="/trust-and-safety" className="text-primary underline-offset-4 hover:underline">
            Trust &amp; safety
          </Link>{" "}
          — including exactly how we make money.
        </li>
      </ul>
    </div>
  );
}