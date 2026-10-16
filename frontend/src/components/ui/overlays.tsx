"use client";

import * as React from "react";
import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

export interface SheetProps {
  open: boolean;
  onClose: () => void;
  title?: React.ReactNode;
  description?: React.ReactNode;
  children: React.ReactNode;
  side?: "left" | "right" | "bottom";
  className?: string;
}

/** Slide-over panel used for mobile navigation and filter drawers. */
export function Sheet({
  open,
  onClose,
  title,
  description,
  children,
  side = "left",
  className,
}: SheetProps) {
  React.useEffect(() => {
    if (!open) return;
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handler);
      document.body.style.overflow = previous;
    };
  }, [open, onClose]);

  const offset = side === "left" ? { x: "-100%" } : side === "right" ? { x: "100%" } : { y: "100%" };

  return (
    <AnimatePresence>
      {open ? (
        <div className="fixed inset-0 z-[90]">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="absolute inset-0 bg-background/70 backdrop-blur-sm"
          />
          <motion.aside
            role="dialog"
            aria-modal="true"
            initial={offset}
            animate={{ x: 0, y: 0 }}
            exit={offset}
            transition={{ type: "spring", stiffness: 340, damping: 34 }}
            className={cn(
              "absolute flex flex-col border-border bg-background shadow-2xl",
              side === "left" && "inset-y-0 left-0 w-[86vw] max-w-sm border-r",
              side === "right" && "inset-y-0 right-0 w-[86vw] max-w-sm border-l",
              side === "bottom" && "inset-x-0 bottom-0 max-h-[85vh] rounded-t-2xl border-t",
              className,
            )}
          >
            {title || description ? (
              <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
                <div>
                  {title ? <p className="text-sm font-semibold">{title}</p> : null}
                  {description ? (
                    <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>
                  ) : null}
                </div>
                <button
                  type="button"
                  onClick={onClose}
                  className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                  aria-label="Close"
                >
                  <X className="size-4" />
                </button>
              </div>
            ) : null}
            <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
          </motion.aside>
        </div>
      ) : null}
    </AnimatePresence>
  );
}

/** Centred modal dialog. */
export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  className,
}: SheetProps) {
  return (
    <AnimatePresence>
      {open ? (
        <div className="fixed inset-0 z-[95] flex items-end justify-center p-0 sm:items-center sm:p-4">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="absolute inset-0 bg-background/75 backdrop-blur-sm"
          />
          <motion.div
            role="dialog"
            aria-modal="true"
            initial={{ opacity: 0, y: 24, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.98 }}
            transition={{ type: "spring", stiffness: 360, damping: 30 }}
            className={cn(
              "relative w-full max-w-lg overflow-hidden rounded-t-2xl border border-border bg-card shadow-2xl sm:rounded-2xl",
              className,
            )}
          >
            <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
              <div>
                {title ? <p className="text-sm font-semibold">{title}</p> : null}
                {description ? (
                  <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>
                ) : null}
              </div>
              <button
                type="button"
                onClick={onClose}
                className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                aria-label="Close"
              >
                <X className="size-4" />
              </button>
            </div>
            <div className="max-h-[70vh] overflow-y-auto px-5 py-4">{children}</div>
          </motion.div>
        </div>
      ) : null}
    </AnimatePresence>
  );
}

/** Horizontal tab strip. */
export function Tabs({
  tabs,
  value,
  onChange,
  className,
}: {
  tabs: { value: string; label: React.ReactNode; count?: number }[];
  value: string;
  onChange: (value: string) => void;
  className?: string;
}) {
  return (
    <div
      role="tablist"
      className={cn(
        "scrollbar-none flex gap-1 overflow-x-auto border-b border-border",
        className,
      )}
    >
      {tabs.map((tab) => {
        const active = tab.value === value;
        return (
          <button
            key={tab.value}
            role="tab"
            aria-selected={active}
            type="button"
            onClick={() => onChange(tab.value)}
            className={cn(
              "relative whitespace-nowrap px-3.5 py-2.5 text-sm font-medium transition-colors",
              active ? "text-foreground" : "text-muted-foreground hover:text-foreground",
            )}
          >
            <span className="inline-flex items-center gap-1.5">
              {tab.label}
              {typeof tab.count === "number" ? (
                <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] tabular-nums text-muted-foreground">
                  {tab.count}
                </span>
              ) : null}
            </span>
            {active ? (
              <motion.span
                layoutId="tab-underline"
                className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-primary"
              />
            ) : null}
          </button>
        );
      })}
    </div>
  );
}