import type { Source } from "../types/chat";

/**
 * Inject inline citation links into response text. Replaces [1], [2], [1, p. 3],
 * [1, p. 1–2], [1, p. 1; 1, p. 2] etc. with markdown links to the document proxy URL.
 * Appends #page=N when the citation has an explicit page or the source has pages.
 * Uses source.file as link title (path). Returns text suitable for react-markdown.
 */
export function injectCitationLinks(content: string, sources: Source[]): string {
  if (!content || !sources || sources.length === 0) return content;

  const sourceUrls: string[] = [];
  const sourceTitles: string[] = [];

  for (const s of sources) {
    if (!s.url) {
      sourceUrls.push("");
      sourceTitles.push(s.file.split(/[/\\]/).pop() ?? "");
      continue;
    }
    let fullUrl: string;
    try {
      fullUrl = new URL(s.url, window.location.origin).toString();
    } catch {
      fullUrl = s.url;
    }
    sourceUrls.push(fullUrl);
    sourceTitles.push(s.file);
  }

  const citationRe =
    /\[(\d+)(?:,\s*p\.\s*(\d+)(?:[\u2013-]\s*\d+)?)?(?:\s*;\s*\d+\s*,\s*p\.\s*\d+(?:[\u2013-]\s*\d+)?)*\]/g;

  return content.replace(citationRe, (match, num, pageInMatch) => {
    const idx = parseInt(num, 10) - 1;
    if (idx < 0 || idx >= sourceUrls.length || !sourceUrls[idx]) return match;

    let u = sourceUrls[idx];
    const pageNum = pageInMatch
      ? parseInt(pageInMatch, 10)
      : sources[idx].pages?.length > 0
        ? sources[idx].pages[0]
        : null;

    if (pageNum != null && pageNum > 0) u = `${u}#page=${pageNum}`;

    const t = sourceTitles[idx];
    return t ? `[${match}](${u} "${t.replace(/"/g, "&quot;")}")` : `[${match}](${u})`;
  });
}
