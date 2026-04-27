import { PaperclipIcon, PaperPlaneRightIcon, PlusIcon } from "@phosphor-icons/react";
import * as React from "react";
import { useAppStore } from "../../store/appStore";
import { cn } from "../../utils/utils";
import {
  ChatInputAction,
  ChatInputActionArea,
  ChatInput as ChatInputPrimitive,
  ChatInputTextarea,
} from "../ui/chat-input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu";
import { IconButton } from "../ui/icon-button";

interface Props {
  onSend: (text: string) => void;
  value?: string;
  onValueChange?: (value: string) => void;
  className?: string;
}

export function ChatInput({ onSend, value: valueProp, onValueChange, className }: Props) {
  const [localValue, setLocalValue] = React.useState("");
  const isControlled = valueProp !== undefined;
  const value = isControlled ? valueProp : localValue;
  const setValue = (v: string) => {
    if (!isControlled) setLocalValue(v);
    onValueChange?.(v);
  };
  const isConnected = useAppStore((state) => state.isConnected);
  const isStreaming = useAppStore((state) => state.isStreaming);
  const isDisabled = !isConnected || isStreaming;
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed || isDisabled) return;
    onSend(trimmed);
    setValue("");
  };

  return (
    <ChatInputPrimitive
      disabled={isDisabled}
      className={cn(className)}
      onClick={() => textareaRef.current?.focus()}
    >
      <ChatInputTextarea
        ref={textareaRef}
        placeholder="Ask anything..."
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
          }
        }}
      />
      <ChatInputActionArea>
        <ChatInputAction>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <IconButton variant="subtle" size="s" aria-label="Attach file" disabled={isDisabled}>
                <PlusIcon weight="bold" />
              </IconButton>
            </DropdownMenuTrigger>
            <DropdownMenuContent side="top" align="start" className="w-44">
              <DropdownMenuItem role="button">
                <PaperclipIcon weight="bold" />
                Upload files
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </ChatInputAction>
        <ChatInputAction className="ml-auto">
          <IconButton
            variant="primary"
            size="s"
            aria-label="Send message"
            disabled={isDisabled || !value.trim()}
            onClick={handleSend}
          >
            <PaperPlaneRightIcon weight="bold" />
          </IconButton>
        </ChatInputAction>
      </ChatInputActionArea>
    </ChatInputPrimitive>
  );
}
