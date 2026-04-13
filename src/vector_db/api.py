"""FastAPI service for vector database (SQLite or MongoDB)."""

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, Protocol

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vector_db.api")


class VectorStoreProtocol(Protocol):
    """Protocol for vector store implementations."""

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]: ...

    def get_product(self, product_id: str) -> dict[str, Any] | None: ...

    def count(self) -> int: ...

    def load_products(self, json_path: str | Path) -> int: ...

    def is_healthy(self) -> bool: ...


# Global store instance
_store: VectorStoreProtocol | None = None


def get_store() -> VectorStoreProtocol:
    """Get the global store instance."""
    if _store is None:
        msg = "VectorStore not initialized"
        raise RuntimeError(msg)
    return _store


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    product_count: int


class CountResponse(BaseModel):
    """Count response."""

    count: int


class ProductResponse(BaseModel):
    """Single product response."""

    id: str
    name: str
    category: str
    brand: str
    price: float
    description: str
    sizes: list[str]
    colors: list[str]
    material: str
    care_instructions: str
    in_stock: bool


class SearchResultProduct(ProductResponse):
    """Product with optional similarity score from search."""

    similarity: float | None = None


class SearchResponse(BaseModel):
    """Search results response."""

    products: list[SearchResultProduct]
    total: int
    query: str


def _create_store() -> VectorStoreProtocol:
    """Create the appropriate store based on VECTOR_STORE_TYPE env var."""
    store_type = os.getenv("VECTOR_STORE_TYPE", "sqlite").lower()

    if store_type == "mongodb":
        from vector_db.mongodb_store import MongoVectorStore  # noqa: PLC0415

        store: VectorStoreProtocol = MongoVectorStore()
        return store

    # Default to SQLite — same default file as chat persistence (see env.example)
    from vector_db.store import VectorStore  # noqa: PLC0415

    db_path = os.getenv("VECTOR_SQLITE_DB_PATH", "/data/chatguru.db")
    sqlite_store: VectorStoreProtocol = VectorStore(db_path=db_path)
    return sqlite_store


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize vector store on startup."""
    global _store  # noqa: PLW0603
    store_type = os.getenv("VECTOR_STORE_TYPE", "sqlite").lower()
    logger.info("Starting vector database service (type: %s)...", store_type)

    # Initialize store
    _store = _create_store()

    # Load products if not already loaded
    products_path = Path("/app/data/products.json")
    if products_path.exists():
        count = _store.load_products(products_path)
        if count > 0:
            logger.info("Loaded %d products", count)
        else:
            logger.info("Products already loaded: %d total", _store.count())
    else:
        logger.warning("Products file not found: %s", products_path)

    yield

    logger.info("Shutting down vector database service...")


app = FastAPI(
    title="Vector Database",
    description="Semantic search API (SQLite-vec or MongoDB)",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> HealthResponse:
    """Health check endpoint."""
    store = get_store()
    # Check health for MongoDB, SQLite store doesn't have is_healthy
    if hasattr(store, "is_healthy") and not store.is_healthy():
        raise HTTPException(status_code=503, detail="Database connection unhealthy")
    return HealthResponse(status="healthy", product_count=store.count())


@app.get("/count")
def count() -> CountResponse:
    """Get total product count."""
    store = get_store()
    return CountResponse(count=store.count())


@app.get("/search")
def search(
    q: Annotated[str, Query(description="Search query")],
    limit: Annotated[int, Query(ge=1, le=50, description="Max results")] = 10,
) -> SearchResponse:
    """Semantic search."""
    store = get_store()
    products = store.search(query=q, limit=limit)
    return SearchResponse(
        products=[SearchResultProduct(**p) for p in products],
        total=len(products),
        query=q,
    )


@app.get("/products/{product_id}", response_model=ProductResponse | None)
def get_product(product_id: str) -> Any:
    """Get a single product by ID."""
    store = get_store()
    product = store.get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
