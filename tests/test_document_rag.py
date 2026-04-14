"""Behavior tests for the document RAG repository architecture."""

from dataclasses import asdict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from config import DocumentRagSettings, get_document_rag_settings
from document_rag import (
    DocumentRetrievalHit,
    DocumentSourceReference,
    build_document_rag_repository,
    get_document_rag_repository,
    init_document_rag,
    shutdown_document_rag,
)
from document_rag.adapters.mongodb import MongoDocumentRagRepository
from document_rag.embeddings import build_document_embedding_provider
from document_rag.ingestion.factory import build_document_rag_ingestion_repository


class _FakeRepository:
    def __init__(self) -> None:
        self.connected = 0
        self.closed = 0

    async def connect(self) -> None:
        self.connected += 1

    async def search(self, query: str, limit: int = 5) -> list[DocumentRetrievalHit]:
        return [
            DocumentRetrievalHit(
                snippet=f"Result for {query}",
                source=DocumentSourceReference(source_id="doc-1"),
            )
        ]

    async def close(self) -> None:
        self.closed += 1


@pytest.mark.asyncio
async def test_factory_rejects_unsupported_backend() -> None:
    settings = DocumentRagSettings(enabled=True, backend="pinecone")
    with pytest.raises(ValueError, match="Unsupported DOCUMENT_RAG_BACKEND"):
        await build_document_rag_repository(settings)


def test_ingestion_factory_rejects_unsupported_backend() -> None:
    settings = DocumentRagSettings(enabled=True, backend="pinecone")
    with pytest.raises(
        ValueError, match="Unsupported DOCUMENT_RAG_BACKEND for ingestion"
    ):
        build_document_rag_ingestion_repository(settings)


def test_ingestion_factory_builds_mongodb_adapter() -> None:
    settings = DocumentRagSettings(enabled=True, backend="mongodb")
    adapter = build_document_rag_ingestion_repository(settings)
    assert adapter.__class__.__name__ == "MongoDocumentRagIngestionRepository"


def test_embedding_provider_rejects_unsupported_provider() -> None:
    settings = DocumentRagSettings(embedding_provider="bedrock")
    with pytest.raises(ValueError, match="Unsupported DOCUMENT_RAG_EMBEDDING_PROVIDER"):
        build_document_embedding_provider(settings)


def test_embedding_provider_requires_custom_class() -> None:
    settings = DocumentRagSettings(
        embedding_provider="custom", embedding_custom_class=""
    )
    with pytest.raises(ValueError, match="DOCUMENT_RAG_EMBEDDING_CUSTOM_CLASS"):
        build_document_embedding_provider(settings)


def test_embedding_provider_loads_custom_class() -> None:
    class _CustomProvider:
        def embed_query(self, query: str) -> list[float]:
            return [float(len(query))]

    fake_module = MagicMock()
    fake_module.CustomProvider = _CustomProvider
    settings = DocumentRagSettings(
        embedding_provider="custom",
        embedding_custom_class="my.module:CustomProvider",
    )

    with patch(
        "document_rag.embeddings.importlib.import_module", return_value=fake_module
    ):
        provider = build_document_embedding_provider(settings)

    assert provider.embed_query("abc") == [3.0]


@pytest.mark.asyncio
async def test_factory_builds_mongodb_repository_and_connects() -> None:
    fake_repo = _FakeRepository()
    settings = DocumentRagSettings(enabled=True, backend="mongodb")

    with patch(
        "document_rag.adapters.mongodb.MongoDocumentRagRepository",
        return_value=fake_repo,
    ):
        repo = await build_document_rag_repository(settings)

    assert repo is fake_repo
    assert fake_repo.connected == 1


def test_document_hit_models_expose_stable_typed_shape() -> None:
    hit = DocumentRetrievalHit(
        snippet="Snippet",
        score=0.99,
        source=DocumentSourceReference(
            source_id="doc-123",
            source_type="markdown",
            source_uri="/docs/a.md",
            title="A",
            chunk_id="chunk-1",
        ),
    )

    payload = asdict(hit)
    assert payload["snippet"] == "Snippet"
    assert payload["source"]["source_id"] == "doc-123"
    assert payload["source"]["source_uri"] == "/docs/a.md"


