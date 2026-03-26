import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import type * as React from "react";

import { cn } from "../../../utils/utils";

const buttonVariants = cva(
  [
    "inline-flex items-center justify-center gap-2 whitespace-nowrap",
    "rounded-m",
    "transition-colors",
    "cursor-pointer",
    "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:ring-offset-2 focus-visible:ring-offset-focus-offset",
    "disabled:pointer-events-none",
    "[&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  ],
  {
    variants: {
      variant: {
        fill: [
          "text-text-inverted",
          "disabled:bg-surface-disabled-base disabled:text-text-disabled-interactive",
        ],
        outline: [
          "bg-transparent border",
          "disabled:bg-transparent disabled:border-border-disabled-strong-stronger disabled:text-text-disabled-interactive",
        ],
        ghost: [
          "bg-transparent text-text-interactive",
          "hover:bg-surface-hover-interactive-strong/10",
          "disabled:text-text-disabled-interactive",
        ],
        subtle: [
          "bg-transparent",
          "hover:bg-surface-hover-interactive-strong/10",
          "active:bg-surface-active-interactive-strong/20",
          "disabled:text-text-disabled-interactive",
        ],
        text: ["bg-transparent text-text-interactive", "disabled:text-text-disabled-interactive"],
      },
      color: {
        accent: "",
        error: "",
        success: "",
        inverted: "",
        neutral: "",
      },
      size: {
        s: "h-8 px-3 py-1.5 text-button-s",
        m: "h-10 px-3 py-2 text-button-m",
        l: "h-12 px-4 py-3 text-button-l",
        xl: "h-14 px-5 py-5 text-button-l",
      },
    },
    compoundVariants: [
      /*
       * ----
       * Fill
       * ----
       */
      {
        variant: "fill",
        color: "accent",
        className: [
          "bg-surface-interactive-strong",
          "hover:bg-surface-hover-interactive-strong",
          "active:bg-surface-active-interactive-strong",
          "focus-visible:bg-surface-interactive-strong",
        ],
      },
      {
        variant: "fill",
        color: "error",
        className: [
          "bg-semantic-error-strong",
          "hover:bg-semantic-error-hover-strong",
          "active:bg-semantic-error-active-strong",
          "focus-visible:bg-semantic-error-strong",
        ],
      },
      {
        variant: "fill",
        color: "success",
        className: [
          "bg-semantic-success-strong",
          "hover:bg-semantic-success-hover-strong",
          "active:bg-semantic-success-active-strong",
          "focus-visible:bg-semantic-success-strong",
        ],
      },
      {
        variant: "fill",
        color: "inverted",
        className: [
          "bg-surface-inverted text-text-interactive",
          "hover:bg-surface-hover-base hover:text-text-active-interactive",
          "active:bg-surface-active-base active:text-text-active-interactive",
          "focus-visible:bg-surface-inverted",
          "disabled:text-text-disabled-interactive",
        ],
      },
      {
        variant: "fill",
        color: "neutral",
        className: [
          "bg-surface-neutral-stronger text-text-inverted",
          "hover:bg-surface-hover-neutral-stronger",
          "active:bg-surface-active-neutral-stronger",
          "focus-visible:bg-surface-neutral-stronger",
        ],
      },
      /*
       * -------
       * Outline
       * -------
       */
      {
        variant: "outline",
        color: "accent",
        className: [
          "border-border-interactive-strong text-text-interactive",
          "hover:bg-surface-hover-interactive-strong/10 hover:border-border-hover-interactive-strong hover:text-text-hover-interactive",
          "active:bg-surface-active-interactive-strong/10 active:border-border-active-interactive-strong active:text-text-active-interactive",
          "focus-visible:bg-transparent focus-visible:border-border-interactive-strong focus-visible:text-text-interactive",
        ],
      },
      {
        variant: "outline",
        color: "error",
        className: [
          "border-semantic-error-active-strong text-semantic-error-strong",
          "hover:bg-semantic-error-hover-strong/10 hover:border-semantic-error-hover-strong hover:text-semantic-error-hover-strong",
          "active:bg-semantic-error-active-strong/10 active:border-semantic-error-active-strong active:text-semantic-error-active-strong",
          "focus-visible:bg-transparent focus-visible:border-semantic-error-active-strong focus-visible:text-semantic-error-strong",
        ],
      },
      {
        variant: "outline",
        color: "success",
        className: [
          "border-semantic-success-strong text-semantic-success-strong",
          "hover:bg-semantic-success-strong/10 hover:border-semantic-success-hover-strong hover:text-semantic-success-strong",
          "active:bg-semantic-success-strong/10 active:border-semantic-success-active-strong active:text-semantic-success-active-strong",
          "focus-visible:bg-transparent focus-visible:border-semantic-success-strong focus-visible:text-semantic-success-strong",
        ],
      },
      {
        variant: "outline",
        color: "inverted",
        className: [
          "border-border-neutral-soft text-text-inverted",
          "hover:bg-text-hover-inverted/10 hover:border-border-hover-neutral-soft hover:text-text-hover-inverted",
          "active:bg-surface-active-interactive-soft/10 active:border-border-inverted active:text-text-active-inverted",
          "focus-visible:bg-transparent focus-visible:border-border-neutral-soft focus-visible:text-text-inverted",
          "disabled:border-border-disabled-medium-soft-softer disabled:text-text-disabled-inverted",
        ],
      },
      {
        variant: "outline",
        color: "neutral",
        className: [
          "border-border-neutral-strong text-text-secondary",
          "hover:border-border-active-neutral-strong hover:text-text-secondary hover:bg-surface-hover-neutral-medium/10",
          "active:border-border-active-neutral-strong active:text-text-primary active:bg-surface-active-neutral-strong/10",
          "focus-visible:border-border-neutral-strong focus-visible:text-text-secondary",
          "disabled:border-border-disabled-strong-stronger disabled:text-text-disabled-secondary",
        ],
      },
      /*
       * -----
       * Ghost
       * -----
       */
      {
        variant: "ghost",
        color: "accent",
        className: [
          "text-text-interactive",
          "hover:bg-surface-hover-interactive-strong/10 hover:text-text-hover-interactive",
          "active:bg-surface-active-interactive-strong/10 active:text-text-active-interactive",
          "focus-visible:bg-transparent focus-visible:text-text-interactive",
          "disabled:text-text-disabled-interactive",
        ],
      },
      {
        variant: "ghost",
        color: "error",
        className: [
          "text-semantic-error-strong",
          "hover:bg-semantic-error-hover-strong/10 hover:text-semantic-error-hover-strong",
          "active:bg-semantic-error-active-strong/10 active:text-semantic-error-active-strong",
          "focus-visible:bg-transparent focus-visible:text-semantic-error-strong",
        ],
      },
      {
        variant: "ghost",
        color: "success",
        className: [
          "text-semantic-success-strong",
          "hover:bg-semantic-success-strong/10 hover:text-semantic-success-strong",
          "active:bg-semantic-success-active-strong/10 active:text-semantic-success-active-strong",
          "focus-visible:bg-transparent focus-visible:text-semantic-success-strong",
        ],
      },
      {
        variant: "ghost",
        color: "inverted",
        className: [
          "text-text-inverted",
          "hover:bg-text-hover-inverted/10 hover:text-text-hover-inverted",
          "active:bg-surface-active-interactive-soft/10 active:text-text-inverted",
          "focus-visible:bg-transparent focus-visible:text-text-inverted",
          "disabled:text-text-disabled-inverted",
        ],
      },
      {
        variant: "ghost",
        color: "neutral",
        className: [
          "text-text-secondary",
          "hover:text-text-primary hover:bg-surface-hover-neutral-medium",
          "active:text-text-primary active:bg-surface-active-neutral-strong",
          "focus-visible:text-text-secondary focus-visible:bg-core-white",
          "disabled:text-text-disabled-secondary",
        ],
      },
      /*
       * ------
       * Subtle
       * ------
       */
      {
        variant: "subtle",
        color: "accent",
        className: [
          "text-text-interactive",
          "hover:text-text-hover-interactive",
          "active:text-text-active-interactive",
          "focus-visible:text-text-interactive",
        ],
      },
      {
        variant: "subtle",
        color: "error",
        className: [
          "text-semantic-error-strong",
          "hover:bg-semantic-error-hover-strong/10 hover:text-semantic-error-hover-strong",
          "active:bg-semantic-error-active-strong/20 active:text-semantic-error-active-strong",
          "focus-visible:bg-transparent focus-visible:text-semantic-error-strong",
        ],
      },
      {
        variant: "subtle",
        color: "success",
        className: [
          "text-semantic-success-strong",
          "hover:bg-semantic-success-strong/10 hover:text-semantic-success-strong",
          "active:bg-semantic-success-active-strong/20 active:text-semantic-success-active-strong",
          "focus-visible:bg-transparent focus-visible:text-semantic-success-strong",
        ],
      },
      {
        variant: "subtle",
        color: "inverted",
        className: [
          "text-text-inverted",
          "hover:bg-text-hover-inverted/10 hover:text-text-hover-inverted",
          "active:bg-surface-active-interactive-soft/20 active:text-text-inverted",
          "focus-visible:bg-transparent focus-visible:text-text-inverted",
          "disabled:text-text-disabled-inverted",
        ],
      },
      {
        variant: "subtle",
        color: "neutral",
        className: [
          "bg-surface-neutral-soft text-text-secondary",
          "hover:bg-surface-hover-neutral-soft hover:text-text-secondary",
          "active:bg-surface-hover-neutral-soft active:text-text-primary",
          "focus-visible:bg-surface-active-neutral-soft focus-visible:text-text-primary",
          "disabled:bg-surface-disabled-medium-soft-softer disabled:text-text-disabled-primary",
        ],
      },
      /*
       * ----
       * Text
       * ----
       */
      {
        variant: "text",
        color: "error",
        className: ["text-semantic-error-strong", "hover:text-semantic-error-hover-strong"],
      },
      {
        variant: "text",
        color: "success",
        className: ["text-semantic-success-strong", "hover:text-semantic-success-strong"],
      },
      {
        variant: "text",
        color: "inverted",
        className: [
          "text-text-inverted",
          "hover:text-text-hover-inverted",
          "disabled:text-text-disabled-inverted",
        ],
      },
    ],
    defaultVariants: {
      variant: "fill",
      color: "accent",
      size: "m",
    },
  }
);

type ButtonProps = Omit<React.ComponentProps<"button">, "color"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean;
  };

function Button({ className, variant, color, size, asChild = false, ref, ...props }: ButtonProps) {
  const Comp = asChild ? Slot : "button";
  return (
    <Comp
      className={cn(buttonVariants({ variant, color, size }), className)}
      ref={ref as React.Ref<HTMLButtonElement>}
      {...props}
    />
  );
}
Button.displayName = "Button";

export type { ButtonProps };
export { Button, buttonVariants };
