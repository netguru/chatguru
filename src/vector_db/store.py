"""Vector store with sqlite-vec for semantic search."""

import json
import sqlite3
import struct
from pathlib import Path
from typing import Any

import sqlite_vec
from langchain_openai import OpenAIEmbeddings

from config import get_llm_settings, get_logger

logger = get_logger("vector_db.store")

EMBEDDING_DIM = 1536


def _serialize_embedding(embedding: list[float]) -> bytes:
    """Serialize embedding list to bytes for sqlite-vec."""
    return struct.pack(f"{len(embedding)}f", *embedding)


class VectorStore:
    """
    Vector store with semantic search using sqlite-vec.

    Stores data in SQLite, generates embeddings via the configured OpenAI-compatible
    endpoint, and performs vector similarity search with sqlite-vec.
    """

    def __init__(self, db_path: str = "data/chatguru.db") -> None:
        """
        Initialize the vector store.

        Args:
            db_path: Path to SQLite database file
        """
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize embeddings model
        llm_settings = get_llm_settings()
        embeddings_base_url = llm_settings.embeddings_endpoint or llm_settings.endpoint
        embeddings_api_key = llm_settings.embeddings_api_key or llm_settings.api_key
        self._embeddings = OpenAIEmbeddings(
            model=llm_settings.embedding_deployment_name,
            api_key=embeddings_api_key,
            base_url=embeddings_base_url.rstrip("/"),
            default_headers={"api-key": embeddings_api_key},
        )

        # Setup database
        self._setup_database()
        logger.info("VectorStore initialized: %s", self._db_path)

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with sqlite-vec loaded."""
        conn = sqlite3.connect(str(self._db_path))
        conn.enable_load_extension(True)  # noqa: FBT003
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)  # noqa: FBT003
        return conn

    def _setup_database(self) -> None:
        """Create tables if they don't exist."""
        conn = self._get_connection()
        try:
            # Products table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS products (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    category TEXT,
                    brand TEXT,
                    price REAL,
                    description TEXT,
                    sizes TEXT,
                    colors TEXT,
                    material TEXT,
                    care_instructions TEXT,
                    in_stock INTEGER DEFAULT 1
                )
            """
            )

            # Vector embeddings table using sqlite-vec
            conn.execute(
                f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS product_embeddings USING vec0(
                    product_id TEXT PRIMARY KEY,
                    embedding FLOAT[{EMBEDDING_DIM}]
                )
            """
            )

            conn.commit()
            logger.info("Database tables created")
        finally:
            conn.close()

    def load_products(self, json_path: str | Path) -> int:
        """
        Load products from JSON file into database.

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

        conn = self._get_connection()
        try:
            # Check if already loaded
            cursor = conn.execute("SELECT COUNT(*) FROM products")
            existing = cursor.fetchone()[0]
            if existing > 0:
                logger.info("Database already has %d products, skipping load", existing)
                return 0

            # Insert products
            for product in products:
                conn.execute(
                    """
                    INSERT INTO products (id, name, category, brand, price, description,
                                         sizes, colors, material, care_instructions, in_stock)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(product["id"]),
                        product["name"],
                        product.get("category", ""),
                        product.get("brand", ""),
                        product.get("price", 0.0),
                        product.get("description", ""),
                        json.dumps(product.get("sizes", [])),
                        json.dumps(product.get("colors", [])),
                        product.get("material", ""),
                        product.get("care_instructions", ""),
                        1 if product.get("in_stock", True) else 0,
                    ),
                )

            conn.commit()
            logger.info("Loaded %d products into database", len(products))

            # Generate and store embeddings
            self._generate_embeddings(conn, products)

            return len(products)
        finally:
            conn.close()

    def _generate_embeddings(
        self, conn: sqlite3.Connection, products: list[dict[str, Any]]
    ) -> None:
        """Generate embeddings for all products and store them."""
        logger.info("Generating embeddings for %d products...", len(products))

        # Create searchable text for each product
        texts = [
            f"{p['name']} {p.get('category', '')} {p.get('brand', '')} "
            f"{p.get('description', '')} {' '.join(p.get('colors', []))}"
            for p in products
        ]

        # Generate embeddings in batches
        batch_size = 100
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i : i + batch_size]
            batch_products = products[i : i + batch_size]

            embeddings = self._embeddings.embed_documents(batch_texts)

            for product, embedding in zip(batch_products, embeddings, strict=True):
                conn.execute(
                    "INSERT INTO product_embeddings (product_id, embedding) VALUES (?, ?)",
                    (str(product["id"]), _serialize_embedding(embedding)),
                )

            conn.commit()
            logger.info("Generated embeddings for batch %d-%d", i, i + len(batch_texts))

        logger.info("Embeddings generation complete")

    def search(
        self,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Search using semantic similarity.

        Args:
            query: Search query (natural language)
            limit: Maximum results to return

        Returns:
            List of matching results with similarity scores
        """
        # Generate query embedding
        query_embedding = self._embeddings.embed_query(query)
        query_bytes = _serialize_embedding(query_embedding)

        conn = self._get_connection()
        try:
            # Vector similarity search with optional filters
            sql = """
                SELECT p.*, e.distance
                FROM product_embeddings e
                JOIN products p ON e.product_id = p.id
                WHERE e.embedding MATCH ?
                  AND k = ?
            """
            params: list[Any] = [query_bytes, limit * 3]  # Get more for filtering

            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()

            # Get column names
            columns = [desc[0] for desc in cursor.description]

            # Convert to dicts and apply filters
            results = []
            for row in rows:
                product = dict(zip(columns, row, strict=True))
                product["sizes"] = (
                    json.loads(product["sizes"]) if product["sizes"] else []
                )
                product["colors"] = (
                    json.loads(product["colors"]) if product["colors"] else []
                )
                product["in_stock"] = bool(product["in_stock"])

                results.append(product)
                if len(results) >= limit:
                    break

            logger.info("Search '%s' returned %d results", query, len(results))
            return results
        finally:
            conn.close()

    def get_product(self, product_id: str) -> dict[str, Any] | None:
        """Get a single product by ID."""
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,))
            row = cursor.fetchone()
            if not row:
                return None

            columns = [desc[0] for desc in cursor.description]
            product = dict(zip(columns, row, strict=True))
            product["sizes"] = json.loads(product["sizes"]) if product["sizes"] else []
            product["colors"] = (
                json.loads(product["colors"]) if product["colors"] else []
            )
            product["in_stock"] = bool(product["in_stock"])
            return product
        finally:
            conn.close()

    def count(self) -> int:
        """Get the total number of products in the database."""
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM products")
            result: int = cursor.fetchone()[0]
            return result
        finally:
            conn.close()
