"""Process-wide title generator (FastAPI app lifespan)."""

from config import get_logger
from title_generation.factory import build_title_generator
from title_generation.repository import TitleGenerator
from title_generation.utils import truncate_title
from tracing import flush_langfuse_async, propagate_attributes

logger = get_logger(__name__)

_title_generator: TitleGenerator | None = None


async def init_title_generation() -> None:
    """Initialize the process-wide title generator (call once at startup)."""
    global _title_generator  # noqa: PLW0603
    if _title_generator is not None:
        return
    _title_generator = await build_title_generator()
    logger.info("Title generation initialized")


async def shutdown_title_generation() -> None:
    """Close the title generator (call at shutdown)."""
    global _title_generator  # noqa: PLW0603
    if _title_generator is not None:
        await _title_generator.close()
        _title_generator = None
        logger.info("Title generation shut down")


def get_title_generator() -> TitleGenerator:
    """Return the process-wide title generator."""
    if _title_generator is None:
        msg = "Title generator is not initialized"
        raise RuntimeError(msg)
    return _title_generator


async def generate_title(
    first_message: str,
    *,
    session_id: str | None = None,
    visitor_id: str | None = None,
) -> str:
    """Generate title through configured provider with hard safety fallback.

    Args:
        first_message: The first user message used to derive the title.
        session_id: Optional session ID forwarded to Langfuse for trace grouping.
        visitor_id: Optional visitor/user ID forwarded to Langfuse.
    """
    try:
        with propagate_attributes(session_id=session_id, user_id=visitor_id):
            try:
                title = str(await get_title_generator().generate(first_message))
            finally:
                await flush_langfuse_async()
        if title.strip():
            return title
    except Exception:
        logger.exception(
            "Title provider failed unexpectedly, falling back to truncation"
        )
    return str(truncate_title(first_message))
