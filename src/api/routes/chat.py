"""Chat API routes."""

import contextlib
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, ValidationError

from agent.service import Agent
from api.errors import InvalidMessageFormatError
from config import get_app_settings, get_logger
from vector_db import VectorDatabase, create_vector_database

logger = get_logger(__name__)


class HistoryMessage(BaseModel):
    """Individual message in conversation history."""

    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class ChatMessage(BaseModel):
    """Message model for websocket chat."""

    message: str = Field(..., description="User message", min_length=1, max_length=2000)
    session_id: str | None = Field(
        None, description="Session ID for conversation continuity"
    )
    messages: list[HistoryMessage] | None = Field(
        None, description="Conversation history for context awareness"
    )


router = APIRouter(tags=["chat"])


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

    _vector_database_initialized = True
    return _vector_database_cache


@router.websocket("/ws")
async def websocket_chat(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for streaming chat with the agent.

    Expected message format (JSON):
    {
        "message": "User message here",
        "session_id": "optional-session-id",
        "messages": [  // Optional conversation history
            {"role": "user", "content": "previous user message"},
            {"role": "assistant", "content": "previous assistant response"}
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
        # Initialize vector database (sqlite-vec service)
        vector_db = await _initialize_vector_database()
        agent = Agent(vector_database=vector_db)

        while True:
            data = await websocket.receive_text()
            logger.info("Received websocket message: %s", data)

            session_id = _extract_session_id(data)

            try:
                message_data = json.loads(data)
                _validate_message_format(message_data)
                chat_message = ChatMessage(**message_data)
            except json.JSONDecodeError:
                error_msg = {
                    "type": "error",
                    "content": "Invalid JSON format",
                    "session_id": session_id,
                }
                await websocket.send_json(error_msg)
                logger.exception("Invalid JSON format")
                continue
            except (ValidationError, InvalidMessageFormatError):
                error_msg = {
                    "type": "error",
                    "content": "Invalid message format or validation failed",
                    "session_id": session_id,
                }
                await websocket.send_json(error_msg)
                logger.exception("Message validation failed")
                continue

            session_id = (
                chat_message.session_id
                if chat_message.session_id is not None
                else "default"
            )

            try:
                # Convert history to list of dicts for agent
                history = None
                if chat_message.messages:
                    history = [
                        {"role": msg.role, "content": msg.content}
                        for msg in chat_message.messages
                    ]

                # Accumulate full response while streaming
                full_response = ""

                async for chunk in agent.astream(
                    chat_message.message,
                    history=history,
                    session_id=session_id,
                ):
                    full_response += chunk
                    await websocket.send_json(
                        {
                            "type": "token",
                            "content": chunk,
                            "session_id": session_id,
                        }
                    )

                # Send end signal with complete response as safety measure
                # This ensures the client has the full message even if some
                # token events were missed due to race conditions
                await websocket.send_json(
                    {
                        "type": "end",
                        "content": full_response,
                        "session_id": session_id,
                    }
                )
                logger.info("Streaming completed for session: %s", session_id)

            except Exception as e:
                logger.exception("Error during streaming:")
                app_settings = get_app_settings()
                error_content = (
                    f"An error occurred: {type(e).__name__}"
                    if app_settings.debug
                    else "An error occurred while processing your request."
                )
                error_msg = {
                    "type": "error",
                    "content": error_content,
                    "session_id": session_id,
                }
                await websocket.send_json(error_msg)

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception:
        logger.exception("Unexpected error in websocket endpoint:")
        with contextlib.suppress(Exception):
            await websocket.close()
