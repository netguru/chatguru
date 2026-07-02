import {
  CircleNotchIcon,
  FilePdfIcon,
  FileTextIcon,
  PaperPlaneRightIcon,
  PlusIcon,
  XIcon,
} from "@phosphor-icons/react";
import * as React from "react";
import { useAppStore } from "../../store/appStore";
import type { LlmModelProvider } from "../../types/chat";
import { processDocument, uploadAttachment } from "../../utils/documentProcessing";
import { cn } from "../../utils/utils";
import { getOrCreateVisitorId } from "../../utils/visitorId";
import { PdfViewerModal } from "../modals/PdfViewerModal";
import {
  ChatInputAction,
  ChatInputActionArea,
  ChatInput as ChatInputPrimitive,
  ChatInputTextarea,
} from "../ui/chat-input";
import { IconButton, iconButtonVariants } from "../ui/icon-button";
import { ModelSelector } from "./ModelSelector";

const DOCUMENT_UPLOAD_ENABLED = import.meta.env.VITE_DOCUMENT_UPLOAD_ENABLED !== "false";

const IMAGE_MIME_TYPES = new Set(["image/png", "image/jpeg", "image/gif", "image/webp"]);

interface AttachedDocument {
  id: string;
  filename: string;
  mimeType: string;
  markdown: string;
  /** Server-assigned ID from POST /process-document (null when storage unavailable). */
  attachmentId: string | null;
}

interface AttachedImage {
  id: string;
  filename: string;
  mimeType: string;
  /** Object URL for thumbnail preview — valid until page unload. */
  previewUrl: string;
  /** Server-assigned ID from POST /upload-attachment (null when storage unavailable). */
  attachmentId: string | null;
}

interface Props {
  onSend: (text: string, attachmentIds?: string[], imagePreviewUrls?: string[]) => void;
  value?: string;
  onValueChange?: (value: string) => void;
  className?: string;
  /** LiteLLM model groups. Empty when the LiteLLM provider is not active. */
  modelProviders?: LlmModelProvider[];
  selectedModelId?: string | null;
  onSelectModel?: (id: string) => void;
}

export function ChatInput({
  onSend,
  value: valueProp,
  onValueChange,
  className,
  modelProviders = [],
  selectedModelId = null,
  onSelectModel,
}: Props) {
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
  const [activePdf, setActivePdf] = React.useState<{ url: string; filename: string } | null>(null);
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

    // Collect all pre-uploaded attachment IDs (images + documents).
    const allAttachmentIds: string[] = [
      ...attachedImages.map((img) => img.attachmentId).filter((id): id is string => id !== null),
      ...attachedDocs.map((d) => d.attachmentId).filter((id): id is string => id !== null),
    ];

    // Object URLs for live image preview in the user message bubble.
    // Not revoked here — they stay valid until replaced by server URLs in the end frame.
    const imagePreviewUrls = attachedImages.map((img) => img.previewUrl);

    onSend(
      fullMessage,
      allAttachmentIds.length > 0 ? allAttachmentIds : undefined,
      imagePreviewUrls.length > 0 ? imagePreviewUrls : undefined
    );
    setValue("");
    setAttachedDocs([]);
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

    // Images: upload to the server to obtain an attachment_id.
    if (imageFiles.length > 0) {
      setIsProcessingDocument(true);
      try {
        const newImages: AttachedImage[] = [];
        for (const file of imageFiles) {
          const previewUrl = URL.createObjectURL(file);
          let attachmentId: string | null = null;
          try {
            const result = await uploadAttachment(file);
            attachmentId = result.attachment_id;
          } catch (err) {
            const message = err instanceof Error ? err.message : "Image upload failed";
            window.alert(message);
          }
          newImages.push({
            id: crypto.randomUUID(),
            filename: file.name,
            mimeType: file.type,
            previewUrl,
            attachmentId,
          });
        }
        setAttachedImages((prev) => [...prev, ...newImages]);
      } finally {
        setIsProcessingDocument(false);
      }
    }

    // Documents: process via Docling backend.
    if (docFiles.length > 0) {
      setIsProcessingDocument(true);
      try {
        const results: AttachedDocument[] = [];
        for (const file of docFiles) {
          const { markdown, filename, attachment_id } = await processDocument(file);
          results.push({
            id: crypto.randomUUID(),
            filename,
            mimeType: file.type || "application/octet-stream",
            markdown,
            attachmentId: attachment_id,
          });
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
    <>
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
                  className={cn(
                    iconButtonVariants({ variant: "subtle", size: "s" }),
                    "cursor-pointer"
                  )}
                >
                  {isProcessingDocument ? (
                    <CircleNotchIcon weight="bold" className="animate-spin" />
                  ) : (
                    <PlusIcon weight="bold" />
                  )}
                </button>
              </div>
              {attachedDocs.map((doc, i) => {
                const isPdf = doc.mimeType === "application/pdf";
                const canPreview = isPdf && doc.attachmentId !== null;
                const visitorId = getOrCreateVisitorId();
                const previewUrl = doc.attachmentId
                  ? `/attachments/${doc.attachmentId}?visitor_id=${encodeURIComponent(visitorId)}`
                  : null;
                const icon = isPdf ? (
                  <FilePdfIcon weight="bold" className="size-3 shrink-0 text-text-secondary" />
                ) : (
                  <FileTextIcon weight="bold" className="size-3 shrink-0 text-text-secondary" />
                );
                return (
                  <span
                    key={doc.id}
                    className="inline-flex items-center gap-1.5 rounded-full bg-surface-neutral-soft px-2.5 py-1 text-t3 text-text-primary"
                  >
                    <button
                      type="button"
                      disabled={!canPreview}
                      onClick={() =>
                        canPreview &&
                        previewUrl &&
                        setActivePdf({ url: previewUrl, filename: doc.filename })
                      }
                      title={canPreview ? `Preview ${doc.filename}` : doc.filename}
                      className={cn(
                        "inline-flex items-center gap-1.5 min-w-0",
                        canPreview && "cursor-pointer hover:opacity-80 transition-opacity"
                      )}
                    >
                      {icon}
                      <span className="max-w-[140px] truncate">{doc.filename}</span>
                    </button>
                    <button
                      type="button"
                      aria-label={`Remove ${doc.filename}`}
                      onClick={() => removeDoc(i)}
                      className="ml-0.5 cursor-pointer rounded-full p-0.5 text-text-secondary hover:bg-surface-hover-interactive-medium hover:text-text-primary"
                    >
                      <XIcon weight="bold" className="size-3" />
                    </button>
                  </span>
                );
              })}
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
          <ChatInputAction className="ml-auto flex shrink-0 items-center gap-1">
            {modelProviders.length > 0 && onSelectModel && (
              <ModelSelector
                providers={modelProviders}
                selectedModelId={selectedModelId}
                onSelect={onSelectModel}
                disabled={isInputDisabled}
              />
            )}
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

      <PdfViewerModal
        source={activePdf ? { file: activePdf.filename } : null}
        fileUrl={activePdf?.url}
        open={activePdf !== null}
        onClose={() => setActivePdf(null)}
      />
    </>
  );
}
