"""Composition root for document RAG repository."""

from config import DocumentRagSettings, get_document_rag_settings
from document_rag.repository import DocumentRagRepository


async def build_document_rag_repository(
    settings: DocumentRagSettings | None = None,
) -> DocumentRagRepository:
    """Build configured document RAG adapter and verify connectivity."""
    resolved = settings if settings is not None else get_document_rag_settings()
    backend = resolved.backend.lower().strip()

    if backend == "mongodb":
        from document_rag.adapters.mongodb import (  # noqa: PLC0415
            MongoDocumentRagRepository,
        )

        repo: DocumentRagRepository = MongoDocumentRagRepository(resolved)
        await repo.connect()
        return repo

    msg = "Unsupported DOCUMENT_RAG_BACKEND. Use: mongodb"
    raise ValueError(msg)
