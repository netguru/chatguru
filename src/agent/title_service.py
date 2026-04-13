"""
LLM-based conversation title generation.

Generates a short, descriptive title from the first user message of a conversation.
Falls back to simple truncation when the LLM call fails.
"""

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from config import get_llm_settings, get_logger

logger = get_logger("agent.title_service")

_SYSTEM_PROMPT = (
    "You are a conversation title generator. "
    "Given the user's first message, reply with a short title of at most 7 words "
    "that captures the topic. "
    "Rules: no quotes, no punctuation at the end, title case."
)

_MAX_FALLBACK_LENGTH = 60

_title_llm: ChatOpenAI | None = None


def _get_title_llm() -> ChatOpenAI:
    """Return the shared LLM client for title generation, creating it on first call."""
    global _title_llm  # noqa: PLW0603
    if _title_llm is None:
        settings = get_llm_settings()
        _title_llm = ChatOpenAI(
            model=settings.deployment_name,
            api_key=settings.api_key,
            base_url=settings.endpoint.rstrip("/"),
            default_headers={"api-key": settings.api_key},
            streaming=False,
            temperature=0,
            max_completion_tokens=30,
        )
    return _title_llm


def truncate_title(text: str) -> str:
    """Word-boundary truncation used as the fallback title."""
    text = text.strip()
    if len(text) <= _MAX_FALLBACK_LENGTH:
        return text
    truncated = text[:_MAX_FALLBACK_LENGTH]
    last_space = truncated.rfind(" ")
    return (truncated[:last_space] if last_space > 0 else truncated) + "…"


async def generate_title(first_message: str) -> str:
    """
    Generate a short conversation title from the first user message.

    Uses the configured LLM (same credentials as the main agent).
    Falls back to word-boundary truncation if the call fails, so callers never
    need to handle exceptions from this function.

    Args:
        first_message: The first user message of the conversation.

    Returns:
        A short title string, always non-empty.
    """
    try:
        llm = _get_title_llm()
        response = await llm.ainvoke(
            [
                SystemMessage(content=_SYSTEM_PROMPT),
                HumanMessage(content=first_message),
            ]
        )
        title = str(response.content).strip().strip('"').strip("'")
        if title:
            return title
    except Exception:
        logger.exception("LLM title generation failed, falling back to truncation")

    return truncate_title(first_message)
