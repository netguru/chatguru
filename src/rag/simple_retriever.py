"""In-memory product retriever using semantic search."""

import json
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings

from config import get_llm_settings, get_logger
from rag.documents import ProductData, create_product_document

logger = get_logger("rag.simple_retriever")


class SimpleProductRetriever:
    """
    Product retriever using semantic search.

    Converts products into semantic vectors via the configured embeddings model,
    then performs similarity search using LangChain's InMemoryVectorStore.
    """

    def __init__(self, documents: list[Document], k: int = 5) -> None:
        """
        Initialize retriever with documents.

        Args:
            documents: List of product documents
            k: Number of results to return
        """
        self.k = k
        llm_settings = get_llm_settings()
        embeddings_base_url = llm_settings.embeddings_endpoint or llm_settings.endpoint
        embeddings_api_key = llm_settings.embeddings_api_key or llm_settings.api_key
        embeddings = OpenAIEmbeddings(
            model=llm_settings.embedding_deployment_name,
            api_key=embeddings_api_key,
            base_url=embeddings_base_url.rstrip("/"),
            default_headers={"api-key": embeddings_api_key},
        )

        # Create in-memory vector store from documents
        self._vectorstore = InMemoryVectorStore.from_documents(documents, embeddings)
        logger.info("Initialized semantic retriever with %d products", len(documents))

    def invoke(self, query: str) -> list[Document]:
        """
        Retrieve relevant documents synchronously using semantic similarity.

        Args:
            query: Search query

        Returns:
            List of relevant documents
        """
        results = self._vectorstore.similarity_search(query, k=self.k)
        logger.info("Retrieved %d products for query: '%s'", len(results), query)
        return results

    async def ainvoke(self, query: str) -> list[Document]:
        """
        Retrieve relevant documents asynchronously using semantic similarity.

        Args:
            query: Search query

        Returns:
            List of relevant documents
        """
        results = await self._vectorstore.asimilarity_search(query, k=self.k)
        logger.info("Retrieved %d products for query: '%s'", len(results), query)
        return results

    @classmethod
    def from_documents(
        cls,
        documents: list[Document],
        **kwargs: Any,
    ) -> "SimpleProductRetriever":
        """
        Create a retriever from a list of documents.

        Args:
            documents: List of documents to add
            **kwargs: Additional arguments (k, etc.)

        Returns:
            Configured retriever instance
        """
        return cls(documents, **kwargs)

    @classmethod
    def from_json_file(
        cls,
        json_path: str | Path,
        **kwargs: Any,
    ) -> "SimpleProductRetriever":
        """
        Create a retriever from a products JSON file.

        Args:
            json_path: Path to products.json file
            **kwargs: Additional arguments (k, etc.)

        Returns:
            Configured retriever instance with loaded products
        """
        path = Path(json_path)

        if not path.exists():
            msg = f"Products file not found: {path}"
            raise FileNotFoundError(msg)

        with path.open("r", encoding="utf-8") as f:
            products: list[ProductData] = json.load(f)

        documents = [create_product_document(product) for product in products]
        retriever = cls.from_documents(documents, **kwargs)

        logger.info("Loaded %d products from %s", len(products), path)
        return retriever

    def get_product_count(self) -> int:
        """Get product count from vector store."""
        # InMemoryVectorStore stores documents in a dict keyed by ID
        return len(self._vectorstore.store)
