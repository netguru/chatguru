"""Abstract base class for vector database implementations."""

from abc import ABC, abstractmethod
from typing import Any


class VectorDatabase(ABC):
    """
    Abstract interface for vector database.

    Implementations:
    - SQLiteVectorDatabase: Uses sqlite-vec for semantic search
    - MongoDBVectorDatabase: Uses local MongoDB with embeddings
    """

    @abstractmethod
    async def search(
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
            List of matching results
        """

    @abstractmethod
    async def get_product(self, product_id: str) -> dict[str, Any] | None:
        """Get a single product by ID."""

    @abstractmethod
    async def is_healthy(self) -> bool:
        """Check if the database connection is healthy."""

    @abstractmethod
    async def count(self) -> int:
        """
        Get the total number of items in the database.

        Returns:
            Total count of items
        """

    @staticmethod
    def format_products(products: list[dict[str, Any]]) -> str:
        """Format products for agent response."""
        if not products:
            return "No products found matching your criteria."

        formatted = []
        for p in products:
            sizes = p.get("sizes", [])
            colors = p.get("colors", [])
            url = p.get("url")
            block = f"""
**{p['name']}**
- Category: {p.get('category', 'N/A')}
- Brand: {p.get('brand', 'N/A')}
- Price: ${p.get('price', 0):.2f}
- Description: {p.get('description', 'N/A')}
- Sizes: {', '.join(sizes) if sizes else 'N/A'}
- Colors: {', '.join(colors) if colors else 'N/A'}
- Material: {p.get('material', 'N/A')}
- Status: {'In Stock' if p.get('in_stock', True) else 'Out of Stock'}
""".strip()
            # Canonical, prompt-keyed URL line. Keep this format in sync with
            # `src/rag/documents.py::create_product_document` and the prompt's
            # "URL:" signal in `src/agent/prompt.py`.
            if url:
                block = f"{block}\nURL: {url}"
            formatted.append(block)

        return f"Found {len(products)} product(s):\n\n" + "\n\n---\n\n".join(formatted)
