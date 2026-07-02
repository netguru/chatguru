"""Shared factory for the OpenAI-compatible embeddings client.

Used across product RAG, document RAG and the vector stores. Base URL and key
fall back to the main LLM settings when the embeddings-specific ones are unset.
"""

from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from config import get_llm_settings


def build_embeddings() -> Embeddings:
    """Return an embeddings client for the configured endpoint."""
    settings = get_llm_settings()
    base_url = (settings.embeddings_api_base or settings.api_base).rstrip("/")
    api_key = settings.embeddings_api_key or settings.api_key
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=api_key,
        base_url=base_url or None,
        # Gateways such as Azure APIM authenticate via the `api-key` header.
        default_headers={"api-key": api_key},
    )
