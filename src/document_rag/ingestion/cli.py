"""CLI script to ingest local documents into configured document RAG backend."""

from __future__ import annotations

import argparse
import hashlib
import mimetypes
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from config import DocumentRagSettings, get_document_rag_settings
from document_rag.embeddings import (
    DocumentEmbeddingProvider,
    build_document_embedding_provider,
)
from document_rag.ingestion.factory import build_document_rag_ingestion_repository
from document_rag.models import DocumentChunk, DocumentSourceFile

DEFAULT_EXTENSIONS = {".md", ".txt", ".pdf", ".docx", ".html", ".htm"}


def _load_docling_converter() -> Any:
    try:
        from docling.document_converter import DocumentConverter
    except ImportError as exc:  # pragma: no cover
        msg = "docling is required for document ingestion. Install it with: uv add docling"
        raise RuntimeError(msg) from exc
    return DocumentConverter()


def _read_document_as_markdown(path: Path, converter: Any) -> str:
    if path.suffix.lower() in {".md", ".txt"}:
        return path.read_text(encoding="utf-8", errors="ignore")

    result = converter.convert(str(path))
    document = getattr(result, "document", None)
    if document is None:
        return str(result)
    export_fn = getattr(document, "export_to_markdown", None)
    if callable(export_fn):
        return str(export_fn())
    return str(document)


def _split_markdown_pages(markdown: str) -> list[str]:
    """Split markdown into page-like segments when page breaks are present."""
    if not markdown:
        return []

    candidates = re.split(
        r"\f|<!--\s*pagebreak\s*-->|\n\s*---\s*\n\s*Page\s+\d+\s*\n",
        markdown,
        flags=re.IGNORECASE,
    )
    pages = [" ".join(c.split()) for c in candidates if c and c.strip()]
    return pages


def _extract_docling_page_units(
    path: Path, converter: Any
) -> list[tuple[str, int | None]]:
    """Extract text units from Docling, preferring page-aware units for PDFs."""
    try:
        result = converter.convert(str(path))
    except Exception:
        return []

    document = getattr(result, "document", None)
    if document is None:
        text = str(result)
        normalized = " ".join(text.split())
        return [(normalized, None)] if normalized else []

    pages_attr = getattr(document, "pages", None)
    if pages_attr is not None:
        units: list[tuple[str, int | None]] = []
        for idx, page in enumerate(pages_attr, start=1):
            page_text: str | None = None

            for method_name in (
                "export_to_markdown",
                "export_to_text",
                "to_markdown",
                "to_text",
            ):
                method = getattr(page, method_name, None)
                if not callable(method):
                    continue
                try:
                    value = method()
                except TypeError:
                    continue
                if value:
                    page_text = str(value)
                    break

            if not page_text:
                for attr_name in ("markdown", "text", "content"):
                    value = getattr(page, attr_name, None)
                    if value:
                        page_text = str(value)
                        break

            normalized = " ".join((page_text or "").split())
            if not normalized:
                continue

            page_number = (
                getattr(page, "page_no", None)
                or getattr(page, "page_number", None)
                or getattr(page, "page", None)
                or idx
            )
            try:
                page_no = int(page_number)
            except (TypeError, ValueError):
                page_no = idx

            units.append((normalized, page_no))

        if units:
            return units

    export_dict_fn = getattr(document, "export_to_dict", None)
    if callable(export_dict_fn):
        try:
            doc_dict = export_dict_fn()
        except Exception:
            doc_dict = None
        dict_units = _extract_page_units_from_docling_dict(doc_dict)
        if dict_units:
            return dict_units

    export_fn = getattr(document, "export_to_markdown", None)
    markdown = str(export_fn()) if callable(export_fn) else str(document)
    split_pages = _split_markdown_pages(markdown)
    if len(split_pages) > 1:
        return [(text, idx) for idx, text in enumerate(split_pages, start=1)]

    normalized = " ".join(markdown.split())
    return [(normalized, None)] if normalized else []


