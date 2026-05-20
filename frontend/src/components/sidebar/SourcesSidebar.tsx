import { FileIcon, FilePdfIcon, FileTextIcon, LockSimpleIcon, XIcon } from "@phosphor-icons/react";
import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { useAppStore } from "../../store/appStore";
import type { Source } from "../../types/chat";
import { isMarkdownSource, isPdfSource, isPreviewableSource } from "../../utils/sourceMapping";
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

  function handleSourceClick(source: Source) {
    if (source.restricted) {
      setRequestAccessSource(source);
    } else if (isPreviewableSource(source.file)) {
      setActivePreviewSource(source);
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
              {sources.map((source) => (
                <SidebarMenuItem key={`${source.file}-${source.pages?.join(",")}`}>
                  <SidebarMenuButton
                    onClick={() => handleSourceClick(source)}
                    disabled={!source.restricted && !isPreviewableSource(source.file)}
                  >
                    {source.restricted ? (
                      <LockSimpleIcon weight="bold" />
                    ) : isPdfSource(source.file) ? (
                      <FilePdfIcon weight="bold" />
                    ) : isMarkdownSource(source.file) ? (
                      <FileTextIcon weight="bold" />
                    ) : (
                      <FileIcon weight="bold" />
                    )}
                    <div className="flex flex-col min-w-0">
                      <span className="truncate">{source.file}</span>
                      {(source.pages?.length ?? 0) > 0 && (
                        <span className="text-t5 text-text-tertiary">
                          p. {source.pages?.join(", ")}
                        </span>
                      )}
                    </div>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
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
