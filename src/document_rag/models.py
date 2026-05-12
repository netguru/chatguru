"""Domain models for document retrieval results."""

from dataclasses import dataclass


@dataclass(slots=True)
class DocumentSourceReference:
    """Source reference metadata attached to a retrieved snippet."""

    source_id: str
    source_type: str | None = None
    source_uri: str | None = None
    title: str | None = None
    chunk_id: str | None = None
    page: int | None = None


@dataclass(slots=True)
class DocumentRetrievalHit:
    """Typed hit returned by document retrieval repository."""

    snippet: str
    source: DocumentSourceReference
    score: float | None = None


@dataclass(slots=True)
class DocumentChunk:
    """Ingestion-time chunk record stored in document backend."""

    source_id: str
    source_uri: str
    source_type: str
    title: str
    chunk_id: str
    snippet: str
    content: str
    embedding: list[float]
    page: int | None = None


@dataclass(slots=True)
class DocumentSourceFile:
    """Full source file stored for frontend preview."""

    source_id: str
    source_uri: str
    source_type: str
    title: str
    content_bytes: bytes
    content_type: str | None = None