def _extract_page_no_from_prov(prov: object) -> int | None:
    if isinstance(prov, dict):
        candidate = (
            prov.get("page_no")
            or prov.get("page")
            or prov.get("page_number")
            or prov.get("pageIndex")
        )
        try:
            return int(candidate) if candidate is not None else None
        except (TypeError, ValueError):
            return None
    if isinstance(prov, list):
        for item in prov:
            page_no = _extract_page_no_from_prov(item)
            if page_no is not None:
                return page_no
    return None


def _extract_page_units_from_docling_dict(data: object) -> list[tuple[str, int | None]]:
    """Best-effort extraction of page-numbered text from Docling dict export."""
    if not isinstance(data, (dict, list)):
        return []

    by_page: dict[int, list[str]] = defaultdict(list)

    def visit(node: object, inherited_page: int | None = None) -> None:
        if isinstance(node, dict):
            page_no = _extract_page_no_from_prov(node.get("prov")) or inherited_page

            text_parts: list[str] = []
            for key in ("text", "orig", "markdown", "content", "caption"):
                value = node.get(key)
                if isinstance(value, str) and value.strip():
                    text_parts.append(value)

            if text_parts and page_no is not None:
                combined = " ".join(" ".join(text_parts).split())
                if combined:
                    by_page[page_no].append(combined)

            for value in node.values():
                visit(value, page_no)

        elif isinstance(node, list):
            for item in node:
                visit(item, inherited_page)

    visit(data)

    if not by_page:
        return []

    return [
        (" ".join(chunks), page_no)
        for page_no, chunks in sorted(by_page.items(), key=lambda kv: kv[0])
        if chunks
    ]


def _read_document_units(path: Path, converter: Any) -> list[tuple[str, int | None]]:
    """Return document units as (text, page). Page is set for PDF pages when available."""
    if path.suffix.lower() == ".pdf":
        docling_units = _extract_docling_page_units(path, converter)
        return docling_units

    text = _read_document_as_markdown(path, converter)
    normalized = " ".join(text.split())
    if not normalized:
        return []
    return [(normalized, None)]


def _chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    normalized = " ".join(text.split())
    if not normalized:
        return []

    chunks: list[str] = []
    start = 0
    step = max(1, chunk_size - chunk_overlap)
    while start < len(normalized):
        piece = normalized[start : start + chunk_size].strip()
        if piece:
            chunks.append(piece)
        start += step
    return chunks


def _doc_id(source_uri: str, idx: int, content: str) -> str:
    digest = hashlib.sha1(f"{source_uri}:{idx}:{content}".encode()).hexdigest()
    return f"{source_uri}#{idx}:{digest[:12]}"


def _iter_source_files(source_dir: Path, extensions: set[str]) -> list[Path]:
    files = [
        p
        for p in source_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in extensions
    ]
    return sorted(files)


