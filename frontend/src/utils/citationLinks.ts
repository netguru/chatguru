import type { Source } from "../types/chat";
import { isExternalSourceUrl } from "./sourceMapping";

/**
 * Matches citation patterns: [1], [2, p. 3], [1, p. 1–2], [1, p. 1; 2, p. 3], etc.
 * Requires a closing bracket to avoid false positives on markdown reference links
 * ("[1]: …") or unrelated bracketed numbers ("[2024]" with values > sources.length).
 */
const CITATION_RE =
  /\[(\d+)(?:,\s*p\.\s*(\d+)(?:[\u2013-]\s*\d+)?)?(?:\s*;\s*\d+\s*,\s*p\.\s*\d+(?:[\u2013-]\s*\d+)?)*\]/g;

/**
 * Source URLs come from ingested documents, so an unescaped ")" would close the
 * link early and let the rest render as markdown of its own.
 */
function encodeMarkdownUrl(url: string): string {
  return url.replace(
    /[()<>"\s]/g,
    (c) => `%${c.charCodeAt(0).toString(16).toUpperCase().padStart(2, "0")}`
  );
}

/**
 * Collect distinct 1-based citation numbers from the text, clamped to the
 * valid source range [1..maxNum].  Returns sorted ascending.
 */
function collectCitedNums(content: string, maxNum: number): number[] {
  return [
    ...new Set(
      [...content.matchAll(CITATION_RE)]
        .map((m) => parseInt(m[1], 10))
        .filter((n) => n >= 1 && n <= maxNum)
    ),
  ].sort((a, b) => a - b);
}

/**
 * Return only the sources actually cited in the content (i.e. referenced via
 * [N] markers), compacted from 1.  Useful for the sources sidebar so uncited
 * documents are not displayed.
 */
export function filterCitedSources(content: string, sources: Source[]): Source[] {
  if (!content || !sources || sources.length === 0) return [];

  return collectCitedNums(content, sources.length)
    .map((n) => sources[n - 1])
    .filter((s): s is Source => s != null);
}

/**
 * Inject inline citation links into response text. Replaces [1], [2], [1, p. 3],
 * [1, p. 1–2], [1, p. 1; 1, p. 2] etc. with markdown links to the source's url —
 * the document proxy, or the original page for sources saved from the web.
 * Appends #page=N to proxy links when the citation has an explicit page or the
 * source has pages. Uses source.file as link title (path).
 *
 * Citation numbers are compacted before link injection: e.g. if the model only
 * cited [4] out of sources 1–5, the rendered output will show [1] pointing at
 * that source. The remapping is purely cosmetic — sources are not reordered.
 */
export function injectCitationLinks(content: string, sources: Source[]): string {
  if (!content || !sources || sources.length === 0) return content;

  // Collect distinct source numbers that appear in the text, sorted ascending.
  const citedNums = collectCitedNums(content, sources.length);

  if (citedNums.length === 0) return content;

  // Map old 1-based numbers → new compact 1-based numbers.
  // Document-level deduplication is handled by the backend; the frontend only
  // strips uncited entries and renumbers from 1.
  const remap = new Map(citedNums.map((old, i) => [old, i + 1]));

  // Renumber citation markers using the strict pattern so markdown reference
  // links ("[1]: …") and unrelated bracketed numbers are left untouched.
  const renumbered = content.replace(CITATION_RE, (match, numStr) => {
    const oldNum = parseInt(numStr, 10);
    const newNum = remap.get(oldNum);
    if (newNum == null) return match;
    return match.replace(`[${numStr}`, `[${newNum}`);
  });

  // Build a compact sources array aligned with the new 1-based numbering.
  const compactSources: Source[] = citedNums
    .map((old) => sources[old - 1])
    .filter((s): s is Source => s != null);

  // `external` must be read off the raw url — resolving makes every url
  // absolute, after which the http(s) test can no longer tell them apart.
  const links = compactSources.map((s) => {
    if (!s.url) return { url: "", title: s.file?.split(/[/\\]/).pop() ?? "", external: false };

    let resolved: string;
    try {
      resolved = new URL(s.url, window.location.origin).toString();
    } catch {
      resolved = s.url;
    }
    return { url: resolved, title: s.file ?? "", external: isExternalSourceUrl(s.url) };
  });

  return renumbered.replace(CITATION_RE, (match, num, pageInMatch) => {
    const idx = parseInt(num, 10) - 1;
    const link = links[idx];
    if (!link?.url) return match;

    let u = encodeMarkdownUrl(link.url);

    // #page=N is a fragment only the /documents proxy understands.
    const pageNum = pageInMatch
      ? parseInt(pageInMatch, 10)
      : (compactSources[idx].pages?.[0] ?? null);
    if (!link.external && pageNum != null && pageNum > 0) u = `${u}#page=${pageNum}`;

    const t = link.title;
    return t ? `[${match}](${u} "${t.replace(/"/g, "&quot;")}")` : `[${match}](${u})`;
  });
}
