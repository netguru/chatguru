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

## Per-IP rate limiting (Redis-backed)

**Context:** Prevent any single IP from sending unlimited LLM messages and incurring unbounded inference costs. Rate limiting must be optional (many deployments are internal or authenticated at the proxy layer) and must not introduce a TOCTOU race where concurrent requests from the same IP bypass the quota.

**Decision:**

- Gate the WebSocket handler with a Redis counter keyed by `rate_limit:chat:<ip>`. All configuration is opt-in via `RATE_LIMIT_ENABLED=true`; when false the module is a no-op.
- **Atomic enforcement via Lua:** The check and increment are a single `EVAL` call (`_LUA_CONSUME` in `rate_limiting/bootstrap.py`). This eliminates the TOCTOU window that exists when using separate `GET` + `INCR` calls — two concurrent coroutines cannot both pass a `GET`-based check before either records its use.
- **Consume before streaming:** The slot is consumed *before* the LLM call begins, not after it completes. This means a request that starts generating tokens but fails mid-stream still counts against the quota, preventing clients from exploiting partial-stream errors to bypass the limit.
- **`None` IP, not `"unknown"`:** When `websocket.client` is unavailable (certain ASGI transports), `_get_client_ip` returns `None` and the handler skips enforcement entirely. A shared `"unknown"` key would let one client exhaust the quota for all others in the same situation.
- **Proxy trust is explicit:** `RATE_LIMIT_TRUST_PROXY=true` enables reading `X-Forwarded-For` / `X-Real-IP`. This is off by default; enabling it in a direct-to-internet deployment would allow clients to spoof their IP.
- **IP extracted once per connection:** `_get_client_ip` is called once when the WebSocket is accepted, not on every message, since `websocket.client` cannot change mid-connection.

**Trade-offs:**

- Redis is now a required dependency when rate limiting is enabled. Both docker-compose profiles depend on the Redis service health check.
- The `RATE_LIMIT_MAX_MESSAGES` default is `1` — intentionally restrictive so operators must explicitly raise the limit for their use case rather than accidentally leaving it wide open.
- Counting is per IP, not per authenticated user — suitable for public deployments without authentication. In authenticated deployments the rate limit key should be switched to a user/tenant identifier.

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

---

<a id="llm-endpoint-modes"></a>

## LLM endpoint: universal (`ChatOpenAI`) vs native Azure (`AzureChatOpenAI`)

**Context:** The agent builds one of two LangChain chat clients in `agent/service.py` (`_build_chat_llm`). The choice is **not** where the chatguru API is hosted (e.g. Azure App Service vs. elsewhere). It depends on **which HTTP API** your LLM URL exposes.

### Decision

| Mode | When to use | Environment variables | Client |
|------|-------------|------------------------|--------|
| **Universal / OpenAI-compatible** | The URL speaks the **OpenAI Chat Completions** contract: a single base URL, model id in the request body, paths like `.../chat/completions`. Typical: **Azure API Management** in front of Azure OpenAI, **true OpenAI** (`https://api.openai.com/v1`), LiteLLM, or any custom gateway that exposes `/openai/v1` (or similar). | Set **`LLM_OPENAI_BASE_URL`** to that base (e.g. `https://your-apim.azure-api.net/.../openai/v1`). **`OPENAI_ENDPOINT`** is not used for chat in this mode. `LLM_DEPLOYMENT_NAME` is the **model id** (e.g. `gpt-5-mini`). | `ChatOpenAI` with `base_url` |
| **Native Azure OpenAI** | The app calls **Azure OpenAI Service directly** using the resource host and deployment-based routing (`azure_endpoint` + `azure_deployment` + `api-version`), not a single v1-compatible base URL you fully control yourself. | Leave **`LLM_OPENAI_BASE_URL`** empty. Set **`OPENAI_ENDPOINT`** to the Azure resource base (see `config.py` / `env.example`). Set **`LLM_API_VERSION`**. `LLM_DEPLOYMENT_NAME` is the **deployment name** in Azure. | `AzureChatOpenAI` |

### Notes

- **Hosting the app on Azure** does not force either mode. An app on Azure can use **`LLM_OPENAI_BASE_URL`** if traffic goes through a v1-compatible gateway (common and valid).
- Embeddings may still use **`OPENAI_EMBEDDINGS_ENDPOINT`** (or fall back to `OPENAI_ENDPOINT` when the universal chat path is not used); see `LLMSettings` in `config.py` for precedence.
- Deprecated env names (`LLM_ENDPOINT` for the chat base URL) are not used; prefer **`OPENAI_ENDPOINT`** per project conventions.
