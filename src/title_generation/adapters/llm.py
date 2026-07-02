"""LLM-backed adapter for conversation title generation.

Runs through LiteLLM, so it works with any LiteLLM-supported provider using the
same configuration as the main chat agent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_litellm import ChatLiteLLM

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

from config import LLMSettings, get_logger
from title_generation.prompt import TITLE_GENERATION_SYSTEM_PROMPT
from title_generation.utils import truncate_title
from tracing import get_langfuse_handler

logger = get_logger("title_generation.adapters.llm")

# Generous headroom: reasoning tokens (when enabled) count against this budget
# alongside the visible title.
MAX_TITLE_COMPLETION_TOKENS = 1024
_MAX_LOG_MESSAGE_LENGTH = 500


class LLMTitleGenerator:
    """Generate conversation titles via the configured LLM."""

    def __init__(self, settings: LLMSettings) -> None:
        self._settings = settings
        self._llm: ChatLiteLLM | None = None

    def _build_connection_kwargs(self) -> dict[str, Any]:
        """Assemble LiteLLM connection kwargs, mirroring the chat client."""
        kwargs: dict[str, Any] = {}
        api_base = self._settings.api_base.strip()
        if api_base:
            kwargs["api_base"] = api_base.rstrip("/")
        if self._settings.api_key:
            kwargs["api_key"] = self._settings.api_key
            kwargs["extra_headers"] = {"api-key": self._settings.api_key}
        if self._settings.api_version:
            kwargs["api_version"] = self._settings.api_version
        # Only forward reasoning_effort when set; it errors on models without it.
        if self._settings.reasoning_effort:
            kwargs["reasoning_effort"] = self._settings.reasoning_effort
        return kwargs

    def _get_llm(self) -> ChatLiteLLM:
        """Return the shared LLM client for title generation."""
        if self._llm is None:
            # Mirror the chat client's temperature; reasoning models reject
            # non-default values.
            self._llm = ChatLiteLLM(
                model=self._settings.model,
                streaming=False,
                temperature=self._settings.temperature,
                max_tokens=MAX_TITLE_COMPLETION_TOKENS,
                **self._build_connection_kwargs(),
            )
        return self._llm

    async def connect(self) -> None:
        """No-op: client is initialized lazily on first generate call."""

    async def generate(self, first_message: str) -> str:
        """Generate a short title and fall back to truncation on errors."""
        try:
            logged_message = first_message
            if len(logged_message) > _MAX_LOG_MESSAGE_LENGTH:
                logged_message = logged_message[:_MAX_LOG_MESSAGE_LENGTH] + "…"
            logger.info(
                "Sending title prompt to LLM (system_prompt=%r, user_message=%r)",
                TITLE_GENERATION_SYSTEM_PROMPT,
                logged_message,
            )
            messages = [
                SystemMessage(content=TITLE_GENERATION_SYSTEM_PROMPT),
                HumanMessage(content=first_message),
            ]
            config: RunnableConfig = {}
            langfuse_handler = get_langfuse_handler()
            if langfuse_handler:
                config["callbacks"] = [langfuse_handler]
            response = await self._get_llm().ainvoke(messages, config=config)
            metadata = getattr(response, "response_metadata", {})
            logger.info(
                "LLM title response metadata: finish_reason=%s token_usage=%s",
                metadata.get("finish_reason"),
                metadata.get("token_usage"),
            )
            title = str(response.content).strip().strip('"').strip("'")
            if title:
                logger.info("Title generated via LLM (chars=%d)", len(title))
                return title
            logger.warning("LLM returned an empty title, using fallback")
        except Exception:
            logger.exception("LLM title generation failed, falling back to truncation")

        fallback_title = str(truncate_title(first_message))
        logger.info(
            "Title generated via fallback truncation (chars=%d)", len(fallback_title)
        )
        return fallback_title

    async def close(self) -> None:
        """Release client reference."""
        self._llm = None
