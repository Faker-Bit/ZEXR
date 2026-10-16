"use client";

import * as React from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  ArrowUpRight,
  Bookmark,
  Clock,
  Globe2,
  Info,
  MapPin,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
  UserPlus,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/primitives";
import { useToast } from "@/components/ui/toast";
import { api, claimUrl } from "@/lib/api";
import type { OfferCard as OfferCardType } from "@/lib/types";
import {
  cn,
  expiryLabel,
  formatMoney,
  formatRelativeSafe,
  labelForOfferType,
  priceLine,
} from "@/lib/utils";

interface OfferCardProps {
  offer: OfferCardType;
  index?: number;
  compact?: boolean;
  onBookmarkChange?: (offerId: string, bookmarked: boolean) => void;
  className?: string;
}

export function OfferCard({
  offer,
  index = 0,
  compact,
  onBookmarkChange,
  className,
}: OfferCardProps) {
  const [bookmarked, setBookmarked] = React.useState(offer.bookmarked);
  const [pending, setPending] = React.useState(false);
  const { toast } = useToast();
  const expiry = expiryLabel(offer);

  async function toggleBookmark(event: React.MouseEvent) {
    event.preventDefault();
    event.stopPropagation();
    if (pending) return;
    setPending(true);
    const next = !bookmarked;
    setBookmarked(next);
    onBookmarkChange?.(offer.id, next);
    try {
      if (next) await api.addBookmark(offer.id);
      else await api.removeBookmark(offer.id);
    } catch (error) {
      setBookmarked(!next);
      onBookmarkChange?.(offer.id, !next);
      toast({
        title: next ? "Could not save this offer" : "Could not remove this offer",
        description: error instanceof Error ? error.message : "Please sign in and try again.",
        tone: "error",
      });
    } finally {
      setPending(false);
    }
  }

  return (
    <motion.article
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, delay: Math.min(index * 0.03, 0.24), ease: [0.22, 1, 0.36, 1] }}
      className={cn(
        "group relative flex h-full flex-col overflow-hidden rounded-xl border border-border bg-card shadow-card transition-all duration-200",
        "hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-glow",
        offer.is_sponsored && "border-primary/30",
        className,
      )}
    >
      {offer.is_sponsored ? (
        <span className="absolute right-3 top-3 z-10 rounded-full bg-primary/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-primary">
          Sponsored
        </span>
      ) : null}

      <Link href={`/offers/${offer.slug}`} className="flex flex-1 flex-col p-4 focus:outline-none">
        {/* Brand + category */}
        <div className="mb-3 flex items-center gap-2.5">
          <BrandMark offer={offer} />
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-medium text-muted-foreground">
              {offer.brand?.name ?? offer.category.name}
            </p>
            <Link
              href={`/categories/${offer.category.slug}`}
              onClick={(event) => event.stopPropagation()}
              className="truncate text-[11px] text-muted-foreground/70 hover:text-primary"
            >
              {offer.category.name}
            </Link>
          </div>
          <TypeBadge type={offer.offer_type} />
        </div>

        {/* Title */}
        <h3 className="line-clamp-2 text-[15px] font-semibold leading-snug tracking-tight transition-colors group-hover:text-primary">
          {offer.title}
        </h3>

        {!compact ? (
          <p className="mt-1.5 line-clamp-2 text-[13px] leading-relaxed text-muted-foreground">
            {offer.short_description}
          </p>
        ) : null}

        {/* Price */}
        <div className="mt-3 flex flex-wrap items-baseline gap-x-2 gap-y-1">
          <span
            className={cn(
              "text-xl font-semibold tracking-tight",
              offer.promo_price === 0 || offer.is_genuinely_free ? "text-primary" : "text-foreground",
            )}
          >
            {priceLine(offer)}
          </span>
          {offer.original_price ? (
            <span className="text-xs text-muted-foreground line-through">
              {formatMoney(offer.original_price, offer.currency)}
            </span>
          ) : null}
          {offer.savings_percent > 0 ? (
            <Badge variant="success" size="sm">
              Save {offer.savings_percent}%
            </Badge>
          ) : null}
        </div>

        {/* Reported access level, shown for catalogue-sourced AI providers so a
            documented claim is never mistaken for something we verified. */}
        {offer.eligibility_notes ? (
          <p className="mt-3 line-clamp-2 rounded-lg border border-border bg-muted/40 px-2.5 py-1.5 text-[12px] leading-relaxed text-muted-foreground">
            <span className="font-medium text-foreground">Reported: </span>
            {offer.eligibility_notes}
          </p>
        ) : null}

        {/* Meta */}
        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          {offer.trial_days ? <MetaChip>{offer.trial_days}-day trial</MetaChip> : null}
          {offer.credits_amount ? (
            <MetaChip>
              {formatMoney(offer.credits_amount, offer.currency)} {offer.credits_unit ?? "credit"}
            </MetaChip>
          ) : null}
          {!offer.requires_payment_method && offer.offer_type !== "free" ? (
            <MetaChip icon={<ShieldCheck className="size-3 text-primary" />}>No card needed</MetaChip>
          ) : null}
          {offer.requires_payment_method ? <MetaChip>Card required</MetaChip> : null}
          {offer.is_global ? (
            <MetaChip icon={<Globe2 className="size-3" />}>Worldwide</MetaChip>
          ) : (
            <MetaChip icon={<MapPin className="size-3" />}>
              {offer.country_codes.length
                ? offer.country_codes.slice(0, 3).join(", ")
                : "Selected countries"}
            </MetaChip>
          )}
          {offer.requires_student_id ? <MetaChip>Students only</MetaChip> : null}
          {offer.requires_new_user ? (
            <MetaChip icon={<UserPlus className="size-3" />}>New users</MetaChip>
          ) : null}
        </div>

        {/* Footer */}
        <div className="mt-auto flex items-end justify-between gap-2 pt-4">
          <div className="min-w-0">
            <ExpiryLine offer={offer} expiry={expiry} />
            <VerifiedLine offer={offer} />
          </div>
          <Button asChild size="sm" className="shrink-0">
            <a href={claimUrl(offer)} target="_blank" rel="noopener noreferrer nofollow sponsored">
              Claim
              <ArrowUpRight className="size-3.5" />
            </a>
          </Button>
        </div>
      </Link>

      <button
        type="button"
        onClick={toggleBookmark}
        disabled={pending}
        aria-label={bookmarked ? "Remove from saved offers" : "Save this offer"}
        aria-pressed={bookmarked}
        className={cn(
          "absolute right-2.5 top-2.5 z-20 rounded-lg border p-1.5 transition-all",
          bookmarked
            ? "border-primary/40 bg-primary/15 text-primary"
            : "border-border bg-background/80 text-muted-foreground opacity-0 hover:text-foreground focus-visible:opacity-100 group-hover:opacity-100",
          offer.is_sponsored && "right-auto left-2.5",
        )}
      >
        <Bookmark className={cn("size-3.5", bookmarked && "fill-current")} />
      </button>

      {offer.is_demo_data ? (
        <span className="pointer-events-none absolute inset-x-0 bottom-0 h-0.5 bg-warning/60" />
      ) : null}
    </motion.article>
  );
}

