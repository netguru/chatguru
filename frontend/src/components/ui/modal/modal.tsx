"use client";

import { XIcon } from "@phosphor-icons/react/X";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import type * as React from "react";

import { cn } from "../../../utils/utils";
import { IconButton, type IconButtonProps } from "../icon-button";

/*
 * -----
 * Modal
 * -----
 */

type ModalProps = React.ComponentProps<typeof DialogPrimitive.Root>;
const Modal = DialogPrimitive.Root;
Modal.displayName = "Modal";

/*
 * ------------
 * ModalTrigger
 * ------------
 */

type ModalTriggerProps = React.ComponentProps<typeof DialogPrimitive.Trigger>;
const ModalTrigger = DialogPrimitive.Trigger;
ModalTrigger.displayName = "ModalTrigger";

/*
 * -----------
 * ModalPortal
 * -----------
 */

type ModalPortalProps = React.ComponentProps<typeof DialogPrimitive.Portal>;
const ModalPortal = DialogPrimitive.Portal;
ModalPortal.displayName = "ModalPortal";

/*
 * ----------
 * ModalClose
 * ----------
 */

type ModalCloseProps = React.ComponentProps<typeof DialogPrimitive.Close>;
const ModalClose = DialogPrimitive.Close;
ModalClose.displayName = "ModalClose";

/*
 * ------------
 * ModalOverlay
 * ------------
 */

type ModalOverlayProps = React.ComponentProps<typeof DialogPrimitive.Overlay>;

function ModalOverlay({ className, ...props }: ModalOverlayProps) {
  return (
    <DialogPrimitive.Overlay
      data-slot="modal-overlay"
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
ModalOverlay.displayName = DialogPrimitive.Overlay.displayName;

/*
 * ------------
 * ModalContent
 * ------------
 */

type ModalContentProps = React.ComponentProps<typeof DialogPrimitive.Content> & {
  showCloseButton?: boolean;
  closeButtonProps?: Partial<IconButtonProps>;
};

function ModalContent({
  className,
  children,
  showCloseButton = true,
  closeButtonProps,
  ...props
}: ModalContentProps) {
  return (
    <ModalPortal>
      <ModalOverlay />
      <DialogPrimitive.Content
        data-slot="modal-content"
        className={cn(
          [
            /* Background */
            "bg-surface-base",
            /* Border */
            "border border-border-neutral-medium",
            /* Positioning */
            "fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2",
            /* Layout */
            "grid",
            /* Size */
            "w-[calc(100%-40px)] md:w-115.5 lg:w-169",
            /* Shape & Shadow */
            "rounded-l shadow-medium-top-light",
            /* Focus */
            "focus:outline-none",
            /* Animation */
            "duration-200",
            "data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95",
            "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95",
          ],
          className
        )}
        {...props}
      >
        {children}
        {showCloseButton && (
          <ModalClose asChild>
            <IconButton
              data-slot="modal-close-button"
              variant="tertiary"
              size="m"
              aria-label="Close"
              className="absolute right-3 top-3"
              {...closeButtonProps}
            >
              <XIcon weight="bold" />
            </IconButton>
          </ModalClose>
        )}
      </DialogPrimitive.Content>
    </ModalPortal>
  );
}
ModalContent.displayName = DialogPrimitive.Content.displayName;

/*
 * -----------
 * ModalHeader
 * -----------
 */

function ModalHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="modal-header"
      className={cn("flex gap-2 py-2.5 px-4", "border-b border-border-neutral-soft", className)}
      {...props}
    />
  );
}
ModalHeader.displayName = "ModalHeader";

/*
 * -----------
 * ModalFooter
 * -----------
 */

function ModalFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="modal-footer"
      className={cn(
        "flex flex-col-reverse gap-4 sm:flex-row sm:justify-end",
        "px-4 py-6",
        "border-t border-transparent [[data-slot=modal-body]~&]:border-border-neutral-soft",
        className
      )}
      {...props}
    />
  );
}
ModalFooter.displayName = "ModalFooter";

/*
 * ----------
 * ModalTitle
 * ----------
 */

type ModalTitleProps = React.ComponentProps<typeof DialogPrimitive.Title>;

function ModalTitle({ className, ...props }: ModalTitleProps) {
  return (
    <DialogPrimitive.Title
      data-slot="modal-title"
      className={cn(
        "text-t2 font-strong text-text-title text-center",
        "line-clamp-1",
        "w-full py-3 px-1.5",
        className
      )}
      {...props}
    />
  );
}
ModalTitle.displayName = DialogPrimitive.Title.displayName;

/*
 * ---------
 * ModalBody
 * ---------
 */

type ModalBodyProps = React.ComponentProps<"div">;

function ModalBody({ className, ...props }: ModalBodyProps) {
  return (
    <div
      data-slot="modal-body"
      className={cn("text-text-secondary text-t3 text-center", "p-3", className)}
      {...props}
    />
  );
}
ModalBody.displayName = "ModalBody";

/*
 * -------
 * Exports
 * -------
 */

export type {
  ModalBodyProps,
  ModalCloseProps,
  ModalContentProps,
  ModalOverlayProps,
  ModalPortalProps,
  ModalProps,
  ModalTitleProps,
  ModalTriggerProps,
};
export {
  Modal,
  ModalBody,
  ModalClose,
  ModalContent,
  ModalFooter,
  ModalHeader,
  ModalOverlay,
  ModalPortal,
  ModalTitle,
  ModalTrigger,
};
