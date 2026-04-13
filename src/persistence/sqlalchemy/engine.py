"""Build async SQLAlchemy engines from persistence settings."""

from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.engine.url import URL
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from config import PersistenceSettings

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _is_sqlite_url(url: URL) -> bool:
    return url.get_backend_name() == "sqlite"


def resolve_sqlite_path(url: URL) -> str | None:
    """Resolve a SQLite database path to an absolute path anchored to the project root.

    Relative paths in the URL (e.g. ``data/chatguru.db``) are resolved
    relative to the **project root**, not the process CWD.  This avoids
    creating a second, empty database when ``make dev`` changes CWD to ``src/``.
    """
    if not _is_sqlite_url(url):
        return None
    db = url.database
    if db is None or db in {"", ":memory:"}:
        return None
    path = Path(db)
    path = (
        (_PROJECT_ROOT / path).resolve()
        if not path.is_absolute()
        else path.expanduser().resolve()
    )
    return str(path)


def ensure_sqlite_file_parent_dir(url: URL) -> None:
    """Create parent directory for on-disk SQLite files (not :memory:)."""
    resolved = resolve_sqlite_path(url)
    if resolved is not None:
        Path(resolved).parent.mkdir(parents=True, exist_ok=True)


def _enable_sqlite_wal(engine: AsyncEngine) -> None:
    """Enable WAL journal mode so concurrent readers don't block writers."""

    @event.listens_for(engine.sync_engine, "connect")
    def _set_wal(dbapi_conn, _connection_record) -> None:  # type: ignore[no-untyped-def]  # noqa: ANN001
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


def create_async_engine_from_settings(settings: PersistenceSettings) -> AsyncEngine:
    """
    Create an :class:`AsyncEngine` from ``PERSISTENCE_DATABASE_URL``.

    Relative SQLite paths are resolved against the project root so the same
    file is used regardless of the process CWD.
    """
    url = make_url(settings.database_url)
    ensure_sqlite_file_parent_dir(url)

    resolved_path = resolve_sqlite_path(url)
    engine_url = (
        str(URL.create(url.drivername, database=resolved_path))
        if resolved_path is not None
        else settings.database_url
    )

    engine = create_async_engine(engine_url)
    if _is_sqlite_url(url):
        _enable_sqlite_wal(engine)
    return engine
