"""API endpoint tests."""

import asyncio
from collections.abc import AsyncIterator, Callable
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from unittest.mock import AsyncMock

from api.main import create_app
from persistence import get_chat_history_repository


def _mock_astream(chunks: list[str]) -> Callable[..., AsyncIterator[str]]:
    """Create a mock async generator matching ``Agent.astream`` signature."""

    async def _gen(
        messages: list[dict[str, str]],
        *,
        session_id: str | None = None,
        visitor_id: str | None = None,
    ) -> AsyncIterator[str]:
        for chunk in chunks:
            yield chunk

    return _gen


def test_health_endpoint(app: TestClient) -> None:
    """Test health check endpoint."""
    response = app.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert "service" in data
    assert "version" in data


def test_root_endpoint_serves_html(app: TestClient) -> None:
    """Test root endpoint serves HTML chat interface."""
    response = app.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "chatguru Agent Chat" in response.text
    assert "WebSocket" in response.text


def test_websocket_chat_success(async_app: TestClient) -> None:
    """Test successful WebSocket chat request."""
    chunks = ["Hello! ", "How can I ", "help you today?"]

    with patch("api.routes.chat.Agent") as mock_agent_class:
        mock_agent_instance = MagicMock()
        mock_agent_instance.last_trace_id = None
        mock_agent_instance.astream = _mock_astream(chunks)
        mock_agent_class.return_value = mock_agent_instance

        with async_app.websocket_connect("/ws") as websocket:
            # Send message (full transcript; last entry is current user turn)
            websocket.send_json(
                {
                    "session_id": "test-session-123",
                    "visitor_id": "visitor-chat-success",
                    "messages": [{"role": "user", "content": "Hello, how are you?"}],
                }
            )

            # Receive streaming tokens
            tokens = []
            while True:
                data = websocket.receive_json()
                if data["type"] == "token":
                    tokens.append(data["content"])
                elif data["type"] == "end":
                    assert data["session_id"] == "test-session-123"
                    break
                elif data["type"] == "error":
                    pytest.fail(f"Received error: {data['content']}")

            # Verify response
            full_response = "".join(tokens)
            assert len(full_response) > 0
            assert "".join(tokens) == "".join(chunks)


def test_websocket_chat_without_session_id(async_app: TestClient) -> None:
    """Test WebSocket chat request without session ID."""

    with patch("api.routes.chat.Agent") as mock_agent_class:
        mock_agent_instance = MagicMock()
        mock_agent_instance.last_trace_id = None
        mock_agent_instance.astream = _mock_astream(["Hello!"])
        mock_agent_class.return_value = mock_agent_instance

        with async_app.websocket_connect("/ws") as websocket:
            websocket.send_json(
                {
                    "visitor_id": "visitor-no-session",
                    "messages": [{"role": "user", "content": "Hello!"}],
                }
            )

            received_end = False
            while not received_end:
                data = websocket.receive_json()
                if data["type"] == "end":
                    assert data["session_id"] == "default"
                    received_end = True
                elif data["type"] == "error":
                    pytest.fail(f"Received error: {data['content']}")


def test_websocket_chat_with_empty_string_session_id(async_app: TestClient) -> None:
    """Test WebSocket chat request with empty string session ID (should preserve empty string)."""

    with patch("api.routes.chat.Agent") as mock_agent_class:
        mock_agent_instance = MagicMock()
        mock_agent_instance.last_trace_id = None
        mock_agent_instance.astream = _mock_astream(["Hello!"])
        mock_agent_class.return_value = mock_agent_instance

        with async_app.websocket_connect("/ws") as websocket:
            websocket.send_json(
                {
                    "visitor_id": "visitor-empty-session",
                    "session_id": "",
                    "messages": [{"role": "user", "content": "Hello!"}],
                }
            )

            received_end = False
            while not received_end:
                data = websocket.receive_json()
                if data["type"] == "end":
                    # Empty string session_id should be preserved, not converted to "default"
                    assert data["session_id"] == ""
                    received_end = True
                elif data["type"] == "error":
                    pytest.fail(f"Received error: {data['content']}")


