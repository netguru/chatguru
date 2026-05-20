import type { BackendSource, Source } from "../types/chat";

const MARKDOWN_EXTENSIONS = [".md", ".markdown"] as const;

export function isPdfSource(file: string | undefined): boolean {
  return !!file && file.toLowerCase().endsWith(".pdf");
}

export function isMarkdownSource(file: string | undefined): boolean {
  if (!file) return false;
  const lower = file.toLowerCase();
  return MARKDOWN_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

export function isPreviewableSource(file: string | undefined): boolean {
  return isPdfSource(file) || isMarkdownSource(file);
}

/**
 * Map raw backend source objects (snake_case) to the frontend Source shape.
 * Returns null when the input is empty or absent.
 *
 * Sets `url` to the document proxy path so injectCitationLinks can resolve
 * inline [N] / [N, p. X] citations to clickable links.
 */
export function mapBackendSources(raw: BackendSource[] | null | undefined): Source[] | null {
  if (!raw || raw.length === 0) return null;
  return raw.map((s) => ({
    file: s.source_uri ?? undefined,
    pages: s.page != null ? [s.page] : [],
    url: s.source_uri ? `/documents/${s.source_uri}` : undefined,
  }));
}
