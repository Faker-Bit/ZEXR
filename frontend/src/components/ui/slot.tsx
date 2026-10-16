import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Minimal `asChild` slot.
 *
 * Avoids pulling in @radix-ui/react-slot while keeping the familiar
 * `<Button asChild><Link/></Button>` ergonomics.
 */
export interface SlotProps extends React.HTMLAttributes<HTMLElement> {
  children?: React.ReactNode;
}

export const Slot = React.forwardRef<HTMLElement, SlotProps>(
  ({ children, className, ...props }, ref) => {
    if (!React.isValidElement(children)) return null;
    const child = children as React.ReactElement<Record<string, unknown>>;
    return React.cloneElement(child, {
      ...props,
      ...child.props,
      className: cn(className, child.props.className as string | undefined),
      ref,
    } as Record<string, unknown>);
  },
);
Slot.displayName = "Slot";