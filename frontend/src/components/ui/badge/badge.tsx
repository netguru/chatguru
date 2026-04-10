import { cva, type VariantProps } from "class-variance-authority";
import type * as React from "react";

import { cn } from "../../../utils/utils";

// ------------------------------------------------------------------
// Variants
// ------------------------------------------------------------------

const badgeVariants = cva(
  [
    "text-text-inverted text-t4 text-soft tracking-l",
    "w-fit",
    "inline-flex items-center",
    "rounded-full px-1.5 py-0.5",
    "select-none whitespace-nowrap",
  ],
  {
    variants: {
      variant: {
        default: "",
        brand: "",
        positive: "",
        attention: "",
        critical: "",
      },
      type: {
        strong: "",
        soft: "",
      },
    },
    compoundVariants: [
      // ── strong ──────────────────────────────────────────────────
      {
        variant: "default",
        type: "strong",
        className: ["bg-surface-neutral-stronger", "text-text-inverted"],
      },
      {
        variant: "brand",
        type: "strong",
        className: ["bg-surface-interactive-strong", "text-text-inverted"],
      },
      {
        variant: "positive",
        type: "strong",
        className: ["bg-semantic-success-strong", "text-text-inverted"],
      },
      {
        variant: "attention",
        type: "strong",
        className: ["[background-color:var(--primitive-amber-800)]", "text-text-inverted"],
      },
      {
        variant: "critical",
        type: "strong",
        className: ["bg-semantic-error-strong", "text-text-inverted"],
      },
      // ── soft ────────────────────────────────────────────────────
      {
        variant: "default",
        type: "soft",
        className: ["bg-surface-neutral-medium", "text-text-title"],
      },
      {
        variant: "brand",
        type: "soft",
        className: ["bg-surface-interactive-medium", "text-text-interactive"],
      },
      {
        variant: "positive",
        type: "soft",
        className: ["bg-semantic-success-medium", "text-text-title"],
      },
      {
        variant: "attention",
        type: "soft",
        className: ["bg-semantic-warning-medium", "text-text-title"],
      },
      {
        variant: "critical",
        type: "soft",
        className: ["bg-semantic-error-medium", "text-text-title"],
      },
    ],
    defaultVariants: {
      variant: "default",
      type: "strong",
    },
  }
);

// ------------------------------------------------------------------
// Badge
// ------------------------------------------------------------------

type BadgeProps = React.ComponentProps<"span"> & VariantProps<typeof badgeVariants>;

function Badge({ className, variant, type, ref, ...props }: BadgeProps) {
  return <span ref={ref} className={cn(badgeVariants({ variant, type }), className)} {...props} />;
}
Badge.displayName = "Badge";

export type { BadgeProps };
export { Badge, badgeVariants };