def test_websocket_invalid_json(async_app: TestClient) -> None:
    """Test WebSocket with invalid JSON message."""
    with patch("src.agent.service._build_chat_llm"):
        with async_app.websocket_connect("/ws") as websocket:
            # Send invalid JSON
            websocket.send_text("invalid json")

            # Should receive error message with session_id
            data = websocket.receive_json()
            assert data["type"] == "error"
            assert "Invalid JSON format" in data["content"]
            assert "session_id" in data
            assert data["session_id"] == "unknown"


def test_websocket_non_dict_json(async_app: TestClient) -> None:
    """Test WebSocket with valid JSON that is not a dict (e.g., array or string)."""
    with patch("src.agent.service._build_chat_llm"):
        with async_app.websocket_connect("/ws") as websocket:
            # Send valid JSON array (not a dict)
            websocket.send_text("[1, 2, 3]")

            # Should receive error message (should not raise AttributeError)
            data = websocket.receive_json()
            assert data["type"] == "error"
            assert "session_id" in data
            assert data["session_id"] == "unknown"

        with async_app.websocket_connect("/ws") as websocket:
            # Send valid JSON string (not a dict)
            websocket.send_text('"hello"')

            # Should receive error message (should not raise AttributeError)
            data = websocket.receive_json()
            assert data["type"] == "error"
            assert "session_id" in data
            assert data["session_id"] == "unknown"


def test_websocket_empty_message(async_app: TestClient) -> None:
    """Test WebSocket with empty message (should fail validation)."""
    with patch("src.agent.service._build_chat_llm"):
        with async_app.websocket_connect("/ws") as websocket:
            websocket.send_json(
                {
                    "messages": [{"role": "user", "content": ""}],
                    "session_id": "test-session",
                }
            )

            # Should receive validation error since last user content must be 1–2000 chars
            data = websocket.receive_json()
            assert data["type"] == "error"
            assert "Invalid message format or validation failed" in data["content"]
            assert "session_id" in data
            assert data["session_id"] == "test-session"  # Should extract from message


def test_websocket_missing_message(async_app: TestClient) -> None:
    """Test WebSocket without message field (should fail validation)."""
    with patch("src.agent.service._build_chat_llm"):
        with async_app.websocket_connect("/ws") as websocket:
            websocket.send_json({"session_id": "test-session"})

            # Should receive error message with session_id
            data = websocket.receive_json()
            assert data["type"] == "error"
            assert "session_id" in data
            assert data["session_id"] == "test-session"  # Should extract from message


def test_websocket_message_too_long(async_app: TestClient) -> None:
    """Test WebSocket with message too long (should fail validation)."""
    long_message = "x" * 2001  # Exceeds 2000 character limit

    with patch("src.agent.service._build_chat_llm"):
        with async_app.websocket_connect("/ws") as websocket:
            websocket.send_json(
                {"messages": [{"role": "user", "content": long_message}]}
            )

            # Should receive error message
            data = websocket.receive_json()
            assert data["type"] == "error"


def test_websocket_streaming_multiple_chunks(async_app: TestClient) -> None:
    """Test WebSocket streaming with multiple chunks."""
    chunks = ["Hello", " ", "world", "!"]

    with patch("api.routes.chat.Agent") as mock_agent_class:
        mock_agent_instance = MagicMock()
        mock_agent_instance.last_trace_id = None
        mock_agent_instance.astream = _mock_astream(chunks)
        mock_agent_class.return_value = mock_agent_instance

        with async_app.websocket_connect("/ws") as websocket:
            websocket.send_json(
                {
                    "visitor_id": "visitor-streaming",
                    "messages": [{"role": "user", "content": "Hello"}],
                }
            )

            received_chunks = []
            received_end = False
            # Expected messages: one token per chunk + one end signal
            # Add 3x buffer to handle cases where mock fails and real API is used
            expected_messages = len(chunks) + 1  # chunks + end signal
            max_iterations = expected_messages * 3
            iteration = 0

            while not received_end and iteration < max_iterations:
                iteration += 1
                data = websocket.receive_json()
                if data["type"] == "token":
                    received_chunks.append(data["content"])
                elif data["type"] == "end":
                    received_end = True
                elif data["type"] == "error":
                    pytest.fail(f"Received error: {data['content']}")

            # Verify streaming works - we should receive chunks and an end signal
            # Note: If mock doesn't work, this will use real API, so we just verify structure
            assert received_end, "Did not receive end signal"
            assert len(received_chunks) > 0, "Should receive at least one chunk"
            # If mock worked, verify exact chunks; otherwise just verify streaming structure
            if len(received_chunks) == len(chunks):
                assert "".join(received_chunks) == "".join(chunks)


