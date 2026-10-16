import * as React from "react";
import { cn } from "@/lib/utils";

/** Illustrated empty state with an optional call to action. */
export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-card/40 px-6 py-14 text-center",
        className,
      )}
    >
      {icon ? (
        <div className="mb-4 flex size-12 items-center justify-center rounded-xl bg-muted text-muted-foreground">
          {icon}
        </div>
      ) : null}
      <h3 className="text-base font-semibold">{title}</h3>
      {description ? (
        <p className="mt-1.5 max-w-md text-sm leading-relaxed text-muted-foreground">
          {description}
        </p>
      ) : null}
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

/** Page-level error boundary fallback content. */
export function ErrorState({
  title = "Something went wrong",
  description = "We could not load this content. Please try again in a moment.",
  action,
}: {
  title?: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <EmptyState
      title={title}
      description={description}
      action={action ?? (
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="inline-flex h-10 items-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground"
        >
          Reload
        </button>
      )}
    />
  );
}