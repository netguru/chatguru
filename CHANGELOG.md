# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Breaking Changes

- **Provider-agnostic LLM configuration (LiteLLM)** — Chat now runs through
  LiteLLM instead of a hard-wired Azure/OpenAI client, and the provider is chosen
  by the model id. The `provider` setting and the `LLM_PROVIDER` env var have been
  removed. Config env vars have neutral names; the old names still work as
  aliases, **except** `LLM_ENDPOINT` (from the previous release) which is gone —
  use `LLM_API_BASE`.

  | Old | New | Notes |
  |-----|-----|-------|
  | `LLM_ENDPOINT` / `OPENAI_ENDPOINT` / `LLM_OPENAI_BASE_URL` | `LLM_API_BASE` | Optional; empty = provider default endpoint |
  | `LLM_DEPLOYMENT_NAME` | `LLM_MODEL` | LiteLLM id, e.g. `openai/gpt-4o`, `azure/<deployment>` |
  | `OPENAI_EMBEDDINGS_ENDPOINT` | `LLM_EMBEDDINGS_API_BASE` | |
  | `OPENAI_EMBEDDINGS_API_KEY` | `LLM_EMBEDDINGS_API_KEY` | |
  | `LLM_EMBEDDING_DEPLOYMENT_NAME` | `LLM_EMBEDDING_MODEL` | |
  | `LLM_PROVIDER` | *(removed)* | Provider is inferred from the model id |

  ```bash
  # Before
  LLM_ENDPOINT=https://your-resource.openai.azure.com/
  LLM_DEPLOYMENT_NAME=gpt-4o-mini

  # After
  LLM_MODEL=openai/gpt-4o-mini
  # LLM_API_BASE=https://your-apim.azure-api.net/plc/openai/v1   # optional gateway
  ```

  The `docker-compose.yml` service definitions now use the neutral names; update
  your `.env` accordingly (an empty new-name var shadows the legacy alias, so
  don't set both). The model picker (`GET /models`) now appears whenever a
  `LLM_LITELLM_MODELS_CONFIG` file is present, regardless of provider.

- **Title generation adapter renamed** — `OpenAITitleGenerator`
  (`title_generation/adapters/openai.py`) is now `LLMTitleGenerator`
  (`.../adapters/llm.py`) and runs through LiteLLM. The old class name is kept as
  an alias and `TITLE_GENERATION_PROVIDER=openai` still works (prefer `llm`).

- **`agent.title_service` removed** — Title generation has been extracted into
  the new provider-based module under `title_generation`. Update imports:

  ```python
  # Before
  from agent.title_service import generate_title, truncate_title

  # After
  from title_generation import generate_title, truncate_title
  ```

### Added

- **Redis-backed per-IP rate limiting** (opt-in, disabled by default). Set `RATE_LIMIT_ENABLED=true`
  to enforce a configurable message quota per IP per fixed window. The check and counter increment
  are a single atomic Redis Lua transaction — no TOCTOU gap. Proxy-trust (`RATE_LIMIT_TRUST_PROXY`)
  reads `X-Forwarded-For` / `X-Real-IP` when the application sits behind a known reverse proxy.
  New variables: `RATE_LIMIT_ENABLED`, `RATE_LIMIT_REDIS_URL`, `RATE_LIMIT_MAX_MESSAGES`,
  `RATE_LIMIT_WINDOW_SECONDS`, `RATE_LIMIT_TRUST_PROXY`.
- **Server-side chat history persistence** via `PERSISTENCE_DATABASE_URL` (opt-in).
  Supports SQLite (local dev) and PostgreSQL (production). When unset the server
  remains fully stateless — no database required. See [docs/persistence.md](docs/persistence.md).
- **`GET /history`** and **`GET /conversations`** endpoints (registered only when
  persistence is enabled).
- **Conversation titles** — LLM-generated short titles for each conversation, with
  word-boundary truncation as an instant fallback.
- **History sidebar** in the web UI — browse and restore past conversations.
- **`LLM_EMBEDDINGS_API_BASE`** and **`LLM_EMBEDDINGS_API_KEY`** for a
  separate embeddings endpoint when it differs from the chat endpoint.
- **`make migrate`**, **`make db-downgrade`**, **`make db-revision`** Makefile targets
  for managing Alembic database migrations.
- Docker entrypoint (`docker/entrypoint.sh`) that automatically runs
  `alembic upgrade head` on container start when a SQLAlchemy URL is configured.