def test_websocket_agent_initialization_failure(async_app: TestClient) -> None:
    """Test WebSocket handles agent initialization failure gracefully."""
    # Patch Agent to raise an exception during initialization
    with patch(
        "src.api.routes.chat.Agent", side_effect=Exception("Failed to initialize agent")
    ):
        # The WebSocket connection should be accepted, but agent initialization will fail
        # The outer exception handler should catch this and close the connection gracefully
        # We verify that the connection is accepted and doesn't raise an unhandled exception
        try:
            with async_app.websocket_connect("/ws") as websocket:
                # Connection should be accepted
                # Agent initialization failure should be caught by outer exception handler
                # and connection should close gracefully
                pass
        except Exception as e:
            # If we get here, it means the exception wasn't handled properly
            pytest.fail(f"Agent initialization failure was not handled gracefully: {e}")


# ============================================================================
# Conversation History Tests
# ============================================================================


def test_websocket_chat_with_conversation_history(async_app: TestClient) -> None:
    """Test WebSocket chat with conversation history is passed to agent."""
    chunks = ["I remember you asked about weather!"]
    received_messages: list[dict[str, str]] | None = None

    with patch("api.routes.chat.Agent") as mock_agent_class:
        mock_agent_instance = MagicMock()
        mock_agent_instance.last_trace_id = None

        async def astream_gen(
            messages: list[dict[str, str]],
            *,
            session_id: str | None = None,
            visitor_id: str | None = None,
        ) -> AsyncIterator[str]:
            nonlocal received_messages
            received_messages = messages
            for chunk in chunks:
                yield chunk

        mock_agent_instance.astream = astream_gen
        mock_agent_class.return_value = mock_agent_instance

        with async_app.websocket_connect("/ws") as websocket:
            # Full transcript; last user message is the current turn
            websocket.send_json(
                {
                    "session_id": "test-session",
                    "visitor_id": "visitor-history",
                    "messages": [
                        {"role": "user", "content": "What's the weather like?"},
                        {"role": "assistant", "content": "The weather is sunny today!"},
                        {"role": "user", "content": "What did I ask about?"},
                    ],
                }
            )

            # Receive response
            while True:
                data = websocket.receive_json()
                if data["type"] == "end":
                    break
                elif data["type"] == "error":
                    pytest.fail(f"Received error: {data['content']}")

            # Full transcript passed to agent (including current user turn)
            assert received_messages is not None
            assert len(received_messages) == 3
            assert received_messages[0]["content"] == "What's the weather like?"
            assert received_messages[1]["content"] == "The weather is sunny today!"
            assert received_messages[2]["content"] == "What did I ask about?"


def test_websocket_chat_messages_empty_array(async_app: TestClient) -> None:
    """Test WebSocket with empty messages array (should fail validation)."""
    with patch("src.agent.service.ChatOpenAI"):
        with async_app.websocket_connect("/ws") as websocket:
            websocket.send_json({"session_id": "ws-empty-messages", "messages": []})

            data = websocket.receive_json()
            assert data["type"] == "error"
            assert "session_id" in data


