"""Validation tests for Cosmos vCore document RAG settings."""

import pytest
from pydantic import ValidationError

from config import DocumentRagSettings


def test_rejects_invalid_cosmos_vector_index_kind() -> None:
    with pytest.raises(ValidationError, match="cosmos_vector_index_kind"):
        DocumentRagSettings(
            enabled=True, backend="cosmos", cosmos_vector_index_kind="flat"
        )


def test_rejects_invalid_cosmos_vector_similarity() -> None:
    with pytest.raises(ValidationError, match="cosmos_vector_similarity"):
        DocumentRagSettings(
            enabled=True, backend="cosmos", cosmos_vector_similarity="cosine"
        )


def test_accepts_valid_cosmos_vector_values() -> None:
    settings = DocumentRagSettings(
        enabled=True,
        backend="cosmos",
        cosmos_vector_index_kind="vector-hnsw",
        cosmos_vector_similarity="L2",
    )

    assert settings.cosmos_vector_index_kind == "vector-hnsw"
    assert settings.cosmos_vector_similarity == "L2"
