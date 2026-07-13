"""Chat API routes."""

import asyncio
import base64
import contextlib
import json
import mimetypes
import urllib.parse
import uuid
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any, Literal, Self

from fastapi import (
    APIRouter,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import StreamingResponse
from gridfs import GridFSBucket, GridOut
from gridfs.errors import NoFile
from pydantic import BaseModel, Field, ValidationError, model_validator
from pymongo import MongoClient

from agent.service import Agent
from api.errors import (
    InvalidJSONError,
    InvalidMessageFormatError,
    ValidationFailedError,
    WebSocketErrorType,
)
from api.utils import get_client_ip
from attachment_storage import get_attachment_storage, is_attachment_storage_enabled
from config import (
    get_app_settings,
    get_document_rag_settings,
    get_litellm_models_config,
    get_logger,
)
from document_rag import get_document_rag_repository
from mcp_integration import get_mcp_connections
from persistence import get_chat_history_repository, is_persistence_enabled
from rate_limiting import consume_rate_limit

if TYPE_CHECKING:
    from persistence.repository import ChatHistoryRepository
from title_generation import strip_document_tags, truncate_title
from tracing import get_client, is_langfuse_initialized
from vector_db import VectorDatabase, create_vector_database

logger = get_logger(__name__)


_MAX_CONTENT_LENGTH = 200_000  # large enough for document attachments
_MAX_TRANSCRIPT_MESSAGES = 200
_MAX_LAST_USER_MESSAGE_LENGTH = 200_000  # same ceiling as _MAX_CONTENT_LENGTH


_MAX_ATTACHMENTS_PER_MESSAGE = 5


class HistoryMessage(BaseModel):
    """Individual message in conversation history."""

    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(
        ..., max_length=_MAX_CONTENT_LENGTH, description="Message content"
    )
    attachment_ids: list[str] | None = Field(
        default=None,
        max_length=_MAX_ATTACHMENTS_PER_MESSAGE,
        description=(
            "IDs of pre-stored attachments (images via POST /upload-attachment, "
            "documents via POST /process-document). Only allowed on the last user message."
        ),
    )


def _validate_model_id(model: str | None) -> None:
    """Reject a per-request model ID that isn't in the models config.

    No-op when no model is requested or no models config is loaded.
    """
    if model is None:
        return
    config = get_litellm_models_config()
    if config is None:
        return
    valid_ids = {m.id for p in config.providers for m in p.models}
    if model not in valid_ids:
        msg = f"Unknown model '{model}'. Valid models: {sorted(valid_ids)}"
        raise ValueError(msg)


class ChatMessage(BaseModel):
    """WebSocket chat payload: full transcript including the current user turn last."""

    session_id: str | None = Field(
        None, description="Session ID for conversation continuity"
    )
    visitor_id: str | None = Field(
        None,
        description=(
            "Stable ID for persisted history (per device or user); required when "
            "persistence is enabled, otherwise a per-connection default is generated"
        ),
    )
    messages: list[HistoryMessage] = Field(
        default_factory=list,
        max_length=_MAX_TRANSCRIPT_MESSAGES,
        description="Full conversation for this request; last entry must be the current user message",
    )
    model: str | None = Field(
        None,
        max_length=256,
        description=(
            "Model ID to use for this request (e.g. 'openai/gpt-4o', "
            "'anthropic/claude-3-5-sonnet-20241022'). Must be one of the models "
            "listed in the models config; ignored when no models config is set."
        ),
    )
    auth_token: str | None = Field(
        None,
        max_length=8192,
        description=(
            "Per-user token forwarded to MCP servers whose config references "
            "${user_token}. Never persisted or logged; used only to authorize "
            "MCP tool access for this turn."
        ),
    )

    @model_validator(mode="after")
    def ensure_messages_valid(self) -> Self:
        if not self.messages:
            msg = "'messages' must be a non-empty array"
            raise ValueError(msg)

        # Only the last message may carry attachment_ids.
        for m in self.messages[:-1]:
            if m.attachment_ids:
                msg = "Only the last (current) message may contain attachment_ids"
                raise ValueError(msg)

        last = self.messages[-1]
        if last.role != "user":
            msg = 'Last message in messages must have role "user" (current turn)'
            raise ValueError(msg)

        has_attachments = bool(last.attachment_ids)
        # When attachments are present, allow empty text content.
        if has_attachments:
            if len(last.content) > _MAX_LAST_USER_MESSAGE_LENGTH:
                msg = f"Last user message content must be at most {_MAX_LAST_USER_MESSAGE_LENGTH} characters"
                raise ValueError(msg)
        elif len(last.content) < 1 or len(last.content) > _MAX_LAST_USER_MESSAGE_LENGTH:
            msg = f"Last user message content must be between 1 and {_MAX_LAST_USER_MESSAGE_LENGTH} characters"
            raise ValueError(msg)
        # When no models config is present, ignore any per-request model override.
        if get_litellm_models_config() is None:
            self.model = None
        _validate_model_id(self.model)
        return self


class FeedbackRequest(BaseModel):
    """HTTP payload for submitting user feedback on an assistant message."""

    trace_id: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="Langfuse trace ID for the message",
    )
    visitor_id: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="Visitor ID that originated the message — used to verify ownership",
    )
    value: Literal[0, 1] = Field(..., description="1 = thumbs up, 0 = thumbs down")
    comment: str | None = Field(
        None, max_length=2000, description="Optional freeform comment"
    )