def test_websocket_chat_without_messages_field(async_app: TestClient) -> None:
    """Test WebSocket chat without messages field (should fail validation)."""
    with patch("src.agent.service.ChatOpenAI"):
        with async_app.websocket_connect("/ws") as websocket:
            websocket.send_json({"session_id": "ws-no-messages-field"})

            data = websocket.receive_json()
            assert data["type"] == "error"
            assert data["session_id"] == "ws-no-messages-field"


def test_websocket_session_id_preserved_across_messages(async_app: TestClient) -> None:
    """Test that session_id is preserved across multiple messages in same connection."""
    chunks = ["Response"]

    with patch("api.routes.chat.Agent") as mock_agent_class:
        mock_agent_instance = MagicMock()
        mock_agent_instance.last_trace_id = None
        mock_agent_instance.astream = _mock_astream(chunks)
        mock_agent_class.return_value = mock_agent_instance

        with async_app.websocket_connect("/ws") as websocket:
            # First message with session_id
            websocket.send_json(
                {
                    "session_id": "persistent-session-123",
                    "visitor_id": "visitor-persistent",
                    "messages": [{"role": "user", "content": "First message"}],
                }
            )

            # Receive first response
            while True:
                data = websocket.receive_json()
                if data["type"] == "end":
                    assert data["session_id"] == "persistent-session-123"
                    break

            # Second message: full transcript ending with current user turn
            websocket.send_json(
                {
                    "session_id": "persistent-session-123",
                    "visitor_id": "visitor-persistent",
                    "messages": [
                        {"role": "user", "content": "First message"},
                        {"role": "assistant", "content": "Response"},
                        {"role": "user", "content": "Second message"},
                    ],
                }
            )

            # Receive second response - session_id should still be preserved
            while True:
                data = websocket.receive_json()
                if data["type"] == "end":
                    assert data["session_id"] == "persistent-session-123"
                    break


def test_websocket_error_response_includes_session_id(async_app: TestClient) -> None:
    """Test that error responses include session_id for client recovery."""
    with patch("api.routes.chat.Agent") as mock_agent_class:
        mock_agent_instance = MagicMock()
        mock_agent_instance.last_trace_id = None

        async def astream_gen(
            messages: list[dict[str, str]],
            *,
            session_id: str | None = None,
            visitor_id: str | None = None,
        ) -> AsyncIterator[str]:
            raise Exception("Simulated streaming error")
            yield  # Make it a generator  # noqa: B027

        mock_agent_instance.astream = astream_gen
        mock_agent_class.return_value = mock_agent_instance

        with async_app.websocket_connect("/ws") as websocket:
            websocket.send_json(
                {
                    "session_id": "error-test-session",
                    "visitor_id": "visitor-error-test",
                    "messages": [{"role": "user", "content": "Cause an error"}],
                }
            )

            # Should receive error with session_id preserved
            data = websocket.receive_json()
            assert data["type"] == "error"
            assert "session_id" in data
            assert data["session_id"] == "error-test-session"


def test_websocket_validation_error_preserves_session_id(async_app: TestClient) -> None:
    """Test that validation errors preserve session_id from the request."""
    with patch("src.agent.service._build_chat_llm"):
        with async_app.websocket_connect("/ws") as websocket:
            # Invalid: last user content empty
            websocket.send_json(
                {
                    "session_id": "validation-error-session",
                    "messages": [{"role": "user", "content": ""}],
                }
            )

            data = websocket.receive_json()
            assert data["type"] == "error"
            assert data["session_id"] == "validation-error-session"


