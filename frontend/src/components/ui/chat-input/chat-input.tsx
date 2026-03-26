"use client";

import * as React from "react";
import { cn } from "../../../utils/utils";

type ChatInputContextValue = { disabled: boolean };

const ChatInputContext = React.createContext<ChatInputContextValue>({
  disabled: false,
});

type ChatInputProps = React.ComponentProps<"div"> & {
  disabled?: boolean;
};

function ChatInput({ className, disabled = false, children, ...props }: ChatInputProps) {
  return (
    <ChatInputContext.Provider value={{ disabled }}>
      <div
        data-disabled={disabled || undefined}
        className={cn(
          [
            "flex flex-col items-end gap-1",
            "rounded-m border border-border-neutral-strong",
            "bg-surface-inverted",
            "p-2",
            "focus-visible:ring",
            "data-disabled:cursor-not-allowed data-disabled:opacity-50",
          ],
          className
        )}
        {...props}
      >
        {children}
      </div>
    </ChatInputContext.Provider>
  );
}

type ChatInputTextareaProps = Omit<React.ComponentProps<"textarea">, "disabled"> & {
  maxRows?: number;
};

function ChatInputTextarea({
  maxRows = 5,
  onChange,
  ref: externalRef,
  className,
  ...props
}: ChatInputTextareaProps) {
  const { disabled } = React.useContext(ChatInputContext);
  const innerRef = React.useRef<HTMLTextAreaElement | null>(null);

  const resize = () => {
    const el = innerRef.current;
    if (!el) return;
    const { lineHeight, paddingTop, paddingBottom } = window.getComputedStyle(el);
    const max =
      (parseFloat(lineHeight) || 20) * maxRows +
      (parseFloat(paddingTop) || 0) +
      (parseFloat(paddingBottom) || 0);
    el.style.height = "auto";
    const next = Math.min(el.scrollHeight, max);
    el.style.height = `${next}px`;
    el.style.overflowY = el.scrollHeight > max ? "auto" : "hidden";
  };

  // biome-ignore lint/correctness/useExhaustiveDependencies: props.value and props.defaultValue trigger resize but are not read inside resize directly
  React.useEffect(resize, [props.value, props.defaultValue, maxRows]);

  const ref = React.useCallback(
    (el: HTMLTextAreaElement | null) => {
      innerRef.current = el;
      if (typeof externalRef === "function") externalRef(el);
      else if (externalRef) (externalRef as { current: HTMLTextAreaElement | null }).current = el;
    },
    [externalRef]
  );

  return (
    <textarea
      ref={ref}
      disabled={disabled}
      rows={1}
      className={cn(
        [
          "text-t2",
          "flex min-h-9 w-full resize-none bg-surface-inverted",
          "p-2",
          "placeholder:text-text-placeholder",
          "focus-visible:outline-none",
          "disabled:cursor-not-allowed",
        ],
        className
      )}
      onChange={(e) => {
        resize();
        onChange?.(e);
      }}
      {...props}
    />
  );
}
ChatInputTextarea.displayName = "ChatInputTextarea";

type ChatInputActionAreaProps = React.ComponentProps<"div">;

function ChatInputActionArea({ className, children, ...props }: ChatInputActionAreaProps) {
  return (
    <div className={cn("flex w-full justify-between items-end", className)} {...props}>
      {children}
    </div>
  );
}
ChatInputActionArea.displayName = "ChatInputActionArea";

type ChatInputActionProps = React.ComponentProps<"div">;

function ChatInputAction({ className, children, ref, ...props }: ChatInputActionProps) {
  const { disabled } = React.useContext(ChatInputContext);
  return (
    <div
      ref={ref}
      data-disabled={disabled || undefined}
      className={cn("shrink-0 data-disabled:pointer-events-none", className)}
      {...props}
    >
      {children}
    </div>
  );
}
ChatInputAction.displayName = "ChatInputAction";

export type {
  ChatInputActionAreaProps,
  ChatInputActionProps,
  ChatInputProps,
  ChatInputTextareaProps,
};
export { ChatInput, ChatInputAction, ChatInputActionArea, ChatInputTextarea };