@pytest.mark.asyncio
async def test_get_document_repository_none_when_disabled() -> None:
    await shutdown_document_rag()
    with patch("document_rag.bootstrap.is_document_rag_enabled", return_value=False):
        assert get_document_rag_repository() is None


@pytest.mark.asyncio
async def test_get_document_repository_raises_when_enabled_and_uninitialized() -> None:
    await shutdown_document_rag()
    with patch("document_rag.bootstrap.is_document_rag_enabled", return_value=True):
        with pytest.raises(
            RuntimeError, match="Document RAG repository is not initialized"
        ):
            get_document_rag_repository()


@pytest.mark.asyncio
async def test_init_document_rag_is_idempotent() -> None:
    fake_repo = _FakeRepository()
    await shutdown_document_rag()
    with (
        patch("document_rag.bootstrap.is_document_rag_enabled", return_value=True),
        patch(
            "document_rag.bootstrap.build_document_rag_repository",
            new=AsyncMock(return_value=fake_repo),
        ) as build,
    ):
        await init_document_rag()
        first = get_document_rag_repository()
        await init_document_rag()
        second = get_document_rag_repository()

    assert first is fake_repo
    assert second is fake_repo
    assert build.await_count == 1
    await shutdown_document_rag()


@pytest.mark.asyncio
async def test_shutdown_document_rag_closes_repository() -> None:
    fake_repo = _FakeRepository()
    await shutdown_document_rag()
    with (
        patch("document_rag.bootstrap.is_document_rag_enabled", return_value=True),
        patch(
            "document_rag.bootstrap.build_document_rag_repository",
            new=AsyncMock(return_value=fake_repo),
        ),
    ):
        await init_document_rag()

    await shutdown_document_rag()
    assert fake_repo.closed == 1


@pytest.mark.asyncio
async def test_init_document_rag_skips_build_when_disabled() -> None:
    await shutdown_document_rag()
    with (
        patch("document_rag.bootstrap.is_document_rag_enabled", return_value=False),
        patch(
            "document_rag.bootstrap.build_document_rag_repository",
            new=AsyncMock(),
        ) as build,
    ):
        await init_document_rag()

    build.assert_not_awaited()


def test_api_startup_fails_fast_when_document_rag_enabled_but_init_fails() -> None:
    with (
        patch(
            "api.main.init_document_rag",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ),
        patch("api.main.shutdown_document_rag", new=AsyncMock()),
    ):
        with pytest.raises(RuntimeError, match="boom"):
            with TestClient(create_app()):
                pass


def test_api_startup_succeeds_when_document_rag_disabled() -> None:
    get_document_rag_settings.cache_clear()
    with (
        patch("api.main.init_document_rag", new=AsyncMock(return_value=None)),
        patch("api.main.shutdown_document_rag", new=AsyncMock(return_value=None)),
    ):
        with TestClient(create_app()) as client:
            response = client.get("/health")
            assert response.status_code == 200


@pytest.mark.asyncio
async def test_mongodb_adapter_maps_snippets_and_sources() -> None:
    fake_collection = MagicMock()
    fake_collection.aggregate.return_value = [
        {
            "snippet": "Read me",
            "similarity": 0.85,
            "source_id": "doc-1",
            "source_uri": "docs/readme.md",
            "title": "README",
            "chunk_id": "c-1",
            "source_type": "markdown",
        }
    ]
    fake_embeddings = MagicMock()
    fake_embeddings.embed_query.return_value = [0.1, 0.2]
    fake_client = MagicMock()

    repo = MongoDocumentRagRepository(
        settings=DocumentRagSettings(enabled=True),
        client=fake_client,
        collection=fake_collection,
        embeddings=fake_embeddings,
    )
    results = await repo.search("how to install", limit=3)

    assert len(results) == 1
    assert results[0].snippet == "Read me"
    assert results[0].source.source_uri == "docs/readme.md"
    assert results[0].score == 0.85
