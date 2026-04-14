"""Factory for document RAG ingestion adapters."""

from config import DocumentRagSettings, get_document_rag_settings
from document_rag.ingestion.repository import DocumentRagIngestionRepository


def build_document_rag_ingestion_repository(
    settings: DocumentRagSettings | None = None,
) -> DocumentRagIngestionRepository:
    """Build ingestion adapter for the configured document RAG backend."""
    resolved = settings if settings is not None else get_document_rag_settings()
    backend = resolved.backend.lower().strip()

    if backend == "mongodb":
        from document_rag.ingestion.adapters.mongodb import (  # noqa: PLC0415
            MongoDocumentRagIngestionRepository,
        )

        return MongoDocumentRagIngestionRepository(resolved)

    msg = "Unsupported DOCUMENT_RAG_BACKEND for ingestion. Use: mongodb"
    raise ValueError(msg)
