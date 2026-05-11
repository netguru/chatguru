"""Repository port (interface) for document retrieval."""

from typing import Protocol

from document_rag.models import DocumentRetrievalHit


class DocumentRagRepository(Protocol):
    """Port for retrieval-only document search."""

    async def connect(self) -> None:
        """Validate repository connectivity."""
        ...

    async def search(self, query: str, limit: int = 5) -> list[DocumentRetrievalHit]:
        """Search document snippets relevant to the query."""
        ...

    async def close(self) -> None:
        """Release repository resources."""
        ...