router = APIRouter(tags=["chat"])

# Strong references to background tasks so they aren't garbage-collected before completion.
_background_tasks: set[asyncio.Task] = set()


@router.get("/models")
async def get_available_models() -> dict[str, Any]:
    """Return the list of selectable models.

    Returns an empty providers list when no models config file is configured,
    so the frontend can use this to decide whether to show the model picker.
    """
    config = get_litellm_models_config()
    if config is None:
        return {"providers": []}
    return {"providers": [p.model_dump() for p in config.providers]}


async def await_background_tasks() -> None:
    """Await all pending background tasks (call during shutdown)."""
    if _background_tasks:
        await asyncio.gather(*_background_tasks, return_exceptions=True)


async def _send_error(
    websocket: WebSocket,
    *,
    session_id: str,
    error_type: WebSocketErrorType,
    content: str,
) -> None:
    """Send a standardized WebSocket error frame."""
    await websocket.send_json(
        {
            "type": "error",
            "error_type": error_type.value,
            "content": content,
            "session_id": session_id,
        }
    )


def _extract_session_id(data: str) -> str:
    """
    Extract session_id from raw JSON data for error handling.

    This function safely extracts session_id even when JSON parsing fails,
    ensuring error responses always include a session_id field.

    Args:
        data: Raw JSON string from WebSocket message

    Returns:
        Extracted session_id or "unknown" if extraction fails
    """
    try:
        raw_data = json.loads(data)
        if isinstance(raw_data, dict):
            session_id = raw_data.get("session_id")
            return str(session_id) if session_id is not None else "unknown"
        else:
            return "unknown"
    except (json.JSONDecodeError, AttributeError, TypeError):
        return "unknown"


def _validate_message_format(message_data: object) -> None:
    """
    Validate that message data is a dictionary.

    Raises:
        InvalidMessageFormatError: If message_data is not a dict
    """
    if not isinstance(message_data, dict):
        msg = "Message must be a JSON object"
        raise InvalidMessageFormatError(msg)


_vector_database_cache: VectorDatabase | None = None
_vector_database_initialized: bool = False


