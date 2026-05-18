"""MongoDB adapter for document retrieval repository."""

import asyncio
from typing import Any

from pymongo import MongoClient, errors

from config import DocumentRagSettings, get_logger
from document_rag.embeddings import (
    DocumentEmbeddingProvider,
    build_document_embedding_provider,
)
from document_rag.models import DocumentRetrievalHit, DocumentSourceReference

logger = get_logger("document_rag.mongodb")


class MongoDocumentRagRepository:
    """MongoDB vector-search backed implementation of document retrieval port."""

    def __init__(
        self,
        settings: DocumentRagSettings,
        *,
        client: MongoClient[dict[str, Any]] | None = None,
        collection: Any | None = None,
        embeddings: DocumentEmbeddingProvider | Any | None = None,
    ) -> None:
        self._settings = settings
        self._client = client
        self._collection = collection
        self._embeddings = embeddings or build_document_embedding_provider(settings)

        if self._collection is None:
            self._client = self._client or MongoClient(
                settings.mongodb_uri,
                serverSelectionTimeoutMS=settings.mongodb_connection_timeout_ms,
                connectTimeoutMS=settings.mongodb_connection_timeout_ms,
            )
            self._collection = self._client[settings.mongodb_database][
                settings.mongodb_collection
            ]

    async def connect(self) -> None:
        if self._client is None:
            return
        try:
            await asyncio.to_thread(self._client.admin.command, "ping")
        except errors.PyMongoError as exc:
            msg = "Document RAG MongoDB connectivity check failed"
            raise RuntimeError(msg) from exc

    async def search(self, query: str, limit: int = 5) -> list[DocumentRetrievalHit]:
        if self._collection is None:
            msg = "Document RAG collection is not initialized"
            raise RuntimeError(msg)
        collection = self._collection
        query_vector = await asyncio.to_thread(self._embeddings.embed_query, query)
        pipeline: list[dict[str, Any]] = [
            {
                "$vectorSearch": {
                    "index": self._settings.mongodb_index_name,
                    "path": "embedding",
                    "queryVector": query_vector,
                    "numCandidates": limit * 20,
                    "limit": limit,
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "snippet": {"$ifNull": ["$snippet", "$content"]},
                    "source_id": {"$ifNull": ["$source_id", "$id"]},
                    "source_type": 1,
                    "source_uri": 1,
                    "title": 1,
                    "chunk_id": 1,
                    "page": 1,
                    "similarity": {"$meta": "vectorSearchScore"},
                }
            },
        ]
        rows = await asyncio.to_thread(lambda: list(collection.aggregate(pipeline)))

        hits: list[DocumentRetrievalHit] = []
        for row in rows:
            source_id = str(row.get("source_id", ""))
            snippet = str(row.get("snippet", "")).strip()
            if not source_id or not snippet:
                continue

            hits.append(
                DocumentRetrievalHit(
                    snippet=snippet,
                    score=(
                        float(row["similarity"])
                        if row.get("similarity") is not None
                        else None
                    ),
                    source=DocumentSourceReference(
                        source_id=source_id,
                        source_type=(
                            str(row["source_type"])
                            if row.get("source_type") is not None
                            else None
                        ),
                        source_uri=(
                            str(row["source_uri"])
                            if row.get("source_uri") is not None
                            else None
                        ),
                        title=(
                            str(row["title"]) if row.get("title") is not None else None
                        ),
                        chunk_id=(
                            str(row["chunk_id"])
                            if row.get("chunk_id") is not None
                            else None
                        ),
                        page=(
                            int(row["page"]) if row.get("page") is not None else None
                        ),
                    ),
                )
            )
        logger.info("Document RAG search returned %d hits", len(hits))
        return hits

    async def close(self) -> None:
        if self._client is not None:
            await asyncio.to_thread(self._client.close)
