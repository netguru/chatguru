"""Port (interface) for document RAG ingestion backends."""

from typing import Protocol

from document_rag.models import DocumentChunk, DocumentSourceFile


class DocumentRagIngestionRepository(Protocol):
    """Ingestion contract implemented by backend adapters."""

    def prepare_target(self) -> None:
        """Validate backend connectivity and ensure target collection exists."""
        ...

    def reset_all(self) -> None:
        """Delete all existing ingestion data from the target backend."""
        ...

    def ensure_ready(self, *, embedding_dimensions: int) -> None:
        """Ensure backend is ready for vector ingestion (index/schema checks)."""
        ...

    def upsert_chunks(self, chunks: list[DocumentChunk]) -> int:
        """Upsert chunk records and return number of changed records."""
        ...

    def upsert_source_files(self, files: list[DocumentSourceFile]) -> int:
        """Upsert full source files and return number of changed records."""
        ...
