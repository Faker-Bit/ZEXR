"use client";

import * as React from "react";
import { motion } from "framer-motion";
import {
  ArrowUpRight,
  Bookmark,
  Copy,
  Flag,
  Share2,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, Tabs } from "@/components/ui/overlays";
import { Label, Select, Textarea } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { useSessionId } from "@/components/site/auth-provider";
import { api, claimUrl } from "@/lib/api";
import type { OfferDetail } from "@/lib/types";
import { cn, expiryLabel, formatDateTime, formatMoney, labelForOfferType, priceLine } from "@/lib/utils";

/** Sticky claim panel: pricing, countdown, bookmark, share and reporting. */
export function OfferDetailView({ offer }: { offer: OfferDetail }) {
  const [bookmarked, setBookmarked] = React.useState(offer.bookmarked);
  const [busy, setBusy] = React.useState(false);
  const [shareOpen, setShareOpen] = React.useState(false);
  const [reportOpen, setReportOpen] = React.useState(false);
  const { toast } = useToast();
  const sessionId = useSessionId();
  const expiry = expiryLabel(offer);

  async function toggleBookmark() {
    setBusy(true);
    const next = !bookmarked;
    setBookmarked(next);
    try {
      if (next) await api.addBookmark(offer.id);
      else await api.removeBookmark(offer.id);
      toast({
        title: next ? "Saved to your list" : "Removed from your list",
        description: next ? "We will remind you before it expires." : undefined,
        tone: "success",
      });
    } catch (error) {
      setBookmarked(!next);
      toast({
        title: "Sign in to save offers",
        description: error instanceof Error ? error.message : undefined,
        tone: "error",
      });
    } finally {
      setBusy(false);
    }
  }

  async function share() {
    const url = `${window.location.origin}/offers/${offer.slug}`;
    if (navigator.share) {
      try {
        await navigator.share({ title: offer.title, text: offer.short_description, url });
        return;
      } catch {
        /* user cancelled */
      }
    }
    await navigator.clipboard.writeText(url);
    toast({ title: "Link copied", tone: "success" });
  }

  return (
    <div className="space-y-3">
      <div className="overflow-hidden rounded-xl border border-border bg-card shadow-card">
        <div className="border-b border-border p-5">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              {labelForOfferType(offer.offer_type)}
            </span>
            <VerificationPill offer={offer} />
          </div>

          <p
            className={cn(
              "mt-3 text-3xl font-semibold tracking-tight",
              offer.promo_price === 0 || offer.is_genuinely_free ? "text-primary" : "",
            )}
          >
            {priceLine(offer)}
          </p>
          {offer.original_price ? (
            <p className="mt-1 text-sm text-muted-foreground">
              <span className="line-through">
                {formatMoney(offer.original_price, offer.currency)}
              </span>
              {offer.billing_period ? ` ${offer.billing_period}` : ""}
              {offer.savings_percent ? ` · save ${offer.savings_percent}%` : ""}
            </p>
          ) : null}

          {offer.renewal_price ? (
            <p className="mt-2 rounded-lg border border-warning/30 bg-warning/10 px-2.5 py-2 text-xs leading-relaxed text-warning">
              After the free period this costs{" "}
              <strong>{formatMoney(offer.renewal_price, offer.currency)}</strong>
              {offer.requires_auto_renew ? " and renews automatically." : "."} Cancel before the
              deadline if you do not want to pay.
            </p>
          ) : null}

          {!offer.requires_payment_method ? (
            <p className="mt-2 text-xs text-success">No credit card required to start.</p>
          ) : null}
        </div>

        <div className="p-5">
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25 }}
          >
            <Button asChild size="lg" className="w-full">
              <a
                href={claimUrl(offer, sessionId ?? undefined)}
                target="_blank"
                rel="noopener noreferrer nofollow sponsored"
              >
                Claim this offer
                <ArrowUpRight className="size-4" />
              </a>
            </Button>
            <p className="mt-2 text-center text-[11px] text-muted-foreground">
              Opens the official page on {safeHost(offer.official_url)}
              {offer.is_affiliate ? " · affiliate link" : ""}
            </p>
          </motion.div>

          <div className="mt-3 grid grid-cols-2 gap-2">
            <Button variant="outline" size="sm" onClick={toggleBookmark} disabled={busy}>
              <Bookmark className={cn("size-3.5", bookmarked && "fill-current text-primary")} />
              {bookmarked ? "Saved" : "Save"}
            </Button>
            <Button variant="outline" size="sm" onClick={() => setShareOpen(true)}>
              <Share2 className="size-3.5" />
              Share
            </Button>
          </div>

          <div className="mt-4 rounded-lg border border-border bg-background/50 p-3">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">
                {offer.is_expired ? "Status" : "Time left"}
              </span>
              <span
                className={cn(
                  "font-medium",
                  offer.is_expired
                    ? "text-destructive"
                    : expiry.tone === "urgent"
                      ? "text-warning"
                      : "text-foreground",
                )}
              >
                {expiry.label}
              </span>
            </div>
            {offer.expires_at ? (
              <p className="mt-1 text-[11px] text-muted-foreground">
                Ends {formatDateTime(offer.expires_at)}
              </p>
            ) : null}
            <div className="mt-2 flex items-center justify-between text-xs">
              <span className="text-muted-foreground">Last checked</span>
              <span className="font-medium">
                {offer.last_checked_at ? formatDateTime(offer.last_checked_at) : "Not yet checked"}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-card/60 p-4">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Quick eligibility
        </h3>
        <dl className="mt-2.5 space-y-1.5 text-[13px]">
          <Row label="Availability" value={offer.is_global ? "Worldwide" : offer.country_codes.join(", ") || "Selected regions"} />
          <Row
            label="Who can claim"
            value={
              offer.requires_student_id
                ? "Students only"
                : offer.requires_new_user
                  ? "New users only"
                  : "Anyone"
            }
          />
          <Row label="Payment method" value={offer.requires_payment_method ? "Required" : "Not needed"} />
          <Row
            label="After the offer"
            value={offer.is_genuinely_free ? "Stays free" : "Becomes a paid plan"}
          />
        </dl>
      </div>

      <button
        type="button"
        onClick={() => setReportOpen(true)}
        className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-border px-3 py-2 text-xs text-muted-foreground transition-colors hover:border-destructive/40 hover:text-destructive"
      >
        <Flag className="size-3" />
        Report a problem with this offer
      </button>

      <Dialog
        open={shareOpen}
        onClose={() => setShareOpen(false)}
        title="Share this offer"
        description="Copy the link or post it somewhere."
      >
        <ShareBlock offer={offer} onCopied={() => toast({ title: "Copied", tone: "success" })} />
      </Dialog>

      <Dialog
        open={reportOpen}
        onClose={() => setReportOpen(false)}
        title="Report this offer"
        description="Reports trigger a re-check and a human review."
      >
        <ReportForm
          offerId={offer.id}
          onDone={() => {
            setReportOpen(false);
            toast({
              title: "Report submitted",
              description: "A reviewer will re-verify this offer.",
              tone: "success",
            });
          }}
        />
      </Dialog>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <dt className="shrink-0 text-muted-foreground">{label}</dt>
      <dd className="text-right font-medium">{value}</dd>
    </div>
  );
}

