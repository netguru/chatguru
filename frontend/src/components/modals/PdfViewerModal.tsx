import {
  MagnifyingGlassMinusIcon,
  MagnifyingGlassPlusIcon,
  SidebarSimpleIcon,
  WarningCircleIcon,
} from "@phosphor-icons/react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { useEffect, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import { useIsMobile } from "../../hooks/useIsMobile";
import type { Source } from "../../types/chat";
import { cn } from "../../utils/utils";
import { IconButton } from "../ui/icon-button";
import { Loader } from "../ui/loader";
import { Modal, ModalBody, ModalContent, ModalHeader, ModalTitle } from "../ui/modal/modal";

import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import { Badge } from "../ui/badge";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url
).toString();

const ZOOM_STEP = 0.25;
const ZOOM_MIN = 0.5;
const ZOOM_MAX = 3.0;
const ZOOM_DEFAULT = 1.0;
const THUMBNAIL_WIDTH = 84;
// Estimated height per thumbnail item:
// wrapper: no padding (0px) + button p-4 top+bottom (32px) + Page canvas A4 at width=84 (119px) + gap-2 (8px) + Badge (~24px) ≈ 183px
const THUMB_ITEM_HEIGHT = 183;

type LoadState = "loading" | "loaded" | "error";

function PdfLoadingState() {
  return (
    <div className="flex items-center justify-center w-full h-60 bg-surface-neutral-soft">
      <Loader className="justify-center" />
    </div>
  );
}

function PdfErrorState() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 w-full h-60 bg-surface-neutral-soft">
      <WarningCircleIcon size={32} weight="light" className="text-text-secondary" />
      <p className="text-t3 text-text-secondary">Failed to load document.</p>
    </div>
  );
}

interface Props {
  source: Source | null;
  onClose: () => void;
}

