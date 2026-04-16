"""Deterministic fallback adapter for conversation title generation."""

from config import get_logger
from title_generation.prompt import TITLE_GENERATION_SYSTEM_PROMPT
from title_generation.utils import truncate_title

logger = get_logger("title_generation.adapters.fallback")


class FallbackTitleGenerator:
    """Title generator that always truncates the first user message."""

    def __init__(self) -> None:
        self._prompt = TITLE_GENERATION_SYSTEM_PROMPT

    async def connect(self) -> None:
        """No-op for deterministic local implementation."""
        if not self._prompt:
            msg = "Shared title-generation prompt is empty"
            raise RuntimeError(msg)

    async def generate(self, first_message: str) -> str:
        """Generate a title without external model calls."""
        logger.debug(
            "Generating title with fallback adapter and shared prompt rules: %s",
            bool(self._prompt),
        )
        return str(truncate_title(first_message))

    async def close(self) -> None:
        """No-op for deterministic local implementation."""
