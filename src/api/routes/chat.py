"""Chat API routes."""

import asyncio
import contextlib
import json
import uuid
from typing import Annotated, Self

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, ValidationError, model_validator

from agent.service import Agent
from api.errors import (
    InvalidJSONError,
    InvalidMessageFormatError,
    ValidationFailedError,
    WebSocketErrorType,
)
from config import get_app_settings, get_logger, get_rate_limit_settings
from persistence import get_chat_history_repository, is_persistence_enabled
from rate_limiting import consume_rate_limit
from title_generation import generate_title, truncate_title
from vector_db import VectorDatabase, create_vector_database

logger = get_logger(__name__)


_MAX_CONTENT_LENGTH = 8000
_MAX_TRANSCRIPT_MESSAGES = 200
_MAX_LAST_USER_MESSAGE_LENGTH = 2000


class HistoryMessage(BaseModel):
    """Individual message in conversation history."""

    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(
        ..., max_length=_MAX_CONTENT_LENGTH, description="Message content"
    )


class ChatMessage(BaseModel):
    """WebSocket chat payload: full transcript including the current user turn last."""

    session_id: str | None = Field(
        None, description="Session ID for conversation continuity"
    )
    visitor_id: str | None = Field(
        None,
        description=(
            "Stable ID for persisted history (per device or user); "
            "required when persistence is enabled, otherwise a "
            "per-connection default is generated"
        ),
    )
    messages: list[HistoryMessage] = Field(
        default_factory=list,
        max_length=_MAX_TRANSCRIPT_MESSAGES,
        description="Full conversation for this request; last entry must be the current user message",
    )

    @model_validator(mode="after")
    def ensure_messages_valid(self) -> Self:
        if not self.messages:
            msg = "'messages' must be a non-empty array"
            raise ValueError(msg)

        last = self.messages[-1]
        if last.role != "user":
            msg = 'Last message in messages must have role "user" (current turn)'
            raise ValueError(msg)
        if len(last.content) < 1 or len(last.content) > _MAX_LAST_USER_MESSAGE_LENGTH:
            msg = "Last user message content must be between 1 and 2000 characters"
            raise ValueError(msg)
        return self


class GenerateConversationTitleRequest(BaseModel):
    """HTTP payload for generating a conversation title on demand."""

    visitor_id: str = Field(..., min_length=1, max_length=512, description="Visitor ID")
    session_id: str = Field(..., min_length=1, max_length=512, description="Session ID")
    first_message: str = Field(
        ...,
        min_length=1,
        max_length=_MAX_LAST_USER_MESSAGE_LENGTH,
        description="First user message used to generate the title",
    )


router = APIRouter(tags=["chat"])
persistence_router = APIRouter(tags=["history"])

# Strong references to background tasks so they aren't garbage-collected before completion.
_background_tasks: set[asyncio.Task] = set()


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


def _get_client_ip(websocket: WebSocket) -> str | None:
    """Extract the real client IP address from a WebSocket connection.

    Returns ``None`` when the IP cannot be determined (e.g. certain ASGI
    transports set ``websocket.client`` to ``None``). Callers must skip rate
    limiting for a ``None`` result rather than falling back to a shared key —
    a single shared key would let any one client exhaust the quota for every
    other client whose IP is unknown.

    When ``RATE_LIMIT_TRUST_PROXY`` is True, the ``X-Forwarded-For`` and
    ``X-Real-IP`` headers are checked first.  Only enable proxy trust when
    the application is behind a known, trusted reverse proxy — never in
    direct-to-internet deployments, as headers can be spoofed by clients.
    """
    if get_rate_limit_settings().trust_proxy:
        forwarded_for = websocket.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        real_ip = websocket.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
    client = websocket.client
    if client is None:
        logger.warning(
            "Cannot determine client IP — rate limiting skipped for this connection"
        )
        return None
    return client.host


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

    # Only mark as initialized when the database is actually reachable.
    # This intentionally allows retries on subsequent WebSocket connections
    # after a transient startup failure (e.g., vector-db container not ready yet).
    _vector_database_initialized = _vector_database_cache is not None
    return _vector_database_cache


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
    repo = get_chat_history_repository()
    if repo is None:
        msg = "persistence router registered but repository is not initialised"
        raise RuntimeError(msg)
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
) -> list[dict[str, str]]:
    """Return persisted messages for a visitor+session pair, oldest first.

    Note: visitor_id is client-supplied and not authenticated. This endpoint
    is intended for internal / single-tenant deployments. In multi-tenant
    scenarios, add an authentication layer before exposing this route.
    """
    repo = get_chat_history_repository()
    if repo is None:
        msg = "persistence router registered but repository is not initialised"
        raise RuntimeError(msg)
    messages = await repo.list_messages(visitor_id=visitor_id, session_id=session_id)
    return [{"role": m.role, "content": m.content} for m in messages]


