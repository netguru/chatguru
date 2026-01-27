"""Pytest configuration and fixtures."""

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app


@pytest.fixture(scope="session")
def test_env_vars() -> Iterator[dict[str, str]]:
    """Set up test environment variables."""
    test_vars = {
        "LLM_ENDPOINT": "https://test.openai.azure.com/",
        "LLM_API_KEY": "test-api-key",
        "LLM_DEPLOYMENT_NAME": "gpt-4",
        "LLM_API_VERSION": "2024-02-15-preview",
        "DEBUG": "true",
    }

    for key, value in test_vars.items():
        os.environ[key] = value

    yield test_vars

    # Cleanup
    for key in test_vars:
        os.environ.pop(key, None)


@pytest.fixture
def app(test_env_vars: dict[str, str]) -> TestClient:
    """Create test FastAPI application."""
    return TestClient(create_app())


@pytest.fixture
def async_app(test_env_vars: dict[str, str]) -> TestClient:
    """Create test client for WebSocket testing."""
    return TestClient(create_app())
