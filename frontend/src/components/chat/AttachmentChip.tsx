import { FilePdfIcon, FileTextIcon } from "@phosphor-icons/react";
import { useState } from "react";
import type { StoredAttachment } from "../../types/chat";
import { getOrCreateVisitorId } from "../../utils/visitorId";
import { PdfViewerModal } from "../modals/PdfViewerModal";

interface Props {
  attachment: StoredAttachment;
}

export function AttachmentChip({ attachment }: Props) {
  const [pdfOpen, setPdfOpen] = useState(false);
  const isPdf = attachment.mime_type === "application/pdf";

  const visitorId = getOrCreateVisitorId();
  const fileUrl = `/attachments/${attachment.id}?visitor_id=${encodeURIComponent(visitorId)}`;

  const icon = isPdf ? (
    <FilePdfIcon weight="bold" className="size-3 shrink-0 text-text-secondary" />
  ) : (
    <FileTextIcon weight="bold" className="size-3 shrink-0 text-text-secondary" />
  );

  const chipContent = (
    <>
      {icon}
      <span className="max-w-[200px] truncate">{attachment.name}</span>
    </>
  );

  if (isPdf) {
    return (
      <>
        <button
          type="button"
          onClick={() => setPdfOpen(true)}
          className="inline-flex items-center gap-1.5 rounded-full bg-surface-neutral-medium px-2.5 py-1 text-t3 text-text-primary cursor-pointer hover:bg-surface-hover-neutral-medium transition-colors"
          title={`Preview ${attachment.name}`}
        >
          {chipContent}
        </button>
        <PdfViewerModal
          source={{ file: attachment.name }}
          fileUrl={fileUrl}
          onClose={() => setPdfOpen(false)}
          open={pdfOpen}
        />
      </>
    );
  }

  return (
    <a
      href={fileUrl}
      download={attachment.name}
      className="inline-flex items-center gap-1.5 rounded-full bg-surface-neutral-medium px-2.5 py-1 text-t3 text-text-primary cursor-pointer hover:bg-surface-hover-neutral-medium transition-colors no-underline"
      title={`Download ${attachment.name}`}
    >
      {chipContent}
    </a>
  );
}