@persistence_router.post("/conversations/title")
async def generate_conversation_title(
    payload: GenerateConversationTitleRequest,
) -> dict[str, str]:
    """Generate and persist a title for an existing conversation."""
    repo = get_chat_history_repository()
    if repo is None:
        msg = "persistence router registered but repository is not initialised"
        raise RuntimeError(msg)

    exists = await repo.conversation_exists(
        visitor_id=payload.visitor_id,
        session_id=payload.session_id,
    )
    if not exists:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found for visitor_id + session_id",
        )

    title = truncate_title(payload.first_message)
    try:
        title = await generate_title(payload.first_message)
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


async def _handle_chat_turn(
    websocket: WebSocket,
    agent: Agent,
    chat_message: ChatMessage,
    session_id: str,
    visitor_id: str,
) -> None:
    """Stream one assistant reply, persisting turns when persistence is enabled."""
    repo = get_chat_history_repository()  # None when PERSISTENCE_DATABASE_URL is unset
    current_user_content = chat_message.messages[-1].content
    transcript = [{"role": m.role, "content": m.content} for m in chat_message.messages]

    if repo is not None:
        # Check server-side whether a conversation record already exists for this
        # session.  This is authoritative regardless of how many messages the client
        # sends in the transcript, and prevents redundant title-generation calls when
        # clients reconnect without full history.  A lightweight SELECT 1 is used
        # instead of fetching all stored messages.
        is_first_message = not await repo.conversation_exists(
            visitor_id=visitor_id, session_id=session_id
        )
        if is_first_message:
            fallback_title = truncate_title(current_user_content)
            try:
                await repo.create_conversation(
                    visitor_id=visitor_id,
                    session_id=session_id,
                    # Store a fast fallback title immediately so the sidebar shows
                    # something right away. The background task below will replace
                    # it with an LLM-generated title once the call completes.
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
            await repo.append_message(
                visitor_id=visitor_id,
                session_id=session_id,
                role="user",
                content=current_user_content,
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
            return

    full_response = ""
    async for chunk in agent.astream(
        transcript,
        session_id=session_id,
        visitor_id=visitor_id,
    ):
        full_response += chunk
        await websocket.send_json(
            {
                "type": "token",
                "content": chunk,
                "session_id": session_id,
            }
        )

    await websocket.send_json(
        {
            "type": "end",
            "content": full_response,
            "session_id": session_id,
        }
    )
    logger.info("Streaming completed for session: %s", session_id)

    if repo is not None:
        try:
            await repo.append_message(
                visitor_id=visitor_id,
                session_id=session_id,
                role="assistant",
                content=full_response,
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
        "session_id": "session-id"
    }
    """
    await websocket.accept()
    logger.info("WebSocket connection accepted")

    try:
        vector_db = await _initialize_vector_database()
        agent = Agent(vector_database=vector_db)
        connection_visitor_id: str | None = None
        # Extract once per connection — the IP cannot change mid-WebSocket.
        client_ip = _get_client_ip(websocket)

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
