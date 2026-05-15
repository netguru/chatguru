import { CircleNotchIcon, FileTextIcon, PaperPlaneRightIcon, PlusIcon, XIcon } from "@phosphor-icons/react";
import * as React from "react";
import type { ImageAttachment } from "../../types/chat";
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

const IMAGE_MIME_TYPES = new Set(["image/png", "image/jpeg", "image/gif", "image/webp"]);

interface AttachedDocument {
  id: string;
  filename: string;
  markdown: string;
}

interface AttachedImage {
  id: string;
  filename: string;
  mime_type: string;
  data: string;
  previewUrl: string;
}

function readFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      // Strip the data:...;base64, prefix — backend expects raw base64.
      resolve(result.split(",", 2)[1] ?? result);
    };
    reader.onerror = () => reject(new Error("Failed to read file"));
    reader.readAsDataURL(file);
  });
}

interface Props {
  onSend: (text: string, images?: ImageAttachment[]) => void;
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
  const [attachedImages, setAttachedImages] = React.useState<AttachedImage[]>([]);
  const isInputDisabled = !isConnected || isStreaming;
  const isSendBlocked = isInputDisabled || isProcessingDocument;
  const isAttachmentBlocked = isStreaming || isProcessingDocument;
  const hasAttachments = attachedDocs.length > 0 || attachedImages.length > 0;
  const canSend = (value.trim().length > 0 || hasAttachments) && !isSendBlocked;
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const handleSend = () => {
    if (!canSend) return;
    const docBlock = attachedDocs
      .map((d) => `<document name="${d.filename}">\n${d.markdown}\n</document>`)
      .join("\n\n");
    const trimmed = value.trim();
    const fullMessage = [docBlock, trimmed].filter(Boolean).join("\n\n");

    const images: ImageAttachment[] | undefined =
      attachedImages.length > 0
        ? attachedImages.map((img) => ({ name: img.filename, mime_type: img.mime_type, data: img.data }))
        : undefined;

    onSend(fullMessage, images);
    setValue("");
    setAttachedDocs([]);
    // Revoke object URLs to free memory before clearing state.
    for (const img of attachedImages) URL.revokeObjectURL(img.previewUrl);
    setAttachedImages([]);
  };

  const removeDoc = (index: number) => {
    setAttachedDocs((prev) => prev.filter((_, i) => i !== index));
  };

  const removeImage = (index: number) => {
    setAttachedImages((prev) => {
      const removed = prev[index];
      if (removed) URL.revokeObjectURL(removed.previewUrl);
      return prev.filter((_, i) => i !== index);
    });
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const pickedFiles = Array.from(e.target.files ?? []);
    e.target.value = "";

    if (!pickedFiles.length) return;
    if (useAppStore.getState().isStreaming) return;

    const imageFiles = pickedFiles.filter((f) => IMAGE_MIME_TYPES.has(f.type));
    const docFiles = pickedFiles.filter((f) => !IMAGE_MIME_TYPES.has(f.type));

    // Images: read as base64 locally (no server round-trip).
    if (imageFiles.length > 0) {
      const newImages: AttachedImage[] = [];
      for (const file of imageFiles) {
        const data = await readFileAsBase64(file);
        newImages.push({
          id: crypto.randomUUID(),
          filename: file.name,
          mime_type: file.type,
          data,
          previewUrl: URL.createObjectURL(file),
        });
      }
      setAttachedImages((prev) => [...prev, ...newImages]);
    }

    // Documents: process via Docling backend.
    if (docFiles.length > 0) {
      setIsProcessingDocument(true);
      try {
        const results: AttachedDocument[] = [];
        for (const file of docFiles) {
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
        {DOCUMENT_UPLOAD_ENABLED && (
          <ChatInputAction className="flex flex-1 min-w-0 flex-wrap items-center gap-1.5">
            <div className="pointer-events-auto shrink-0">
              <input
                ref={fileInputRef}
                type="file"
                className="absolute size-0 overflow-hidden opacity-0"
                multiple
                accept=".pdf,.doc,.docx,.ppt,.pptx,.html,.htm,.md,.txt,.xlsx,.xls,.png,.jpg,.jpeg,.gif,.webp"
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
            {attachedImages.map((img, i) => (
              <span
                key={img.id}
                className="inline-flex items-center gap-1.5 rounded-full bg-surface-neutral-soft px-2.5 py-1 text-t3 text-text-primary"
              >
                <img
                  src={img.previewUrl}
                  alt={img.filename}
                  className="size-4 shrink-0 rounded-sm object-cover"
                />
                <span className="max-w-[140px] truncate">{img.filename}</span>
                <button
                  type="button"
                  aria-label={`Remove ${img.filename}`}
                  onClick={() => removeImage(i)}
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