export function PdfViewerModal({ source, onClose }: Props) {
  const isMobile = useIsMobile();
  const [numPages, setNumPages] = useState<number | null>(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [scale, setScale] = useState(ZOOM_DEFAULT);
  const [showThumbnails, setShowThumbnails] = useState(() => window.innerWidth >= 768);
  const [loadState, setLoadState] = useState<LoadState>("loading");

  const thumbPanelRef = useRef<HTMLDivElement>(null);
  const [viewerEl, setViewerEl] = useState<HTMLDivElement | null>(null);
  const [containerWidth, setContainerWidth] = useState<number | undefined>();

  // Virtualizer for the thumbnail panel — only renders visible thumbnails.
  // count=0 when document hasn't loaded yet; overscan=3 pre-renders items
  // just outside the viewport so scrolling feels instant.
  const thumbnailVirtualizer = useVirtualizer({
    count: numPages ?? 0,
    getScrollElement: () => thumbPanelRef.current,
    estimateSize: () => THUMB_ITEM_HEIGHT,
    overscan: 3,
    gap: 0.5,
  });

  // Track viewer width for responsive PDF sizing
  useEffect(() => {
    if (!viewerEl) return;
    const resizeObserver = new ResizeObserver(([entry]) => {
      console.log("Viewer resized:", entry.contentRect.width);
      setContainerWidth(entry.contentRect.width - 48); // minus p-6 on each side
    });
    resizeObserver.observe(viewerEl);
    return () => resizeObserver.disconnect();
  }, [viewerEl]);

  // biome-ignore lint/correctness/useExhaustiveDependencies: intentionally reset view state only when the opened file changes, not on every source object re-reference
  useEffect(() => {
    setScale(ZOOM_DEFAULT);
    setLoadState("loading");
  }, [source?.file]);

  // Scroll the virtualizer to keep the active thumbnail visible.
  // "auto" alignment: only scrolls if the item is outside the viewport.
  useEffect(() => {
    if (!showThumbnails || numPages === null) return;
    thumbnailVirtualizer.scrollToIndex(pageNumber - 1, { align: "auto", behavior: "smooth" });
  }, [pageNumber, showThumbnails, numPages, thumbnailVirtualizer]);

  function onDocumentLoadSuccess({ numPages }: { numPages: number }) {
    setNumPages(numPages);
    setPageNumber(source?.pages?.[0] ?? 1);
    setLoadState("loaded");
  }

  function onDocumentLoadError() {
    setLoadState("error");
  }

  function handleThumbnailPageSelect(n: number) {
    setPageNumber(n);
    if (isMobile) setShowThumbnails(false);
  }

  const isLoading = loadState === "loading";

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
          "flex flex-col md:grid",
          "w-full h-dvh top-0 left-0 translate-x-0 translate-y-0 rounded-none",
          "md:w-11/12 md:max-w-6xl md:h-auto md:top-1/2 md:left-1/2 md:-translate-x-1/2 md:-translate-y-1/2 md:rounded-l",
          "lg:w-10/12 lg:max-w-6xl bg-surface-neutral-medium"
        )}
        closeButtonProps={{
          variant: "subtle",
        }}
      >
        <ModalHeader className="border-border-neutral-medium h-fit w-full">
          <div className="flex flex-col w-full md:grid md:grid-cols-[1fr_auto_1fr] md:items-center">
            {/* ── Col 1: thumbnail toggle + title ─────────── */}
            <div className="flex items-center gap-2 min-w-0">
              <IconButton
                variant="subtle"
                size="m"
                aria-label="Toggle thumbnail panel"
                title="Toggle thumbnails"
                onClick={() => setShowThumbnails((prev) => !prev)}
                disabled={isLoading}
              >
                <SidebarSimpleIcon weight="bold" />
              </IconButton>
              <ModalTitle className="text-t3 tracking-s text-text-secondary text-left w-auto truncate max-w-60">
                {source?.file ?? ""}
              </ModalTitle>
            </div>

            {/* ── Col 2: page nav + zoom (always centered) ─── */}
            {loadState !== "error" && (
              <div className="flex items-center justify-center gap-2">
                <p className="text-t3 font-medium tracking-s text-text-secondary px-3 py-1.5">
                  {`${pageNumber} / ${numPages}`}
                </p>

                {/* TODO: Implement QuantityInput when will be available */}
                <IconButton
                  variant="subtle"
                  size="s"
                  aria-label="Zoom out"
                  onClick={() =>
                    setScale((prev) =>
                      Math.max(ZOOM_MIN, Math.round((prev - ZOOM_STEP) * 100) / 100)
                    )
                  }
                  disabled={isLoading || scale <= ZOOM_MIN}
                >
                  <MagnifyingGlassMinusIcon weight="bold" />
                </IconButton>
                <button
                  type="button"
                  title="Click to reset to 100%"
                  onClick={() => setScale(ZOOM_DEFAULT)}
                  disabled={isLoading}
                  className="text-t3 text-text-secondary tabular-nums w-14 text-center hover:text-text-primary transition-colors cursor-pointer"
                >
                  {Math.round(scale * 100)}%
                </button>
                <IconButton
                  variant="subtle"
                  size="s"
                  aria-label="Zoom in"
                  onClick={() =>
                    setScale((prev) =>
                      Math.min(ZOOM_MAX, Math.round((prev + ZOOM_STEP) * 100) / 100)
                    )
                  }
                  disabled={isLoading || scale >= ZOOM_MAX}
                >
                  <MagnifyingGlassPlusIcon weight="bold" />
                </IconButton>
              </div>
            )}

            {/* ── Col 3: empty — balances col 1 ───────────── */}
            <div className="hidden md:block" />
          </div>
        </ModalHeader>

        {/* Main body: thumbnail panel + PDF viewer */}
        <ModalBody className="h-full md:max-h-[80vh] overflow-hidden w-full p-0 rounded-b-l relative">
          {loadState === "loading" && <PdfLoadingState />}
          {loadState === "error" && <PdfErrorState />}
          <Document
            file={source?.file}
            onLoadSuccess={onDocumentLoadSuccess}
            onLoadError={onDocumentLoadError}
            loading={null}
            error={null}
            className={cn(
              "flex flex-row w-full h-full overflow-hidden",
              loadState !== "loaded" && "hidden"
            )}
          >
            {/* ── Thumbnail panel (virtualized) ───────────── */}
            {showThumbnails && numPages !== null && (
              <>
                {/* Backdrop — mobile only */}
                {isMobile && (
                  <div
                    className="absolute inset-0 z-40 bg-surface-overlay-strong"
                    onClick={() => setShowThumbnails(false)}
                    aria-hidden="true"
                  />
                )}
                <div
                  ref={thumbPanelRef}
                  className={cn(
                    "w-44 shrink-0 overflow-y-auto border-r border-border-neutral-medium px-8 py-2",
                    isMobile && "absolute inset-y-0 left-0 z-50 bg-surface-neutral-medium"
                  )}
                >
                  {/* Total height placeholder — makes the scrollbar the right size */}
                  <div
                    style={{ height: thumbnailVirtualizer.getTotalSize() }}
                    className="relative w-full"
                  >
                    {thumbnailVirtualizer.getVirtualItems().map((vItem) => {
                      const n = vItem.index + 1;
                      const isActive = n === pageNumber;
                      return (
                        <div
                          key={n}
                          style={{ transform: `translateY(${vItem.start}px)` }}
                          className="absolute top-0 left-0 w-full"
                        >
                          <button
                            type="button"
                            aria-label={`Go to page ${n}`}
                            aria-current={isActive ? "page" : undefined}
                            data-selected={isActive}
                            onClick={() => handleThumbnailPageSelect(n)}
                            className={cn(
                              /* Background */
                              "bg-surface-neutral-medium",
                              "hover:bg-surface-hover-neutral-medium",
                              "active:bg-surface-active-neutral-medium",
                              "data-[selected=true]:bg-surface-active-neutral-medium",
                              /* Focus ring */
                              "has-focus-visible:outline-none has-focus-visible:ring-2 has-focus-visible:ring-focus-ring",
                              "has-focus-visible:ring-offset-2 has-focus-visible:ring-offset-white",
                              /* Layout */
                              "flex w-full flex-col items-center gap-2 rounded-s p-4 transition-colors"
                            )}
                          >
                            <Page
                              pageNumber={n}
                              width={THUMBNAIL_WIDTH}
                              renderTextLayer={false}
                              renderAnnotationLayer={false}
                              className="pointer-events-none select-none overflow-hidden"
                            />
                            <Badge
                              type="soft"
                              className="bg-surface-neutral-strong text-text-inverted"
                            >
                              {n}
                            </Badge>
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </>
            )}

            {/* ── Main viewer ─────────────────────────────── */}
            <div ref={setViewerEl} className="flex-1 overflow-auto bg-surface-neutral-medium">
              <div className="w-max min-w-full flex justify-center p-6">
                <Page
                  pageNumber={pageNumber}
                  width={containerWidth ? Math.round(containerWidth * scale) : undefined}
                  renderTextLayer
                  renderAnnotationLayer
                />
              </div>
            </div>
          </Document>
        </ModalBody>
      </ModalContent>
    </Modal>
  );
}