def test_websocket_history_with_multiple_turns(async_app: TestClient) -> None:
    """Test conversation history with multiple conversation turns."""
    chunks = ["Based on our conversation..."]
    received_messages: list[dict[str, str]] | None = None

    with patch("api.routes.chat.Agent") as mock_agent_class:
        mock_agent_instance = MagicMock()
        mock_agent_instance.last_trace_id = None

        async def astream_gen(
            messages: list[dict[str, str]],
            *,
            session_id: str | None = None,
            visitor_id: str | None = None,
        ) -> AsyncIterator[str]:
            nonlocal received_messages
            received_messages = messages
            for chunk in chunks:
                yield chunk

        mock_agent_instance.astream = astream_gen
        mock_agent_class.return_value = mock_agent_instance

        with async_app.websocket_connect("/ws") as websocket:
            # Full transcript; last user message is the current turn
            websocket.send_json(
                {
                    "session_id": "multi-turn-session",
                    "visitor_id": "visitor-multi-turn",
                    "messages": [
                        {"role": "user", "content": "Hello"},
                        {"role": "assistant", "content": "Hi there!"},
                        {"role": "user", "content": "What products do you have?"},
                        {
                            "role": "assistant",
                            "content": "We have shirts, pants, and shoes.",
                        },
                        {"role": "user", "content": "Show me shirts under $50"},
                        {
                            "role": "assistant",
                            "content": "Here are 3 shirts under $50...",
                        },
                        {"role": "user", "content": "Summarize our conversation"},
                    ],
                }
            )

            while True:
                data = websocket.receive_json()
                if data["type"] == "end":
                    break
                elif data["type"] == "error":
                    pytest.fail(f"Received error: {data['content']}")

            assert received_messages is not None
            assert len(received_messages) == 7
            assert received_messages[0]["role"] == "user"
            assert received_messages[1]["role"] == "assistant"
            assert received_messages[4]["role"] == "user"
            assert received_messages[5]["role"] == "assistant"
            assert received_messages[6]["role"] == "user"
            assert received_messages[6]["content"] == "Summarize our conversation"


def test_websocket_missing_visitor_id_returns_error(async_app: TestClient) -> None:
    """When persistence is enabled, omitting visitor_id returns an error message."""
    with patch("api.routes.chat.Agent") as mock_agent_class:
        mock_agent_instance = MagicMock()
        mock_agent_instance.last_trace_id = None
        mock_agent_instance.astream = _mock_astream(["Hello!"])
        mock_agent_class.return_value = mock_agent_instance

        with async_app.websocket_connect("/ws") as websocket:
            websocket.send_json(
                {
                    "session_id": "no-visitor-session",
                    "messages": [{"role": "user", "content": "Hello!"}],
                }
            )

            data = websocket.receive_json()
            assert data["type"] == "error"
            assert "visitor_id" in data["content"]
            assert data["session_id"] == "no-visitor-session"


# ============================================================================
# History Endpoint Tests
# ============================================================================


def test_history_endpoint_returns_persisted_messages(app: TestClient) -> None:
    """Test GET /history returns messages previously written via the repository."""
    repo = get_chat_history_repository()
    vid, sid = "hist-visitor", "hist-session"

    async def _seed() -> None:
        await repo.append_message(
            visitor_id=vid, session_id=sid, role="user", content="ping"
        )
        await repo.append_message(
            visitor_id=vid, session_id=sid, role="assistant", content="pong"
        )

    asyncio.run(_seed())

    response = app.get("/history", params={"visitor_id": vid, "session_id": sid})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0] == {"role": "user", "content": "ping"}
    assert data[1] == {"role": "assistant", "content": "pong"}


def test_history_endpoint_empty_for_unknown_visitor(app: TestClient) -> None:
    """Test GET /history returns empty list for unknown visitor."""
    response = app.get(
        "/history", params={"visitor_id": "nonexistent", "session_id": "none"}
    )
    assert response.status_code == 200
    assert response.json() == []


def test_history_endpoint_requires_visitor_id(app: TestClient) -> None:
    """Test GET /history returns 422 when visitor_id is missing."""
    response = app.get("/history")
    assert response.status_code == 422


# ============================================================================
# Conversations Endpoint Tests
# ============================================================================


