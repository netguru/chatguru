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
 * True when the source's url points at an external page (a `source_url`
 * kept by mapBackendSources) rather than the relative /documents proxy path.
 */
export function isExternalSourceUrl(url: string | null | undefined): url is string {
  return !!url && /^https?:\/\//i.test(url);
}

export type SourceKind = "restricted" | "pdf" | "markdown" | "external" | "opaque";

/** Decides what a source opens and which icon it gets. "opaque" opens nothing. */
export function classifySource(source: Source): SourceKind {
  if (source.restricted) return "restricted";
  if (isPdfSource(source.file)) return "pdf";
  if (isMarkdownSource(source.file)) return "markdown";
  if (isExternalSourceUrl(source.url)) return "external";
  return "opaque";
}

/**
 * Map raw backend source objects (snake_case) to the frontend Source shape.
 * Returns null when the input is empty or absent.
 *
 * Sets `url` so injectCitationLinks can resolve inline [N] / [N, p. X]
 * citations to clickable links. This is the single gate on `source_url` —
 * consumers can treat `url` as usable.
 */
export function mapBackendSources(raw: BackendSource[] | null | undefined): Source[] | null {
  if (!raw || raw.length === 0) return null;
  return raw.map((s) => ({
    file: s.source_uri ?? undefined,
    pages: s.page != null ? [s.page] : [],
    url: isExternalSourceUrl(s.source_url)
      ? s.source_url
      : s.source_uri
        ? `/documents/${s.source_uri}`
        : undefined,
  }));
}