def _build_chunk_documents(
    *,
    source_dir: Path,
    files: list[Path],
    converter: Any,
    embedder: DocumentEmbeddingProvider,
    chunk_size: int,
    chunk_overlap: int,
) -> tuple[list[DocumentChunk], int]:
    docs: list[DocumentChunk] = []
    skipped = 0

    for file_path in files:
        relative = file_path.relative_to(source_dir).as_posix()
        units = _read_document_units(file_path, converter)
        if not units:
            skipped += 1
            continue

        chunk_counter = 0
        for unit_text, page in units:
            chunks = _chunk_text(
                unit_text,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
            if not chunks:
                continue

            vectors = [embedder.embed_query(chunk) for chunk in chunks]
            for chunk, vector in zip(chunks, vectors, strict=True):
                chunk_counter += 1
                chunk_id = _doc_id(relative, chunk_counter, chunk)
                docs.append(
                    DocumentChunk(
                        source_id=relative,
                        source_uri=relative,
                        source_type=file_path.suffix.lower().lstrip("."),
                        title=file_path.stem,
                        chunk_id=chunk_id,
                        snippet=chunk[:400],
                        content=chunk,
                        embedding=vector,
                        page=page,
                    )
                )

    return docs, skipped


def _build_source_files(
    *, source_dir: Path, files: list[Path]
) -> list[DocumentSourceFile]:
    sources: list[DocumentSourceFile] = []
    for file_path in files:
        relative = file_path.relative_to(source_dir).as_posix()
        content_type, _ = mimetypes.guess_type(str(file_path))
        sources.append(
            DocumentSourceFile(
                source_id=relative,
                source_uri=relative,
                source_type=file_path.suffix.lower().lstrip("."),
                title=file_path.stem,
                content_bytes=file_path.read_bytes(),
                content_type=content_type,
            )
        )
    return sources


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest local files into configured document RAG backend"
    )
    parser.add_argument(
        "--source-dir", required=True, help="Local folder with source documents"
    )
    parser.add_argument("--backend", default=None)
    parser.add_argument("--chunk-size", type=int, default=1200)
    parser.add_argument("--chunk-overlap", type=int, default=150)
    parser.add_argument("--extensions", default=",".join(sorted(DEFAULT_EXTENSIONS)))
    parser.add_argument("--mongodb-uri", default=None)
    parser.add_argument("--database", default=None)
    parser.add_argument("--collection", default=None)
    parser.add_argument("--index-name", default=None)
    parser.add_argument(
        "--full-replace",
        action="store_true",
        help="Delete all existing chunks and source files before ingesting",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_dir = Path(args.source_dir).resolve()
    if not source_dir.exists() or not source_dir.is_dir():
        print(f"Source directory not found: {source_dir}", file=sys.stderr)
        return 1
    if args.chunk_overlap >= args.chunk_size:
        print("chunk-overlap must be smaller than chunk-size", file=sys.stderr)
        return 1

    settings = get_document_rag_settings()
    runtime_settings = DocumentRagSettings(
        enabled=True,
        backend=args.backend or settings.backend,
        mongodb_uri=args.mongodb_uri or settings.mongodb_uri,
        mongodb_database=args.database or settings.mongodb_database,
        mongodb_collection=args.collection or settings.mongodb_collection,
        mongodb_index_name=args.index_name or settings.mongodb_index_name,
        search_limit_default=settings.search_limit_default,
        mongodb_connection_timeout_ms=settings.mongodb_connection_timeout_ms,
        embedding_provider=settings.embedding_provider,
        embedding_custom_class=settings.embedding_custom_class,
    )

    extensions = {
        (
            ext.strip().lower()
            if ext.strip().startswith(".")
            else f".{ext.strip().lower()}"
        )
        for ext in args.extensions.split(",")
        if ext.strip()
    }

    ingestion_repo = None
    if not args.dry_run:
        ingestion_repo = build_document_rag_ingestion_repository(runtime_settings)
        ingestion_repo.prepare_target()
        if args.full_replace:
            ingestion_repo.reset_all()
            print("Full replace enabled: cleared existing document RAG data")

    files = _iter_source_files(source_dir, extensions)
    if not files:
        print("No matching files found")
        return 0

    source_files = _build_source_files(source_dir=source_dir, files=files)
    if ingestion_repo is not None:
        stored_files = ingestion_repo.upsert_source_files(source_files)
        print(f"Stored source files: {stored_files}")

    converter = _load_docling_converter()
    embedder = build_document_embedding_provider(runtime_settings)

    chunks, skipped = _build_chunk_documents(
        source_dir=source_dir,
        files=files,
        converter=converter,
        embedder=embedder,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )

    print(f"Scanned files: {len(files)}")
    print(f"Generated chunks: {len(chunks)}")
    print(f"Skipped empty documents: {skipped}")

    if args.dry_run:
        print("Dry run enabled: no backend writes")
        return 0

    if ingestion_repo is None:
        msg = "Ingestion repository not initialized"
        raise RuntimeError(msg)

    changed = ingestion_repo.upsert_chunks(chunks)
    embedding_dimensions = len(chunks[0].embedding) if chunks else 1536
    if chunks:
        ingestion_repo.ensure_ready(embedding_dimensions=embedding_dimensions)

    print(f"Upserted/updated chunks: {changed}")
    print("Done. Backend:", runtime_settings.backend)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