export function VerificationPill({ offer }: { offer: Pick<OfferDetail, "verification_status" | "is_demo_data"> }) {
  if (offer.is_demo_data) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-warning/15 px-2 py-0.5 text-[10px] font-semibold uppercase text-warning">
        <TriangleAlert className="size-3" />
        Demo
      </span>
    );
  }
  if (offer.verification_status === "verified") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-success/15 px-2 py-0.5 text-[10px] font-semibold uppercase text-success">
        <ShieldCheck className="size-3" />
        Verified
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-[10px] font-semibold uppercase text-muted-foreground">
      Needs review
    </span>
  );
}

function ShareBlock({
  offer,
  onCopied,
}: {
  offer: OfferDetail;
  onCopied: () => void;
}) {
  const [copied, setCopied] = React.useState(false);
  const url = `${typeof window !== "undefined" ? window.location.origin : ""}/offers/${offer.slug}`;
  const text = encodeURIComponent(offer.title);
  const link = encodeURIComponent(url);

  async function copy() {
    await navigator.clipboard.writeText(url);
    setCopied(true);
    onCopied();
    window.setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 rounded-lg border border-border bg-background/60 px-3 py-2">
        <input readOnly value={url} className="min-w-0 flex-1 bg-transparent text-sm outline-none" />
        <Button size="sm" variant="ghost" onClick={copy}>
          {copied ? "Copied" : <Copy className="size-3.5" />}
        </Button>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <a
          href={`https://twitter.com/intent/tweet?text=${text}&url=${link}`}
          target="_blank"
          rel="noopener noreferrer nofollow"
          className="flex h-9 items-center justify-center rounded-lg border border-border text-sm text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
        >
          Share on X
        </a>
        <a
          href={`https://www.linkedin.com/sharing/share-offsite/?url=${link}`}
          target="_blank"
          rel="noopener noreferrer nofollow"
          className="flex h-9 items-center justify-center rounded-lg border border-border text-sm text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
        >
          LinkedIn
        </a>
        <a
          href={`https://wa.me/?text=${text}%20${link}`}
          target="_blank"
          rel="noopener noreferrer nofollow"
          className="flex h-9 items-center justify-center rounded-lg border border-border text-sm text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
        >
          WhatsApp
        </a>
        <a
          href={`https://t.me/share/url?url=${link}&text=${text}`}
          target="_blank"
          rel="noopener noreferrer nofollow"
          className="flex h-9 items-center justify-center rounded-lg border border-border text-sm text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
        >
          Telegram
        </a>
      </div>
      <p className="text-xs text-muted-foreground">
        {offer.brand?.name ?? "This offer"} ·{" "}
        {offer.is_global ? "available worldwide" : `available in ${offer.country_codes.join(", ") || "selected regions"}`}.
      </p>
    </div>
  );
}