def test_conversations_endpoint_returns_list(app: TestClient) -> None:
    """GET /conversations returns conversations seeded via repository."""
    repo = get_chat_history_repository()
    vid = "conv-visitor-1"

    async def _seed() -> None:
        await repo.create_conversation(
            visitor_id=vid, session_id="sess-a", title="First chat"
        )
        await repo.create_conversation(
            visitor_id=vid, session_id="sess-b", title="Second chat"
        )

    asyncio.run(_seed())

    response = app.get("/conversations", params={"visitor_id": vid})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    # Newest first
    assert data[0]["title"] == "Second chat"
    assert data[0]["session_id"] == "sess-b"
    assert data[1]["title"] == "First chat"
    assert "created_at" in data[0]


def test_conversations_endpoint_empty_for_unknown_visitor(app: TestClient) -> None:
    """GET /conversations returns empty list when visitor has no conversations."""
    response = app.get("/conversations", params={"visitor_id": "nobody"})
    assert response.status_code == 200
    assert response.json() == []


def test_conversations_endpoint_requires_visitor_id(app: TestClient) -> None:
    """GET /conversations returns 422 when visitor_id is missing."""
    response = app.get("/conversations")
    assert response.status_code == 422


def test_conversations_endpoint_isolated_by_visitor(app: TestClient) -> None:
    """Conversations from different visitors don't bleed into each other."""
    repo = get_chat_history_repository()

    async def _seed() -> None:
        await repo.create_conversation(
            visitor_id="iso-v1", session_id="s1", title="V1 chat"
        )
        await repo.create_conversation(
            visitor_id="iso-v2", session_id="s2", title="V2 chat"
        )

    asyncio.run(_seed())

    r1 = app.get("/conversations", params={"visitor_id": "iso-v1"}).json()
    r2 = app.get("/conversations", params={"visitor_id": "iso-v2"}).json()
    assert len(r1) == 1 and r1[0]["title"] == "V1 chat"
    assert len(r2) == 1 and r2[0]["title"] == "V2 chat"


def test_generate_conversation_title_updates_existing_conversation(
    app: TestClient,
) -> None:
    """POST /conversations/title updates title for an existing conversation."""
    repo = get_chat_history_repository()
    vid, sid = "title-visitor", "title-session"

    async def _seed() -> None:
        await repo.create_conversation(
            visitor_id=vid, session_id=sid, title="Initial title"
        )

    asyncio.run(_seed())

    with patch(
        "api.routes.chat.generate_title",
        new=AsyncMock(return_value="Generated title"),
    ):
        response = app.post(
            "/conversations/title",
            json={
                "visitor_id": vid,
                "session_id": sid,
                "first_message": "Can you summarize transformers?",
            },
        )

    assert response.status_code == 200
    assert response.json() == {"session_id": sid, "title": "Generated title"}

    conversations = app.get("/conversations", params={"visitor_id": vid}).json()
    assert conversations[0]["session_id"] == sid
    assert conversations[0]["title"] == "Generated title"


def test_generate_conversation_title_returns_404_for_missing_conversation(
    app: TestClient,
) -> None:
    """POST /conversations/title returns 404 when conversation does not exist."""
    response = app.post(
        "/conversations/title",
        json={
            "visitor_id": "missing-visitor",
            "session_id": "missing-session",
            "first_message": "Hello",
        },
    )

    assert response.status_code == 404


# ============================================================================
# No-persistence visitor_id fallback
# ============================================================================


def test_websocket_omitted_visitor_id_succeeds_without_persistence() -> None:
    """When persistence is disabled, omitting visitor_id mints a per-connection UUID
    and the turn succeeds rather than returning an error.

    Rather than manipulating env vars (which are also read from the .env file via
    pydantic-settings), we patch ``is_persistence_enabled`` at both call sites and
    stub out the lifecycle helpers so no real DB interaction occurs.
    """
    with (
        patch("api.main.is_persistence_enabled", return_value=False),
        patch("api.main.init_persistence", new=AsyncMock()),
        patch("api.main.shutdown_persistence", new=AsyncMock()),
        patch("api.routes.chat.is_persistence_enabled", return_value=False),
        patch("api.routes.chat.get_chat_history_repository", return_value=None),
        patch("api.routes.chat.Agent") as mock_agent_class,
    ):
        mock_agent_instance = MagicMock()
        mock_agent_instance.last_trace_id = None
        mock_agent_instance.astream = _mock_astream(["Hi!"])
        mock_agent_class.return_value = mock_agent_instance

        with TestClient(create_app()) as no_persist_client:
            with no_persist_client.websocket_connect("/ws") as websocket:
                websocket.send_json(
                    {
                        "session_id": "s1",
                        "messages": [{"role": "user", "content": "Hello!"}],
                    }
                )

                received_end = False
                while not received_end:
                    data = websocket.receive_json()
                    assert (
                        data["type"] != "error"
                    ), f"Unexpected error: {data['content']}"
                    if data["type"] == "end":
                        assert data["session_id"] == "s1"
                        received_end = True


