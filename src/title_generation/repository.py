"""Repository port (interface) for conversation title generation."""

from typing import Protocol


class TitleGenerator(Protocol):
    """Port for generating a conversation title from the first user message."""

    async def connect(self) -> None:
        """Initialize provider resources (optional no-op for simple adapters)."""
        ...

    async def generate(self, first_message: str) -> str:
        """Generate a short title. Implementations should never raise."""
        ...

    async def close(self) -> None:
        """Release provider resources (optional no-op for simple adapters)."""
        ...