const REASONS = [
  { value: "expired", label: "The offer has expired" },
  { value: "wrong_price", label: "The price shown is wrong" },
  { value: "misleading", label: "The description is misleading" },
  { value: "broken_link", label: "The link is broken" },
  { value: "region_restricted", label: "Not available in my country" },
  { value: "fraud", label: "This looks like a scam" },
  { value: "duplicate", label: "Duplicate listing" },
  { value: "other", label: "Something else" },
];

function ReportForm({ offerId, onDone }: { offerId: string; onDone: () => void }) {
  const [reason, setReason] = React.useState("expired");
  const [details, setDetails] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    try {
      await api.report({ offer_id: offerId, reason, details, email: email || undefined });
      onDone();
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <div>
        <Label htmlFor="reason">What is wrong?</Label>
        <Select id="reason" value={reason} onChange={(event) => setReason(event.target.value)} className="mt-1.5">
          {REASONS.map((item) => (
            <option key={item.value} value={item.value}>
              {item.label}
            </option>
          ))}
        </Select>
      </div>
      <div>
        <Label htmlFor="details">Details (optional)</Label>
        <Textarea
          id="details"
          value={details}
          onChange={(event) => setDetails(event.target.value)}
          placeholder="What did you see on the official page?"
          className="mt-1.5"
        />
      </div>
      <div>
        <Label htmlFor="report-email">Your email (optional)</Label>
        <input
          id="report-email"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="Only if you want a reply"
          className="mt-1.5 flex h-10 w-full rounded-lg border border-input bg-background/60 px-3 text-sm outline-none focus:border-primary/60"
        />
      </div>
      <Button type="submit" disabled={submitting} className="w-full">
        {submitting ? "Sending…" : "Submit report"}
      </Button>
    </form>
  );
}

function safeHost(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "the official site";
  }
}