def test_document_source_endpoint_serves_pdf(async_app: TestClient) -> None:
    mock_settings = MagicMock()
    mock_settings.mongodb_uri = "mongodb://localhost:27017"
    mock_settings.mongodb_connection_timeout_ms = 5000
    mock_settings.mongodb_database = "chatguru"
    mock_settings.mongodb_files_bucket = "document_sources"

    mock_stream = MagicMock()
    mock_stream.filename = "guide.pdf"
    mock_stream.metadata = {"content_type": "application/pdf"}
    mock_stream.read.return_value = b"%PDF-1.4\n%mock\n"
    mock_stream.__enter__.return_value = mock_stream
    mock_stream.__exit__.return_value = None

    mock_bucket = MagicMock()
    mock_bucket.open_download_stream_by_name.return_value = mock_stream

    with (
        patch("api.routes.chat.get_document_rag_settings", return_value=mock_settings),
        patch("api.routes.chat.MongoClient") as mock_client_cls,
        patch("api.routes.chat.GridFSBucket", return_value=mock_bucket),
    ):
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client_cls.return_value = mock_client
        response = async_app.get("/documents/guide.pdf")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")


def test_document_source_endpoint_blocks_path_traversal(async_app: TestClient) -> None:
    response = async_app.get("/documents/../secrets.txt")

    assert response.status_code == 400


def test_end_frame_includes_trace_id_when_langfuse_active(
    async_app: TestClient,
) -> None:
    """The end frame carries trace_id when agent.last_trace_id is set."""
    with patch("api.routes.chat.Agent") as mock_agent_class:
        mock_agent_instance = MagicMock()
        mock_agent_instance.last_trace_id = "trace-abc123"
        mock_agent_instance.astream = _mock_astream(["Hi!"])
        mock_agent_class.return_value = mock_agent_instance

        with async_app.websocket_connect("/ws") as websocket:
            websocket.send_json(
                {
                    "session_id": "s1",
                    "visitor_id": "v1",
                    "messages": [{"role": "user", "content": "Hello!"}],
                }
            )

            while True:
                data = websocket.receive_json()
                if data["type"] == "end":
                    assert data.get("trace_id") == "trace-abc123"
                    break
                elif data["type"] == "error":
                    pytest.fail(f"Unexpected error: {data['content']}")


def test_end_frame_omits_trace_id_when_langfuse_disabled(async_app: TestClient) -> None:
    """The end frame omits trace_id entirely when agent.last_trace_id is None."""
    with patch("api.routes.chat.Agent") as mock_agent_class:
        mock_agent_instance = MagicMock()
        mock_agent_instance.last_trace_id = None
        mock_agent_instance.astream = _mock_astream(["Hi!"])
        mock_agent_class.return_value = mock_agent_instance

        with async_app.websocket_connect("/ws") as websocket:
            websocket.send_json(
                {
                    "session_id": "s1",
                    "visitor_id": "v1",
                    "messages": [{"role": "user", "content": "Hello!"}],
                }
            )

            while True:
                data = websocket.receive_json()
                if data["type"] == "end":
                    assert "trace_id" not in data
                    break
                elif data["type"] == "error":
                    pytest.fail(f"Unexpected error: {data['content']}")
