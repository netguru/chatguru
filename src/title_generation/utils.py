"""Utility helpers for title generation."""

MAX_FALLBACK_LENGTH = 60


def truncate_title(text: str) -> str:
    """Word-boundary truncation used as fallback title generation."""
    text = text.strip()
    if len(text) <= MAX_FALLBACK_LENGTH:
        return text
    truncated = text[:MAX_FALLBACK_LENGTH]
    last_space = truncated.rfind(" ")
    return (truncated[:last_space] if last_space > 0 else truncated) + "…"