async def _initialize_vector_database() -> VectorDatabase | None:
    """
    Initialize VectorDatabase (sqlite-vec service) for RAG.

    Returns:
        VectorDatabase instance if healthy, None otherwise
    """
    global _vector_database_cache, _vector_database_initialized  # noqa: PLW0603

    if _vector_database_initialized:
        return _vector_database_cache

    try:
        db = create_vector_database()

        if await db.is_healthy():
            item_count = await db.count()
            logger.info("Vector database connected (%d items)", item_count)
            _vector_database_cache = db
        else:
            logger.warning("Vector database service not available")
            _vector_database_cache = None
    except NotImplementedError as e:
        logger.warning("Vector database not implemented: %s", e)
        _vector_database_cache = None
    except Exception:
        logger.exception("Failed to initialize vector database")
        _vector_database_cache = None

    # Set only when healthy so later connections can retry after transient startup failures.
    _vector_database_initialized = _vector_database_cache is not None
    return _vector_database_cache


@router.get("/documents/{source_path:path}")
async def get_document_source(source_path: str) -> StreamingResponse:
    """Serve a source document from MongoDB GridFS.

    Blocking PyMongo/GridFS calls are offloaded to the default thread-pool
    executor so the async event loop is never blocked.  The file is streamed
    in chunks to avoid loading the entire document into memory.
    """
    settings = get_document_rag_settings()
    if not source_path.strip():
        raise HTTPException(status_code=400, detail="Invalid document path")
    if source_path.startswith("/") or ".." in source_path.split("/"):
        raise HTTPException(status_code=400, detail="Invalid document path")

    loop = asyncio.get_running_loop()

    def _open_gridfs_stream() -> (
        tuple[MongoClient[dict[str, Any]], GridOut, str, str]
        | tuple[None, None, None, None]
    ):
        client: MongoClient[dict[str, Any]] = MongoClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=settings.mongodb_connection_timeout_ms,
            connectTimeoutMS=settings.mongodb_connection_timeout_ms,
        )
        database = client[settings.mongodb_database]
        bucket = GridFSBucket(database, bucket_name=settings.mongodb_files_bucket)
        try:
            stream = bucket.open_download_stream_by_name(source_path)
        except NoFile:
            client.close()
            return None, None, None, None
        metadata = dict(stream.metadata or {})
        media_type = metadata.get("content_type")
        if not media_type:
            guessed, _ = mimetypes.guess_type(source_path)
            media_type = guessed or "application/octet-stream"
        filename = stream.filename or source_path
        return client, stream, media_type, filename

    client, stream, media_type, filename = await loop.run_in_executor(
        None, _open_gridfs_stream
    )
    if stream is None or client is None:
        raise HTTPException(status_code=404, detail="Document not found")

    chunk_size = 256 * 1024  # 256 KB

    async def _stream_chunks() -> AsyncIterator[bytes]:
        try:
            while True:
                chunk = await loop.run_in_executor(None, stream.read, chunk_size)
                if not chunk:
                    break
                yield chunk
        finally:
            await loop.run_in_executor(None, stream.close)
            await loop.run_in_executor(None, client.close)

    safe_filename = urllib.parse.quote(filename or source_path, safe="")
    headers = {
        "Content-Disposition": f"inline; filename*=UTF-8''{safe_filename}",
    }
    return StreamingResponse(
        content=_stream_chunks(), media_type=media_type, headers=headers
    )


