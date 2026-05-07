import type { BackendSource, Source } from "../types/chat";

/**
 * Map raw backend source objects (snake_case) to the frontend Source shape.
 * Returns null when the input is empty or absent.
 */
export function mapBackendSources(raw: BackendSource[] | null | undefined): Source[] | null {
  if (!raw || raw.length === 0) return null;
  return raw.map((s) => ({
    file: s.source_uri ?? undefined,
    pages: s.page != null ? [s.page] : [],
  }));
}