function BrandMark({ offer }: { offer: OfferCardType }) {
  const [failed, setFailed] = React.useState(false);
  const size = 36;
  const name = offer.brand?.name ?? offer.category.name;

  if (offer.brand?.logo_url && !failed) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={offer.brand.logo_url}
        alt=""
        width={size}
        height={size}
        loading="lazy"
        onError={() => setFailed(true)}
        className="size-9 shrink-0 rounded-lg border border-border bg-background object-contain p-1"
      />
    );
  }

  const letters = name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part.charAt(0))
    .join("")
    .toUpperCase();

  return (
    <span
      aria-hidden
      className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-border bg-gradient-to-br from-primary/15 to-transparent text-[11px] font-bold text-primary"
    >
      {letters || <Sparkles className="size-4" />}
    </span>
  );
}

export function TypeBadge({ type }: { type: string }) {
  const styles: Record<string, string> = {
    free: "bg-primary/15 text-primary border-transparent",
    free_trial: "bg-sky-500/15 text-sky-400 border-transparent",
    free_credits: "bg-violet-500/15 text-violet-400 border-transparent",
    discount: "bg-amber-500/15 text-amber-500 border-transparent",
    coupon: "bg-pink-500/15 text-pink-400 border-transparent",
    cashback: "bg-emerald-500/15 text-emerald-400 border-transparent",
    freemium: "bg-teal-500/15 text-teal-400 border-transparent",
    free_alternative: "bg-indigo-500/15 text-indigo-400 border-transparent",
  };
  return (
    <span
      className={cn(
        "shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        styles[type] ?? "border-border text-muted-foreground",
      )}
    >
      {labelForOfferType(type)}
    </span>
  );
}

