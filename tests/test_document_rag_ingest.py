"""Tests for local document ingestion helpers."""

from pathlib import Path
from typing import Any

from document_rag.ingestion.cli import (
    _build_chunk_documents,
    _build_source_files,
    _chunk_text,
    _doc_id,
    _extract_source_url,
    _iter_source_files,
)


def test_chunk_text_generates_overlapping_chunks() -> None:
    text = "a" * 30
    chunks = _chunk_text(text, chunk_size=10, chunk_overlap=2)
    assert chunks[0] == "a" * 10
    assert chunks[1] == "a" * 10
    assert len(chunks) >= 3


def test_doc_id_is_deterministic() -> None:
    first = _doc_id("docs/a.md", 1, "hello")
    second = _doc_id("docs/a.md", 1, "hello")
    third = _doc_id("docs/a.md", 2, "hello")
    assert first == second
    assert first != third


def test_iter_source_files_filters_extensions(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("a", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    (tmp_path / "c.json").write_text("c", encoding="utf-8")

    files = _iter_source_files(tmp_path, {".md", ".txt"})
    names = [p.name for p in files]
    assert names == ["a.md", "b.txt"]


_URL = "https://example.com/articles/sample/"


def test_extract_source_url_saved_from_comment_wins(tmp_path: Path) -> None:
    other = "https://example.com/articles/other/"
    html = tmp_path / "page.html"
    html.write_text(
        "<!DOCTYPE html>\n"
        f"<!-- saved from url=({len(_URL):04d}){_URL} -->\n"
        f'<head><link rel="canonical" href="{other}"></head>',
        encoding="utf-8",
    )
    assert _extract_source_url(html) == _URL


def test_extract_source_url_falls_back_to_canonical_link(tmp_path: Path) -> None:
    html = tmp_path / "page.html"
    html.write_text(
        f'<!DOCTYPE html>\n<head><link rel="canonical" href="{_URL}"></head>',
        encoding="utf-8",
    )
    assert _extract_source_url(html) == _URL


def test_extract_source_url_handles_href_before_rel(tmp_path: Path) -> None:
    html = tmp_path / "page.html"
    html.write_text(
        f'<!DOCTYPE html>\n<head><link href="{_URL}" rel="canonical"></head>',
        encoding="utf-8",
    )
    assert _extract_source_url(html) == _URL


def test_extract_source_url_non_html_extension(tmp_path: Path) -> None:
    md = tmp_path / "page.md"
    md.write_text(f'<link rel="canonical" href="{_URL}">', encoding="utf-8")
    assert _extract_source_url(md) is None


def test_extract_source_url_no_markers(tmp_path: Path) -> None:
    html = tmp_path / "page.html"
    html.write_text("<!DOCTYPE html>\n<head><title>x</title></head>", encoding="utf-8")
    assert _extract_source_url(html) is None


def test_extract_source_url_ignores_relative_canonical(tmp_path: Path) -> None:
    html = tmp_path / "page.html"
    html.write_text(
        '<!DOCTYPE html>\n<head><link rel="canonical" href="/articles/sample/"></head>',
        encoding="utf-8",
    )
    assert _extract_source_url(html) is None


def test_extract_source_url_ignores_non_http_scheme(tmp_path: Path) -> None:
    html = tmp_path / "page.html"
    html.write_text(
        '<!DOCTYPE html>\n<head><link rel="canonical" href="httpfoo://evil"></head>',
        encoding="utf-8",
    )
    assert _extract_source_url(html) is None


def test_extract_source_url_missing_file(tmp_path: Path) -> None:
    assert _extract_source_url(tmp_path / "does-not-exist.html") is None


def test_extract_source_url_deep_in_head(tmp_path: Path) -> None:
    filler = '<meta property="og:description" content="x">\n' * 200
    html = tmp_path / "page.html"
    html.write_text(
        "<!DOCTYPE html>\n<head>\n"
        f"{filler}"
        f'<link rel="canonical" href="{_URL}">\n'
        "</head><body>x</body>",
        encoding="utf-8",
    )
    assert _extract_source_url(html) == _URL


def test_extract_source_url_ignores_link_after_head(tmp_path: Path) -> None:
    html = tmp_path / "page.html"
    html.write_text(
        "<!DOCTYPE html>\n<head><title>x</title></head>\n"
        f'<body><link rel="canonical" href="{_URL}"></body>',
        encoding="utf-8",
    )
    assert _extract_source_url(html) is None


def test_extract_source_url_head_end_is_case_and_space_insensitive(
    tmp_path: Path,
) -> None:
    for closing in ("</Head>", "</HEAD>", "</head >"):
        html = tmp_path / "page.html"
        html.write_text(
            f"<!DOCTYPE html>\n<head><title>x</title>{closing}\n"
            f'<body><link rel="canonical" href="{_URL}"></body>',
            encoding="utf-8",
        )
        assert _extract_source_url(html) is None, closing


def test_extract_source_url_accepts_unquoted_attributes(tmp_path: Path) -> None:
    html = tmp_path / "page.html"
    html.write_text(
        f"<!DOCTYPE html>\n<head><link rel=canonical href={_URL}></head>",
        encoding="utf-8",
    )
    assert _extract_source_url(html) == _URL


def test_extract_source_url_ignores_non_canonical_rel(tmp_path: Path) -> None:
    html = tmp_path / "page.html"
    html.write_text(
        f'<!DOCTYPE html>\n<head><link rel="stylesheet" href="{_URL}"></head>',
        encoding="utf-8",
    )
    assert _extract_source_url(html) is None


class _FakeDoclingDocument:
    def export_to_markdown(self) -> str:
        return "Some extracted body text."


class _FakeDoclingResult:
    document = _FakeDoclingDocument()


class _FakeConverter:
    def convert(self, _path: str) -> Any:
        return _FakeDoclingResult()


class _FakeEmbedder:
    def embed_query(self, _text: str) -> list[float]:
        return [0.1, 0.2, 0.3]


def test_build_chunk_documents_sets_source_url_for_html(tmp_path: Path) -> None:
    html = tmp_path / "article.html"
    html.write_text(
        "<!DOCTYPE html>\n"
        f"<!-- saved from url=({len(_URL):04d}){_URL} -->\n"
        "<head></head><body>Body text of the saved page.</body>",
        encoding="utf-8",
    )
    md = tmp_path / "notes.md"
    md.write_text("Some notes.", encoding="utf-8")

    files = _iter_source_files(tmp_path, {".html", ".md"})
    chunks, skipped = _build_chunk_documents(
        source_dir=tmp_path,
        files=files,
        converter=_FakeConverter(),
        embedder=_FakeEmbedder(),
        chunk_size=1200,
        chunk_overlap=150,
    )

    assert skipped == 0
    by_uri = {c.source_uri: c for c in chunks}
    assert by_uri["article.html"].source_url == _URL
    assert by_uri["notes.md"].source_url is None


def test_build_source_files_sets_source_url_for_html(tmp_path: Path) -> None:
    html = tmp_path / "article.html"
    html.write_text(
        "<!DOCTYPE html>\n"
        f"<!-- saved from url=({len(_URL):04d}){_URL} -->\n"
        "<head></head><body>Body text of the saved page.</body>",
        encoding="utf-8",
    )
    md = tmp_path / "notes.md"
    md.write_text("Some notes.", encoding="utf-8")

    files = _iter_source_files(tmp_path, {".html", ".md"})
    sources = _build_source_files(source_dir=tmp_path, files=files)

    by_uri = {s.source_uri: s for s in sources}
    assert by_uri["article.html"].source_url == _URL
    assert by_uri["notes.md"].source_url is None