@router.post("/feedback")
async def submit_feedback(payload: FeedbackRequest, request: Request) -> dict[str, str]:
    """Submit a user thumbs-up / thumbs-down score for an assistant message.

    Submits a ``BOOLEAN`` score named ``user-feedback`` to Langfuse using the
    provided trace ID.  The ``score_id`` field on the score acts as an idempotency key
    so re-submissions overwrite rather than duplicate the existing score.

    Returns ``{"status": "skipped"}`` when Langfuse is not configured so that
    non-instrumented deployments don't surface errors to users.
    """
    client_ip = get_client_ip(request)
    if client_ip is not None and not await consume_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # Verify the trace_id belongs to the calling visitor before scoring.
    # When persistence is disabled we cannot validate, so we allow the request
    # through — trace_ids are unguessable UUIDs from Langfuse in that case.
    repo = get_chat_history_repository()
    if repo is not None:
        owned = await repo.trace_id_owned_by_visitor(
            trace_id=payload.trace_id,
            visitor_id=payload.visitor_id,
        )
        if not owned:
            raise HTTPException(
                status_code=403,
                detail="trace_id does not belong to this visitor",
            )

    if not is_langfuse_initialized():
        return {"status": "skipped"}

    safe_trace_id = payload.trace_id.replace("\n", "\\n").replace("\r", "\\r")
    # Scope score_id per visitor so different visitors cannot overwrite each other's scores.
    score_id = f"{payload.trace_id}-{payload.visitor_id}-user-feedback"
    try:
        get_client().create_score(
            trace_id=payload.trace_id,
            name="user-feedback",
            value=float(payload.value),
            data_type="BOOLEAN",
            comment=payload.comment,
            score_id=score_id,
        )
    except Exception as exc:
        logger.exception(
            "Failed to submit feedback score to Langfuse (trace_id=%s)",
            safe_trace_id,
        )
        raise HTTPException(
            status_code=500, detail="Failed to submit feedback"
        ) from exc

    return {"status": "ok"}


_MAX_IMAGE_BYTES_FOR_LLM = 4 * 1024 * 1024  # 4 MB per image sent to the LLM


async def _load_image_attachments(
    *,
    attachment_ids: list[str],
    visitor_id: str,
    repo: "ChatHistoryRepository",
) -> list[dict[str, str]]:
    """Fetch image attachments from storage and return base64 payloads for the LLM.

    Non-image attachments (e.g. PDFs) are skipped — only image/* types are
    included so the agent service can build multimodal content blocks.
    Images exceeding _MAX_IMAGE_BYTES_FOR_LLM are skipped to avoid token overflow.
    """
    if not is_attachment_storage_enabled():
        return []
    storage = get_attachment_storage()
    result: list[dict[str, str]] = []
    for att_id in attachment_ids:
        att = await repo.get_attachment(attachment_id=att_id, visitor_id=visitor_id)
        if att is None or not att.mime_type.startswith("image/"):
            continue
        if att.size > _MAX_IMAGE_BYTES_FOR_LLM:
            logger.warning(
                "Skipping image attachment %s (%d bytes) — exceeds %d byte LLM limit",
                att_id,
                att.size,
                _MAX_IMAGE_BYTES_FOR_LLM,
            )
            continue
        try:
            stream = await storage.retrieve(att.storage_key)
            raw = b"".join([chunk async for chunk in stream])
            result.append(
                {
                    "name": att.name,
                    "mime_type": att.mime_type,
                    "data": base64.b64encode(raw).decode(),
                }
            )
        except Exception:
            logger.exception("Failed to load image attachment %s for LLM", att_id)
    return result


async def _store_user_attachments(
    *,
    repo: "ChatHistoryRepository",
    user_message_id: str,
    visitor_id: str,
    last_message: "HistoryMessage",
) -> list[dict[str, str]]:
    """Link pre-stored attachments (images + documents) to the user message.

    All attachments must already be persisted via ``/upload-attachment`` or
    ``/process-document`` before the WebSocket message is sent.  This function
    only links them to the newly created message row and returns their metadata
    for the end frame.
    """
    if not is_attachment_storage_enabled() or not last_message.attachment_ids:
        return []

    stored: list[dict[str, str]] = []
    try:
        await repo.link_attachments_to_message(
            attachment_ids=last_message.attachment_ids,
            message_id=user_message_id,
            visitor_id=visitor_id,
        )
        linked = await repo.get_attachments_for_message(user_message_id)
        ids_set = set(last_message.attachment_ids)
        stored.extend(
            {"id": att.id, "name": att.name, "mime_type": att.mime_type}
            for att in linked
            if att.id in ids_set
        )
    except Exception:
        logger.exception(
            "Failed to link attachments %s to message %s",
            last_message.attachment_ids,
            user_message_id,
        )
    return stored


