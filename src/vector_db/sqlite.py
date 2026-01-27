"""SQLite implementation of VectorDatabase using sqlite-vec for semantic search."""

from typing import Any

import httpx

from config import get_logger
from vector_db.base import VectorDatabase

logger = get_logger("vector_db.sqlite")

DEFAULT_TIMEOUT = 30


class SQLiteVectorDatabase(VectorDatabase):
    """
    SQLite vector database client.

    Connects to the sqlite-vec powered database service via HTTP.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8001",
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        """
        Initialize the SQLite database client.

        Args:
            base_url: Base URL of the SQLite database service
            timeout: Request timeout in seconds
        """
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        logger.info("SQLiteVectorDatabase initialized: %s", self._base_url)

    async def search(
        self,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search using semantic similarity via sqlite-vec."""
        params: dict[str, str | int] = {"q": query, "limit": limit}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(f"{self._base_url}/search", params=params)
            response.raise_for_status()
            data = response.json()
            logger.info(
                "Search '%s' returned %d results", query, len(data.get("products", []))
            )
            products: list[dict[str, Any]] = data.get("products", [])
            return products

    async def get_product(self, product_id: str) -> dict[str, Any] | None:
        """Get a single product by ID."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(f"{self._base_url}/products/{product_id}")
            if response.status_code == httpx.codes.NOT_FOUND:
                return None
            response.raise_for_status()
            result: dict[str, Any] = response.json()
            return result

    async def is_healthy(self) -> bool:
        """Check if the database service is healthy."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self._base_url}/health")
                return response.status_code == httpx.codes.OK
        except httpx.HTTPError:
            return False

    async def count(self) -> int:
        """Get the total number of products in the database."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(f"{self._base_url}/count")
            response.raise_for_status()
            data = response.json()
            count: int = data.get("count", 0)
            return count
