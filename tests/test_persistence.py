"""Tests for chat history persistence (repository port + factory)."""

import asyncio
import os
from datetime import UTC
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine.url import URL

from api.main import create_app
from config import PersistenceSettings, get_persistence_settings
from persistence import (
    build_chat_history_repository,
    get_chat_history_repository,
    init_persistence,
    shutdown_persistence,
)
from persistence import upgrade_head
from persistence.repository import ChatHistoryRepository


async def _open_repo(db_path: Path) -> ChatHistoryRepository:
    database_url = str(URL.create("sqlite+aiosqlite", database=str(db_path.resolve())))
    previous = os.environ.get("PERSISTENCE_DATABASE_URL")
    os.environ["PERSISTENCE_DATABASE_URL"] = database_url
    get_persistence_settings.cache_clear()
    try:
        upgrade_head()
        return await build_chat_history_repository(
            PersistenceSettings(database_url=database_url),
        )
    finally:
        if previous is None:
            os.environ.pop("PERSISTENCE_DATABASE_URL", None)
        else:
            os.environ["PERSISTENCE_DATABASE_URL"] = previous
        get_persistence_settings.cache_clear()


@pytest.mark.asyncio
async def test_append_and_list_messages_roundtrip(tmp_path: Path) -> None:
    repo = await _open_repo(tmp_path / "history.db")
    try:
        await repo.append_message(
            visitor_id="v1",
            session_id="s1",
            role="user",
            content="hello",
        )
        await repo.append_message(
            visitor_id="v1",
            session_id="s1",
            role="assistant",
            content="hi",
        )
        messages = await repo.list_messages(visitor_id="v1", session_id="s1")
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[0].content == "hello"
        assert messages[0].created_at.tzinfo is not None
        assert messages[0].created_at.astimezone(UTC).tzinfo is not None
        assert messages[1].role == "assistant"
        assert messages[1].content == "hi"
    finally:
        await repo.close()


@pytest.mark.asyncio
async def test_sessions_isolated_by_visitor_and_session(tmp_path: Path) -> None:
    repo = await _open_repo(tmp_path / "history.db")
    try:
        await repo.append_message(
            visitor_id="a", session_id="x", role="user", content="1"
        )
        await repo.append_message(
            visitor_id="b", session_id="x", role="user", content="2"
        )
        await repo.append_message(
            visitor_id="a", session_id="y", role="user", content="3"
        )

        ax = await repo.list_messages(visitor_id="a", session_id="x")
        assert len(ax) == 1 and ax[0].content == "1"

        bx = await repo.list_messages(visitor_id="b", session_id="x")
        assert len(bx) == 1 and bx[0].content == "2"

        ay = await repo.list_messages(visitor_id="a", session_id="y")
        assert len(ay) == 1 and ay[0].content == "3"
    finally:
        await repo.close()


@pytest.mark.asyncio
async def test_empty_string_session_id_preserved(tmp_path: Path) -> None:
    repo = await _open_repo(tmp_path / "history.db")
    try:
        await repo.append_message(
            visitor_id="v", session_id="", role="user", content="edge"
        )
        rows = await repo.list_messages(visitor_id="v", session_id="")
        assert len(rows) == 1
        assert rows[0].session_id == ""
    finally:
        await repo.close()


@pytest.mark.asyncio
async def test_invalid_role_rejected(tmp_path: Path) -> None:
    repo = await _open_repo(tmp_path / "history.db")
    try:
        with pytest.raises(ValueError, match="Invalid role"):
            await repo.append_message(
                visitor_id="v",
                session_id="s",
                role="system",
                content="nope",
            )
    finally:
        await repo.close()


