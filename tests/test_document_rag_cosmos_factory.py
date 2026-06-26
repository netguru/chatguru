"""Factory wiring tests for the Cosmos document RAG backend."""

from unittest.mock import AsyncMock, patch

import pytest

from config import DocumentRagSettings
from document_rag.factory import build_document_rag_repository
from document_rag.ingestion.adapters.cosmos import CosmosDocumentRagIngestionRepository
from document_rag.ingestion.factory import build_document_rag_ingestion_repository


@pytest.mark.asyncio
async def test_factory_returns_cosmos_repository_and_connects() -> None:
    fake_repo = AsyncMock()
    settings = DocumentRagSettings(enabled=True, backend="cosmos")

    with patch(
        "document_rag.adapters.cosmos.CosmosDocumentRagRepository",
        return_value=fake_repo,
    ):
        repo = await build_document_rag_repository(settings)

    assert repo is fake_repo
    fake_repo.connect.assert_awaited_once()


def test_ingestion_factory_returns_cosmos_adapter_for_cosmos_backend() -> None:
    settings = DocumentRagSettings(enabled=True, backend="cosmos")

    repo = build_document_rag_ingestion_repository(settings)

    assert isinstance(repo, CosmosDocumentRagIngestionRepository)


def test_ingestion_factory_rejects_unknown_backend() -> None:
    settings = DocumentRagSettings(enabled=True, backend="redis")

    with pytest.raises(ValueError, match="mongodb or cosmos"):
        build_document_rag_ingestion_repository(settings)
