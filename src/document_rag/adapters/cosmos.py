"""Cosmos DB for MongoDB vCore adapter for document retrieval.

Cosmos vCore is wire-compatible with MongoDB but does NOT support the Atlas
``$vectorSearch`` stage or the Atlas search-index management API. It uses the
``$search`` stage with the ``cosmosSearch`` operator for queries and reports
similarity via ``{$meta: "searchScore"}``. GridFS and ordinary CRUD work
unchanged, so this adapter reuses the Mongo adapter for everything except
connectivity verification and the search pipeline.
"""

import asyncio
from typing import Any

from pymongo import errors

from config import get_logger
from document_rag.adapters.mongodb import (
    MongoDocumentRagRepository,
    projection_stage,
    row_to_hit,
)
from document_rag.models import DocumentRetrievalHit

logger = get_logger("document_rag.cosmos")

# Cosmos vCore HNSW rejects a query whose candidate count `k` exceeds `efSearch`
# (which defaults to 40), so never request fewer than this and always cover `k`.
_HNSW_MIN_EF_SEARCH = 40


class CosmosDocumentRagRepository(MongoDocumentRagRepository):
    """Cosmos vCore (cosmosSearch) backed implementation of the retrieval port."""

    async def connect(self) -> None:
        if self._client is None:
            return
        try:
            await asyncio.to_thread(self._client.admin.command, "ping")
            await asyncio.to_thread(self._verify_vector_index_present)
        except errors.PyMongoError as exc:
            msg = "Document RAG Cosmos connectivity check failed"
            raise RuntimeError(msg) from exc

    def _verify_vector_index_present(self) -> None:
        """Fail fast when the cosmosSearch vector index is missing.

        Cosmos vCore exposes vector indexes through ordinary ``listIndexes``
        (there is no async READY state like Atlas), so a name lookup is enough.
        """
        if self._collection is None:
            msg = "Document RAG collection is not initialized"
            raise RuntimeError(msg)

        index_name = self._settings.mongodb_index_name
        info = self._collection.index_information()
        if index_name not in info:
            msg = (
                f"Document RAG vector index '{index_name}' is missing on Cosmos. "
                "Run document ingestion before starting the app."
            )
            raise RuntimeError(msg)

    async def search(self, query: str, limit: int = 5) -> list[DocumentRetrievalHit]:
        if self._collection is None:
            msg = "Document RAG collection is not initialized"
            raise RuntimeError(msg)
        collection = self._collection
        query_vector = await asyncio.to_thread(self._embeddings.embed_query, query)

        cosmos_search: dict[str, Any] = {
            "vector": query_vector,
            "path": "embedding",
            "k": limit,
        }
        # HNSW rejects queries where k exceeds efSearch, so raise efSearch to
        # cover k. IVF has no such cap.
        if self._settings.cosmos_vector_index_kind == "vector-hnsw":
            cosmos_search["efSearch"] = max(_HNSW_MIN_EF_SEARCH, limit)

        pipeline: list[dict[str, Any]] = [
            {"$search": {"cosmosSearch": cosmos_search}},
            # Materialise the score immediately off $search: Cosmos vCore only
            # exposes {$meta: "searchScore"} on the stage directly following
            # $search, so capture it before any later stage reshapes the docs.
            {"$addFields": {"similarity": {"$meta": "searchScore"}}},
            # `similarity` was already materialised by $addFields, so just include it.
            projection_stage(1),
        ]
        rows = await asyncio.to_thread(lambda: list(collection.aggregate(pipeline)))

        hits = [hit for row in rows if (hit := row_to_hit(row)) is not None]
        logger.info("Document RAG (cosmos) search returned %d hits", len(hits))
        return hits
