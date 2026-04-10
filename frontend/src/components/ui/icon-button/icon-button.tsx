import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import type * as React from "react";

import { cn } from "../../../utils/utils";

const iconButtonVariants = cva(
  [
    "inline-flex items-center justify-center shrink-0",
    "rounded-m",
    "transition-colors",
    "cursor-pointer",
    "focus-visible:outline-hidden focus-visible:ring focus-visible:ring-offset-2",
    "disabled:pointer-events-none",
    "[&_svg]:pointer-events-none [&_svg]:shrink-0",
  ],
  {
    variants: {
      variant: {
        primary: [
          "text-text-inverted",
          "disabled:bg-surface-disabled-strong-stronger disabled:text-text-inverted",
          "bg-surface-interactive-strong",
          "hover:bg-surface-hover-interactive-strong",
          "focus-visible:bg-surface-interactive-strong",
        ],
        secondary: [
          "bg-transparent border",
          "border-border-interactive-strong text-text-interactive",
          "hover:bg-surface-hover-interactive-strong/10 hover:border-border-hover-interactive-strong hover:text-text-hover-interactive",
          "focus-visible:bg-transparent focus-visible:border-border-interactive-strong focus-visible:text-text-interactive",
          "disabled:bg-transparent disabled:border-border-disabled-strong-stronger disabled:text-text-disabled-interactive",
        ],
        tertiary: [
          "bg-transparent text-text-interactive",
          "hover:bg-surface-hover-interactive-strong/10",
          "focus-visible:bg-transparent focus-visible:text-text-interactive",
          "disabled:text-text-disabled-interactive",
        ],
        subtle: [
          "bg-transparent",
          "hover:bg-surface-hover-interactive-strong/10",
          "active:bg-surface-active-interactive-strong/20",
          "disabled:text-text-disabled-interactive",
        ],
      },
      color: {
        error: "",
        success: "",
        inverted: "",
      },
      size: {
        xs: ["size-6 p-1", "[&_svg]:size-4"],
        s: ["size-8 p-2", "[&_svg]:size-4"],
        m: ["size-10 p-2", "[&_svg]:size-6"],
        l: ["size-12 p-3", "[&_svg]:size-6"],
        xl: ["size-14 p-4", "[&_svg]:size-6"],
      },
    },
    compoundVariants: [
      {
        variant: "primary",
        color: "error",
        className: [
          "bg-semantic-error-strong",
          "hover:bg-semantic-error-hover-strong",
          "focus-visible:bg-semantic-error-strong",
        ],
      },
      {
        variant: "primary",
        color: "success",
        className: [
          "bg-semantic-success-strong",
          "hover:bg-semantic-success-hover-strong",
          "focus-visible:bg-semantic-success-strong",
        ],
      },
      {
        variant: "primary",
        color: "inverted",
        className: [
          "bg-surface-inverted text-text-interactive",
          "hover:bg-surface-hover-base hover:text-text-active-interactive",
          "focus-visible:bg-surface-inverted",
          "disabled:text-text-disabled-interactive",
        ],
      },
      {
        variant: "secondary",
        color: "error",
        className: [
          "border-semantic-error-active-strong text-semantic-error-strong",
          "hover:bg-semantic-error-hover-strong/10 hover:border-semantic-error-hover-strong hover:text-semantic-error-hover-strong",
          "focus-visible:bg-transparent focus-visible:border-semantic-error-active-strong focus-visible:text-semantic-error-strong",
        ],
      },
      {
        variant: "secondary",
        color: "success",
        className: [
          "border-semantic-success-strong text-semantic-success-strong",
          "hover:bg-semantic-success-strong/10 hover:border-semantic-success-hover-strong hover:text-semantic-success-strong",
          "focus-visible:bg-transparent focus-visible:border-semantic-success-strong focus-visible:text-semantic-success-strong",
        ],
      },
      {
        variant: "secondary",
        color: "inverted",
        className: [
          "border-border-neutral-soft text-text-inverted",
          "hover:bg-text-hover-inverted/10 hover:border-border-hover-neutral-soft hover:text-text-hover-inverted",
          "focus-visible:bg-transparent focus-visible:border-border-neutral-soft focus-visible:text-text-inverted",
          "disabled:border-border-disabled-medium-soft-softer disabled:text-text-disabled-inverted",
        ],
      },
      {
        variant: "tertiary",
        color: "error",
        className: [
          "text-semantic-error-strong",
          "hover:bg-semantic-error-hover-strong/10 hover:text-semantic-error-hover-strong",
          "focus-visible:bg-transparent focus-visible:text-semantic-error-strong",
        ],
      },
      {
        variant: "tertiary",
        color: "success",
        className: [
          "text-semantic-success-strong",
          "hover:bg-semantic-success-strong/10 hover:text-semantic-success-strong",
          "focus-visible:bg-transparent focus-visible:text-semantic-success-strong",
        ],
      },
      {
        variant: "tertiary",
        color: "inverted",
        className: [
          "text-text-inverted",
          "hover:bg-text-hover-inverted/10 hover:text-text-hover-inverted",
          "focus-visible:bg-transparent focus-visible:text-text-inverted",
          "disabled:text-text-disabled-inverted",
        ],
      },
    ],
    defaultVariants: {
      variant: "primary",
      size: "m",
    },
  }
);

type IconButtonProps = Omit<React.ComponentProps<"button">, "color"> &
  VariantProps<typeof iconButtonVariants> & {
    asChild?: boolean;
    "aria-label": string;
  };

function IconButton({
  className,
  variant,
  color,
  size,
  asChild = false,
  ...props
}: IconButtonProps) {
  const Comp = asChild ? Slot : "button";
  return (
    <Comp className={cn(iconButtonVariants({ variant, color, size }), className)} {...props} />
  );
}
IconButton.displayName = "IconButton";

export type { IconButtonProps };
export { IconButton, iconButtonVariants };
