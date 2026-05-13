"""Document RAG repository package."""

from document_rag.bootstrap import (
    get_document_rag_repository,
    init_document_rag,
    is_document_rag_enabled,
    shutdown_document_rag,
)
from document_rag.factory import build_document_rag_repository
from document_rag.ingestion.factory import build_document_rag_ingestion_repository
from document_rag.ingestion.repository import DocumentRagIngestionRepository
from document_rag.models import (
    DocumentChunk,
    DocumentRetrievalHit,
    DocumentSourceFile,
    DocumentSourceReference,
)
from document_rag.repository import DocumentRagRepository

__all__ = [
    "DocumentChunk",
    "DocumentRagIngestionRepository",
    "DocumentRagRepository",
    "DocumentRetrievalHit",
    "DocumentSourceFile",
    "DocumentSourceReference",
    "build_document_rag_ingestion_repository",
    "build_document_rag_repository",
    "get_document_rag_repository",
    "init_document_rag",
    "is_document_rag_enabled",
    "shutdown_document_rag",
]
