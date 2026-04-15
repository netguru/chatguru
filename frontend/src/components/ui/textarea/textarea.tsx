import type * as React from "react";

import { cn } from "../../../utils/utils";

// ─── Types ───────────────────────────────────────────────────────────────────

type TextareaProps = React.ComponentProps<"textarea">;

type TextareaFieldProps = React.ComponentProps<"div">;

type TextareaLabelProps = React.ComponentProps<"label"> & {
  required?: boolean;
};

type TextareaHintTextProps = React.ComponentProps<"p">;

type TextareaCounterProps = React.ComponentProps<"span"> & {
  current: number;
  max: number;
};

// ─── Field ───────────────────────────────────────────────────────────────────

function TextareaField({ className, ...props }: TextareaFieldProps) {
  return <div className={cn("group flex w-full flex-col gap-1.5", className)} {...props} />;
}

// ─── Label ───────────────────────────────────────────────────────────────────

function TextareaLabel({ className, required, children, ...props }: TextareaLabelProps) {
  return (
    // biome-ignore lint/a11y/noLabelWithoutControl: <label> is used as a wrapper for the label text and the required asterisk, and is associated with the textarea via aria-labelledby.
    <label
      className={cn(
        "text-t4",
        "text-text-label",
        "peer-disabled:cursor-not-allowed peer-disabled:text-text-disabled-label",
        className
      )}
      {...props}
    >
      {children}
      {required && (
        <span className="ml-0.5 text-destructive" aria-hidden="true">
          *
        </span>
      )}
    </label>
  );
}

// ─── HintText ────────────────────────────────────────────────────────────────

function TextareaHintText({ className, ...props }: TextareaHintTextProps) {
  return (
    <p
      className={cn(
        "text-t4 text-text-label",
        "peer-aria-invalid:text-semantic-error-strong",
        className
      )}
      {...props}
    />
  );
}

// ─── Counter ─────────────────────────────────────────────────────────────────

function TextareaCounter({ current, max, className, ...props }: TextareaCounterProps) {
  const isOver = current > max;
  return (
    <span className={cn("text-text-primary", "text-t4 tabular-nums", className)} {...props}>
      <span
        className={cn(
          "group-has-focus:text-text-interactive",
          isOver && "text-semantic-error-strong"
        )}
      >
        {current}
      </span>
      /{max}
    </span>
  );
}

// ─── Textarea ─────────────────────────────────────────────────────────────────

function Textarea({ className, ...props }: TextareaProps) {
  return (
    <textarea
      className={cn(
        // Layout
        "peer flex w-full",
        "rounded-m border",
        // Spacing & typography
        "p-3 text-t2",
        // Base colors
        "bg-surface-inverted text-text-primary",
        "placeholder:text-text-placeholder",
        // Transition
        "transition-colors",
        // Focus
        "outline-hidden",
        "focus-visible:ring",
        // Default interactive states
        "border-border-neutral-strong",
        "hover:border-border-hover-neutral-strong hover:bg-surface-hover-base",
        "focus:border-surface-active-interactive-strong focus:bg-surface-inverted focus:text-text-primary",
        // aria-invalid overrides
        "aria-invalid:border-semantic-error-strong aria-invalid:bg-surface-inverted",
        "aria-invalid:hover:border-semantic-error-hover-strong aria-invalid:hover:bg-surface-base",
        "aria-invalid:focus:border-semantic-error-strong aria-invalid:focus:bg-surface-inverted aria-invalid:focus:text-text-primary",
        // Disabled
        "disabled:pointer-events-none",
        "disabled:bg-surface-disabled-base disabled:border-border-disabled-medium-soft-softer",
        "disabled:text-text-disabled-primary disabled:placeholder:text-text-disabled-placeholder",
        className
      )}
      {...props}
    />
  );
}

export type {
  TextareaCounterProps,
  TextareaFieldProps,
  TextareaHintTextProps,
  TextareaLabelProps,
  TextareaProps,
};
export { Textarea, TextareaCounter, TextareaField, TextareaHintText, TextareaLabel };
