import { WarningCircleIcon } from "@phosphor-icons/react";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Source } from "../../types/chat";
import { cn } from "../../utils/utils";
import { Loader } from "../ui/loader";
import { Modal, ModalBody, ModalContent, ModalHeader, ModalTitle } from "../ui/modal/modal";

type LoadState = "loading" | "loaded" | "error";

const MARKDOWN_PROSE_CLASS =
  "text-t2 tracking-m leading-xl [&_p]:mb-2 [&_p:last-child]:mb-0 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:mb-2 [&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:mb-2 [&_li]:mb-0.5 [&_h1]:text-h3 [&_h1]:font-strong [&_h1]:mb-2 [&_h2]:text-h4 [&_h2]:font-strong [&_h2]:mb-2 [&_h3]:text-h5 [&_h3]:font-strong [&_h3]:mb-1 [&_code]:bg-surface-neutral-soft [&_code]:px-1 [&_code]:rounded [&_code]:text-t3 [&_pre]:bg-surface-neutral-soft [&_pre]:p-3 [&_pre]:rounded-m [&_pre]:overflow-x-auto [&_pre]:mb-2 [&_blockquote]:border-l-2 [&_blockquote]:border-border-neutral-soft [&_blockquote]:pl-3 [&_blockquote]:opacity-70 [&_blockquote]:mb-2 [&_a]:text-text-interactive [&_a]:underline [&_a]:underline-offset-2 [&_a]:transition-colors [&_a:hover]:text-text-hover-interactive [&_a:active]:text-text-active-interactive [&_hr]:border-border-neutral-soft [&_hr]:my-3 [&_table]:w-full [&_table]:text-t3 [&_th]:text-left [&_th]:font-strong [&_th]:pb-1 [&_td]:py-0.5";

interface Props {
  source: Source | null;
  onClose: () => void;
}

export function MarkdownViewerModal({ source, onClose }: Props) {
  const [content, setContent] = useState("");
  const [loadState, setLoadState] = useState<LoadState>("loading");

  useEffect(() => {
    if (!source?.file) {
      setContent("");
      setLoadState("loading");
      return;
    }

    const controller = new AbortController();
    setLoadState("loading");
    setContent("");

    void fetch(`/documents/${source.file}`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error("Failed to load document");
        return response.text();
      })
      .then((text) => {
        setContent(text);
        setLoadState("loaded");
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setLoadState("error");
      });

    return () => controller.abort();
  }, [source?.file]);

  return (
    <Modal
      open={source !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <ModalContent
        showCloseButton
        className={cn(
          "flex flex-col",
          "w-full h-dvh top-0 left-0 translate-x-0 translate-y-0 rounded-none",
          "md:w-11/12 md:max-w-4xl md:h-auto md:top-1/2 md:left-1/2 md:-translate-x-1/2 md:-translate-y-1/2 md:rounded-l",
          "lg:w-10/12 lg:max-w-4xl bg-surface-neutral-medium"
        )}
        closeButtonProps={{
          variant: "subtle",
        }}
      >
        <ModalHeader className="border-border-neutral-medium h-fit w-full">
          <ModalTitle className="text-t3 tracking-s text-text-secondary text-left truncate max-w-full">
            {source?.file ?? ""}
          </ModalTitle>
        </ModalHeader>

        <ModalBody className="h-full md:max-h-[80vh] overflow-auto w-full p-6 rounded-b-l">
          {loadState === "loading" && (
            <div className="flex items-center justify-center w-full h-60">
              <Loader className="justify-center" />
            </div>
          )}
          {loadState === "error" && (
            <div className="flex flex-col items-center justify-center gap-3 w-full h-60">
              <WarningCircleIcon size={32} weight="light" className="text-text-secondary" />
              <p className="text-t3 text-text-secondary">Failed to load document.</p>
            </div>
          )}
          {loadState === "loaded" && (
            <div className={MARKDOWN_PROSE_CLASS}>
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  a: ({ node: _node, ...props }) => (
                    <a {...props} target="_blank" rel="noopener noreferrer" />
                  ),
                }}
              >
                {content}
              </ReactMarkdown>
            </div>
          )}
        </ModalBody>
      </ModalContent>
    </Modal>
  );
}
