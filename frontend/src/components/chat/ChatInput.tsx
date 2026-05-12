import { CircleNotchIcon, FileTextIcon, PaperPlaneRightIcon, PlusIcon, XIcon } from "@phosphor-icons/react";
import * as React from "react";
import { useAppStore } from "../../store/appStore";
import { processDocument } from "../../utils/documentProcessing";
import { cn } from "../../utils/utils";
import {
  ChatInputAction,
  ChatInputActionArea,
  ChatInput as ChatInputPrimitive,
  ChatInputTextarea,
} from "../ui/chat-input";
import { IconButton, iconButtonVariants } from "../ui/icon-button";

const DOCUMENT_UPLOAD_ENABLED = import.meta.env.VITE_DOCUMENT_UPLOAD_ENABLED !== "false";

interface AttachedDocument {
  id: string;
  filename: string;
  markdown: string;
}

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
  const [isProcessingDocument, setIsProcessingDocument] = React.useState(false);
  const [attachedDocs, setAttachedDocs] = React.useState<AttachedDocument[]>([]);
  /** Disables the entire input shell (textarea + actions) — excludes document processing so the user can still type while a file uploads. */
  const isInputDisabled = !isConnected || isStreaming;
  /** Sending requires a live WebSocket and no in-flight upload or stream. */
  const isSendBlocked = isInputDisabled || isProcessingDocument;
  const isAttachmentBlocked = isStreaming || isProcessingDocument;
  const canSend = (value.trim().length > 0 || attachedDocs.length > 0) && !isSendBlocked;
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const handleSend = () => {
    if (!canSend) return;
    // Wrap each attached document in an XML-like tag the backend and ChatMessage
    // renderer both understand. Body content is kept so the LLM sees the full text.
    const docBlock = attachedDocs
      .map((d) => `<document name="${d.filename}">\n${d.markdown}\n</document>`)
      .join("\n\n");
    const trimmed = value.trim();
    const fullMessage = [docBlock, trimmed].filter(Boolean).join("\n\n");
    onSend(fullMessage);
    setValue("");
    setAttachedDocs([]);
  };

  const removeDoc = (index: number) => {
    setAttachedDocs((prev) => prev.filter((_, i) => i !== index));
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    // Snapshot files into a plain Array immediately — some browsers mutate the
    // FileList in-place when input.value is cleared, so we must copy first.
    const pickedFiles = Array.from(e.target.files ?? []);
    e.target.value = "";

    if (!pickedFiles.length) return;
    if (useAppStore.getState().isStreaming) return;

    setIsProcessingDocument(true);
    try {
      const results: AttachedDocument[] = [];
      for (const file of pickedFiles) {
        const { markdown, filename } = await processDocument(file);
        results.push({ id: crypto.randomUUID(), filename, markdown });
      }
      setAttachedDocs((prev) => [...prev, ...results]);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Document processing failed";
      window.alert(message);
    } finally {
      setIsProcessingDocument(false);
    }
  };

  return (
    <ChatInputPrimitive
      disabled={isInputDisabled}
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
        {/* Left side: attach button + document pills inline (hidden when upload is disabled) */}
        {DOCUMENT_UPLOAD_ENABLED && (
          <ChatInputAction className="flex flex-1 min-w-0 flex-wrap items-center gap-1.5">
            {/* pointer-events-auto overrides the action-row's pointer-events-none when WS is offline — uploads are plain HTTP. */}
            <div className="pointer-events-auto shrink-0">
              {/* Hidden input — opened programmatically from the button's onClick (synchronous user-gesture call, works in all browsers). */}
              {/* Use absolute + zero-size instead of display:none — some browsers
                  won't fire the change event on a display:none file input. */}
              <input
                ref={fileInputRef}
                type="file"
                className="absolute size-0 overflow-hidden opacity-0"
                multiple
                accept=".pdf,.doc,.docx,.ppt,.pptx,.html,.htm,.md,.txt,.xlsx,.xls"
                tabIndex={-1}
                onChange={handleFileChange}
              />
              <button
                type="button"
                aria-label={isProcessingDocument ? "Processing document…" : "Attach file"}
                disabled={isAttachmentBlocked}
                onClick={() => fileInputRef.current?.click()}
                className={cn(iconButtonVariants({ variant: "subtle", size: "s" }), "cursor-pointer")}
              >
                {isProcessingDocument ? (
                  <CircleNotchIcon weight="bold" className="animate-spin" />
                ) : (
                  <PlusIcon weight="bold" />
                )}
              </button>
            </div>
            {attachedDocs.map((doc, i) => (
              <span
                key={doc.id}
                className="inline-flex items-center gap-1.5 rounded-full bg-surface-neutral-soft px-2.5 py-1 text-t3 text-text-primary"
              >
                <FileTextIcon weight="bold" className="size-3 shrink-0 text-text-secondary" />
                <span className="max-w-[140px] truncate">{doc.filename}</span>
                <button
                  type="button"
                  aria-label={`Remove ${doc.filename}`}
                  onClick={() => removeDoc(i)}
                  className="ml-0.5 cursor-pointer rounded-full p-0.5 text-text-secondary hover:bg-surface-hover-interactive-medium hover:text-text-primary"
                >
                  <XIcon weight="bold" className="size-3" />
                </button>
              </span>
            ))}
          </ChatInputAction>
        )}
        <ChatInputAction className="ml-auto shrink-0">
          <IconButton
            variant="primary"
            size="s"
            aria-label="Send message"
            disabled={!canSend}
            onClick={handleSend}
          >
            <PaperPlaneRightIcon weight="bold" />
          </IconButton>
        </ChatInputAction>
      </ChatInputActionArea>
    </ChatInputPrimitive>
  );
}
