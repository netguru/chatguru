/**
 * Calls the backend `/process-document` endpoint to convert a document to markdown via Docling.
 */
export async function processDocument(file: File): Promise<{ markdown: string; filename: string }> {
  const formData = new FormData();
  formData.append("file", file);

  let response: Response;
  try {
    response = await fetch("/process-document", {
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

  return response.json() as Promise<{ markdown: string; filename: string }>;
}