async def _build_transcript(
    chat_message: ChatMessage,
    *,
    visitor_id: str,
    repo: "ChatHistoryRepository | None",
) -> list[dict[str, Any]]:
    """Build the LLM transcript, hydrating image attachments from storage.

    Image bytes are loaded server-side so the client never sends raw base64
    over the WebSocket.
    """
    last_message = chat_message.messages[-1]
    transcript: list[dict[str, Any]] = [
        {"role": m.role, "content": m.content} for m in chat_message.messages[:-1]
    ]
    current_entry: dict[str, Any] = {"role": "user", "content": last_message.content}
    if last_message.attachment_ids and repo is not None:
        image_parts = await _load_image_attachments(
            attachment_ids=last_message.attachment_ids,
            visitor_id=visitor_id,
            repo=repo,
        )
        if image_parts:
            current_entry["attachments"] = image_parts
    transcript.append(current_entry)
    return transcript


async def _persist_user_turn(
    websocket: WebSocket,
    *,
    repo: "ChatHistoryRepository",
    chat_message: ChatMessage,
    session_id: str,
    visitor_id: str,
) -> list[dict[str, str]] | None:
    """Create the conversation row if needed, persist the user message, and link
    its attachments.

    Returns the list of stored attachment metadata, or ``None`` if persistence
    failed (in which case an error frame and terminating ``end`` frame have
    already been sent and the caller must abort the turn).
    """
    last_message = chat_message.messages[-1]
    # Server-side check is authoritative regardless of how many messages the
    # client sends in the transcript; prevents redundant title-generation calls
    # on reconnect. Uses a lightweight SELECT 1 instead of fetching messages.
    is_first_message = not await repo.conversation_exists(
        visitor_id=visitor_id, session_id=session_id
    )
    if is_first_message:
        fallback_title = truncate_title(strip_document_tags(last_message.content))
        try:
            await repo.create_conversation(
                visitor_id=visitor_id,
                session_id=session_id,
                # Store a fast fallback title immediately so the sidebar shows
                # something right away. The /conversations/title endpoint will
                # replace it with an LLM-generated title once that call completes.
                title=fallback_title,
            )
            logger.info(
                "Created conversation with fallback title (session_id=%s, title=%r)",
                session_id,
                fallback_title,
            )
        except Exception:
            logger.exception(
                "Failed to create conversation record (session_id=%s)", session_id
            )

    try:
        user_message_id = await repo.append_message(
            visitor_id=visitor_id,
            session_id=session_id,
            role="user",
            content=last_message.content,
        )
    except Exception:
        logger.exception("Failed to persist user message")
        await _send_error(
            websocket,
            session_id=session_id,
            error_type=WebSocketErrorType.PERSISTENCE_WRITE_FAILED,
            content="Could not save your message. Please try again.",
        )
        await websocket.send_json(
            {"type": "end", "content": "", "session_id": session_id}
        )
        return None

    return await _store_user_attachments(
        repo=repo,
        user_message_id=user_message_id,
        visitor_id=visitor_id,
        last_message=last_message,
    )


async def _stream_assistant_response(  # noqa: PLR0913
    websocket: WebSocket,
    agent: Agent,
    transcript: list[dict[str, Any]],
    *,
    session_id: str,
    visitor_id: str,
    model: str | None = None,
    auth_token: str | None = None,
) -> str:
    """Stream the assistant reply token-by-token to *websocket* and return the
    accumulated full response.
    """
    full_response = ""
    async for chunk in agent.astream(
        transcript,
        session_id=session_id,
        visitor_id=visitor_id,
        model=model,
        auth_token=auth_token,
    ):
        full_response += chunk
        await websocket.send_json(
            {
                "type": "token",
                "content": chunk,
                "session_id": session_id,
            }
        )
    return full_response


