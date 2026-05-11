"""Document RAG ingestion package."""

from document_rag.ingestion.cli import main
from document_rag.ingestion.factory import build_document_rag_ingestion_repository
from document_rag.ingestion.repository import DocumentRagIngestionRepository

__all__ = [
    "DocumentRagIngestionRepository",
    "build_document_rag_ingestion_repository",
    "main",
]
