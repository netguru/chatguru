"""Alembic environment: async engine, metadata from persistence tables."""

from __future__ import annotations

import asyncio
import concurrent.futures
import sys
from logging.config import fileConfig
from pathlib import Path
from typing import TYPE_CHECKING

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection

# Project root = 4 levels up from  src/persistence/sqlalchemy/alembic/env.py
_ROOT = Path(__file__).resolve().parents[4]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config import get_persistence_settings  # noqa: E402
from persistence.sqlalchemy.engine import (  # noqa: E402
    ensure_sqlite_file_parent_dir,
    resolve_sqlite_path,
)
from persistence.sqlalchemy.tables import metadata as target_metadata  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def get_database_url() -> str:
    """Resolved URL for migrations (relative SQLite paths become absolute)."""
    from sqlalchemy.engine import make_url  # noqa: PLC0415
    from sqlalchemy.engine.url import URL as SaURL  # noqa: N811, PLC0415

    raw = get_persistence_settings().database_url
    if raw is None:
        msg = (
            "PERSISTENCE_DATABASE_URL is not set. "
            "Export it before running migrations:  export PERSISTENCE_DATABASE_URL=..."
        )
        raise RuntimeError(msg)
    url = make_url(raw)
    resolved = resolve_sqlite_path(url)
    if resolved is not None:
        return str(SaURL.create(url.drivername, database=resolved))
    return str(raw)


def run_migrations_offline() -> None:
    """Generate SQL without a live connection (e.g. ``alembic upgrade --sql``)."""
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations against the async engine (sqlite+aiosqlite, postgresql+asyncpg, …)."""
    ini_section = config.get_section(config.config_ini_section) or {}
    url = get_database_url()
    ini_section["sqlalchemy.url"] = url

    from sqlalchemy.engine import make_url  # noqa: PLC0415

    ensure_sqlite_file_parent_dir(make_url(url))

    connectable = async_engine_from_config(
        ini_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations; use a fresh event loop in a thread if one is already running (e.g. pytest-async)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(run_async_migrations())
    else:

        def _run_in_thread() -> None:
            asyncio.run(run_async_migrations())

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            executor.submit(_run_in_thread).result()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
