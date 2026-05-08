#!/bin/sh
# Docker entrypoint:
#   1. Runs Alembic migrations when a SQLAlchemy-compatible URL is configured.
#   2. Ingests documents from /app/rag_data when DOCUMENT_RAG_ENABLED=true,
#      unless already ingested (sentinel at /app/rag_ingest_state/.ingested).
#      Set DOCUMENT_RAG_INGEST_FULL_REPLACE=1 to force a full re-ingest.
#
# Binaries (alembic, python) are called directly from the virtualenv via PATH
# (/app/.venv/bin is prepended in the Dockerfile ENV), so uv is not required
# at runtime.
#
# The container exits non-zero on failure so the health-check never turns green.
set -e

if [ -n "$PERSISTENCE_DATABASE_URL" ]; then
    case "$PERSISTENCE_DATABASE_URL" in
        sqlite+*|postgresql+*|mysql+*|mariadb+*|mssql+*|oracle+*|cockroachdb+*)
            echo "[entrypoint] SQLAlchemy URL detected — running database migrations..."
            alembic -c /app/src/persistence/sqlalchemy/alembic.ini upgrade head
            echo "[entrypoint] Migrations complete."
            ;;
        *)
            echo "[entrypoint] Non-SQLAlchemy URL detected — skipping Alembic migrations."
            ;;
    esac
fi

_rag_enabled=$(echo "${DOCUMENT_RAG_ENABLED:-false}" | tr '[:upper:]' '[:lower:]')
_sentinel=/app/rag_ingest_state/.ingested

if [ "$_rag_enabled" = "true" ] && [ -d /app/rag_data ] && [ -n "$(ls -A /app/rag_data 2>/dev/null)" ]; then
    if [ -n "${DOCUMENT_RAG_INGEST_FULL_REPLACE}" ] || [ ! -f "$_sentinel" ]; then
        echo "[entrypoint] DOCUMENT_RAG_ENABLED=true — ingesting documents from /app/rag_data ..."
        mkdir -p "$(dirname "$_sentinel")"
        cd /app && python -m document_rag.ingestion.cli \
            --source-dir /app/rag_data \
            ${DOCUMENT_RAG_INGEST_FULL_REPLACE:+--full-replace}
        touch "$_sentinel"
        echo "[entrypoint] Document ingestion complete."
    else
        echo "[entrypoint] Documents already ingested (sentinel found) — skipping. Set DOCUMENT_RAG_INGEST_FULL_REPLACE=1 to re-ingest."
    fi
fi

exec "$@"
