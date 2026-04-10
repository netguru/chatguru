import {
  CheckIcon,
  CopyIcon,
  FoldersIcon,
  SparkleIcon,
  ThumbsDownIcon,
  ThumbsUpIcon,
} from "@phosphor-icons/react";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useCopyToClipboard } from "../../hooks/useCopyToClipboard";
import { useAppStore } from "../../store/appStore";
import type { ChatMessage as ChatMessageType } from "../../types/chat";
import { injectCitationLinks } from "../../utils/citationLinks";
import { cn } from "../../utils/utils";
import { ThumbsDownModal } from "../modals/ThumbsDownModal";
import { Avatar, AvatarFallback } from "../ui/avatar";
import { Button } from "../ui/button";
import { IconButton } from "../ui/icon-button";
import { Loader } from "../ui/loader";

interface Props {
  message: ChatMessageType;
}

export function ChatMessage({ message }: Props) {
  const isUser = message.role === "user";
  const { copied, copy } = useCopyToClipboard();
  const openSourcesPanel = useAppStore((s) => s.openSourcesPanel);
  const [thumbsDownOpen, setThumbsDownOpen] = useState(false);

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
            <span className="text-t2 tracking-m leading-xl whitespace-pre-wrap wrap-break-words">
              {message.content || (message.isStreaming ? "" : "—")}
            </span>
          ) : (
            <div className="text-t2 tracking-m leading-xl [&_p]:mb-2 [&_p:last-child]:mb-0 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:mb-2 [&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:mb-2 [&_li]:mb-0.5 [&_h1]:text-h3 [&_h1]:font-strong [&_h1]:mb-2 [&_h2]:text-h4 [&_h2]:font-strong [&_h2]:mb-2 [&_h3]:text-h5 [&_h3]:font-strong [&_h3]:mb-1 [&_code]:bg-surface-neutral-soft [&_code]:px-1 [&_code]:rounded [&_code]:text-t3 [&_pre]:bg-surface-neutral-soft [&_pre]:p-3 [&_pre]:rounded-m [&_pre]:overflow-x-auto [&_pre]:mb-2 [&_blockquote]:border-l-2 [&_blockquote]:border-border-neutral-soft [&_blockquote]:pl-3 [&_blockquote]:opacity-70 [&_blockquote]:mb-2 [&_a]:text-text-interactive [&_a]:underline [&_a]:underline-offset-2 [&_a]:transition-colors [&_a:hover]:text-text-hover-interactive [&_a:active]:text-text-active-interactive [&_hr]:border-border-neutral-soft [&_hr]:my-3 [&_table]:w-full [&_table]:text-t3 [&_th]:text-left [&_th]:font-strong [&_th]:pb-1 [&_td]:py-0.5">
              {message.content ? (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
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
              {message.sources && message.sources.length > 0 && (
                <Button
                  variant="subtle"
                  color="neutral"
                  size="s"
                  onClick={() => openSourcesPanel(message.sources ?? [])}
                >
                  <FoldersIcon weight="bold" />
                  {message.sources.length} sources
                </Button>
              )}
              <div className="ms-auto">
                <IconButton variant="subtle" aria-label="Thumb up" size="xs">
                  <ThumbsUpIcon weight="bold" />
                </IconButton>
                <IconButton
                  variant="subtle"
                  aria-label="Thumb down"
                  size="xs"
                  onClick={() => setThumbsDownOpen(true)}
                >
                  <ThumbsDownIcon weight="bold" />
                </IconButton>
              </div>
            </div>
          )}
        </div>
      </div>

      <ThumbsDownModal open={thumbsDownOpen} onOpenChange={setThumbsDownOpen} />
    </>
  );
}
