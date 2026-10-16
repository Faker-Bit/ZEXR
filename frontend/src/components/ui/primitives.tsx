import * as React from "react";
import { Check, ChevronDown, Minus } from "lucide-react";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ switch */
export interface SwitchProps {
  checked?: boolean;
  defaultChecked?: boolean;
  onCheckedChange?: (checked: boolean) => void;
  disabled?: boolean;
  className?: string;
  id?: string;
  "aria-label"?: string;
}

export function Switch({
  checked,
  defaultChecked = false,
  onCheckedChange,
  disabled,
  className,
  id,
  ...props
}: SwitchProps) {
  const [internal, setInternal] = React.useState(defaultChecked);
  const isControlled = checked !== undefined;
  const value = isControlled ? checked : internal;

  return (
    <button
      type="button"
      role="switch"
      id={id}
      aria-checked={value}
      disabled={disabled}
      onClick={() => {
        const next = !value;
        if (!isControlled) setInternal(next);
        onCheckedChange?.(next);
      }}
      className={cn(
        "relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        "disabled:cursor-not-allowed disabled:opacity-50",
        value ? "bg-primary" : "bg-input",
        className,
      )}
      {...props}
    >
      <span
        className={cn(
          "pointer-events-none block h-5 w-5 rounded-full bg-background shadow-lg ring-0 transition-transform",
          value ? "translate-x-5" : "translate-x-0",
        )}
      />
    </button>
  );
}

/* ---------------------------------------------------------------- checkbox */
export interface CheckboxProps {
  checked?: boolean;
  onCheckedChange?: (checked: boolean) => void;
  disabled?: boolean;
  className?: string;
  id?: string;
  label?: React.ReactNode;
  count?: number;
}

export function Checkbox({
  checked = false,
  onCheckedChange,
  disabled,
  className,
  id,
  label,
  count,
}: CheckboxProps) {
  return (
    <label
      htmlFor={id}
      className={cn(
        "flex cursor-pointer select-none items-center gap-2.5 text-sm",
        disabled && "cursor-not-allowed opacity-50",
        className,
      )}
    >
      <span className="relative flex h-[18px] w-[18px] shrink-0 items-center justify-center">
        <input
          id={id}
          type="checkbox"
          checked={checked}
          disabled={disabled}
          onChange={(event) => onCheckedChange?.(event.target.checked)}
          className="peer sr-only"
        />
        <span
          className={cn(
            "flex h-[18px] w-[18px] items-center justify-center rounded-[5px] border border-input bg-background transition-all",
            "peer-focus-visible:ring-2 peer-focus-visible:ring-ring peer-focus-visible:ring-offset-2 peer-focus-visible:ring-offset-background",
            checked && "border-primary bg-primary text-primary-foreground",
          )}
        >
          {checked ? <Check className="size-3" strokeWidth={3} /> : null}
        </span>
      </span>
      {label ? <span className="flex-1 leading-tight">{label}</span> : null}
      {typeof count === "number" ? (
        <span className="text-xs tabular-nums text-muted-foreground">{count}</span>
      ) : null}
    </label>
  );
}

/* --------------------------------------------------------------- accordion */
export function Accordion({
  title,
  children,
  defaultOpen = false,
  badge,
  className,
}: {
  title: React.ReactNode;
  children: React.ReactNode;
  defaultOpen?: boolean;
  badge?: React.ReactNode;
  className?: string;
}) {
  const [open, setOpen] = React.useState(defaultOpen);
  return (
    <div className={cn("border-b border-border last:border-0", className)}>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex w-full items-center justify-between py-3 text-left text-sm font-medium hover:text-primary"
      >
        <span className="flex items-center gap-2">
          {title}
          {badge}
        </span>
        <ChevronDown
          className={cn("size-4 shrink-0 transition-transform", open && "rotate-180")}
        />
      </button>
      {open ? <div className="animate-fade-up pb-4">{children}</div> : null}
    </div>
  );
}

/* ----------------------------------------------------------------- tooltip */
export function Tooltip({
  content,
  children,
  side = "top",
}: {
  content: React.ReactNode;
  children: React.ReactNode;
  side?: "top" | "bottom";
}) {
  const [open, setOpen] = React.useState(false);
  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      {children}
      {open ? (
        <span
          role="tooltip"
          className={cn(
            "pointer-events-none absolute left-1/2 z-50 w-max max-w-[16rem] -translate-x-1/2 rounded-lg border border-border bg-popover px-2.5 py-1.5 text-xs font-normal text-popover-foreground shadow-lg",
            side === "top" ? "bottom-full mb-2" : "top-full mt-2",
          )}
        >
          {content}
        </span>
      ) : null}
    </span>
  );
}

/* ---------------------------------------------------------------- skeleton */
export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("skeleton rounded-md", className)} {...props} />;
}

/* ---------------------------------------------------------------- progress */
export function Progress({
  value,
  className,
}: {
  value: number;
  className?: string;
}) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div className={cn("h-1.5 w-full overflow-hidden rounded-full bg-muted", className)}>
      <div
        className="h-full rounded-full bg-primary transition-[width] duration-500"
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}

/* --------------------------------------------------------------- separator */
export function Separator({
  className,
  orientation = "horizontal",
}: {
  className?: string;
  orientation?: "horizontal" | "vertical";
}) {
  return (
    <div
      role="separator"
      className={cn(
        "shrink-0 bg-border",
        orientation === "horizontal" ? "h-px w-full" : "h-full w-px",
        className,
      )}
    />
  );
}

/* ------------------------------------------------------------------ avatar */
export function Avatar({
  src,
  name,
  size = 36,
  className,
}: {
  src?: string | null;
  name: string;
  size?: number;
  className?: string;
}) {
  const [failed, setFailed] = React.useState(false);
  const letters = name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join("");

  if (src && !failed) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={src}
        alt=""
        width={size}
        height={size}
        onError={() => setFailed(true)}
        className={cn("shrink-0 rounded-lg object-cover", className)}
        style={{ width: size, height: size }}
      />
    );
  }
  return (
    <span
      className={cn(
        "flex shrink-0 items-center justify-center rounded-lg border border-border bg-muted font-semibold text-muted-foreground",
        className,
      )}
      style={{ width: size, height: size, fontSize: size * 0.36 }}
      aria-hidden
    >
      {letters || <Minus className="size-3" />}
    </span>
  );
}