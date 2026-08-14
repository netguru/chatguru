import {
  ArrowSquareOutIcon,
  FileIcon,
  FilePdfIcon,
  FileTextIcon,
  GlobeIcon,
  LockSimpleIcon,
  XIcon,
} from "@phosphor-icons/react";
import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { useAppStore } from "../../store/appStore";
import type { Source } from "../../types/chat";
import { classifySource, type SourceKind } from "../../utils/sourceMapping";
import { RequestAccessModal } from "../modals/RequestAccessModal";
import { SourceViewerModal } from "../modals/SourceViewerModal";
import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
} from "../ui/sidebar/sidebar";

const KIND_ICONS: Record<SourceKind, typeof FileIcon> = {
  restricted: LockSimpleIcon,
  pdf: FilePdfIcon,
  markdown: FileTextIcon,
  external: GlobeIcon,
  opaque: FileIcon,
};

export function SourcesSidebar() {
  const sources = useAppStore((s) => s.sourcesPanelSources);
  const sourcesPanelOpen = useAppStore((s) => s.sourcesPanelOpen);
  const closeSourcesPanel = useAppStore((s) => s.closeSourcesPanel);
  const currentSessionId = useAppStore((s) => s.currentSessionId);
  const [activePreviewSource, setActivePreviewSource] = useState<Source | null>(null);
  const [requestAccessSource, setRequestAccessSource] = useState<Source | null>(null);
  const { pathname } = useLocation();

  // biome-ignore lint/correctness/useExhaustiveDependencies: pathname and currentSessionId are intentional trigger deps
  useEffect(() => {
    closeSourcesPanel();
  }, [pathname, currentSessionId, closeSourcesPanel]);

  function handleSourceClick(source: Source, kind: SourceKind) {
    if (kind === "restricted") {
      setRequestAccessSource(source);
    } else if (kind === "pdf" || kind === "markdown") {
      setActivePreviewSource(source);
    } else if (kind === "external") {
      window.open(source.url, "_blank", "noopener,noreferrer");
    }
  }

  return (
    <>
      <SidebarProvider
        side="right"
        open={sourcesPanelOpen}
        onOpenChange={(open) => {
          if (!open) closeSourcesPanel();
        }}
        style={{ display: "contents" } as React.CSSProperties}
      >
        <Sidebar side="right" collapsible="offcanvas">
          <SidebarHeader className="flex-row items-center justify-between">
            <span className="text-t2 font-strong text-text-primary px-2">
              Sources ({sources.length})
            </span>
            <SidebarTrigger aria-label="Close sources panel" onClick={closeSourcesPanel}>
              <XIcon weight="bold" />
            </SidebarTrigger>
          </SidebarHeader>

          <SidebarContent>
            <SidebarMenu>
              {sources.map((source) => {
                const kind = classifySource(source);
                const Icon = KIND_ICONS[kind];
                return (
                  <SidebarMenuItem key={`${source.file}-${source.pages?.join(",")}`}>
                    <SidebarMenuButton
                      onClick={() => handleSourceClick(source, kind)}
                      disabled={kind === "opaque"}
                    >
                      <Icon weight="bold" />
                      <div className="flex flex-col min-w-0">
                        <span className="truncate">{source.file}</span>
                        {(source.pages?.length ?? 0) > 0 && (
                          <span className="text-t5 text-text-tertiary">
                            p. {source.pages?.join(", ")}
                          </span>
                        )}
                      </div>
                      {kind === "external" && (
                        <>
                          <span className="sr-only">Opens in a new tab</span>
                          <ArrowSquareOutIcon
                            weight="bold"
                            aria-hidden="true"
                            className="ms-auto shrink-0 text-text-tertiary"
                          />
                        </>
                      )}
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>

      <SourceViewerModal
        source={activePreviewSource}
        onClose={() => setActivePreviewSource(null)}
      />
      <RequestAccessModal
        open={requestAccessSource !== null}
        onOpenChange={(open) => {
          if (!open) setRequestAccessSource(null);
        }}
      />
    </>
  );
}
