"""Cosmos DB for MongoDB vCore ingestion adapter for document RAG chunks.

Reuses the Mongo ingestion adapter for connectivity, chunk upserts and GridFS
source-file storage (all wire-compatible on Cosmos vCore). Only the vector
index creation differs: Cosmos vCore builds the index synchronously via the
``createIndexes`` command with ``cosmosSearchOptions`` rather than the Atlas
search-index management API used by the Mongo adapter.
"""

import logging

from pymongo import errors

from document_rag.ingestion.adapters.mongodb import (
    MongoDocumentRagIngestionRepository,
)

logger = logging.getLogger(__name__)

# OperationFailure code for a collection that does not exist yet.
_NAMESPACE_NOT_FOUND = 26


class CosmosDocumentRagIngestionRepository(MongoDocumentRagIngestionRepository):
    """Cosmos vCore-backed ingestion adapter for document chunks."""

    def ensure_ready(
        self,
        *,
        embedding_dimensions: int,
        timeout_seconds: int = 120,  # noqa: ARG002 — kept for parity with the Atlas adapter; Cosmos creation is synchronous
    ) -> None:
        """Create the cosmosSearch vector index if absent. Idempotent.

        ``timeout_seconds`` is accepted for interface parity with the Atlas
        adapter but unused: Cosmos vCore index creation returns once the index
        is registered, so there is no READY state to poll.
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
