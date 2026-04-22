"""OpenAI-compatible adapter for conversation title generation."""

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from pydantic import SecretStr

from config import LLMSettings, get_logger
from title_generation.prompt import TITLE_GENERATION_SYSTEM_PROMPT
from title_generation.utils import truncate_title

logger = get_logger("title_generation.adapters.openai")

MAX_TITLE_COMPLETION_TOKENS = 256
_MAX_LOG_MESSAGE_LENGTH = 500


class OpenAITitleGenerator:
    """Generate conversation titles with an OpenAI-compatible chat endpoint."""

    def __init__(self, settings: LLMSettings) -> None:
        self._settings = settings
        self._llm: ChatOpenAI | AzureChatOpenAI | None = None

    def _get_llm(self) -> ChatOpenAI | AzureChatOpenAI:
        """Return the shared LLM client for title generation."""
        if self._llm is None:
            compat_base = self._settings.openai_base_url.strip()
            if compat_base:
                self._llm = ChatOpenAI(
                    model=self._settings.deployment_name,
                    api_key=SecretStr(self._settings.api_key),
                    base_url=compat_base.rstrip("/"),
                    default_headers={"api-key": self._settings.api_key},
                    streaming=False,
                    temperature=0,
                    max_completion_tokens=MAX_TITLE_COMPLETION_TOKENS,
                )
            else:
                self._llm = AzureChatOpenAI(
                    azure_deployment=self._settings.deployment_name,
                    api_key=SecretStr(self._settings.api_key),
                    azure_endpoint=self._settings.endpoint.rstrip("/"),
                    api_version=self._settings.api_version,
                    default_headers={"api-key": self._settings.api_key},
                    streaming=False,
                    temperature=0,
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
            response = await self._get_llm().ainvoke(
                [
                    SystemMessage(content=TITLE_GENERATION_SYSTEM_PROMPT),
                    HumanMessage(content=first_message),
                ]
            )
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
