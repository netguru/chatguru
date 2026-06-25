"""Factory wiring tests for the Cosmos document RAG backend."""

import pytest

from config import DocumentRagSettings
from document_rag.ingestion.adapters.cosmos import CosmosDocumentRagIngestionRepository
from document_rag.ingestion.factory import build_document_rag_ingestion_repository


def test_ingestion_factory_returns_cosmos_adapter_for_cosmos_backend() -> None:
    settings = DocumentRagSettings(enabled=True, backend="cosmos")

    repo = build_document_rag_ingestion_repository(settings)

    assert isinstance(repo, CosmosDocumentRagIngestionRepository)


def test_ingestion_factory_rejects_unknown_backend() -> None:
    settings = DocumentRagSettings(enabled=True, backend="redis")

    with pytest.raises(ValueError, match="mongodb or cosmos"):
        build_document_rag_ingestion_repository(settings)
