"""Pytest configuration and fixtures."""

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine.url import URL

from config import (
    get_docling_settings,
    get_document_rag_settings,
    get_persistence_settings,
    get_rate_limit_settings,
)
from api.main import create_app
from persistence import upgrade_head


@pytest.fixture(scope="session")
def test_env_vars(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, str]]:
    """Set up test environment variables."""
    get_docling_settings.cache_clear()
    get_document_rag_settings.cache_clear()
    get_persistence_settings.cache_clear()
    get_rate_limit_settings.cache_clear()
    persist_dir = tmp_path_factory.mktemp("persistence")
    db_file = persist_dir / "chat_history.db"
    database_url = str(URL.create("sqlite+aiosqlite", database=str(db_file.resolve())))
    test_vars = {
        "OPENAI_ENDPOINT": "https://test.openai.azure.com/v1",
        "LLM_API_KEY": "test-api-key",
        "LLM_DEPLOYMENT_NAME": "gpt-4",
        "DEBUG": "true",
        "PERSISTENCE_DATABASE_URL": database_url,
        "DOCUMENT_RAG_ENABLED": "false",
        # Disable Redis-backed rate limiting in all tests — no Redis is available
        # in CI or local test runs without a running Redis instance.
        "RATE_LIMIT_ENABLED": "false",
    }

    for key, value in test_vars.items():
        os.environ[key] = value

    upgrade_head()

    yield test_vars

    # Cleanup
    for key in test_vars:
        os.environ.pop(key, None)
    get_docling_settings.cache_clear()
    get_document_rag_settings.cache_clear()
    get_persistence_settings.cache_clear()
    get_rate_limit_settings.cache_clear()


@pytest.fixture
def app(test_env_vars: dict[str, str]) -> Iterator[TestClient]:
    """Create test FastAPI application (lifespan runs so persistence is initialized)."""
    with TestClient(create_app()) as client:
        yield client


@pytest.fixture
def async_app(test_env_vars: dict[str, str]) -> Iterator[TestClient]:
    """Create test client for WebSocket testing."""
    with TestClient(create_app()) as client:
        yield client
