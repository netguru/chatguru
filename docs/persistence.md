# Chat History Persistence

## Overview

The persistence layer stores conversation turns, conversation metadata, and file attachments per visitor and session. It follows a **ports-and-adapters** (hexagonal) architecture: application code depends on an abstract `Protocol`, never on a concrete database library. The only shipped adapter today uses async SQLAlchemy, but adding a new one (e.g. DynamoDB, Firestore, raw asyncpg) requires no changes to the rest of the codebase.

## Package layout

```
src/persistence/
├── __init__.py              # Re-exports public API
├── repository.py            # Port (Protocol) — the contract
├── models.py                # Domain dataclasses (StoredChatMessage, StoredConversation, StoredAttachment)
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
            ├── 003_conversations_unique_constraint.py
            ├── 004_chat_messages_trace_id.py
            ├── 005_chat_messages_sources.py
            ├── 006_chat_attachments.py
            └── 007_chat_attachments_fk.py
```

Everything under `sqlalchemy/` is an implementation detail. If you don't use SQL-based persistence, this entire subtree is irrelevant.

Note that only attachment **metadata** lives here. The file bytes are held by the separate `attachment_storage` module; `StoredAttachment.storage_key` is the handle that ties the two together.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Application code (chat routes, agent, tests)                │
│  depends ONLY on:                                            │
│    ChatHistoryRepository  (Protocol)                         │
│    StoredChatMessage / StoredConversation /                  │
│    StoredAttachment  (dataclasses)                           │
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
    async def conversation_exists(self, *, visitor_id, session_id) -> bool: ...
    async def list_conversations(self, *, visitor_id) -> list[StoredConversation]: ...

    # Messages
    async def append_message(
        self, *, visitor_id, session_id, role, content,
        trace_id: str | None = None, sources: str | None = None,
    ) -> str: ...
    async def list_messages(self, *, visitor_id, session_id) -> list[StoredChatMessage]: ...
    async def trace_id_owned_by_visitor(self, *, trace_id, visitor_id) -> bool: ...

    # Attachments
    async def save_attachment(self, attachment: StoredAttachment) -> None: ...
    async def link_attachments_to_message(self, *, attachment_ids, message_id, visitor_id) -> None: ...
    async def get_attachments_for_message(self, message_id: str) -> list[StoredAttachment]: ...
    async def get_attachments_for_messages(self, message_ids: list[str]) -> list[StoredAttachment]: ...
    async def get_attachment(self, *, attachment_id, visitor_id) -> StoredAttachment | None: ...

    async def close(self) -> None: ...
