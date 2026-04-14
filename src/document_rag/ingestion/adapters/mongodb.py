"""MongoDB ingestion adapter for document RAG chunks."""

import contextlib
from typing import Any

from gridfs import GridFSBucket
from gridfs.errors import NoFile
from pymongo import MongoClient, errors
from pymongo.operations import SearchIndexModel, UpdateOne

from config import DocumentRagSettings
from document_rag.models import DocumentChunk, DocumentSourceFile


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

    def ensure_ready(self, *, embedding_dimensions: int) -> None:
        namespace_not_found = 26
        with self._mongo_client() as client:
            collection = self._collection(client)
            try:
                existing = list(collection.list_search_indexes())
            except errors.OperationFailure as exc:
                if exc.code != namespace_not_found:  # NamespaceNotFound
                    raise
                # Collection may not exist yet on a fresh deployment.
                # It will be created by the first upsert operation.
                return
            if any(
                idx.get("name") == self._settings.mongodb_index_name for idx in existing
            ):
                return

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
                name=self._settings.mongodb_index_name,
                type="vectorSearch",
            )
            collection.create_search_index(model=model)

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
