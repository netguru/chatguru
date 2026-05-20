"""History / persistence API routes.

These endpoints expose the read/manage side of persisted conversations,
messages, attachments, and titles. They live on a separate router from the
chat WebSocket because they are only registered when persistence is enabled
(see ``src.api.main``).
"""

import contextlib
import json
import urllib.parse
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from attachment_storage import get_attachment_storage, is_attachment_storage_enabled
from config import get_logger
from persistence import get_chat_history_repository
from title_generation import generate_title, strip_document_tags, truncate_title

logger = get_logger(__name__)


_MAX_TITLE_FIRST_MESSAGE_LENGTH = 200_000


class GenerateConversationTitleRequest(BaseModel):
    """HTTP payload for generating a conversation title on demand."""

    visitor_id: str = Field(..., min_length=1, max_length=512, description="Visitor ID")
    session_id: str = Field(..., min_length=1, max_length=512, description="Session ID")
    first_message: str = Field(
        ...,
        min_length=1,
        max_length=_MAX_TITLE_FIRST_MESSAGE_LENGTH,
        description="First user message used to generate the title",
    )


persistence_router = APIRouter(tags=["history"])


def _require_repo() -> Any:
    """Return the chat history repository or raise if it isn't initialised.

    The persistence router is only registered when persistence is enabled,
    so a missing repository here indicates a wiring bug rather than a
    runtime configuration choice.
    """
    repo = get_chat_history_repository()
    if repo is None:
        msg = "persistence router registered but repository is not initialised"
        raise RuntimeError(msg)
    return repo


@persistence_router.get("/attachments/{attachment_id}")
async def get_attachment(
    attachment_id: str,
    visitor_id: Annotated[
        str, Query(min_length=1, max_length=512, description="Visitor ID")
    ],
) -> StreamingResponse:
    """Stream a stored attachment file.

    Only the visitor that uploaded the attachment may retrieve it.
    """
    repo = get_chat_history_repository()
    if repo is None:
        raise HTTPException(status_code=404, detail="Attachment not found")

    attachment = await repo.get_attachment(
        attachment_id=attachment_id, visitor_id=visitor_id
    )
    if attachment is None:
        raise HTTPException(status_code=404, detail="Attachment not found")

    if not is_attachment_storage_enabled():
        raise HTTPException(status_code=503, detail="Attachment storage not available")

    storage = get_attachment_storage()
    try:
        stream = await storage.retrieve(attachment.storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail="Attachment file not found"
        ) from exc

    safe_filename = urllib.parse.quote(attachment.name, safe="")
    is_pdf = attachment.mime_type == "application/pdf"
    disposition = (
        "inline" if is_pdf else f"attachment; filename*=UTF-8''{safe_filename}"
    )
    headers = {
        "Content-Disposition": disposition,
        # Prevent browsers from MIME-sniffing the response away from the declared type.
        "X-Content-Type-Options": "nosniff",
    }
    if is_pdf:
        # Sandbox PDF JavaScript so it cannot access cookies or localStorage on the
        # main app origin even when served inline.
        headers["Content-Security-Policy"] = "sandbox"
    return StreamingResponse(
        content=stream, media_type=attachment.mime_type, headers=headers
    )


@persistence_router.get("/conversations")
async def get_conversations(
    visitor_id: Annotated[
        str, Query(min_length=1, max_length=512, description="Visitor ID")
    ],
) -> list[dict[str, str]]:
    """Return all conversations for a visitor, newest first.

    Note: visitor_id is client-supplied and not authenticated. This endpoint
    is intended for internal / single-tenant deployments. In multi-tenant
    scenarios, add an authentication layer before exposing this route.
    """
    repo = _require_repo()
    convos = await repo.list_conversations(visitor_id=visitor_id)
    return [
        {
            "session_id": c.session_id,
            "title": c.title,
            "created_at": c.created_at.isoformat(),
        }
        for c in convos
    ]


@persistence_router.get("/history")
async def get_history(
    visitor_id: Annotated[
        str, Query(min_length=1, max_length=512, description="Visitor ID")
    ],
    session_id: Annotated[str, Query(description="Session ID")] = "default",
) -> list[dict[str, Any]]:
    """Return persisted messages for a visitor+session pair, oldest first.

    Note: visitor_id is client-supplied and not authenticated. This endpoint
    is intended for internal / single-tenant deployments. In multi-tenant
    scenarios, add an authentication layer before exposing this route.
    """
    repo = _require_repo()
    messages = await repo.list_messages(visitor_id=visitor_id, session_id=session_id)

    # Batch-load all attachments for the session in a single query.
    all_attachments = await repo.get_attachments_for_messages([m.id for m in messages])
    attachments_by_message: dict[str, list[Any]] = {}
    for a in all_attachments:
        if a.message_id:
            attachments_by_message.setdefault(a.message_id, []).append(a)

    result = []
    for m in messages:
        entry: dict[str, Any] = {"role": m.role, "content": m.content}
        if m.trace_id is not None:
            entry["trace_id"] = m.trace_id
        if m.sources is not None:
            with contextlib.suppress(Exception):
                entry["sources"] = json.loads(m.sources)
        msg_attachments = attachments_by_message.get(m.id, [])
        if msg_attachments:
            entry["stored_attachments"] = [
                {"id": a.id, "name": a.name, "mime_type": a.mime_type}
                for a in msg_attachments
            ]
        result.append(entry)
    return result


@persistence_router.post("/conversations/title")
async def generate_conversation_title(
    payload: GenerateConversationTitleRequest,
) -> dict[str, str]:
    """Generate and persist a title for an existing conversation."""
    repo = _require_repo()

    exists = await repo.conversation_exists(
        visitor_id=payload.visitor_id,
        session_id=payload.session_id,
    )
    if not exists:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found for visitor_id + session_id",
        )

    first_message_text = strip_document_tags(payload.first_message)
    title = truncate_title(first_message_text)
    try:
        title = await generate_title(
            first_message_text,
            session_id=payload.session_id,
            visitor_id=payload.visitor_id,
        )
    except Exception:
        logger.exception(
            "Title generation failed (session_id=%s), using fallback",
            payload.session_id,
        )

    await repo.update_conversation_title(
        visitor_id=payload.visitor_id,
        session_id=payload.session_id,
        title=title,
    )
    return {"session_id": payload.session_id, "title": title}
