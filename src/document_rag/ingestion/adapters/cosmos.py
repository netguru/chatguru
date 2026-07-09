"""Cosmos DB for MongoDB vCore ingestion adapter for document RAG chunks.

Connectivity, chunk upserts and GridFS source-file storage are wire-compatible
on Cosmos vCore, so they are delegated to an injected Mongo ingestion adapter
(composition, not inheritance). Only vector-index creation differs: Cosmos vCore
builds the index synchronously via the ``createIndexes`` command with
``cosmosSearchOptions`` rather than the Atlas search-index management API.
"""

import logging
from typing import Any

from pymongo import MongoClient, errors

from config import DocumentRagSettings
from document_rag.ingestion.adapters.mongodb import (
    MongoDocumentRagIngestionRepository,
    create_mongo_client,
)
from document_rag.models import DocumentChunk, DocumentSourceFile

logger = logging.getLogger(__name__)

# OperationFailure code for a collection that does not exist yet.
_NAMESPACE_NOT_FOUND = 26


class CosmosDocumentRagIngestionRepository:
    """Cosmos vCore-backed ingestion adapter for document chunks."""

    def __init__(
        self,
        settings: DocumentRagSettings,
        *,
        shared_ops: MongoDocumentRagIngestionRepository | None = None,
    ) -> None:
        self._settings = settings
        # Connectivity and CRUD are identical on Cosmos vCore, so delegate them
        # to the Mongo adapter rather than inheriting from a sibling backend.
        self._shared: MongoDocumentRagIngestionRepository = (
            shared_ops or MongoDocumentRagIngestionRepository(settings)
        )

    def prepare_target(self) -> None:
        self._shared.prepare_target()

    def reset_all(self) -> None:
        self._shared.reset_all()

    def upsert_chunks(self, chunks: list[DocumentChunk]) -> int:
        return int(self._shared.upsert_chunks(chunks))

    def upsert_source_files(self, files: list[DocumentSourceFile]) -> int:
        return int(self._shared.upsert_source_files(files))

    def ensure_ready(self, *, embedding_dimensions: int) -> None:
        """Create the cosmosSearch vector index if absent. Idempotent.

        Cosmos vCore index creation returns once the index is registered, so
        (unlike the Atlas adapter) there is no READY state to poll.
        """
        index_name = self._settings.mongodb_index_name

        with self._mongo_client() as client:
            database = client[self._settings.mongodb_database]
            collection = database[self._settings.mongodb_collection]

            try:
                existing = collection.index_information()
            except errors.OperationFailure as exc:
                # Collection not created yet — proceed to create the index
                # (creating it implicitly creates the collection on Cosmos).
                if exc.code != _NAMESPACE_NOT_FOUND:
                    raise
                existing = {}

            if index_name in existing:
                logger.info("Cosmos vector index '%s' already present.", index_name)
                return

            cosmos_options = self._build_cosmos_search_options(embedding_dimensions)
            database.command(
                {
                    "createIndexes": self._settings.mongodb_collection,
                    "indexes": [
                        {
                            "name": index_name,
                            "key": {"embedding": "cosmosSearch"},
                            "cosmosSearchOptions": cosmos_options,
                        }
                    ],
                }
            )
            logger.info(
                "Created Cosmos vector index '%s' (%s, %d dims).",
                index_name,
                cosmos_options["kind"],
                embedding_dimensions,
            )

    def _build_cosmos_search_options(
        self, embedding_dimensions: int
    ) -> dict[str, object]:
        kind = self._settings.cosmos_vector_index_kind
        options: dict[str, object] = {
            "kind": kind,
            "similarity": self._settings.cosmos_vector_similarity,
            "dimensions": embedding_dimensions,
        }
        if kind == "vector-hnsw":
            options["m"] = self._settings.cosmos_vector_m
            options["efConstruction"] = self._settings.cosmos_vector_ef_construction
        else:
            # vector-ivf (default) and any other IVF-style kind.
            options["numLists"] = self._settings.cosmos_vector_num_lists
        return options

    def _mongo_client(self) -> MongoClient[dict[str, Any]]:
        client: MongoClient[dict[str, Any]] = create_mongo_client(self._settings)
        return client
