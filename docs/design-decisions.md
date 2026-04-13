# Design decisions

## Database schema ownership

**Current state:** schemas are not defined in a single place. The codebase uses separate DDL sources for chat persistence and for RAG (SQLite vector) by design today. Putting both table families in one SQLite *file* on disk does not merge their definitions in source control.

### 1. Chat history (main API)

| What | Where |
|------|--------|
| SQLAlchemy Core table objects | `src/persistence/sqlalchemy/tables.py` (`chat_messages`, indexes) |
| Versioned migrations (authoritative DDL for this feature) | `src/persistence/sqlalchemy/alembic/versions/*.py` |
| Runtime access | Async SQLAlchemy via `PERSISTENCE_DATABASE_URL` |

**Workflow when changing this schema:** Update `persistence/sqlalchemy/tables.py` and add an Alembic revision so they match, then run `make migrate`. Alembic is the source of truth for what gets applied to databases over time; `tables.py` must reflect the same columns and indexes the app expects at runtime.

### 2. RAG / products (SQLite + sqlite-vec microservice)

| What | Where |
|------|--------|
| Table and virtual table DDL | `src/vector_db/store.py` (`_setup_database`: `products`, `product_embeddings` / `vec0`) |
| Migrations | **None** — tables are created with `CREATE TABLE IF NOT EXISTS` / `CREATE VIRTUAL TABLE IF NOT EXISTS` at store init |
| Runtime access | Separate HTTP service; file path `VECTOR_SQLITE_DB_PATH` (default `/data/chatguru.db` in Docker) |

This path is **not** managed by Alembic. Changes require editing `store.py` (and redeploying the vector service).

### 3. RAG / products (MongoDB backend)

When `VECTOR_DB_TYPE=mongodb`, product data and vectors live in MongoDB. Schema is driven by the Mongo-backed implementation and configuration (`VECTOR_DB_MONGODB_*`), not by `persistence/` or Alembic.

### 4. Optional: one SQLite file on disk

Chat tables and vector tables can share a **single** `.db` file (see `PERSISTENCE_DATABASE_URL`, `VECTOR_SQLITE_DB_PATH`, and Docker Compose sqlite profile). That is **co-location of the file**, not a unified schema module: DDL for chat remains in Alembic + `tables.py`; DDL for vectors remains in `vector_db/store.py`.

---

## Chat history persistence (repository pattern)

**Context:** Persist conversation turns per visitor and session for continuity and analytics.

**Decision:**

- Define a **port** `ChatHistoryRepository` (`Protocol`) in `persistence/repository.py` with async methods only. Call sites depend on the port, not on SQLAlchemy.
- Implement the port in `persistence/sqlalchemy/repository.py` (adapter). Table definitions live in `persistence/sqlalchemy/tables.py`; the async engine is built in `persistence/sqlalchemy/engine.py`. All SQL-specific code (including Alembic migrations) is encapsulated inside the `persistence/sqlalchemy/` subpackage.
- Use a **composition root** `build_chat_history_repository()` in `persistence/factory.py` as the only place that constructs the concrete adapter and engine.
- **Bootstrap:** `init_persistence()` / `shutdown_persistence()` / `get_chat_history_repository()` in `persistence/bootstrap.py` (re-exported from `persistence`) register a single repository instance for the FastAPI app lifecycle. `get_chat_history_repository()` raises `RuntimeError` if called before `init_persistence()` (e.g. tests must trigger app lifespan or call `init_persistence` explicitly).
- **Schema:** Alembic migrations are authoritative for DDL. `sqlalchemy/tables.py` must stay aligned with the latest migration (indexes, columns). After changing either, run `make migrate`.

**Trade-offs:** Global singleton simplifies handlers; tests that need isolation call `shutdown_persistence()` and clear `get_persistence_settings` cache where URLs are swapped.

**Single SQLite file (optional):** Chat history (`chat_messages` via Alembic) and the sqlite-vec product tables can live in one `.db` file — different tables, no conflict. Use the same path for `PERSISTENCE_DATABASE_URL` and `VECTOR_SQLITE_DB_PATH` (vector microservice). Docker Compose sqlite profile mounts one volume at `/data` on both `vector-db` and `chatguru-agent-sqlite`.