async def _send_end_frame(
    websocket: WebSocket,
    *,
    session_id: str,
    resolved_answer: str,
    sources: list[Any],
    stored_user_attachments: list[dict[str, str]],
    trace_id: str | None,
) -> None:
    """Send the terminating ``end`` frame for a chat turn."""
    end_frame: dict[str, Any] = {
        "type": "end",
        "content": resolved_answer,
        "session_id": session_id,
        "sources": sources,
        "user_attachments": stored_user_attachments,
    }
    safe_trace_id = (
        trace_id.replace("\n", "\\n").replace("\r", "\\r")
        if trace_id is not None
        else None
    )
    logger.info(
        "Streaming completed, trace_id=%s, langfuse_initialized=%s",
        safe_trace_id,
        is_langfuse_initialized(),
    )
    if trace_id is not None:
        end_frame["trace_id"] = trace_id
    await websocket.send_json(end_frame)
    logger.info("Streaming completed for session: %s", session_id)


async def _handle_chat_turn(
    websocket: WebSocket,
    agent: Agent,
    chat_message: ChatMessage,
    session_id: str,
    visitor_id: str,
) -> None:
    """Stream one assistant reply, persisting turns when persistence is enabled."""
    repo = get_chat_history_repository()  # None when PERSISTENCE_DATABASE_URL is unset

    transcript = await _build_transcript(chat_message, visitor_id=visitor_id, repo=repo)

    stored_user_attachments: list[dict[str, str]] = []
    if repo is not None:
        stored_user_attachments_or_none = await _persist_user_turn(
            websocket,
            repo=repo,
            chat_message=chat_message,
            session_id=session_id,
            visitor_id=visitor_id,
        )
        if stored_user_attachments_or_none is None:
            return
        stored_user_attachments = stored_user_attachments_or_none

    resolved_answer = await _stream_assistant_response(
        websocket,
        agent,
        transcript,
        session_id=session_id,
        visitor_id=visitor_id,
        model=chat_message.model,
        auth_token=chat_message.auth_token,
    )
    sources = agent.get_last_used_sources()
    trace_id = agent.last_trace_id

    await _send_end_frame(
        websocket,
        session_id=session_id,
        resolved_answer=resolved_answer,
        sources=sources,
        stored_user_attachments=stored_user_attachments,
        trace_id=trace_id,
    )

    if repo is not None:
        try:
            await repo.append_message(
                visitor_id=visitor_id,
                session_id=session_id,
                role="assistant",
                content=resolved_answer,
                trace_id=trace_id,
                sources=json.dumps(sources) if sources else None,
            )
        except Exception:
            # The response has already been delivered to the client via the "end"
            # frame. Sending another frame here would violate the protocol contract
            # (clients treat "end" as terminal). Log and move on.
            logger.exception(
                "Failed to persist assistant message (session_id=%s); response already delivered",
                session_id,
            )


async def _parse_message(
    websocket: WebSocket, data: str, session_id: str
) -> ChatMessage | None:
    """Parse and validate a raw WebSocket payload.

    Sends an error frame and returns ``None`` on any parsing failure so the
    caller can ``continue`` the receive loop without extra branches.
    """
    try:
        message_data = json.loads(data)
        _validate_message_format(message_data)
        return ChatMessage(**message_data)
    except json.JSONDecodeError:
        error = InvalidJSONError()
        await _send_error(
            websocket,
            session_id=session_id,
            error_type=error.error_type,
            content=error.content,
        )
        logger.exception("Invalid JSON format")
    except InvalidMessageFormatError as invalid_message_error:
        await _send_error(
            websocket,
            session_id=session_id,
            error_type=invalid_message_error.error_type,
            content=invalid_message_error.content,
        )
        logger.exception("Message validation failed")
    except ValidationError:
        validation_error = ValidationFailedError()
        await _send_error(
            websocket,
            session_id=session_id,
            error_type=validation_error.error_type,
            content=validation_error.content,
        )
        logger.exception("Message validation failed")
    return None


