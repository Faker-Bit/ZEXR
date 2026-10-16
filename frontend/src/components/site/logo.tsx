"use client";

import * as React from "react";
import Image from "next/image";
import Link from "next/link";
import { cn } from "@/lib/utils";

/**
 * Brand mark for the header and footer.
 *
 * Deliberately the compact inline `ZexrMark` rather than `/logo.png`. The
 * supplied artwork is a full square lockup — the Z, the chrome "ZEXR"
 * wordmark, "DEAL HUB", the tagline and six decorative tiles. At header size
 * (36px) that reduces to unreadable noise, and pairing it with the text
 * wordmark beside it would print "ZEXR DEAL HUB" twice.
 *
 * The wordmark is therefore real text, which keeps it selectable,
 * translatable and crisp at any size. The full artwork is used where it has
 * room to breathe: `LogoImage` on /about, and as the social preview image.
 */
export function Logo({
  className,
  href = "/",
  showText = true,
}: {
  className?: string;
  href?: string;
  showText?: boolean;
}) {
  return (
    <Link
      href={href}
      className={cn("group inline-flex items-center gap-2.5", className)}
      aria-label="ZEXR Deal Hub home"
    >
      <span className="relative flex size-9 shrink-0 items-center justify-center">
        <ZexrMark className="size-9 transition-transform duration-200 group-hover:scale-105" />
      </span>

      {showText ? (
        <span className="flex flex-col leading-none">
          <span className="text-[15px] font-bold tracking-tight">
            ZEXR{" "}
            <span className="bg-gradient-to-r from-primary to-emerald-300 bg-clip-text text-transparent">
              DEAL HUB
            </span>
          </span>
          <span className="mt-0.5 text-[9.5px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
            Freebies · Discounts · Premium
          </span>
        </span>
      ) : null}
    </Link>
  );
}

/**
 * Neon "Z" mark. Mirrors the supplied artwork: angular chrome-and-green Z with a
 * glow. Purely decorative — the accessible name comes from the link's label.
 */
export function ZexrMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 64 64"
      className={cn("size-9", className)}
      fill="none"
      aria-hidden
      role="presentation"
    >
      <defs>
        <linearGradient id="zexr-z" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#eafff2" />
          <stop offset="42%" stopColor="#7dff9b" />
          <stop offset="100%" stopColor="#22c55e" />
        </linearGradient>
        <filter id="zexr-glow" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="2.6" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      <g filter="url(#zexr-glow)">
        {/* Top bar */}
        <path d="M14 9h40l-5 11H20z" fill="url(#zexr-z)" />
        {/* Diagonal */}
        <path d="M40 20l7 11-24 24H11l31-35z" fill="url(#zexr-z)" />
        {/* Bottom bar */}
        <path d="M38 44h16l-5 11H30z" fill="url(#zexr-z)" />
      </g>

      {/* Orbit ring, echoing the artwork's arc */}
      <path
        d="M32 3a29 29 0 1 1-20.5 49.5"
        stroke="#4ade80"
        strokeOpacity="0.5"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

/**
 * Full brand artwork (1254x1254) for surfaces with room to show it.
 * Falls back to the mark if the asset is missing, rather than leaving a gap.
 */
export function LogoImage({ className }: { className?: string }) {
  const [failed, setFailed] = React.useState(false);

  if (failed) {
    return (
      <div className={cn("flex items-center justify-center", className)}>
        <ZexrMark className="size-32" />
      </div>
    );
  }

  return (
    <Image
      src="/logo.png"
      alt="ZEXR Deal Hub — freebies, discounts and premium deals"
      width={1254}
      height={1254}
      className={cn("h-auto w-full", className)}
      onError={() => setFailed(true)}
    />
  );
}