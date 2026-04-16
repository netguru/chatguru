# Chat History Persistence

## Overview

The persistence layer stores conversation turns and conversation metadata per visitor and session. It follows a **ports-and-adapters** (hexagonal) architecture: application code depends on an abstract `Protocol`, never on a concrete database library. The only shipped adapter today uses async SQLAlchemy, but adding a new one (e.g. DynamoDB, Firestore, raw asyncpg) requires no changes to the rest of the codebase.

## Package layout

```
src/persistence/
├── __init__.py              # Re-exports public API
├── repository.py            # Port (Protocol) — the contract
├── models.py                # Domain dataclasses (StoredChatMessage, StoredConversation)
├── validation.py            # Shared validation (role allow-list)
├── factory.py               # Composition root — builds the concrete adapter
├── bootstrap.py             # Process-wide singleton lifecycle (init / shutdown / get)
└── sqlalchemy/              # ── SQLAlchemy adapter (all SQL lives here) ──
    ├── __init__.py
    ├── repository.py        # Adapter implementation
    ├── tables.py            # SQLAlchemy Core table definitions
    ├── engine.py            # Async engine factory (SQLite WAL, path resolution)
    ├── migrate.py           # Alembic helper (upgrade_head)
    ├── alembic.ini          # Alembic config (Makefile points here with -c)
    └── alembic/             # Alembic environment and revisions
        ├── env.py
        ├── script.py.mako
        └── versions/
            ├── 001_initial_chat_messages.py
            ├── 002_conversations.py
            └── 003_conversations_unique_constraint.py
```

Everything under `sqlalchemy/` is an implementation detail. If you don't use SQL-based persistence, this entire subtree is irrelevant.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Application code (chat routes, agent, tests)                │
│  depends ONLY on:                                            │
│    ChatHistoryRepository  (Protocol)                         │
│    StoredChatMessage / StoredConversation  (dataclasses)     │
└──────────────┬───────────────────────────────────────────────┘
               │ calls via
               ▼
┌──────────────────────────┐
│  persistence/factory.py  │  ← composition root
│  build_chat_history_     │    creates the concrete adapter
│  repository()            │    and returns it as the Protocol
└──────────┬───────────────┘
           │ constructs
           ▼
┌───────────────────────────────────────────────┐
│  SqlAlchemyChatHistoryRepository              │  ← adapter (swappable)
│  (persistence/sqlalchemy/repository.py)       │
│  owns one AsyncEngine                         │
└───────────────────────────────────────────────┘
```

### Key rules

1. **Application code never imports the adapter module.** It imports `ChatHistoryRepository` (the protocol) and calls `get_chat_history_repository()` or `build_chat_history_repository()`.
2. **The factory is the only place that picks which adapter to instantiate.** If you add a second backend, the factory is where you read a setting and choose between them.
3. **Domain models are plain frozen dataclasses** — no SQLAlchemy, no Pydantic, no ORM in `models.py`.

## The repository port

`persistence/repository.py` defines the contract as a `typing.Protocol`:

```python
class ChatHistoryRepository(Protocol):
    async def connect(self) -> None: ...

    # Conversations
    async def create_conversation(self, *, visitor_id, session_id, title) -> StoredConversation: ...
    async def update_conversation_title(self, *, visitor_id, session_id, title) -> None: ...
    async def list_conversations(self, *, visitor_id) -> list[StoredConversation]: ...

    # Messages
    async def append_message(self, *, visitor_id, session_id, role, content) -> None: ...
    async def list_messages(self, *, visitor_id, session_id) -> list[StoredChatMessage]: ...

    async def close(self) -> None: ...
```

All parameters after `self` are **keyword-only** (`*`). This prevents positional-argument mistakes when every method has several string parameters.

`connect()` is called once at startup to verify the backend is reachable. `close()` disposes of connections at shutdown.

## Lifecycle (bootstrap)

The FastAPI lifespan wires everything together:

```
startup  →  init_persistence()  →  build_chat_history_repository()
                                        ↓
                                   stores singleton in module global
                                        ↓
runtime  →  get_chat_history_repository()  →  returns the singleton
                                        ↓
