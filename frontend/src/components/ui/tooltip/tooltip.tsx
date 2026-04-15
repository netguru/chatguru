"use client";

import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import type * as React from "react";

import { cn } from "../../../utils/utils";

/*
 * ---------------
 * TooltipProvider
 * ---------------
 */

type TooltipProviderProps = React.ComponentProps<typeof TooltipPrimitive.Provider>;
const TooltipProvider = TooltipPrimitive.Provider;
TooltipProvider.displayName = "TooltipProvider";

/*
 * -------
 * Tooltip
 * -------
 */

type TooltipProps = React.ComponentProps<typeof TooltipPrimitive.Root>;
const Tooltip = TooltipPrimitive.Root;
Tooltip.displayName = "Tooltip";

/*
 * ---------------
 * TooltipTrigger
 * ---------------
 */

type TooltipTriggerProps = React.ComponentProps<typeof TooltipPrimitive.Trigger>;
const TooltipTrigger = TooltipPrimitive.Trigger;
TooltipTrigger.displayName = "TooltipTrigger";

/*
 * --------------
 * TooltipContent
 * --------------
 */

type TooltipContentProps = React.ComponentProps<typeof TooltipPrimitive.Content>;

function TooltipContent({ className, sideOffset = 4, children, ...props }: TooltipContentProps) {
  return (
    <TooltipPrimitive.Portal>
      <TooltipPrimitive.Content
        data-slot="tooltip-content"
        sideOffset={sideOffset}
        className={cn(
          "bg-surface-neutral-stronger",
          "text-t3 font-medium text-text-inverted tracking-s",
          "shadow-medium-top-light",
          "px-3 py-2",
          "z-50 max-w-xs rounded-s",
          "origin-[--radix-tooltip-content-transform-origin]",
          "animate-in fade-in-0 zoom-in-95",
          "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95",
          "data-[side=bottom]:slide-in-from-top-2",
          "data-[side=left]:slide-in-from-right-2",
          "data-[side=right]:slide-in-from-left-2",
          "data-[side=top]:slide-in-from-bottom-2",
          className
        )}
        {...props}
      >
        {children}
        <TooltipPrimitive.Arrow className="fill-surface-neutral-stronger" />
      </TooltipPrimitive.Content>
    </TooltipPrimitive.Portal>
  );
}
TooltipContent.displayName = "TooltipContent";

/*
 * -------
 * Exports
 * -------
 */

export type { TooltipContentProps, TooltipProps, TooltipProviderProps, TooltipTriggerProps };
export { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger };
