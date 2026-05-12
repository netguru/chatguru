"""Embedding provider abstraction for document RAG."""

import importlib
from typing import Any, Protocol, cast

from langchain_openai import OpenAIEmbeddings

from config import DocumentRagSettings, get_llm_settings


class DocumentEmbeddingProvider(Protocol):
    """Contract for query embedding providers."""

    def embed_query(self, text: str, **kwargs: Any) -> list[float]:
        """Return embedding vector for a query string."""
        ...


def _build_openai_embeddings() -> OpenAIEmbeddings:
    llm_settings = get_llm_settings()
    embeddings_base_url = llm_settings.embeddings_endpoint or llm_settings.endpoint
    embeddings_api_key = llm_settings.embeddings_api_key or llm_settings.api_key
    return OpenAIEmbeddings(
        model=llm_settings.embedding_deployment_name,
        api_key=embeddings_api_key,
        base_url=embeddings_base_url.rstrip("/"),
        default_headers={"api-key": embeddings_api_key},
    )


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
        return cast(DocumentEmbeddingProvider, _build_openai_embeddings())
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