```

Fourteen methods in total — an adapter must implement **all** of them.

Most parameters are **keyword-only** (`*`). This prevents positional-argument mistakes when a method has several string parameters. The three exceptions take a single unambiguous positional argument: `save_attachment`, `get_attachments_for_message`, and `get_attachments_for_messages`.

`connect()` is called once at startup to verify the backend is reachable. `close()` disposes of connections at shutdown.

### Notes on individual methods

- **`append_message` returns the generated message ID.** Callers need it to link attachments to the persisted turn, so returning `None` breaks the upload flow. `trace_id` correlates the message with an observability trace; `sources` is a JSON-encoded string of RAG citations (the repository stores it opaquely and does not parse it).
- **`trace_id_owned_by_visitor`** backs authorization checks — it prevents one visitor from submitting feedback against another visitor's trace.
- **Attachments are stored in two phases.** The upload endpoint calls `save_attachment()` with `message_id=None`; once the chat turn is persisted, `link_attachments_to_message()` fills in the ID. The link query must match only rows that still have `message_id IS NULL` **and** belong to the given `visitor_id`, otherwise one visitor could re-parent another's attachment.
- **`get_attachments_for_messages`** exists so `GET /history` can batch-load a whole session in one query instead of N. It must return `[]` for an empty ID list without touching the database — an unguarded `IN ()` is a syntax error on some backends.
- **`get_attachment`** takes `visitor_id` and returns `None` on a mismatch. This is the ownership check for the download endpoint — do not drop the predicate.

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

**Response** — array of message objects. `role` and `content` are always present; `trace_id`, `sources`, and `stored_attachments` are omitted when absent:

```json
[
  {
    "role": "user",
    "content": "What does the contract say?",
    "stored_attachments": [
      {"id": "att-1", "name": "contract.pdf", "mime_type": "application/pdf"}
    ]
  },
  {
    "role": "assistant",
    "content": "Clause 4 covers termination.",
    "trace_id": "trace-abc123",
    "sources": [{"title": "contract.pdf", "page": 4}]
  }
]
```

The `sources` entries above are **abbreviated** — real payloads also carry `source_id`, `source_uri`, `chunk_id`, and `source_type`. The column is stored as an opaque JSON string and decoded on the way out; if it fails to parse, the key is dropped rather than the request failing. `stored_attachments` is a trimmed projection of `StoredAttachment` — it deliberately excludes `storage_key`, which is internal to the storage backend.

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

### `POST /conversations/title`

Generates an LLM summary title for an existing conversation and persists it.

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `visitor_id` | string | ✅ | Visitor ID (1–512 chars) |
| `session_id` | string | ✅ | Session ID (1–512 chars) |
| `first_message` | string | ✅ | First user message the title is derived from (1–200,000 chars) |

Returns `404` if no conversation exists for the `visitor_id` + `session_id` pair. If title generation fails, the endpoint falls back to a truncated version of the first message rather than erroring — so a `200` does not guarantee an LLM-generated title.

**Response:**

```json
{"session_id": "abc-123", "title": "Questions about pricing"}
```

### `GET /attachments/{attachment_id}`

Streams a stored attachment file back to the client.

| Parameter | In | Type | Required | Description |
|-----------|----|------|----------|-------------|
| `attachment_id` | path | string | ✅ | Attachment ID |
| `visitor_id` | query | string | ✅ | Must match the visitor that uploaded the attachment |

Only the uploading visitor may retrieve an attachment: a mismatched `visitor_id` returns `404` (not `403`, so the endpoint does not leak which IDs exist). `503` is returned when attachment storage is not configured, and `404` when the metadata row exists but the underlying file is gone.

Headers are set defensively on the **file response only** — the `404` and `503` error paths return FastAPI's default responses and carry none of these:

- `X-Content-Type-Options: nosniff` on every successful file response.
- PDFs are served `inline` with `Content-Security-Policy: sandbox`, so embedded JavaScript cannot reach cookies or `localStorage` on the app origin.
- Everything else is served as a download with an RFC 5987-encoded filename.

## Schema management

| Source of truth | Location |
|---|---|
| Runtime table definitions | `persistence/sqlalchemy/tables.py` (SQLAlchemy Core `Table` objects) |
| Versioned DDL migrations | `persistence/sqlalchemy/alembic/versions/*.py` |

Three tables:

| Table | Holds | Notes |
|---|---|---|
| `conversations` | One metadata row per session | Unique on `(visitor_id, session_id)` |
| `chat_messages` | One row per message — a single turn writes two (user + assistant) | `trace_id` and `sources` are nullable (added in 004 / 005) |
| `chat_attachments` | Uploaded file metadata | `message_id` is nullable with `ON DELETE SET NULL` (see caveat below) |

> **The `ON DELETE SET NULL` on `chat_attachments.message_id` is not enforced under SQLite.** SQLite ignores foreign keys unless `PRAGMA foreign_keys=ON` is issued per connection, and the engine factory only sets `journal_mode=WAL` ([`sqlalchemy/engine.py`](../src/persistence/sqlalchemy/engine.py)). The intent — deleting a message orphans its attachment rather than cascading — holds on PostgreSQL but is inert on the default SQLite backend. Nothing deletes messages today, so this is latent rather than broken; if you add a delete path, either enable the pragma on connect or do the null-out explicitly in the adapter.

Both sources must stay in sync. The workflow for schema changes:

1. Edit `persistence/sqlalchemy/tables.py` (add columns, indexes, constraints).
2. Create an Alembic revision: `make db-revision MESSAGE='describe change'`.
3. Review the generated migration in `persistence/sqlalchemy/alembic/versions/`, adjust if needed (e.g. use `batch_alter_table` for SQLite).
4. Apply: `make migrate`.

## Adding a new adapter (step by step)

This section walks through adding a hypothetical PostgreSQL adapter that uses raw `asyncpg` instead of SQLAlchemy. The same pattern applies to DynamoDB, Firestore, or any other backend.

### Step 1 — Create the adapter module

Create `src/persistence/asyncpg/repository.py`. The class must implement all fourteen methods of `ChatHistoryRepository` — the full listing below is deliberately unabridged, because a partial implementation fails the type check and then misbehaves at runtime:

```python
"""Chat history adapter backed by raw asyncpg."""

import uuid
from datetime import UTC, datetime

import asyncpg

from persistence.models import StoredAttachment, StoredChatMessage, StoredConversation
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

    async def conversation_exists(
        self, *, visitor_id: str, session_id: str,
    ) -> bool:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM conversations "
                "WHERE visitor_id = $1 AND session_id = $2 LIMIT 1",
                visitor_id, session_id,
            )
        return row is not None

    async def append_message(  # noqa: PLR0913
        self, *, visitor_id: str, session_id: str, role: str, content: str,
        trace_id: str | None = None, sources: str | None = None,
    ) -> str:
        validate_chat_message_role(role)
        message_id = str(uuid.uuid4())
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO chat_messages "
                "(id, visitor_id, session_id, role, content, created_at, trace_id, sources) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
                message_id, visitor_id, session_id,
                role, content, datetime.now(UTC), trace_id, sources,
            )
        return message_id

    async def list_messages(
        self, *, visitor_id: str, session_id: str,
    ) -> list[StoredChatMessage]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, visitor_id, session_id, role, content, created_at, "
                "trace_id, sources "
                "FROM chat_messages "
                "WHERE visitor_id = $1 AND session_id = $2 "
                "ORDER BY created_at ASC, id ASC",
                visitor_id, session_id,
            )
        return [StoredChatMessage(**dict(r)) for r in rows]

    async def trace_id_owned_by_visitor(
        self, *, trace_id: str, visitor_id: str,
    ) -> bool:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM chat_messages "
                "WHERE trace_id = $1 AND visitor_id = $2 LIMIT 1",
                trace_id, visitor_id,
            )
        return row is not None

    # ------------------------------------------------------------------
    # Attachments
    # ------------------------------------------------------------------

    async def save_attachment(self, attachment: StoredAttachment) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO chat_attachments "
                "(id, message_id, visitor_id, storage_key, name, mime_type, "
                "size, created_at) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
                attachment.id, attachment.message_id, attachment.visitor_id,
                attachment.storage_key, attachment.name, attachment.mime_type,
                attachment.size, attachment.created_at,
            )

    async def link_attachments_to_message(
        self, *, attachment_ids: list[str], message_id: str, visitor_id: str,
    ) -> None:
        if not attachment_ids:
            return
        async with self._pool.acquire() as conn:
            # visitor_id + "message_id IS NULL" together prevent re-parenting
            # an attachment that belongs to someone else or to another turn.
            await conn.execute(
                "UPDATE chat_attachments SET message_id = $1 "
                "WHERE id = ANY($2::text[]) AND visitor_id = $3 "
                "AND message_id IS NULL",
                message_id, attachment_ids, visitor_id,
            )

    async def get_attachments_for_message(
        self, message_id: str,
    ) -> list[StoredAttachment]:
        return await self._fetch_attachments(
            "WHERE message_id = $1", [message_id],
        )

    async def get_attachments_for_messages(
        self, message_ids: list[str],
    ) -> list[StoredAttachment]:
        if not message_ids:
            return []
        return await self._fetch_attachments(
            "WHERE message_id = ANY($1::text[])", [message_ids],
        )

    async def _fetch_attachments(
        self, where: str, params: list,
    ) -> list[StoredAttachment]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, message_id, visitor_id, storage_key, name, "
                f"mime_type, size, created_at FROM chat_attachments {where} "
                "ORDER BY created_at ASC",
                *params,
            )
        return [StoredAttachment(**dict(r)) for r in rows]

    async def get_attachment(
        self, *, attachment_id: str, visitor_id: str,
    ) -> StoredAttachment | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, message_id, visitor_id, storage_key, name, "
                "mime_type, size, created_at FROM chat_attachments "
                "WHERE id = $1 AND visitor_id = $2",
                attachment_id, visitor_id,
            )
        return StoredAttachment(**dict(row)) if row is not None else None

    async def close(self) -> None:
        await self._pool.close()
```

Key implementation notes:

- **Implement all fourteen methods.** `ChatHistoryRepository` is a `typing.Protocol`, so a partial implementation still constructs at runtime and nothing complains at startup. How it then fails depends on whether you subclass the protocol:
  - **Subclassing it** (as `SqlAlchemyChatHistoryRepository` does) is the dangerous case: an unimplemented method inherits the protocol's `...` body, so it *silently returns `None`* instead of raising. A missing `get_attachments_for_messages` makes `GET /history` blow up on `for a in None`, and a missing `link_attachments_to_message` corrupts nothing loudly — attachments just never link.
  - **Not subclassing it** (as the example above) at least gets you an `AttributeError` at the call site.

  Neither is a substitute for running a type checker against the protocol, which catches the gap at build time.
- **Use `validate_chat_message_role()`** from `persistence/validation.py` in `append_message`. This is shared across all adapters.
- **`append_message` must return the new message ID**, not `None` — the attachment-linking flow depends on it.
- **Return frozen `StoredChatMessage` / `StoredConversation` / `StoredAttachment` dataclasses**, not database-specific rows.
- **Normalize `created_at` to timezone-aware UTC.** Some drivers return naive datetimes; the tests assert `tzinfo is not None`.
- **Preserve the ownership predicates.** `get_attachment` and `link_attachments_to_message` filter on `visitor_id` — these are authorization boundaries, not optimizations.
- **`close()` must release all resources** (connection pools, file handles).
- **`create_conversation` must be idempotent** — return the existing record if the `(visitor_id, session_id)` pair already exists. Handle the race: catch the unique-constraint violation and re-fetch the winning row (see `SqlAlchemyChatHistoryRepository.create_conversation`).

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

Copy the pattern from `tests/test_persistence.py`. The existing tests exercise the protocol's contract: message roundtrip, visitor/session isolation, `create_conversation` idempotency, invalid roles, title updates on missing conversations, attachment save/get roundtrip, wrong-visitor rejection on both `get_attachment` and `link_attachments_to_message`, and batch attachment loading. Your new adapter should pass the same assertions:

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
| 1 | Implement **all 14** methods of `ChatHistoryRepository` | `persistence/<backend>/repository.py` |
| 2 | Use `validate_chat_message_role()` in `append_message` | Import from `persistence.validation` |
| 3 | Return the generated message ID from `append_message` | Attachment linking depends on it |
| 4 | Persist and read back `trace_id` and `sources` on messages | Nullable columns; `sources` is an opaque JSON string |
| 5 | Return `StoredChatMessage` / `StoredConversation` / `StoredAttachment` dataclasses | Import from `persistence.models` |
| 6 | Normalize `created_at` to timezone-aware UTC | Tests assert `tzinfo is not None` |
| 7 | Make `create_conversation` idempotent and race-safe | SELECT-then-INSERT, catch unique violation, re-fetch |
| 8 | Filter `get_attachment` by `visitor_id`; return `None` on mismatch | Authorization boundary — download endpoint |
| 9 | Filter `link_attachments_to_message` by `visitor_id` **and** `message_id IS NULL` | Prevents re-parenting another visitor's attachment |
| 10 | Short-circuit `get_attachments_for_messages` on an empty ID list | Return `[]` without a query |
| 11 | Implement `close()` to release all resources | Pool, engine, connection |
| 12 | Add backend selection logic to `factory.py` | URL prefix or new config field |
| 13 | Add the dependency to `pyproject.toml` | e.g. `asyncpg`, `aiobotocore` |
| 14 | Write tests covering the full protocol contract | `tests/test_persistence.py` or new file |
| 15 | Handle schema/migrations for the new backend | Alembic (SQL) or `connect()` (NoSQL) |
