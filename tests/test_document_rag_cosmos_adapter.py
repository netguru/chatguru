"""Tests for the Cosmos DB for MongoDB vCore document retrieval adapter."""

from unittest.mock import MagicMock

import pytest

from config import DocumentRagSettings
from document_rag.adapters.cosmos import CosmosDocumentRagRepository


def _make_repo(
    *,
    indexes: dict | None = None,
    collections: list[str] | None = None,
    aggregate_rows: list[dict] | None = None,
    settings: DocumentRagSettings | None = None,
) -> tuple[CosmosDocumentRagRepository, MagicMock]:
    resolved_settings = settings or DocumentRagSettings(enabled=True, backend="cosmos")
    fake_collection = MagicMock()
    fake_collection.index_information.return_value = indexes or {}
    fake_collection.database.list_collection_names.return_value = (
        collections
        if collections is not None
        else [resolved_settings.mongodb_collection]
    )
    fake_collection.aggregate.return_value = aggregate_rows or []
    embeddings = MagicMock()
    embeddings.embed_query.return_value = [0.1, 0.2, 0.3]
    repo = CosmosDocumentRagRepository(
        settings=resolved_settings,
        client=MagicMock(),
        collection=fake_collection,
        embeddings=embeddings,
    )
    return repo, fake_collection


@pytest.mark.asyncio
async def test_cosmos_connect_passes_when_vector_index_present() -> None:
    repo, _ = _make_repo(indexes={"document_vector_index": {"key": {"embedding": 1}}})

    await repo.connect()


@pytest.mark.asyncio
async def test_cosmos_connect_fails_when_vector_index_missing() -> None:
    repo, _ = _make_repo(indexes={"_id_": {}})

    with pytest.raises(RuntimeError, match="vector index .* is missing on Cosmos"):
        await repo.connect()


@pytest.mark.asyncio
async def test_cosmos_connect_fails_when_collection_missing() -> None:
    # Collection absent entirely (ingestion never ran): the error must name the
    # missing collection, not be masked as a missing index or a connectivity fault.
    repo, _ = _make_repo(collections=[])

    with pytest.raises(RuntimeError, match="collection .* does not exist on Cosmos"):
        await repo.connect()


@pytest.mark.asyncio
async def test_cosmos_search_uses_cosmossearch_stage_and_search_score() -> None:
    repo, collection = _make_repo(
        aggregate_rows=[
            {"source_id": "docs/a.md", "snippet": "hello", "similarity": 0.9}
        ],
    )

    hits = await repo.search("query", limit=4)

    pipeline = collection.aggregate.call_args.args[0]
    search_stage = pipeline[0]["$search"]["cosmosSearch"]
    assert search_stage["path"] == "embedding"
    assert search_stage["vector"] == [0.1, 0.2, 0.3]
    assert search_stage["k"] == 4

    # searchScore is materialised by an $addFields directly after $search (it is
    # only available on the stage following $search), then merely included by
    # the $project.
    assert pipeline[1]["$addFields"]["similarity"] == {"$meta": "searchScore"}
    project = next(stage["$project"] for stage in pipeline if "$project" in stage)
    assert project["similarity"] == 1

    assert not any("$match" in stage for stage in pipeline)
    assert len(hits) == 1
    assert hits[0].source.source_id == "docs/a.md"
    assert hits[0].score == pytest.approx(0.9)


@pytest.mark.asyncio
async def test_cosmos_search_sets_efsearch_for_hnsw() -> None:
    settings = DocumentRagSettings(
        enabled=True, backend="cosmos", cosmos_vector_index_kind="vector-hnsw"
    )
    repo, collection = _make_repo(settings=settings, aggregate_rows=[])

    await repo.search("query", limit=4)

    cosmos_search = collection.aggregate.call_args.args[0][0]["$search"]["cosmosSearch"]
    # efSearch raised to cover k (limit=4) but never below the HNSW floor of 40.
    assert cosmos_search["efSearch"] == 40


@pytest.mark.asyncio
async def test_cosmos_search_omits_efsearch_for_ivf() -> None:
    repo, collection = _make_repo(aggregate_rows=[])  # default kind = vector-ivf

    await repo.search("query", limit=4)

    cosmos_search = collection.aggregate.call_args.args[0][0]["$search"]["cosmosSearch"]
    assert "efSearch" not in cosmos_search
