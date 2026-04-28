"""OpenAI-compatible adapter for conversation title generation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from pydantic import SecretStr

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

from config import LLMSettings, get_logger
from title_generation.prompt import TITLE_GENERATION_SYSTEM_PROMPT
from title_generation.utils import truncate_title
from tracing import get_langfuse_handler

logger = get_logger("title_generation.adapters.openai")

# Token budget for the title call. Reasoning tokens (when enabled on gpt-5/o-series)
# are counted against this budget alongside the visible completion, so we leave
# generous headroom even though the visible title itself is tiny.
MAX_TITLE_COMPLETION_TOKENS = 1024
_MAX_LOG_MESSAGE_LENGTH = 500


class OpenAITitleGenerator:
    """Generate conversation titles with an OpenAI-compatible chat endpoint."""

    def __init__(self, settings: LLMSettings) -> None:
        self._settings = settings
        self._llm: ChatOpenAI | AzureChatOpenAI | None = None

    def _build_extra_kwargs(self) -> dict[str, Any]:
        """Build optional kwargs (reasoning_effort) only when configured.

        Title generation is a simple naming task, so when the underlying model is
        a reasoning model we cap effort at the user-configured level (or the
        provider default if unset). Passing ``reasoning_effort`` against a
        non-reasoning deployment would 400, hence the conditional.
        """
        extra: dict[str, Any] = {}
        if self._settings.reasoning_effort:
            extra["reasoning_effort"] = self._settings.reasoning_effort
        return extra

    def _get_llm(self) -> ChatOpenAI | AzureChatOpenAI:
        """Return the shared LLM client for title generation."""
        if self._llm is None:
            extra_kwargs = self._build_extra_kwargs()
            # Reasoning models (gpt-5 family) reject anything other than the
            # default temperature=1, so we mirror the chat client's setting
            # rather than hard-coding 0.
            temperature = self._settings.temperature
            compat_base = self._settings.openai_base_url.strip()
            if compat_base:
                self._llm = ChatOpenAI(
                    model=self._settings.deployment_name,
                    api_key=SecretStr(self._settings.api_key),
                    base_url=compat_base.rstrip("/"),
                    default_headers={"api-key": self._settings.api_key},
                    streaming=False,
                    temperature=temperature,
                    max_completion_tokens=MAX_TITLE_COMPLETION_TOKENS,
                    **extra_kwargs,
                )
            else:
                self._llm = AzureChatOpenAI(
                    azure_deployment=self._settings.deployment_name,
                    api_key=SecretStr(self._settings.api_key),
                    azure_endpoint=self._settings.endpoint.rstrip("/"),
                    api_version=self._settings.api_version,
                    default_headers={"api-key": self._settings.api_key},
                    streaming=False,
                    temperature=temperature,
                    max_completion_tokens=MAX_TITLE_COMPLETION_TOKENS,
                    **extra_kwargs,
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
