"""Tests for Docling vision-URL / model-name derivation."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from document_processing import service


def test_bare_model_name_strips_provider_prefix() -> None:
    assert service._bare_model_name("azure/mydeploy") == "mydeploy"
    assert service._bare_model_name("openai/gpt-4o") == "gpt-4o"
    # Bare id (no provider prefix) is returned unchanged.
    assert service._bare_model_name("gpt-4o-mini") == "gpt-4o-mini"


def _patch_settings(
    monkeypatch: pytest.MonkeyPatch,
    *,
    api_base: str,
    api_version: str,
    model: str,
    picture_description_url: str = "",
) -> None:
    monkeypatch.setattr(
        service,
        "get_docling_settings",
        lambda: SimpleNamespace(picture_description_url=picture_description_url),
    )
    monkeypatch.setattr(
        service,
        "get_llm_settings",
        lambda: SimpleNamespace(
            api_base=api_base, api_version=api_version, model=model
        ),
    )


def test_vision_url_azure_path_strips_provider_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Azure deployment path must use the bare deployment, not 'azure/<deployment>'."""
    _patch_settings(
        monkeypatch,
        api_base="https://res.example.com",
        api_version="2024-02-15-preview",
        model="azure/mydeploy",
    )
    url = service._build_vision_url()
    assert url == (
        "https://res.example.com/openai/deployments/mydeploy"
        "/chat/completions?api-version=2024-02-15-preview"
    )
    assert "azure/" not in url


def test_vision_url_openai_compatible_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no api_version the base URL is treated as an OpenAI-compatible /v1 base."""
    _patch_settings(
        monkeypatch,
        api_base="https://gateway.example.com/v1",
        api_version="",
        model="openai/gpt-4o",
    )
    assert (
        service._build_vision_url() == "https://gateway.example.com/v1/chat/completions"
    )


@pytest.mark.parametrize("model", ["openai/gpt-4o", "gpt-4o"])
def test_vision_url_openai_default_endpoint_without_api_base(
    monkeypatch: pytest.MonkeyPatch, model: str
) -> None:
    """No api_base + an OpenAI model (prefixed or bare) → OpenAI's public URL."""
    _patch_settings(monkeypatch, api_base="", api_version="", model=model)
    assert service._build_vision_url() == service.OPENAI_CHAT_COMPLETIONS_URL


@pytest.mark.parametrize(
    "model", ["anthropic/claude-3-5-sonnet", "gemini/gemini-2.5-pro"]
)
def test_vision_url_non_openai_default_endpoint_raises(
    monkeypatch: pytest.MonkeyPatch, model: str
) -> None:
    """No api_base + a non-OpenAI provider → cannot infer a URL, so it raises."""
    _patch_settings(monkeypatch, api_base="", api_version="", model=model)
    with pytest.raises(ValueError, match="DOCLING_PICTURE_DESCRIPTION_URL"):
        service._build_vision_url()


def test_vision_url_explicit_override_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(
        monkeypatch,
        api_base="https://res.example.com",
        api_version="2024-02-15-preview",
        model="azure/mydeploy",
        picture_description_url="https://explicit.example.com/chat/completions",
    )
    assert (
        service._build_vision_url() == "https://explicit.example.com/chat/completions"
    )
