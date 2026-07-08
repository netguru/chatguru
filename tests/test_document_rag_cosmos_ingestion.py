"""Tests for the Cosmos DB for MongoDB vCore document ingestion adapter."""

from unittest.mock import MagicMock, patch

from config import DocumentRagSettings
from document_rag.ingestion.adapters.cosmos import CosmosDocumentRagIngestionRepository


def _adapter_with_index_info(
    index_info: dict, settings: DocumentRagSettings
) -> tuple[CosmosDocumentRagIngestionRepository, MagicMock, MagicMock]:
    adapter = CosmosDocumentRagIngestionRepository(settings)
    client_context = MagicMock()
    client = MagicMock()
    client_context.__enter__.return_value = client
    client_context.__exit__.return_value = None
    database = MagicMock()
    collection = MagicMock()
    collection.index_information.return_value = index_info
    client.__getitem__.return_value = database
    database.__getitem__.return_value = collection
    return adapter, client_context, database


def test_cosmos_ensure_ready_creates_ivf_index_when_absent() -> None:
    settings = DocumentRagSettings(
        enabled=True,
        backend="cosmos",
        cosmos_vector_index_kind="vector-ivf",
        cosmos_vector_num_lists=7,
        cosmos_vector_similarity="COS",
    )
    adapter, client_context, database = _adapter_with_index_info({"_id_": {}}, settings)

    with patch.object(adapter, "_mongo_client", return_value=client_context):
        adapter.ensure_ready(embedding_dimensions=1536)

    command = database.command.call_args.args[0]
    assert command["createIndexes"] == settings.mongodb_collection
    index_def = command["indexes"][0]
    assert index_def["name"] == settings.mongodb_index_name
    assert index_def["key"] == {"embedding": "cosmosSearch"}
    options = index_def["cosmosSearchOptions"]
    assert options["kind"] == "vector-ivf"
    assert options["numLists"] == 7
    assert options["similarity"] == "COS"
    assert options["dimensions"] == 1536
    assert "m" not in options


def test_cosmos_ensure_ready_creates_hnsw_index_with_hnsw_options() -> None:
    settings = DocumentRagSettings(
        enabled=True,
        backend="cosmos",
        cosmos_vector_index_kind="vector-hnsw",
        cosmos_vector_m=24,
        cosmos_vector_ef_construction=128,
    )
    adapter, client_context, database = _adapter_with_index_info({"_id_": {}}, settings)

    with patch.object(adapter, "_mongo_client", return_value=client_context):
        adapter.ensure_ready(embedding_dimensions=768)

    options = database.command.call_args.args[0]["indexes"][0]["cosmosSearchOptions"]
    assert options["kind"] == "vector-hnsw"
    assert options["m"] == 24
    assert options["efConstruction"] == 128
    assert options["dimensions"] == 768
    assert "numLists" not in options


def test_cosmos_ensure_ready_skips_when_index_present() -> None:
    settings = DocumentRagSettings(enabled=True, backend="cosmos")
    adapter, client_context, database = _adapter_with_index_info(
        {settings.mongodb_index_name: {"key": {"embedding": "cosmosSearch"}}}, settings
    )

    with patch.object(adapter, "_mongo_client", return_value=client_context):
        adapter.ensure_ready(embedding_dimensions=1536)

    database.command.assert_not_called()
