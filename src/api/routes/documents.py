"""REST endpoints for document conversion and raw file attachment uploads."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, UploadFile

from api.utils import get_client_ip
from attachment_storage import get_attachment_storage, is_attachment_storage_enabled
from config import get_docling_settings, get_logger
from document_processing.service import convert_document_to_markdown
from persistence import get_chat_history_repository
from persistence.models import StoredAttachment
from rate_limiting import consume_upload_rate_limit

logger = get_logger(__name__)

router = APIRouter()

# ── Mime-type constants ───────────────────────────────────────────────────────

# Accepted types for the raw image upload endpoint.
ALLOWED_IMAGE_MIME_TYPES: frozenset[str] = frozenset(
    {"image/png", "image/jpeg", "image/gif", "image/webp"}
)

# Types that are safe to store and later serve with their original Content-Type.
# Anything outside this list gets normalized to application/octet-stream so that
# a client-supplied type can never trigger in-browser script execution.
_SAFE_STORED_MIME_TYPES: frozenset[str] = frozenset(
    {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/plain",
        "text/markdown",
        *ALLOWED_IMAGE_MIME_TYPES,
    }
)

# 10 MB — maximum raw binary size for the upload-attachment endpoint.
_MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024


def safe_mime_type(mime: str | None) -> str:
    """Return *mime* if it is in the safe allowlist, otherwise ``application/octet-stream``.

    Prevents a maliciously crafted Content-Type (e.g. ``text/html``) from
    being persisted and later served inline to other visitors.
    """
    if mime and mime in _SAFE_STORED_MIME_TYPES:
        return mime
    return "application/octet-stream"


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _persist_attachment(
    *,
    file_bytes: bytes,
    filename: str,
    mime_type: str,
    visitor_id: str,
) -> str | None:
    """Store *file_bytes* in attachment storage and create a DB record.

    Returns the attachment ID on success, ``None`` on failure or when either
    backend is not available.
    """
    repo = get_chat_history_repository()
    if repo is None or not is_attachment_storage_enabled() or not visitor_id:
        return None
    try:
        storage = get_attachment_storage()
        attachment_id = str(uuid.uuid4())
        storage_key = await storage.store(file_bytes, attachment_id)
        await repo.save_attachment(
            StoredAttachment(
                id=attachment_id,
                message_id=None,
                visitor_id=visitor_id,
                storage_key=storage_key,
                name=filename,
                mime_type=mime_type,
                size=len(file_bytes),
                created_at=datetime.now(UTC),
            )
        )
    except Exception:
        logger.exception(
            "Failed to store attachment visitor_id=%s filename=%s",
            visitor_id,
            filename,
        )
        return None
    return attachment_id


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/process-document")
async def process_document(
    request: Request,
    file: UploadFile,
    visitor_id: Annotated[
        str | None,
        Query(
            max_length=512,
            description="Visitor ID used to scope the stored attachment",
        ),
    ] = None,
) -> dict[str, str | None]:
    """Accept a document upload, convert it to markdown via Docling, and return the result.

    When attachment storage and persistence are both enabled the original file
    is stored and an ``attachment_id`` is returned.  The frontend should pass
    this ID as part of ``attachment_ids`` in the subsequent WebSocket message
    so the attachment is linked to the persisted chat message.
    """
    client_ip = get_client_ip(request)
    if client_ip is not None and not await consume_upload_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    settings = get_docling_settings()

    if not settings.enabled:
        raise HTTPException(status_code=503, detail="Document processing is disabled")

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    max_bytes = settings.max_file_size_bytes
    _chunk_size = 256 * 1024  # 256 KB read window
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            max_mb = max_bytes // (1024 * 1024)
            raise HTTPException(
                status_code=400, detail=f"File exceeds {max_mb}MB limit"
            )
        chunks.append(chunk)
    file_bytes = b"".join(chunks)

    try:
        markdown = await convert_document_to_markdown(file_bytes, file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    attachment_id: str | None = None
    if visitor_id:
        mime_type = safe_mime_type(file.content_type)
        attachment_id = await _persist_attachment(
            file_bytes=file_bytes,
            filename=file.filename,
            mime_type=mime_type,
            visitor_id=visitor_id,
        )

    return {
        "markdown": markdown,
        "filename": file.filename,
        "attachment_id": attachment_id,
    }


@router.post("/upload-attachment")
async def upload_attachment(
    request: Request,
    file: UploadFile,
    visitor_id: Annotated[
        str | None,
        Query(
            max_length=512,
            description="Visitor ID used to scope the stored attachment",
        ),
    ] = None,
) -> dict[str, str | None]:
    """Upload a raw image file and store it for later retrieval.

    Unlike ``/process-document`` this endpoint performs no document conversion —
    it accepts image files, validates them, stores them, and returns an
    ``attachment_id`` to be included in the subsequent WebSocket message.
    """
    client_ip = get_client_ip(request)
    if client_ip is not None and not await consume_upload_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    mime_type = file.content_type or ""
    if mime_type not in ALLOWED_IMAGE_MIME_TYPES:
        allowed = ", ".join(sorted(ALLOWED_IMAGE_MIME_TYPES))
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type. Allowed: {allowed}",
        )

    _chunk_size = 256 * 1024  # 256 KB read window
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > _MAX_UPLOAD_SIZE_BYTES:
            max_mb = _MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
            raise HTTPException(
                status_code=400, detail=f"File exceeds {max_mb}MB limit"
            )
        chunks.append(chunk)
    file_bytes = b"".join(chunks)

    attachment_id: str | None = None
    if visitor_id:
        attachment_id = await _persist_attachment(
            file_bytes=file_bytes,
            filename=file.filename,
            mime_type=mime_type,
            visitor_id=visitor_id,
        )

    return {
        "attachment_id": attachment_id,
        "name": file.filename,
        "mime_type": mime_type,
    }
