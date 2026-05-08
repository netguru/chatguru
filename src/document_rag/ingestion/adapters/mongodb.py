"""MongoDB ingestion adapter for document RAG chunks."""

import contextlib
import logging
import time
from typing import Any

from gridfs import GridFSBucket
from gridfs.errors import NoFile
from pymongo import MongoClient, errors
from pymongo.operations import SearchIndexModel, UpdateOne

from config import DocumentRagSettings
from document_rag.models import DocumentChunk, DocumentSourceFile

logger = logging.getLogger(__name__)


class MongoDocumentRagIngestionRepository:
    """MongoDB-backed ingestion adapter for document chunks."""

    def __init__(self, settings: DocumentRagSettings) -> None:
        self._settings = settings

    def prepare_target(self) -> None:
        """Validate Mongo connectivity and ensure collection exists."""
        with self._mongo_client() as client:
            client.admin.command("ping")
            database = client[self._settings.mongodb_database]
            collection_name = self._settings.mongodb_collection
            if collection_name not in database.list_collection_names():
                with contextlib.suppress(errors.CollectionInvalid):
                    database.create_collection(collection_name)

    def reset_all(self) -> None:
        """Fully replace mode: remove all chunks and all GridFS source files."""
        with self._mongo_client() as client:
            database = client[self._settings.mongodb_database]

            database[self._settings.mongodb_collection].delete_many({})

            files_collection = database[f"{self._settings.mongodb_files_bucket}.files"]
            chunks_collection = database[
                f"{self._settings.mongodb_files_bucket}.chunks"
            ]
            files_collection.delete_many({})
            chunks_collection.delete_many({})

    def ensure_ready(
        self, *, embedding_dimensions: int, timeout_seconds: int = 120
    ) -> None:
        """Create the vector search index if absent, then wait until it is READY."""
        namespace_not_found = 26
        index_name = self._settings.mongodb_index_name
        last_status = "missing"

        with self._mongo_client() as client:
            collection = self._collection(client)
            try:
                existing = list(collection.list_search_indexes())
            except errors.OperationFailure as exc:
                if exc.code != namespace_not_found:  # NamespaceNotFound
                    raise
                existing = []

            if not any(idx.get("name") == index_name for idx in existing):
                model = SearchIndexModel(
                    definition={
                        "fields": [
                            {
                                "type": "vector",
                                "path": "embedding",
                                "numDimensions": embedding_dimensions,
                                "similarity": "cosine",
                            },
                            {"type": "filter", "path": "source_id"},
                            {"type": "filter", "path": "source_type"},
                        ]
                    },
                    name=index_name,
                    type="vectorSearch",
                )
                collection.create_search_index(model=model)
                logger.info(
                    "Created vector search index '%s', waiting for READY ...",
                    index_name,
                )

            # Poll until READY — index build is async in MongoDB Atlas Local.
            deadline = time.monotonic() + timeout_seconds
            while time.monotonic() < deadline:
                indexes = list(collection.list_search_indexes())
                for idx in indexes:
                    if idx.get("name") == index_name:
                        last_status = idx.get("status", "") or "unknown"
                        if last_status == "READY":
                            logger.info(
                                "Vector search index '%s' is READY.", index_name
                            )
                            return
                        logger.info(
                            "Index '%s' status: %s — waiting ...",
                            index_name,
                            last_status,
                        )
                        break
                time.sleep(5)

            msg = f"Index '{index_name}' did not reach READY within {timeout_seconds}s (last status: {last_status})."
            logger.warning(
                msg,
            )
            raise TimeoutError(
                msg
            )

    def upsert_chunks(self, chunks: list[DocumentChunk]) -> int:
        operations = [
            UpdateOne(
                {"chunk_id": chunk.chunk_id},
                {
                    "$set": {
                        "id": chunk.chunk_id,
                        "source_id": chunk.source_id,
                        "source_uri": chunk.source_uri,
                        "source_type": chunk.source_type,
                        "title": chunk.title,
                        "chunk_id": chunk.chunk_id,
                        "snippet": chunk.snippet,
                        "content": chunk.content,
                        "embedding": chunk.embedding,
                        "page": chunk.page,
                    }
                },
                upsert=True,
            )
            for chunk in chunks
        ]
        if not operations:
            return 0

        with self._mongo_client() as client:
            result = self._collection(client).bulk_write(operations, ordered=False)
        return int(result.upserted_count + result.modified_count)

    def upsert_source_files(self, files: list[DocumentSourceFile]) -> int:
        if not files:
            return 0

        changed = 0
        with self._mongo_client() as client:
            database = client[self._settings.mongodb_database]
            bucket = GridFSBucket(
                database, bucket_name=self._settings.mongodb_files_bucket
            )

            for file in files:
                for existing in database[
                    f"{self._settings.mongodb_files_bucket}.files"
                ].find({"filename": file.source_uri}):
                    bucket.delete(existing["_id"])

                metadata = {
                    "source_id": file.source_id,
                    "source_uri": file.source_uri,
                    "source_type": file.source_type,
                    "title": file.title,
                    "content_type": file.content_type,
                }
                bucket.upload_from_stream(
                    file.source_uri,
                    file.content_bytes,
                    metadata=metadata,
                )
                changed += 1
        return changed

    def get_source_file(self, source_uri: str) -> tuple[bytes, dict[str, Any]]:
        with self._mongo_client() as client:
            database = client[self._settings.mongodb_database]
            bucket = GridFSBucket(
                database, bucket_name=self._settings.mongodb_files_bucket
            )
            try:
                stream = bucket.open_download_stream_by_name(source_uri)
            except NoFile as exc:
                msg = f"Document source not found: {source_uri}"
                raise FileNotFoundError(msg) from exc

            with stream:
                metadata = dict(stream.metadata or {})
                return stream.read(), metadata

    def _mongo_client(self) -> MongoClient[dict[str, Any]]:
        return MongoClient(
            self._settings.mongodb_uri,
            serverSelectionTimeoutMS=self._settings.mongodb_connection_timeout_ms,
            connectTimeoutMS=self._settings.mongodb_connection_timeout_ms,
        )

    def _collection(self, client: MongoClient[dict[str, Any]]) -> Any:
        return client[self._settings.mongodb_database][
            self._settings.mongodb_collection
        ]
