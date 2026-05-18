import {
  CheckIcon,
  CopyIcon,
  FileTextIcon,
  FoldersIcon,
  SparkleIcon,
  ThumbsDownIcon,
  ThumbsUpIcon,
} from "@phosphor-icons/react";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useCopyToClipboard } from "../../hooks/useCopyToClipboard";
import { useFeedback } from "../../hooks/useFeedback";
import { useAppStore } from "../../store/appStore";
import type { ChatMessage as ChatMessageType, Source } from "../../types/chat";
import { filterCitedSources, injectCitationLinks } from "../../utils/citationLinks";
import { cn } from "../../utils/utils";
import { PdfViewerModal } from "../modals/PdfViewerModal";
import { ThumbsDownModal } from "../modals/ThumbsDownModal";
import { Avatar, AvatarFallback } from "../ui/avatar";
import { Button } from "../ui/button";
import { IconButton } from "../ui/icon-button";
import { Loader } from "../ui/loader";

interface Props {
  message: ChatMessageType;
}

const DOCUMENT_TAG_RE = /<document name="([^"]+)">([\s\S]*?)<\/document>/g;

function parseUserMessage(content: string): { documents: string[]; text: string } {
  const documents: string[] = [];
  const text = content
    .replace(DOCUMENT_TAG_RE, (_, filename: string) => {
      documents.push(filename);
      return "";
    })
    .trim();
  return { documents, text };
}

function isDocumentCitationHref(href: string | undefined): boolean {
  if (!href) return false;
  try {
    return new URL(href, window.location.origin).pathname.startsWith("/documents/");
  } catch {
    return false;
  }
}

