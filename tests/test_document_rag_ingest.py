"""Tests for local document ingestion helpers."""

from pathlib import Path

from document_rag.ingestion.cli import _chunk_text, _doc_id, _iter_source_files


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
