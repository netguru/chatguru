"use client";

import * as AvatarPrimitive from "@radix-ui/react-avatar";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "../../../utils/utils";

const avatarVariants = cva(
  ["relative flex shrink-0", "bg-surface-neutral-medium", "border border-border-neutral-soft"],
  {
    variants: {
      shape: {
        circle: "rounded-full",
        square: "",
      },
      size: {
        s: "size-6",
        m: "size-8",
        l: "size-10",
        xl: "size-12",
        "2xl": "size-14",
      },
    },
    compoundVariants: [
      { shape: "square", size: "s", className: "rounded-s" },
      { shape: "square", size: "m", className: "rounded-s" },
      { shape: "square", size: "l", className: "rounded-m" },
      { shape: "square", size: "xl", className: "rounded-l" },
      { shape: "square", size: "2xl", className: "rounded-l" },
    ],
    defaultVariants: {
      shape: "circle",
      size: "l",
    },
  }
);

type AvatarProps = React.ComponentProps<typeof AvatarPrimitive.Root> &
  VariantProps<typeof avatarVariants>;

const AvatarContext = React.createContext<Pick<AvatarProps, "shape" | "size">>({
  shape: "circle",
  size: "l",
});

function Avatar({ className, shape = "circle", size = "l", children, ...props }: AvatarProps) {
  return (
    <AvatarContext.Provider value={{ shape, size }}>
      <AvatarPrimitive.Root className={cn(avatarVariants({ shape, size }), className)} {...props}>
        {children}
      </AvatarPrimitive.Root>
    </AvatarContext.Provider>
  );
}
Avatar.displayName = AvatarPrimitive.Root.displayName;

type AvatarImageProps = React.ComponentProps<typeof AvatarPrimitive.Image>;

function AvatarImage({ className, ...props }: AvatarImageProps) {
  return (
    <AvatarPrimitive.Image
      className={cn("aspect-square size-full rounded-[inherit]", className)}
      {...props}
    />
  );
}
AvatarImage.displayName = AvatarPrimitive.Image.displayName;

type AvatarFallbackProps = React.ComponentProps<typeof AvatarPrimitive.Fallback>;

function AvatarFallback({ className, ...props }: AvatarFallbackProps) {
  return (
    <AvatarPrimitive.Fallback
      className={cn(
        [
          "bg-muted text-muted-foreground",
          "flex size-full items-center justify-center",
          "rounded-[inherit] overflow-hidden",
          "text-sm font-medium",
        ],
        className
      )}
      {...props}
    />
  );
}
AvatarFallback.displayName = AvatarPrimitive.Fallback.displayName;

const avatarStatusVariants = cva(["absolute size-2 rounded-full", "ring ring-core-white"], {
  variants: {
    status: {
      online: "bg-semantic-success-strong",
      offline: "bg-text-disabled-primary",
      busy: "bg-semantic-error-strong",
    },
    shape: {
      circle: "",
      square: "",
    },
    size: {
      s: "",
      m: "",
      l: "",
      xl: "",
      "2xl": "",
    },
  },
  compoundVariants: [
    { shape: "circle", size: "s", className: "-right-0.5 -bottom-0.5" },
    { shape: "circle", size: "m", className: "right-0 bottom-0" },
    { shape: "circle", size: "l", className: "right-px bottom-px" },
    { shape: "circle", size: "xl", className: "right-0.75 bottom-0.75" },
    { shape: "circle", size: "2xl", className: "right-1 bottom-1" },

    { shape: "square", size: "s", className: "-right-0.5 -bottom-0.5" },
    { shape: "square", size: "m", className: "-right-0.5 -bottom-0.5" },
    { shape: "square", size: "l", className: "right-0 bottom-0" },
    { shape: "square", size: "xl", className: "-right-0.5 -bottom-0.5" },
    { shape: "square", size: "2xl", className: "-right-0.5 -bottom-0.5" },
  ],
});

type AvatarStatusProps = React.ComponentProps<"span"> &
  Omit<VariantProps<typeof avatarStatusVariants>, "shape" | "size">;

function AvatarStatus({ className, status, ...props }: AvatarStatusProps) {
  const { shape, size } = React.useContext(AvatarContext);

  return (
    <span
      data-status={status}
      className={cn(avatarStatusVariants({ status, shape, size }), className)}
      {...props}
    />
  );
}
AvatarStatus.displayName = "AvatarStatus";

export type { AvatarFallbackProps, AvatarImageProps, AvatarProps, AvatarStatusProps };
export { Avatar, AvatarFallback, AvatarImage, AvatarStatus };
