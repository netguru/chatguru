"""Embedding provider abstraction for document RAG."""

import importlib
from typing import Any, Protocol, cast

from config import DocumentRagSettings
from embeddings import build_embeddings


class DocumentEmbeddingProvider(Protocol):
    """Contract for query embedding providers."""

    def embed_query(self, text: str, **kwargs: Any) -> list[float]:
        """Return embedding vector for a query string."""
        ...


def _resolve_custom_embedding_provider(class_path: str) -> DocumentEmbeddingProvider:
    module_path, separator, class_name = class_path.partition(":")
    if not separator or not module_path or not class_name:
        msg = (
            "DOCUMENT_RAG_EMBEDDING_CUSTOM_CLASS must be in the format "
            "'module.path:ClassName'"
        )
        raise ValueError(msg)

    module = importlib.import_module(module_path)
    provider_cls = getattr(module, class_name)
    provider = provider_cls()
    embed_query = getattr(provider, "embed_query", None)
    if embed_query is None or not callable(embed_query):
        msg = "Custom embedding provider must define: embed_query(query: str) -> list[float]"
        raise ValueError(msg)
    return cast(DocumentEmbeddingProvider, provider)


def build_document_embedding_provider(
    settings: DocumentRagSettings,
) -> DocumentEmbeddingProvider:
    """Build configured embedding provider for document retrieval."""
    provider = settings.embedding_provider.lower().strip()
    if provider == "openai":
        return cast(DocumentEmbeddingProvider, build_embeddings())
    if provider == "custom":
        if not settings.embedding_custom_class.strip():
            msg = (
                "DOCUMENT_RAG_EMBEDDING_CUSTOM_CLASS must be set when "
                "DOCUMENT_RAG_EMBEDDING_PROVIDER=custom"
            )
            raise ValueError(msg)
        return _resolve_custom_embedding_provider(
            settings.embedding_custom_class.strip()
        )

    msg = "Unsupported DOCUMENT_RAG_EMBEDDING_PROVIDER. Use: openai or custom"
    raise ValueError(msg)
