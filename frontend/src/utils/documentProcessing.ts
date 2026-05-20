import { getOrCreateVisitorId } from "./visitorId";

/**
 * Calls the backend `/upload-attachment` endpoint to store a raw image file.
 * Returns the server-assigned `attachment_id` (or `null` when storage is unavailable).
 */
export async function uploadAttachment(
  file: File
): Promise<{ attachment_id: string | null; name: string; mime_type: string }> {
  const formData = new FormData();
  formData.append("file", file);

  const visitorId = getOrCreateVisitorId();
  const params = new URLSearchParams({ visitor_id: visitorId });

  let response: Response;
  try {
    response = await fetch(`/upload-attachment?${params.toString()}`, {
      method: "POST",
      body: formData,
    });
  } catch {
    throw new Error(
      "Could not reach the server. Make sure the backend is running and requests to /upload-attachment reach it."
    );
  }

  if (!response.ok) {
    const detail = await response.text().catch(() => response.statusText);
    throw new Error(`Image upload failed: ${detail}`);
  }

  const data = (await response.json()) as {
    attachment_id?: string | null;
    name: string;
    mime_type: string;
  };
  return {
    attachment_id: data.attachment_id ?? null,
    name: data.name,
    mime_type: data.mime_type,
  };
}

/**
 * Calls the backend `/process-document` endpoint to convert a document to markdown via Docling.
 * When the backend has attachment storage enabled, `attachment_id` is returned so the
 * original file can be linked to the persisted chat message and served for preview.
 */
export async function processDocument(
  file: File
): Promise<{ markdown: string; filename: string; attachment_id: string | null }> {
  const formData = new FormData();
  formData.append("file", file);

  const visitorId = getOrCreateVisitorId();
  const params = new URLSearchParams({ visitor_id: visitorId });

  let response: Response;
  try {
    response = await fetch(`/process-document?${params.toString()}`, {
      method: "POST",
      body: formData,
    });
  } catch {
    throw new Error(
      "Could not reach the server. Start the backend (for example uv run uvicorn) and ensure requests to /process-document reach it."
    );
  }

  if (!response.ok) {
    const detail = await response.text().catch(() => response.statusText);
    throw new Error(`Document processing failed: ${detail}`);
  }

  const data = (await response.json()) as {
    markdown: string;
    filename: string;
    attachment_id?: string | null;
  };
  return {
    markdown: data.markdown,
    filename: data.filename,
    attachment_id: data.attachment_id ?? null,
  };
}