def test_app_lifespan_initializes_persistence(
    test_env_vars: dict[str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FastAPI lifespan wires init/shutdown (uses tmp DB path).

    This is intentionally a *sync* test: ``TestClient`` drives the ASGI
    lifespan on its own internal event loop, so we must not already be inside
    an asyncio loop when entering the ``with TestClient(...)`` block.
    ``asyncio.run()`` is used for the tiny async setup/teardown calls that
    happen *outside* the client context, where no loop is running.
    """
    asyncio.run(shutdown_persistence())

    db_file = tmp_path / "app.db"
    database_url = str(URL.create("sqlite+aiosqlite", database=str(db_file.resolve())))
    monkeypatch.setenv("PERSISTENCE_DATABASE_URL", database_url)
    get_persistence_settings.cache_clear()
    upgrade_head()

    async def _append() -> None:
        repo = get_chat_history_repository()
        await repo.append_message(
            visitor_id="v", session_id="s", role="user", content="ok"
        )

    try:
        with TestClient(create_app()) as client:
            client.get("/health")
            asyncio.run(_append())
    finally:
        asyncio.run(shutdown_persistence())
        get_persistence_settings.cache_clear()

    assert db_file.is_file()


@pytest.mark.asyncio
async def test_shutdown_persistence_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = str(
        URL.create("sqlite+aiosqlite", database=str((tmp_path / "once.db").resolve()))
    )
    monkeypatch.setenv("PERSISTENCE_DATABASE_URL", database_url)
    get_persistence_settings.cache_clear()
    upgrade_head()

    await shutdown_persistence()
    await shutdown_persistence()
    get_persistence_settings.cache_clear()


# ============================================================================
# Conversation repository tests
# ============================================================================


@pytest.mark.asyncio
async def test_create_and_list_conversations(tmp_path: Path) -> None:
    repo = await _open_repo(tmp_path / "convos.db")
    try:
        c1 = await repo.create_conversation(
            visitor_id="v1", session_id="s1", title="Hello world"
        )
        c2 = await repo.create_conversation(
            visitor_id="v1", session_id="s2", title="Another one"
        )

        assert c1.session_id == "s1"
        assert c1.title == "Hello world"
        assert c1.created_at.tzinfo is not None

        convos = await repo.list_conversations(visitor_id="v1")
        assert len(convos) == 2
        # Newest first
        assert convos[0].session_id == "s2"
        assert convos[1].session_id == "s1"
    finally:
        await repo.close()


@pytest.mark.asyncio
async def test_create_conversation_is_idempotent(tmp_path: Path) -> None:
    repo = await _open_repo(tmp_path / "idem.db")
    try:
        first = await repo.create_conversation(
            visitor_id="v", session_id="s", title="Original"
        )
        second = await repo.create_conversation(
            visitor_id="v", session_id="s", title="Different title"
        )

        # Returns the original; doesn't overwrite
        assert second.title == "Original"
        assert second.id == first.id

        convos = await repo.list_conversations(visitor_id="v")
        assert len(convos) == 1
    finally:
        await repo.close()


@pytest.mark.asyncio
async def test_update_conversation_title(tmp_path: Path) -> None:
    repo = await _open_repo(tmp_path / "update.db")
    try:
        await repo.create_conversation(
            visitor_id="v", session_id="s", title="Old Title"
        )
        await repo.update_conversation_title(
            visitor_id="v", session_id="s", title="New Title"
        )

        convos = await repo.list_conversations(visitor_id="v")
        assert convos[0].title == "New Title"
    finally:
        await repo.close()


@pytest.mark.asyncio
async def test_update_conversation_title_noop_for_missing(tmp_path: Path) -> None:
    """update_conversation_title is a no-op when the conversation doesn't exist."""
    repo = await _open_repo(tmp_path / "noop.db")
    try:
        await repo.update_conversation_title(
            visitor_id="v", session_id="ghost", title="Any"
        )
        convos = await repo.list_conversations(visitor_id="v")
        assert convos == []
    finally:
        await repo.close()


@pytest.mark.asyncio
async def test_conversations_isolated_by_visitor(tmp_path: Path) -> None:
    repo = await _open_repo(tmp_path / "iso.db")
    try:
        await repo.create_conversation(
            visitor_id="a", session_id="s1", title="A's chat"
        )
        await repo.create_conversation(
            visitor_id="b", session_id="s1", title="B's chat"
        )

        a_convos = await repo.list_conversations(visitor_id="a")
        b_convos = await repo.list_conversations(visitor_id="b")

        assert len(a_convos) == 1 and a_convos[0].title == "A's chat"
        assert len(b_convos) == 1 and b_convos[0].title == "B's chat"
    finally:
        await repo.close()


@pytest.mark.asyncio
async def test_init_persistence_twice_same_instance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = str(
        URL.create("sqlite+aiosqlite", database=str((tmp_path / "twice.db").resolve()))
    )
    monkeypatch.setenv("PERSISTENCE_DATABASE_URL", database_url)
    get_persistence_settings.cache_clear()
    upgrade_head()

    await shutdown_persistence()
    await init_persistence()
    first = get_chat_history_repository()
    await init_persistence()
    second = get_chat_history_repository()
    assert first is second
    await shutdown_persistence()
    get_persistence_settings.cache_clear()
