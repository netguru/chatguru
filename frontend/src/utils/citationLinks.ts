import type { Source } from "../types/chat";

/**
 * Return only the sources actually cited in the content (i.e. referenced via
 * [N] markers), renumbered compactly from 1.  Useful for the sources sidebar
 * so uncited documents are not displayed.
 */
export function filterCitedSources(content: string, sources: Source[]): Source[] {
  if (!content || !sources || sources.length === 0) return [];

  const citedNums = [
    ...new Set([...content.matchAll(/\[(\d+)/g)].map((m) => parseInt(m[1], 10))),
  ].sort((a, b) => a - b);

  return citedNums.map((n) => sources[n - 1]).filter((s): s is Source => s != null);
}

/**
 * Inject inline citation links into response text. Replaces [1], [2], [1, p. 3],
 * [1, p. 1–2], [1, p. 1; 1, p. 2] etc. with markdown links to the document proxy URL.
 * Appends #page=N when the citation has an explicit page or the source has pages.
 * Uses source.file as link title (path). Returns text suitable for react-markdown.
 *
 * Citation numbers are compacted before link injection: e.g. if the model only
 * cited [4] out of sources 1–5, the rendered output will show [1] pointing at
 * that source. The remapping is purely cosmetic — sources are not reordered.
 */
export function injectCitationLinks(content: string, sources: Source[]): string {
  if (!content || !sources || sources.length === 0) return content;

  // Collect distinct source numbers that appear in the text, sorted ascending.
  const citedNums = [
    ...new Set([...content.matchAll(/\[(\d+)/g)].map((m) => parseInt(m[1], 10))),
  ].sort((a, b) => a - b);

  if (citedNums.length === 0) return content;

  // Map old 1-based numbers → new compact 1-based numbers.
  // Document-level deduplication is handled by the backend; the frontend only
  // strips uncited entries and renumbers from 1.
  const remap = new Map(citedNums.map((old, i) => [old, i + 1]));

  // Renumber all [N…] occurrences in the content.
  const renumbered = content.replace(/\[(\d+)([^\]]*)\]/g, (match, numStr, rest) => {
    const newNum = remap.get(parseInt(numStr, 10));
    return newNum != null ? `[${newNum}${rest}]` : match;
  });

  // Build a compact sources array aligned with the new 1-based numbering.
  const compactSources: Source[] = citedNums
    .map((old) => sources[old - 1])
    .filter((s): s is Source => s != null);

  const sourceUrls: string[] = [];
  const sourceTitles: string[] = [];

  for (const s of compactSources) {
    if (!s.url) {
      sourceUrls.push("");
      sourceTitles.push(s.file?.split(/[/\\]/).pop() ?? "");
      continue;
    }
    let fullUrl: string;
    try {
      fullUrl = new URL(s.url, window.location.origin).toString();
    } catch {
      fullUrl = s.url;
    }
    sourceUrls.push(fullUrl);
    sourceTitles.push(s.file ?? "");
  }

  const citationRe =
    /\[(\d+)(?:,\s*p\.\s*(\d+)(?:[\u2013-]\s*\d+)?)?(?:\s*;\s*\d+\s*,\s*p\.\s*\d+(?:[\u2013-]\s*\d+)?)*\]/g;

  return renumbered.replace(citationRe, (match, num, pageInMatch) => {
    const idx = parseInt(num, 10) - 1;
    if (idx < 0 || idx >= sourceUrls.length || !sourceUrls[idx]) return match;

    let u = sourceUrls[idx];
    const pageNum = pageInMatch
      ? parseInt(pageInMatch, 10)
      : (compactSources[idx].pages?.length ?? 0) > 0
        ? compactSources[idx].pages?.[0]
        : null;

    if (pageNum != null && pageNum > 0) u = `${u}#page=${pageNum}`;

    const t = sourceTitles[idx];
    return t ? `[${match}](${u} "${t.replace(/"/g, "&quot;")}")` : `[${match}](${u})`;
  });
}