export function ChatMessage({ message }: Props) {
  const isUser = message.role === "user";
  const citedSources =
    !isUser && message.sources?.length && message.content
      ? filterCitedSources(message.content, message.sources)
      : [];
  const { copied, copy } = useCopyToClipboard();
  const openSourcesPanel = useAppStore((s) => s.openSourcesPanel);
  const [thumbsDownOpen, setThumbsDownOpen] = useState(false);
  const [feedbackGiven, setFeedbackGiven] = useState<0 | 1 | null>(null);
  const [activePdfSource, setActivePdfSource] = useState<Source | null>(null);
  const { submitFeedback, isSubmitting } = useFeedback();

  function handleCitationLinkClick(href: string) {
    try {
      const url = new URL(href, window.location.origin);
      const isDocumentLink = url.pathname.startsWith("/documents/");
      if (!isDocumentLink) return false;
      const sourceUri = url.pathname.replace("/documents/", "");
      const pageMatch = url.hash.match(/^#page=(\d+)$/);
      const page = pageMatch ? parseInt(pageMatch[1], 10) : undefined;
      setActivePdfSource({
        file: sourceUri,
        url: url.pathname,
        pages: page != null ? [page] : [],
      });
      return true;
    } catch {
      return false;
    }
  }

  return (
    <>
      <div className={cn("flex items-start gap-3", isUser ? "justify-end" : "justify-start")}>
        {!isUser && (
          <Avatar size="m" shape="circle" className="shrink-0">
            <AvatarFallback>
              <SparkleIcon weight="bold" />
            </AvatarFallback>
          </Avatar>
        )}

        <div
          className={cn(
            // TODO: Set default font-soft
            "[*]:font-soft",
            isUser
              ? "max-w-[80%] bg-surface-neutral-soft text-text-primary pt-3 pb-4 px-4 rounded-l-m text-t2 tracking-m leading-xl whitespace-pre-wrap wrap-break-words"
              : "flex-1 min-w-0 bg-transparent text-text-primary"
          )}
        >
          {isUser ? (
            (() => {
              const { documents, text } = parseUserMessage(message.content ?? "");
              const images = message.imageUrls ?? [];
              const hasContent = text || documents.length > 0 || images.length > 0;
              return (
                <>
                  {images.length > 0 && (
                    <div className="flex flex-wrap gap-2 mb-2">
                      {images.map((url) => (
                        <img
                          key={url}
                          src={url}
                          alt="Attached"
                          className="max-h-48 max-w-full rounded-m object-contain"
                        />
                      ))}
                    </div>
                  )}
                  {documents.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mb-2">
                      {documents.map((filename) => (
                        <span
                          key={filename}
                          className="inline-flex items-center gap-1.5 rounded-full bg-surface-neutral-medium px-2.5 py-1 text-t3 text-text-primary"
                        >
                          <FileTextIcon weight="bold" className="size-3 shrink-0 text-text-secondary" />
                          <span className="max-w-[200px] truncate">{filename}</span>
                        </span>
                      ))}
                    </div>
                  )}
                  {text && (
                    <span className="text-t2 tracking-m leading-xl whitespace-pre-wrap wrap-break-words">
                      {text}
                    </span>
                  )}
                  {!hasContent && (
                    <span className="text-t2 tracking-m leading-xl whitespace-pre-wrap wrap-break-words">
                      {message.isStreaming ? "" : "—"}
                    </span>
                  )}
                </>
              );
            })()
          ) : (
            <div className="text-t2 tracking-m leading-xl [&_p]:mb-2 [&_p:last-child]:mb-0 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:mb-2 [&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:mb-2 [&_li]:mb-0.5 [&_h1]:text-h3 [&_h1]:font-strong [&_h1]:mb-2 [&_h2]:text-h4 [&_h2]:font-strong [&_h2]:mb-2 [&_h3]:text-h5 [&_h3]:font-strong [&_h3]:mb-1 [&_code]:bg-surface-neutral-soft [&_code]:px-1 [&_code]:rounded [&_code]:text-t3 [&_pre]:bg-surface-neutral-soft [&_pre]:p-3 [&_pre]:rounded-m [&_pre]:overflow-x-auto [&_pre]:mb-2 [&_blockquote]:border-l-2 [&_blockquote]:border-border-neutral-soft [&_blockquote]:pl-3 [&_blockquote]:opacity-70 [&_blockquote]:mb-2 [&_a]:text-text-interactive [&_a]:underline [&_a]:underline-offset-2 [&_a]:transition-colors [&_a:hover]:text-text-hover-interactive [&_a:active]:text-text-active-interactive [&_hr]:border-border-neutral-soft [&_hr]:my-3 [&_table]:w-full [&_table]:text-t3 [&_th]:text-left [&_th]:font-strong [&_th]:pb-1 [&_td]:py-0.5">
              {message.content ? (
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    a: ({ node: _node, href, ...props }) => {
                      const isDocLink = isDocumentCitationHref(href);
                      if (isDocLink && href) {
                        return (
                          <a
                            {...props}
                            href={href}
                            onClick={(e) => {
                              e.preventDefault();
                              handleCitationLinkClick(href);
                            }}
                            style={{ cursor: "pointer" }}
                          />
                        );
                      }
                      return <a {...props} href={href} target="_blank" rel="noopener noreferrer" />;
                    },
                  }}
                >
                  {injectCitationLinks(message.content, message.sources ?? [])}
                </ReactMarkdown>
              ) : message.isStreaming ? null : (
                "—"
              )}
            </div>
          )}
          {message.isStreaming && message.content === "" && <Loader className="mt-4" />}
          {(!message.isStreaming || message.content !== "") && !isUser && (
            <div className="flex items-center gap-2 mt-4">
              {message.content && (
                <IconButton
                  variant="subtle"
                  size="xs"
                  aria-label="Copy message"
                  onClick={() => copy(message.content)}
                >
                  {copied ? <CheckIcon weight="bold" /> : <CopyIcon weight="bold" />}
                </IconButton>
              )}
              {citedSources.length > 0 && (
                <Button
                  variant="subtle"
                  color="neutral"
                  size="s"
                  onClick={() => openSourcesPanel(citedSources)}
                >
                  <FoldersIcon weight="bold" />
                  {citedSources.length} sources
                </Button>
              )}
              <div className="ms-auto flex items-center gap-1">
                <IconButton
                  variant="subtle"
                  aria-label="Thumb up"
                  size="xs"
                  disabled={!message.traceId || isSubmitting || feedbackGiven !== null}
                  onClick={() => {
                    if (message.traceId) {
                      void submitFeedback(message.traceId, 1);
                      setFeedbackGiven(1);
                    }
                  }}
                >
                  <ThumbsUpIcon
                    weight={feedbackGiven === 1 ? "fill" : "bold"}
                    className={feedbackGiven === 1 ? "text-text-interactive" : undefined}
                  />
                </IconButton>
                <IconButton
                  variant="subtle"
                  aria-label="Thumb down"
                  size="xs"
                  disabled={!message.traceId || feedbackGiven !== null}
                  onClick={() => setThumbsDownOpen(true)}
                >
                  <ThumbsDownIcon
                    weight={feedbackGiven === 0 ? "fill" : "bold"}
                    className={feedbackGiven === 0 ? "text-semantic-error-strong" : undefined}
                  />
                </IconButton>
              </div>
            </div>
          )}
        </div>
      </div>

      <ThumbsDownModal
        open={thumbsDownOpen}
        onOpenChange={setThumbsDownOpen}
        traceId={message.traceId}
        onSent={() => setFeedbackGiven(0)}
      />

      <PdfViewerModal source={activePdfSource} onClose={() => setActivePdfSource(null)} />
    </>
  );
}
