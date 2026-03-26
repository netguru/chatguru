"use client";

import { cva } from "class-variance-authority";
import type * as React from "react";
import { cn } from "../../../utils/utils";

// ------------------------------------------------------------------
// Variants
// ------------------------------------------------------------------

const chipVariants = cva([
  "bg-surface-interactive-medium text-text-primary",
  "text-t3 font-strong",
  "rounded-full",
  "inline-flex items-center gap-2",
  "px-4 py-2",
  "ring-offset-background transition-colors",
  "cursor-pointer select-none",
  "hover:bg-surface-hover-interactive-medium",
  "active:bg-surface-active-interactive-medium",
  "focus-visible:outline-none focus-visible:ring",
  "focus-visible:bg-surface-active-interactive-medium",
  "aria-selected:bg-surface-active-interactive-medium",
  "disabled:pointer-events-none disabled:opacity-50",
  "disabled:bg-surface-disabled-strong-stronger disabled:text-text-inverted",
  "[&_svg]:size-4 [&_svg]:pointer-events-none [&_svg]:shrink-0",
]);

// ------------------------------------------------------------------
// Chip
// ------------------------------------------------------------------

type ChipProps = Omit<React.ComponentProps<"button">, "type">;

function Chip({ className, children, ...props }: ChipProps) {
  return (
    <button type="button" className={chipVariants({ className })} {...props}>
      {children}
    </button>
  );
}
Chip.displayName = "Chip";

// ------------------------------------------------------------------
// ChipLabel
// ------------------------------------------------------------------

type ChipLabelProps = React.HTMLAttributes<HTMLSpanElement>;

function ChipLabel({ className, children, ...props }: ChipLabelProps) {
  return (
    <span className={cn("leading-none", className)} {...props}>
      {children}
    </span>
  );
}
ChipLabel.displayName = "ChipLabel";

// ------------------------------------------------------------------
// Exports
// ------------------------------------------------------------------

export type { ChipLabelProps, ChipProps };
export { Chip, ChipLabel, chipVariants };
