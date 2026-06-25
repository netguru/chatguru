"""Ingestion adapter implementations."""

from document_rag.ingestion.adapters.cosmos import (
    CosmosDocumentRagIngestionRepository,
)
from document_rag.ingestion.adapters.mongodb import MongoDocumentRagIngestionRepository

__all__ = [
    "CosmosDocumentRagIngestionRepository",
    "MongoDocumentRagIngestionRepository",
]