async def _resolve_visitor_id(
    websocket: WebSocket,
    chat_message: ChatMessage,
    connection_visitor_id: str | None,
    session_id: str,
) -> tuple[str | None, str | None]:
    """Return ``(visitor_id, updated_connection_visitor_id)``.

    ``visitor_id`` is ``None`` when an error frame was sent and the caller
    should ``continue`` the receive loop.  When persistence is disabled and
    the client omits ``visitor_id``, a stable per-connection UUID is minted
    on first use and returned as the updated ``connection_visitor_id``.
    """
    if chat_message.visitor_id is not None:
        return chat_message.visitor_id, connection_visitor_id
    if is_persistence_enabled():
        await _send_error(
            websocket,
            session_id=session_id,
            error_type=WebSocketErrorType.MISSING_VISITOR_ID,
            content="visitor_id is required when chat history persistence is enabled",
        )
        return None, connection_visitor_id
    fallback = connection_visitor_id or str(uuid.uuid4())
    return fallback, fallback


@router.websocket("/ws")
async def websocket_chat(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for streaming chat with the agent.

    Expected message format (JSON):
    {
        "session_id": "optional-session-id",
        "visitor_id": "optional-stable-id-for-persistence",
        "messages": [
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": "..."},
            {"role": "user", "content": "current user message (required last)"}
        ]
    }

    Response format (JSON):
    {
        "type": "token" | "end" | "error",
        "content": "chunk of text" | null,
        "session_id": "session-id",
        "trace_id": "langfuse-trace-id"  # end frames only, omitted when Langfuse is disabled
    }
    """
    await websocket.accept()
    logger.info("WebSocket connection accepted")

    try:
        # Legacy products vector DB is disconnected — the Chatguru/Netguru
        # consultant persona uses the document RAG knowledge base (services,
        # case studies, etc.) instead. The Agent still registers
        # `search_products` as a no-op stub, but the system prompt no longer
        # mentions it, so the model has no reason to call it.
        document_repo = get_document_rag_repository()
        agent = Agent(
            vector_database=None,
            document_repository=document_repo,
            mcp_connections=get_mcp_connections(),
        )
        connection_visitor_id: str | None = None
        # Extract once per connection — the IP cannot change mid-WebSocket.
        client_ip = get_client_ip(websocket)

        while True:
            data = await websocket.receive_text()
            session_id = _extract_session_id(data)
            logger.info("Received websocket message, session_id: %s", session_id)

            chat_message = await _parse_message(websocket, data, session_id)
            if chat_message is None:
                continue

            session_id = (
                chat_message.session_id
                if chat_message.session_id is not None
                else "default"
            )
            visitor_id, connection_visitor_id = await _resolve_visitor_id(
                websocket, chat_message, connection_visitor_id, session_id
            )
            if visitor_id is None:
                continue

            # consume_rate_limit is skipped when client_ip is None (undetermined
            # IP) rather than sharing a single "unknown" bucket across all such
            # connections. The slot is consumed atomically before streaming begins
            # so that partial-stream failures still count against the quota.
            if client_ip is not None and not await consume_rate_limit(client_ip):
                await _send_error(
                    websocket,
                    session_id=session_id,
                    error_type=WebSocketErrorType.RATE_LIMIT_EXCEEDED,
                    content="Daily message limit reached. Please try again tomorrow.",
                )
                continue

            try:
                await _handle_chat_turn(
                    websocket, agent, chat_message, session_id, visitor_id
                )
            except Exception as e:
                logger.exception("Error during streaming:")
                app_settings = get_app_settings()
                error_content = (
                    f"An error occurred: {type(e).__name__}"
                    if app_settings.debug
                    else "An error occurred while processing your request."
                )
                await _send_error(
                    websocket,
                    session_id=session_id,
                    error_type=WebSocketErrorType.INTERNAL_ERROR,
                    content=error_content,
                )

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception:
        logger.exception("Unexpected error in websocket endpoint:")
        with contextlib.suppress(Exception):
            await websocket.close()
