# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Breaking Changes

- **`LLM_ENDPOINT` renamed to `OPENAI_ENDPOINT`** — The LLM base URL environment
  variable has been renamed. Update your `.env` and any deployment configs before
  upgrading. The old name is no longer read.

  ```bash
  # Before
  LLM_ENDPOINT=https://your-resource.openai.azure.com/

  # After
  OPENAI_ENDPOINT=https://your-resource.openai.azure.com/openai/v1
  ```

  Note: the expected URL format also changed — it now points to the full
  OpenAI-compatible base URL (ending in `/v1`) rather than the raw Azure
  resource endpoint.

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
- **`OPENAI_EMBEDDINGS_ENDPOINT`** and **`OPENAI_EMBEDDINGS_API_KEY`** for a
  separate embeddings endpoint when it differs from the chat endpoint.
- **`make migrate`**, **`make db-downgrade`**, **`make db-revision`** Makefile targets
  for managing Alembic database migrations.
- Docker entrypoint (`docker/entrypoint.sh`) that automatically runs
  `alembic upgrade head` on container start when a SQLAlchemy URL is configured.