shutdown →  shutdown_persistence()  →  repo.close()
```

- `init_persistence()` is idempotent — calling it twice is safe. When `PERSISTENCE_DATABASE_URL` is unset it is a no-op.
- `get_chat_history_repository()` returns `None` when persistence is disabled, and raises `RuntimeError` if persistence is enabled but `init_persistence()` has not run (catches misconfigured startup early).
- `shutdown_persistence()` is idempotent — safe to call even if init was never called.

## HTTP endpoints

These endpoints are only registered when `PERSISTENCE_DATABASE_URL` is set. When persistence is disabled they are absent entirely — they won't appear in `/docs` and any request to them returns 404.

### `GET /history`

Returns stored messages for a visitor + session pair, oldest first.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `visitor_id` | string | ✅ | — | Stable ID that scopes history to one user/device |
| `session_id` | string | | `"default"` | Conversation session ID |

**Response** — array of message objects:

```json
[
  {"role": "user", "content": "Hello"},
  {"role": "assistant", "content": "Hi! How can I help?"}
]
```

### `GET /conversations`

Returns all conversations for a visitor, newest first.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `visitor_id` | string | ✅ | Stable ID that scopes conversations to one user/device |

**Response** — array of conversation objects:

```json
[
  {
    "session_id": "abc-123",
    "title": "Questions about pricing",
    "created_at": "2026-04-10T11:00:00+00:00"
  }
]
```

Titles are set to the first user message on creation and updated asynchronously with an LLM-generated summary.

## Schema management

| Source of truth | Location |
|---|---|
| Runtime table definitions | `persistence/sqlalchemy/tables.py` (SQLAlchemy Core `Table` objects) |
| Versioned DDL migrations | `persistence/sqlalchemy/alembic/versions/*.py` |

Both must stay in sync. The workflow for schema changes:

1. Edit `persistence/sqlalchemy/tables.py` (add columns, indexes, constraints).
2. Create an Alembic revision: `make db-revision MESSAGE='describe change'`.
3. Review the generated migration in `persistence/sqlalchemy/alembic/versions/`, adjust if needed (e.g. use `batch_alter_table` for SQLite).
4. Apply: `make migrate`.

## Adding a new adapter (step by step)

This section walks through adding a hypothetical PostgreSQL adapter that uses raw `asyncpg` instead of SQLAlchemy. The same pattern applies to DynamoDB, Firestore, or any other backend.

### Step 1 — Create the adapter module

Create `src/persistence/asyncpg/repository.py`. The class must satisfy every method in `ChatHistoryRepository`:

```python
"""Chat history adapter backed by raw asyncpg."""

import uuid
from datetime import UTC, datetime

import asyncpg

from persistence.models import StoredChatMessage, StoredConversation
from persistence.validation import validate_chat_message_role


class AsyncpgChatHistoryRepository:
    """asyncpg-based adapter implementing the chat history port."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def connect(self) -> None:
        async with self._pool.acquire() as conn:
            await conn.fetchval("SELECT 1")

    async def create_conversation(
        self, *, visitor_id: str, session_id: str, title: str,
    ) -> StoredConversation:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, visitor_id, session_id, title, created_at "
                "FROM conversations "
                "WHERE visitor_id = $1 AND session_id = $2",
                visitor_id, session_id,
            )
            if row is not None:
                return StoredConversation(**dict(row))

            conv_id = str(uuid.uuid4())
            now = datetime.now(UTC)
            await conn.execute(
                "INSERT INTO conversations (id, visitor_id, session_id, title, created_at) "
                "VALUES ($1, $2, $3, $4, $5)",
                conv_id, visitor_id, session_id, title, now,
            )
            return StoredConversation(
                id=conv_id, visitor_id=visitor_id,
                session_id=session_id, title=title, created_at=now,
            )

    async def update_conversation_title(
        self, *, visitor_id: str, session_id: str, title: str,
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE conversations SET title = $1 "
                "WHERE visitor_id = $2 AND session_id = $3",
                title, visitor_id, session_id,
            )

    async def list_conversations(
        self, *, visitor_id: str,
    ) -> list[StoredConversation]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, visitor_id, session_id, title, created_at "
                "FROM conversations WHERE visitor_id = $1 "
                "ORDER BY created_at DESC",
                visitor_id,
            )
        return [StoredConversation(**dict(r)) for r in rows]

    async def append_message(
        self, *, visitor_id: str, session_id: str, role: str, content: str,
    ) -> None:
        validate_chat_message_role(role)
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO chat_messages "
                "(id, visitor_id, session_id, role, content, created_at) "
                "VALUES ($1, $2, $3, $4, $5, $6)",
                str(uuid.uuid4()), visitor_id, session_id,
                role, content, datetime.now(UTC),
            )

    async def list_messages(
        self, *, visitor_id: str, session_id: str,
    ) -> list[StoredChatMessage]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, visitor_id, session_id, role, content, created_at "
                "FROM chat_messages "
                "WHERE visitor_id = $1 AND session_id = $2 "
                "ORDER BY created_at ASC, id ASC",
                visitor_id, session_id,
            )
        return [StoredChatMessage(**dict(r)) for r in rows]

    async def close(self) -> None:
        await self._pool.close()
```

Key implementation notes:

- **Use `validate_chat_message_role()`** from `persistence/validation.py` in `append_message`. This is shared across all adapters.
- **Return frozen `StoredChatMessage` / `StoredConversation` dataclasses**, not database-specific rows.
- **`close()` must release all resources** (connection pools, file handles).
- **`create_conversation` must be idempotent** — return the existing record if the `(visitor_id, session_id)` pair already exists.

### Step 2 — Wire it into the factory

Edit `persistence/factory.py` to select the adapter based on the database URL scheme:

```python
from config import PersistenceSettings, get_persistence_settings
from persistence.repository import ChatHistoryRepository


async def build_chat_history_repository(
    settings: PersistenceSettings | None = None,
) -> ChatHistoryRepository:
    resolved = settings if settings is not None else get_persistence_settings()

    if resolved.database_url.startswith("postgresql+asyncpg"):
        import asyncpg
        from persistence.asyncpg.repository import AsyncpgChatHistoryRepository

        pool = await asyncpg.create_pool(resolved.database_url)
        repo = AsyncpgChatHistoryRepository(pool)
    else:
        from persistence.sqlalchemy.engine import create_async_engine_from_settings
        from persistence.sqlalchemy.repository import SqlAlchemyChatHistoryRepository

        engine = create_async_engine_from_settings(resolved)
        repo = SqlAlchemyChatHistoryRepository(engine)

    await repo.connect()
    return repo
```

That's it — no other file needs to change. The bootstrap, routes, and agent code all depend on the `ChatHistoryRepository` protocol, not on SQLAlchemy.

### Step 3 — Write tests

Copy the pattern from `tests/test_persistence.py`. The existing tests exercise the protocol's contract (roundtrip, isolation, idempotency, invalid roles). Your new adapter should pass the same assertions:

```python
@pytest.mark.asyncio
async def test_append_and_list_roundtrip(asyncpg_repo):
    await asyncpg_repo.append_message(
        visitor_id="v1", session_id="s1", role="user", content="hello",
    )
    messages = await asyncpg_repo.list_messages(visitor_id="v1", session_id="s1")
    assert len(messages) == 1
    assert messages[0].role == "user"
    assert messages[0].content == "hello"
    assert messages[0].created_at.tzinfo is not None
```

### Step 4 — Handle migrations

Alembic migrations already target portable SQL (no SQLite-specific DDL). If your new backend is PostgreSQL, the existing migrations work as-is — just change `PERSISTENCE_DATABASE_URL` to a `postgresql+asyncpg://` URL and run `make migrate`.

For non-SQL backends (DynamoDB, Firestore), migrations don't apply. The adapter is responsible for ensuring its tables/collections exist in `connect()`.

## Checklist for a new adapter

| # | Task | Where |
|---|------|-------|
| 1 | Create the adapter class satisfying `ChatHistoryRepository` | `persistence/<backend>/repository.py` |
| 2 | Use `validate_chat_message_role()` in `append_message` | Import from `persistence.validation` |
| 3 | Return `StoredChatMessage` / `StoredConversation` dataclasses | Import from `persistence.models` |
| 4 | Make `create_conversation` idempotent | SELECT-then-INSERT or upsert |
| 5 | Implement `close()` to release all resources | Pool, engine, connection |
| 6 | Add backend selection logic to `factory.py` | URL prefix or new config field |
| 7 | Add the dependency to `pyproject.toml` | e.g. `asyncpg`, `aiobotocore` |
| 8 | Write tests covering the full protocol contract | `tests/test_persistence.py` or new file |
| 9 | Handle schema/migrations for the new backend | Alembic (SQL) or `connect()` (NoSQL) |
