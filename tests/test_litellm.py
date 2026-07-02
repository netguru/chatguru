"""Tests for the LiteLLM provider integration."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from config import (
    LiteLLMModelsConfig,
    LiteLLMModel,
    LiteLLMProvider,
    get_litellm_models_config,
    get_llm_provider,
    get_llm_settings,
)


@pytest.fixture
def models_config_file(tmp_path: Path) -> Path:
    """Write a valid models config JSON file and return its path."""
    config = {
        "providers": [
            {
                "name": "Anthropic",
                "models": [
                    {
                        "label": "Sonnet 3.5",
                        "id": "anthropic/claude-3-5-sonnet-20241022",
                    }
                ],
            },
            {
                "name": "OpenAI",
                "models": [{"label": "GPT-4o", "id": "gpt-4o"}],
            },
        ]
    }
    path = tmp_path / "models.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def _clear_caches() -> None:
    get_llm_settings.cache_clear()
    get_litellm_models_config.cache_clear()


def test_provider_resolves_explicit_litellm(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM_PROVIDER=litellm is honoured verbatim."""
    monkeypatch.setenv("LLM_PROVIDER", "litellm")
    _clear_caches()
    try:
        assert get_llm_provider() == "litellm"
    finally:
        _clear_caches()


def test_provider_auto_detects_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no explicit provider and a base URL set, resolves to openai."""
    # Set empty (not delenv) so a project .env value can't leak in.
    monkeypatch.setenv("LLM_PROVIDER", "")
    monkeypatch.setenv("LLM_OPENAI_BASE_URL", "https://example.com/v1")
    _clear_caches()
    try:
        assert get_llm_provider() == "openai"
    finally:
        _clear_caches()


def test_provider_auto_detects_azure(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no explicit provider and no base URL, defaults to azure."""
    # Set empty (rather than delenv) so a project .env value can't leak in.
    monkeypatch.setenv("LLM_PROVIDER", "")
    monkeypatch.setenv("LLM_OPENAI_BASE_URL", "")
    _clear_caches()
    try:
        assert get_llm_provider() == "azure"
    finally:
        _clear_caches()


def test_models_config_loads(
    monkeypatch: pytest.MonkeyPatch, models_config_file: Path
) -> None:
    """A valid config file parses into the expected structure."""
    monkeypatch.setenv("LLM_LITELLM_MODELS_CONFIG", str(models_config_file))
    _clear_caches()
    try:
        config = get_litellm_models_config()
        assert config is not None
        assert [p.name for p in config.providers] == ["Anthropic", "OpenAI"]
        assert (
            config.providers[0].models[0].id == "anthropic/claude-3-5-sonnet-20241022"
        )
    finally:
        _clear_caches()


def test_models_config_none_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """No config path set → returns None (LiteLLM inactive)."""
    # Set empty (not delenv) so a project .env value can't leak in.
    monkeypatch.setenv("LLM_LITELLM_MODELS_CONFIG", "")
    _clear_caches()
    try:
        assert get_litellm_models_config() is None
    finally:
        _clear_caches()


def test_models_config_missing_file_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """A configured but missing file fails fast."""
    monkeypatch.setenv("LLM_LITELLM_MODELS_CONFIG", "/nonexistent/models.json")
    _clear_caches()
    try:
        with pytest.raises(FileNotFoundError):
            get_litellm_models_config()
    finally:
        _clear_caches()


def test_models_config_malformed_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Malformed JSON raises rather than loading silently."""
    bad = tmp_path / "bad.json"
    bad.write_text("{ not valid json", encoding="utf-8")
    monkeypatch.setenv("LLM_LITELLM_MODELS_CONFIG", str(bad))
    _clear_caches()
    try:
        with pytest.raises(json.JSONDecodeError):
            get_litellm_models_config()
    finally:
        _clear_caches()


def test_build_chat_llm_returns_litellm(monkeypatch: pytest.MonkeyPatch) -> None:
    """When provider is litellm, _build_chat_llm returns a ChatLiteLLM."""
    from langchain_litellm import ChatLiteLLM

    from agent.service import _build_chat_llm

    monkeypatch.setenv("LLM_PROVIDER", "litellm")
    _clear_caches()
    try:
        llm = _build_chat_llm(model="gpt-4o")
        assert isinstance(llm, ChatLiteLLM)
        assert llm.model == "gpt-4o"
    finally:
        _clear_caches()


def test_models_config_validates_shape() -> None:
    """LiteLLMModelsConfig enforces the label/id shape on each model."""
    with pytest.raises(ValueError):  # noqa: PT011
        LiteLLMModelsConfig(
            providers=[{"name": "X", "models": [{"label": "only-label"}]}]
        )


def test_models_endpoint_returns_config_for_litellm(
    test_env_vars: dict[str, str],
) -> None:
    """GET /models returns the configured providers when LiteLLM is active."""
    config = LiteLLMModelsConfig(
        providers=[
            LiteLLMProvider(
                name="OpenAI",
                models=[LiteLLMModel(label="GPT-4o", id="gpt-4o")],
            )
        ]
    )
    with (
        patch("api.routes.chat.get_llm_provider", return_value="litellm"),
        patch("api.routes.chat.get_litellm_models_config", return_value=config),
        TestClient(create_app()) as client,
    ):
        resp = client.get("/models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["providers"][0]["name"] == "OpenAI"
        assert data["providers"][0]["models"][0]["id"] == "gpt-4o"


def test_models_endpoint_empty_for_non_litellm(
    test_env_vars: dict[str, str],
) -> None:
    """GET /models returns an empty list when the provider is not litellm."""
    with (
        patch("api.routes.chat.get_llm_provider", return_value="azure"),
        TestClient(create_app()) as client,
    ):
        resp = client.get("/models")
        assert resp.status_code == 200
        assert resp.json() == {"providers": []}
