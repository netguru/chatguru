import { describe, expect, it } from "vitest";
import type { BackendSource } from "../types/chat";
import { classifySource, isExternalSourceUrl, mapBackendSources } from "./sourceMapping";

describe("mapBackendSources", () => {
  it("prefers source_url over the proxy path for HTML sources", () => {
    const raw: BackendSource[] = [
      {
        source_id: "doc-1",
        source_uri: "article.html",
        source_type: "html",
        source_url: "https://example.com/articles/sample/",
      },
    ];
    const mapped = mapBackendSources(raw);
    expect(mapped?.[0].url).toBe("https://example.com/articles/sample/");
  });

  it("falls back to the proxy path when source_url is null", () => {
    const raw: BackendSource[] = [{ source_id: "doc-1", source_uri: "notes.md", source_url: null }];
    const mapped = mapBackendSources(raw);
    expect(mapped?.[0].url).toBe("/documents/notes.md");
  });

  it("falls back to the proxy path when source_url is absent", () => {
    const raw: BackendSource[] = [{ source_id: "doc-1", source_uri: "notes.md" }];
    const mapped = mapBackendSources(raw);
    expect(mapped?.[0].url).toBe("/documents/notes.md");
  });

  it("keeps the proxy path and pages for a PDF without source_url", () => {
    const raw: BackendSource[] = [
      {
        source_id: "doc-1",
        source_uri: "guide.pdf",
        source_type: "pdf",
        page: 4,
      },
    ];
    const mapped = mapBackendSources(raw);
    expect(mapped?.[0].url).toBe("/documents/guide.pdf");
    expect(mapped?.[0].pages).toEqual([4]);
  });

  it("leaves url undefined when neither source_url nor source_uri is present", () => {
    const raw: BackendSource[] = [{ source_id: "doc-1" }];
    const mapped = mapBackendSources(raw);
    expect(mapped?.[0].url).toBeUndefined();
  });

  it("ignores a source_url that is not an absolute http(s) URL", () => {
    for (const badUrl of ["", "javascript:alert(1)", "//evil.example/x", "/etc/passwd"]) {
      const raw: BackendSource[] = [
        { source_id: "doc-1", source_uri: "notes.md", source_url: badUrl },
      ];
      expect(mapBackendSources(raw)?.[0].url).toBe("/documents/notes.md");
    }
  });
});

describe("classifySource", () => {
  it("puts restricted access ahead of file type", () => {
    expect(classifySource({ file: "a.pdf", url: "/documents/a.pdf", restricted: true })).toBe(
      "restricted"
    );
  });

  it("classifies previewable files by extension", () => {
    expect(classifySource({ file: "a.pdf", url: "/documents/a.pdf" })).toBe("pdf");
    expect(classifySource({ file: "a.md", url: "/documents/a.md" })).toBe("markdown");
  });

  it("classifies a source with an external url", () => {
    expect(classifySource({ file: "a.html", url: "https://example.com/a" })).toBe("external");
  });

  it("classifies anything we cannot open as opaque", () => {
    expect(classifySource({ file: "a.docx", url: "/documents/a.docx" })).toBe("opaque");
    expect(classifySource({ file: "a.html" })).toBe("opaque");
  });
});

describe("isExternalSourceUrl", () => {
  it("accepts absolute http(s) URLs", () => {
    expect(isExternalSourceUrl("https://example.com/articles/sample/")).toBe(true);
    expect(isExternalSourceUrl("http://example.com")).toBe(true);
  });

  it("rejects the /documents proxy path", () => {
    expect(isExternalSourceUrl("/documents/notes.md")).toBe(false);
  });

  it("rejects undefined and empty values", () => {
    expect(isExternalSourceUrl(undefined)).toBe(false);
    expect(isExternalSourceUrl("")).toBe(false);
  });
});
