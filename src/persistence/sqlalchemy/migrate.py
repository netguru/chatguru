"""Apply Alembic migrations (CLI uses the same ``env.py`` as this API)."""

from pathlib import Path

from alembic import command
from alembic.config import Config

_SQLALCHEMY_DIR = Path(__file__).resolve().parent


def upgrade_head() -> None:
    """
    Run ``alembic upgrade head`` for the SQLAlchemy adapter.

    Uses ``PERSISTENCE_DATABASE_URL`` (via ``config.get_persistence_settings()`` in ``alembic/env.py``).
    """
    cfg = Config(str(_SQLALCHEMY_DIR / "alembic.ini"))
    command.upgrade(cfg, "head")
