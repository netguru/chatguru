"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import type * as React from "react";
import { cn } from "../../../utils/utils";

/*
 * -----
 * Sheet
 * -----
 */

const Sheet = DialogPrimitive.Root;
Sheet.displayName = "Sheet";

/*
 * ------------
 * SheetPortal
 * ------------
 */

const SheetPortal = DialogPrimitive.Portal;
SheetPortal.displayName = "SheetPortal";

/*
 * ------------
 * SheetOverlay
 * ------------
 */

function SheetOverlay({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Overlay>) {
  return (
    <DialogPrimitive.Overlay
      data-slot="sheet-overlay"
      className={cn(
        [
          "fixed inset-0 z-50",
          "bg-surface-overlay-strong",
          "data-[state=open]:animate-in data-[state=open]:fade-in-0",
          "data-[state=closed]:animate-out data-[state=closed]:fade-out-0",
        ],
        className
      )}
      {...props}
    />
  );
}
SheetOverlay.displayName = "SheetOverlay";

/*
 * ------------
 * SheetContent
 * ------------
 */

type SheetContentProps = React.ComponentProps<typeof DialogPrimitive.Content> & {
  side?: "left" | "right";
};

function SheetContent({ side = "left", className, children, ...props }: SheetContentProps) {
  return (
    <SheetPortal>
      <SheetOverlay />
      <DialogPrimitive.Content
        data-slot="sheet-content"
        className={cn(
          [
            "fixed inset-y-0 z-50 flex flex-col",
            "bg-surface-base text-text-label shadow-lg",
            "transition ease-in-out",
            "data-[state=open]:duration-300 data-[state=closed]:duration-200",
            "data-[state=open]:animate-in data-[state=closed]:animate-out",
          ],
          side === "left"
            ? [
                "left-0 border-r border-border-neutral-soft",
                "data-[state=open]:slide-in-from-left",
                "data-[state=closed]:slide-out-to-left",
              ]
            : [
                "right-0 border-l border-border-neutral-soft",
                "data-[state=open]:slide-in-from-right",
                "data-[state=closed]:slide-out-to-right",
              ],
          className
        )}
        {...props}
      >
        {children}
      </DialogPrimitive.Content>
    </SheetPortal>
  );
}
SheetContent.displayName = "SheetContent";

/*
 * ------------
 * SheetTitle
 * ------------
 */

const SheetTitle = DialogPrimitive.Title;
SheetTitle.displayName = "SheetTitle";

/*
 * -----------------
 * SheetDescription
 * -----------------
 */

const SheetDescription = DialogPrimitive.Description;
SheetDescription.displayName = "SheetDescription";

export { Sheet, SheetContent, SheetDescription, SheetOverlay, SheetPortal, SheetTitle };
