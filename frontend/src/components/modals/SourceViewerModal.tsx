import type { Source } from "../../types/chat";
import { isMarkdownSource, isPdfSource } from "../../utils/sourceMapping";
import { MarkdownViewerModal } from "./MarkdownViewerModal";
import { PdfViewerModal } from "./PdfViewerModal";

interface Props {
  source: Source | null;
  onClose: () => void;
}

export function SourceViewerModal({ source, onClose }: Props) {
  if (isPdfSource(source?.file)) {
    return <PdfViewerModal source={source} onClose={onClose} />;
  }

  if (isMarkdownSource(source?.file)) {
    return <MarkdownViewerModal source={source} onClose={onClose} />;
  }

  return null;
}
