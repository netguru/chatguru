#!/bin/sh
# Docker entrypoint — runs Alembic migrations when a SQLAlchemy-compatible URL is configured.
#
# Migrations are only triggered for SQL dialects (sqlite+aiosqlite, postgresql+asyncpg, …).
# URLs for other adapters (mongodb://, dynamodb://, …) are passed through untouched.
# The command is idempotent — safe to run on every container start.
# The container exits non-zero if migrations fail so the health-check never turns green.
set -e

if [ -n "$PERSISTENCE_DATABASE_URL" ]; then
    case "$PERSISTENCE_DATABASE_URL" in
        sqlite+*|postgresql+*|mysql+*|mariadb+*|mssql+*|oracle+*|cockroachdb+*)
            echo "[entrypoint] SQLAlchemy URL detected — running database migrations..."
            uv run alembic -c /app/src/persistence/sqlalchemy/alembic.ini upgrade head
            echo "[entrypoint] Migrations complete."
            ;;
        *)
            echo "[entrypoint] Non-SQLAlchemy URL detected — skipping Alembic migrations."
            ;;
    esac
fi

exec "$@"
