import { describe, expect, it } from "vitest";
import type { Source } from "../types/chat";
import { injectCitationLinks } from "./citationLinks";

describe("injectCitationLinks", () => {
  it("links a proxy source and appends the cited page", () => {
    const sources: Source[] = [{ file: "guide.pdf", url: "/documents/guide.pdf", pages: [] }];
    const out = injectCitationLinks("See [1, p. 3].", sources);
    expect(out).toContain("/documents/guide.pdf#page=3");
  });

  it("falls back to the source's own page when the citation has none", () => {
    const sources: Source[] = [{ file: "guide.pdf", url: "/documents/guide.pdf", pages: [7] }];
    const out = injectCitationLinks("See [1].", sources);
    expect(out).toContain("#page=7");
  });

  it("never appends #page= to an external page URL", () => {
    const sources: Source[] = [
      { file: "article.html", url: "https://example.com/articles/", pages: [3] },
    ];
    expect(injectCitationLinks("See [1, p. 3].", sources)).not.toContain("#page=");
    expect(injectCitationLinks("See [1].", sources)).not.toContain("#page=");
  });

  it("percent-encodes parentheses so a crafted URL cannot break out of the link", () => {
    const sources: Source[] = [
      {
        file: "article.html",
        url: "https://example.com/a)![x](https://evil.example/beacon.png",
        pages: [],
      },
    ];
    const out = injectCitationLinks("See [1].", sources);
    expect(out).toContain("%29");
    expect(out).toContain("%28");
    expect(out).not.toContain("](https://evil.example");
    expect(out.match(/\]\(/g)).toHaveLength(1); // one link, not two
  });

  it("percent-encodes quotes and whitespace in the link target", () => {
    const sources: Source[] = [{ file: "a.html", url: 'https://example.com/a b"c', pages: [] }];
    const out = injectCitationLinks("See [1].", sources);
    expect(out).toContain("%22");
    expect(out).not.toMatch(/\(https:\/\/example\.com\/a /);
  });

  it("leaves citations untouched when the source has no url", () => {
    const sources: Source[] = [{ file: "guide.pdf", pages: [] }];
    expect(injectCitationLinks("See [1].", sources)).toBe("See [1].");
  });
});
