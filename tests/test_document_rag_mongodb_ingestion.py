"""Tests for the MongoDB document ingestion adapter."""

from unittest.mock import MagicMock, patch

import pytest

from config import DocumentRagSettings
from document_rag.ingestion.adapters.mongodb import MongoDocumentRagIngestionRepository


def test_mongodb_ingestion_adapter_ensure_ready_raises_on_timeout() -> None:
    settings = DocumentRagSettings(enabled=True, backend="mongodb")
    adapter = MongoDocumentRagIngestionRepository(settings)
    client_context = MagicMock()
    client = MagicMock()
    client_context.__enter__.return_value = client
    client_context.__exit__.return_value = None
    collection = MagicMock()
    collection.list_search_indexes.side_effect = [
        [],
        [{"name": settings.mongodb_index_name, "status": "BUILDING"}],
        [{"name": settings.mongodb_index_name, "status": "BUILDING"}],
    ]

    with (
        patch.object(adapter, "_mongo_client", return_value=client_context),
        patch.object(adapter, "_collection", return_value=collection),
        # Four monotonic() calls: deadline start, two in-time loop checks, then timeout exit.
        patch("document_rag.ingestion.adapters.mongodb.time.monotonic", side_effect=[0, 0, 60, 121]),
        patch("document_rag.ingestion.adapters.mongodb.time.sleep"),
        pytest.raises(
            TimeoutError,
            match=(
                f"Index '{settings.mongodb_index_name}' did not reach READY within 120s "
                r"\(last status: BUILDING\)\."
            ),
        ),
    ):
        adapter.ensure_ready(embedding_dimensions=1536)

    collection.create_search_index.assert_called_once()
    assert collection.list_search_indexes.call_count == 3
