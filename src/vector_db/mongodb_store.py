"""MongoDB Vector Store for semantic search using MongoDB Vector Search."""

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from langchain_openai import OpenAIEmbeddings
from pymongo import MongoClient, errors
from pymongo.operations import SearchIndexModel

from config import get_llm_settings, get_logger, get_vector_db_settings

if TYPE_CHECKING:
    from pymongo.collection import Collection

logger = get_logger("vector_db.mongodb_store")

# Vector search index configuration
VECTOR_INDEX_NAME = "vector_index"
EMBEDDING_DIMENSIONS = 1536  # Azure OpenAI text-embedding-3-small


class MongoVectorStore:
    """
    Vector store with semantic search using MongoDB Vector Search.

    1. Stores product data and embeddings in MongoDB
    2. Generates embeddings via Azure OpenAI
    3. Uses native $vectorSearch for efficient similarity search
    """

    def __init__(
        self,
        mongodb_uri: str | None = None,
        database_name: str | None = None,
        collection_name: str | None = None,
        *,
        connection_timeout_ms: int = 5000,
    ) -> None:
        """
        Initialize the MongoDB vector store.

        Args:
            mongodb_uri: MongoDB connection URI (defaults to settings)
            database_name: MongoDB database name (defaults to settings)
            collection_name: MongoDB collection name (defaults to settings)
            connection_timeout_ms: Timeout for initial connection validation (default: 5000ms)

        Raises:
            ConnectionError: If unable to connect to MongoDB
            ValueError: If configuration is invalid
        """
        settings = get_vector_db_settings()
        llm_settings = get_llm_settings()

        self._mongodb_uri = mongodb_uri or settings.mongodb_uri
        self._database_name = database_name or settings.mongodb_database
        self._collection_name = collection_name or settings.mongodb_collection

        # Validate configuration
        if not self._mongodb_uri:
            msg = "MongoDB URI is required"
            raise ValueError(msg)
        if not self._database_name:
            msg = "MongoDB database name is required"
            raise ValueError(msg)
        if not self._collection_name:
            msg = "MongoDB collection name is required"
            raise ValueError(msg)

        # Initialize MongoDB client with timeout settings
        self._client: MongoClient[dict[str, Any]] = MongoClient(
            self._mongodb_uri,
            serverSelectionTimeoutMS=connection_timeout_ms,
            connectTimeoutMS=connection_timeout_ms,
        )

        # Validate connection by pinging the server
        try:
            self._client.admin.command("ping")
        except errors.ConnectionFailure as e:
            msg = f"Failed to connect to MongoDB at {self._mongodb_uri}: {e}"
            raise ConnectionError(msg) from e
        except errors.ServerSelectionTimeoutError as e:
            msg = f"MongoDB server not available at {self._mongodb_uri}: {e}"
            raise ConnectionError(msg) from e

        self._collection: Collection[dict[str, Any]] = self._client[
            self._database_name
        ][self._collection_name]

        # Initialize embeddings model
        # Resolution order: OPENAI_EMBEDDINGS_ENDPOINT → OPENAI_ENDPOINT → LLM_OPENAI_BASE_URL
        # The last fallback covers setups where only the APIM base URL is configured.
        embeddings_base_url = (
            llm_settings.embeddings_endpoint
            or llm_settings.endpoint
            or llm_settings.openai_base_url
        )
        embeddings_api_key = llm_settings.embeddings_api_key or llm_settings.api_key
        self._embeddings = OpenAIEmbeddings(
            model=llm_settings.embedding_deployment_name,
            api_key=embeddings_api_key,
            base_url=embeddings_base_url.rstrip("/"),
            default_headers={"api-key": embeddings_api_key},
        )

        logger.info(
            "MongoVectorStore initialized: %s/%s",
            self._database_name,
            self._collection_name,
        )

    def _create_vector_index(self) -> None:
        """
        Create a vector search index on the embedding field.

        Uses MongoDB's native vector search index for efficient similarity search.
        """
        # Check if index already exists
        existing_indexes = list(self._collection.list_search_indexes())
        for idx in existing_indexes:
            if idx.get("name") == VECTOR_INDEX_NAME:
                logger.info(
                    "Vector search index '%s' already exists", VECTOR_INDEX_NAME
                )
                return

        # Create the vector search index
        search_index_model = SearchIndexModel(
            definition={
                "fields": [
                    {
                        "type": "vector",
                        "path": "embedding",
                        "numDimensions": EMBEDDING_DIMENSIONS,
                        "similarity": "cosine",
                    },
                    # Add filter fields for pre-filtering
                    {"type": "filter", "path": "category"},
                    {"type": "filter", "path": "brand"},
                    {"type": "filter", "path": "in_stock"},
                ]
            },
            name=VECTOR_INDEX_NAME,
            type="vectorSearch",
        )

        self._collection.create_search_index(model=search_index_model)
        logger.info("Created vector search index '%s'", VECTOR_INDEX_NAME)

    def load_products(self, json_path: str | Path) -> int:
        """
        Load products from JSON file into MongoDB.

        Args:
            json_path: Path to products.json file

        Returns:
            Number of products loaded
        """
        path = Path(json_path)
        if not path.exists():
            msg = f"Products file not found: {path}"
            raise FileNotFoundError(msg)

        with path.open("r", encoding="utf-8") as f:
            products: list[dict[str, Any]] = json.load(f)

        # Check if already loaded
        existing = self._collection.count_documents({})
        if existing > 0:
            logger.info("Database already has %d products, skipping load", existing)
            return 0

        # Insert products with embeddings
        logger.info("Loading %d products into MongoDB...", len(products))

        # Batch generate embeddings for efficiency
        texts = [
            f"{p['name']} {p.get('category', '')} "
            f"{p.get('brand', '')} {p.get('description', '')} "
            f"{' '.join(p.get('colors', []))}"
            for p in products
        ]
        embeddings = self._embeddings.embed_documents(texts)

        docs = []
        for product, embedding in zip(products, embeddings, strict=True):
            doc = {
                "id": str(product["id"]),
                "name": product["name"],
                "category": product.get("category", ""),
                "brand": product.get("brand", ""),
                "price": product.get("price", 0.0),
                "description": product.get("description", ""),
                "sizes": product.get("sizes", []),
                "colors": product.get("colors", []),
                "material": product.get("material", ""),
                "care_instructions": product.get("care_instructions", ""),
                "in_stock": product.get("in_stock", True),
                "embedding": embedding,
            }
            docs.append(doc)

        self._collection.insert_many(docs)
        logger.info("Loaded %d products into MongoDB", len(products))

        # Create vector search index after loading data
        self._create_vector_index()

        return len(products)

    def search(
        self,
        query: str,
        limit: int = 10,
        num_candidates: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Search using MongoDB's native $vectorSearch.

        Uses the vector search index for efficient ANN (Approximate Nearest Neighbor)
        search. Requires MongoDB Atlas or Enterprise with vector search support.

        Args:
            query: Search query (natural language)
            limit: Maximum results to return
            num_candidates: Number of candidates to consider (higher = more accurate but slower)

        Returns:
            List of matching results sorted by similarity
        """
        query_embedding = self._embeddings.embed_query(query)
        return self._vector_search(query_embedding, limit, num_candidates)

    def _vector_search(
        self,
        query_embedding: list[float],
        limit: int,
        num_candidates: int,
    ) -> list[dict[str, Any]]:
        """
        Perform native MongoDB vector search using $vectorSearch aggregation.

        Args:
            query_embedding: Query vector
            limit: Maximum results to return
            num_candidates: Number of candidates for ANN search

        Returns:
            List of matching results with similarity scores
        """
        pipeline: list[dict[str, Any]] = [
            {
                "$vectorSearch": {
                    "index": VECTOR_INDEX_NAME,
                    "path": "embedding",
                    "queryVector": query_embedding,
                    "numCandidates": num_candidates,
                    "limit": limit,
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "embedding": 0,
                    "similarity": {"$meta": "vectorSearchScore"},
                }
            },
        ]

        results = list(self._collection.aggregate(pipeline))
        logger.info("Vector search returned %d results", len(results))
        return results

    def get_product(self, product_id: str) -> dict[str, Any] | None:
        """Get a single product by ID."""
        doc = self._collection.find_one({"id": product_id})
        if not doc:
            return None

        # Remove MongoDB internal fields and embedding
        doc.pop("_id", None)
        doc.pop("embedding", None)
        return dict(doc)

    def is_healthy(self) -> bool:
        """Check if the MongoDB connection is healthy."""
        try:
            self._client.admin.command("ping")
        except errors.PyMongoError:
            return False
        return True

    def count(self) -> int:
        """Get the total number of products in the database."""
        return self._collection.count_documents({})
