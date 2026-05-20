"""Utility helpers for title generation."""

import re

MAX_FALLBACK_LENGTH = 60

_DOCUMENT_TAG_RE = re.compile(r"<document\b[^>]*>.*?</document>", re.DOTALL)


def strip_document_tags(text: str) -> str:
    """Remove <document> blocks from a message before title generation."""
    return _DOCUMENT_TAG_RE.sub("", text).strip()


def truncate_title(text: str) -> str:
    """Word-boundary truncation used as fallback title generation."""
    text = text.strip()
    if len(text) <= MAX_FALLBACK_LENGTH:
        return text
    truncated = text[:MAX_FALLBACK_LENGTH]
    last_space = truncated.rfind(" ")
    return (truncated[:last_space] if last_space > 0 else truncated) + "…"
