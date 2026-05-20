"""Tests for document upload endpoints: /process-document and /upload-attachment."""

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from config import get_docling_settings


def test_process_document_returns_404_when_disabled(
    test_env_vars: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # When DOCLING_ENABLED=false the router is not registered at all,
    # so the endpoint responds with 404 (not found), not 503.
    monkeypatch.setenv("DOCLING_ENABLED", "false")
    get_docling_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            response = client.post(
                "/process-document",
                files={"file": ("test.pdf", b"%PDF-1.4", "application/pdf")},
            )
        assert response.status_code == 404
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
    body = response.json()
    assert body["markdown"] == "# Hello"
    assert body["filename"] == "notes.pdf"
    # attachment_id is None when persistence/storage are not fully configured in tests.
    assert "attachment_id" in body
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


# ── /upload-attachment tests ──────────────────────────────────────────────────


def test_upload_attachment_rejects_non_image_mime(app: TestClient) -> None:
    response = app.post(
        "/upload-attachment",
        files={"file": ("doc.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert response.status_code == 422


def test_upload_attachment_rejects_missing_filename(app: TestClient) -> None:
    response = app.post(
        "/upload-attachment",
        files={"file": ("", b"\x89PNG", "image/png")},
    )
    assert response.status_code in {400, 422}


def test_upload_attachment_rejects_oversized_file(app: TestClient) -> None:
    big = b"x" * (10 * 1024 * 1024 + 1)
    response = app.post(
        "/upload-attachment",
        files={"file": ("huge.png", big, "image/png")},
    )
    assert response.status_code == 400


def test_upload_attachment_success_returns_attachment_id_key(app: TestClient) -> None:
    response = app.post(
        "/upload-attachment",
        files={"file": ("photo.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    )
    assert response.status_code == 200
    body = response.json()
    # attachment_id is None when storage+persistence are not fully configured in tests.
    assert "attachment_id" in body
    assert body["name"] == "photo.png"
    assert body["mime_type"] == "image/png"


# ── GET /attachments/{id} tests ───────────────────────────────────────────────


def test_get_attachment_not_found(app: TestClient) -> None:
    """Non-existent attachment returns 404."""
    response = app.get(
        f"/attachments/{uuid.uuid4()}",
        params={"visitor_id": "some-visitor"},
    )
    assert response.status_code == 404


def test_get_attachment_wrong_visitor_returns_404(
    app: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> None:
    """An attachment owned by visitor A is not accessible to visitor B."""
    import asyncio

    from attachment_storage import (
        get_attachment_storage,
        init_attachment_storage,
        shutdown_attachment_storage,
    )
    from config import get_attachment_storage_settings
    from persistence import get_chat_history_repository

    storage_dir = tmp_path / "store"
    storage_dir.mkdir()
    monkeypatch.setenv("ATTACHMENT_STORAGE_BASE_PATH", str(storage_dir))
    get_attachment_storage_settings.cache_clear()
    # After the test monkeypatch restores the env var, clear the cache so the
    # stale tmp_path value is not carried into the next test's singleton init.
    request.addfinalizer(get_attachment_storage_settings.cache_clear)

    async def _setup() -> tuple[str, bool]:
        # The app fixture already initialised the singleton at lifespan startup.
        # Shut it down first so init_attachment_storage() picks up the new path
        # set by monkeypatch above instead of returning early as a no-op.
        await shutdown_attachment_storage()
        get_attachment_storage_settings.cache_clear()
        await init_attachment_storage()

        storage = get_attachment_storage()
        att_id = str(uuid.uuid4())
        img_bytes = b"\x89PNG\r\n\x1a\n"
        storage_key = await storage.store(img_bytes, att_id)

        repo = get_chat_history_repository()
        persisted = False
        if repo is not None:
            from datetime import UTC, datetime

            from persistence.models import StoredAttachment

            await repo.save_attachment(
                StoredAttachment(
                    id=att_id,
                    message_id=None,
                    visitor_id="owner",
                    storage_key=storage_key,
                    name="photo.png",
                    mime_type="image/png",
                    size=len(img_bytes),
                    created_at=datetime.now(UTC),
                )
            )
            persisted = True
        return att_id, persisted

    att_id, persisted = asyncio.run(_setup())

    owner_response = app.get(f"/attachments/{att_id}", params={"visitor_id": "owner"})
    if persisted:
        # Both persistence and storage are active — the owner must get the file.
        assert owner_response.status_code == 200
    else:
        # Setup skipped DB write (persistence disabled) — retrieval cannot succeed.
        assert owner_response.status_code in {404, 503}

    # Intruder always gets 404.
    intruder_response = app.get(
        f"/attachments/{att_id}", params={"visitor_id": "intruder"}
    )
    assert intruder_response.status_code == 404