function MetaChip({
  children,
  icon,
}: {
  children: React.ReactNode;
  icon?: React.ReactNode;
}) {
  return (
    <span className="inline-flex items-center gap-1 rounded-md border border-border bg-background/60 px-1.5 py-0.5 text-[11px] text-muted-foreground">
      {icon}
      {children}
    </span>
  );
}

function ExpiryLine({
  offer,
  expiry,
}: {
  offer: OfferCardType;
  expiry: { label: string; tone: "urgent" | "soon" | "normal" };
}) {
  if (offer.is_expired) {
    return (
      <p className="flex items-center gap-1 text-[11px] font-medium text-destructive">
        <TriangleAlert className="size-3" />
        This offer has expired
      </p>
    );
  }
  const toneClass =
    expiry.tone === "urgent"
      ? "text-warning"
      : expiry.tone === "soon"
        ? "text-foreground/80"
        : "text-muted-foreground";
  return (
    <p className={cn("flex items-center gap-1 text-[11px] font-medium", toneClass)}>
      <Clock className="size-3" />
      {expiry.label}
    </p>
  );
}

function VerifiedLine({ offer }: { offer: OfferCardType }) {
  if (offer.is_demo_data) {
    return (
      <p className="flex items-center gap-1 text-[11px] font-medium text-warning">
        <TriangleAlert className="size-3" />
        Demo data — not a live verified offer
      </p>
    );
  }
  if (offer.verification_status === "verified") {
    return (
      <Tooltip content={`Last checked ${formatRelativeSafe(offer.last_checked_at)}`}>
        <p className="flex items-center gap-1 text-[11px] font-medium text-success">
          <ShieldCheck className="size-3" />
          Verified {formatRelativeSafe(offer.last_checked_at)}
        </p>
      </Tooltip>
    );
  }
  if (offer.verification_status === "needs_manual") {
    return (
      <Tooltip content="We could not check this automatically — a human reviewer confirms it.">
        <p className="flex items-center gap-1 text-[11px] font-medium text-muted-foreground">
          <Info className="size-3" />
          Needs manual verification
        </p>
      </Tooltip>
    );
  }
  return (
    <p className="flex items-center gap-1 text-[11px] text-muted-foreground">
      <Info className="size-3" />
      Not yet verified
    </p>
  );
}

export function OfferCardSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("flex h-full flex-col rounded-xl border border-border bg-card p-4", className)}>
      <div className="flex items-center gap-2.5">
        <Skeleton className="size-9 rounded-lg" />
        <div className="flex-1 space-y-1.5">
          <Skeleton className="h-2.5 w-20" />
          <Skeleton className="h-2.5 w-14" />
        </div>
        <Skeleton className="h-4 w-16 rounded-full" />
      </div>
      <Skeleton className="mt-3 h-4 w-full" />
      <Skeleton className="mt-1.5 h-3 w-4/5" />
      <Skeleton className="mt-4 h-6 w-28" />
      <div className="mt-3 flex gap-1.5">
        <Skeleton className="h-5 w-16 rounded-md" />
        <Skeleton className="h-5 w-20 rounded-md" />
      </div>
      <div className="mt-auto flex items-center justify-between pt-4">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-8 w-20 rounded-lg" />
      </div>
    </div>
  );
}

function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton", className)} />;
}
