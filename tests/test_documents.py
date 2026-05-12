"""Tests for document upload / process-document endpoint."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from config import get_docling_settings


def test_process_document_returns_503_when_disabled(
    test_env_vars: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DOCLING_ENABLED", "false")
    get_docling_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            response = client.post(
                "/process-document",
                files={"file": ("test.pdf", b"%PDF-1.4", "application/pdf")},
            )
        assert response.status_code == 503
    finally:
        monkeypatch.delenv("DOCLING_ENABLED", raising=False)
        get_docling_settings.cache_clear()


def test_process_document_requires_filename(app: TestClient) -> None:
    response = app.post(
        "/process-document", files={"file": ("", b"x", "application/octet-stream")}
    )
    assert response.status_code in {400, 422}


@patch("api.routes.documents.convert_document_to_markdown", new_callable=AsyncMock)
def test_process_document_success(mock_convert: AsyncMock, app: TestClient) -> None:
    mock_convert.return_value = "# Hello"
    response = app.post(
        "/process-document",
        files={"file": ("notes.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert response.status_code == 200
    assert response.json() == {"markdown": "# Hello", "filename": "notes.pdf"}
    mock_convert.assert_awaited_once()


def test_process_document_rejects_oversized_file(
    app: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DOCLING_MAX_FILE_SIZE_BYTES", "4")
    get_docling_settings.cache_clear()
    try:
        response = app.post(
            "/process-document",
            files={"file": ("big.pdf", b"12345", "application/pdf")},
        )
        assert response.status_code == 400
    finally:
        monkeypatch.delenv("DOCLING_MAX_FILE_SIZE_BYTES", raising=False)
        get_docling_settings.cache_clear()
