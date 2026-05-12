"""Configuration management for chatguru Agent."""

import logging
from functools import lru_cache
from logging import Logger
from logging.config import dictConfig
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_env_file_path() -> str:
    """
    Get the absolute path to the .env file.

    Returns:
        Absolute path to the .env file in the project root
    """
    current_file = Path(__file__)
    project_root = current_file.parent.parent
    env_file = project_root / ".env"
    return str(env_file)


class LoggingSettings(BaseSettings):
    """Get the logging settings for the application."""

    format: str = (
        "%(asctime)s %(name)-15s %(levelname)-8s %(processName)-10s %(threadName)-10s %(message)s"
    )
    level: str = "INFO"
    handlers_level: str = "DEBUG"

    model_config = SettingsConfigDict(env_prefix="log_")

    @property
    def config_dict(self) -> dict:
        """Get the logging configuration for the application."""
        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "human_readable": {"class": "logging.Formatter", "format": self.format},
            },
            "loggers": {
                "logger": {
                    "handlers": ["console_handler"],
                    "propagate": False,
                    "level": self.level,
                },
            },
            "handlers": {
                "console_handler": {
                    "formatter": "human_readable",
                    "class": "logging.StreamHandler",
                },
                "root_handler": {
                    "formatter": "human_readable",
                    "class": "logging.StreamHandler",
                },
            },
            "root": {"handlers": ["root_handler"], "level": self.level},
        }


def get_logger(component: str, log_level: str | None = None) -> Logger:
    """
    Get a logger instance for the given component.

    Args:
        component: Component name for the logger
        log_level: Optional log level override (e.g., "DEBUG", "INFO")

    Returns:
        Configured logger instance
    """
    logging_settings = LoggingSettings()
    dictConfig(logging_settings.config_dict)
    logger = logging.getLogger(f"{component}_logger")
    logger.setLevel(logging.INFO)
    if log_level:
        logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    return logger


class AppSettings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=get_env_file_path(),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    app_name: str = Field(
        default="NG chatguru Agent",
        description="Application name",
    )

    # Application Configuration
    debug: bool = Field(
        default=False,
        description="Enable debug mode",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level",
    )


class FastAPISettings(BaseSettings):
    """FastAPI settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=get_env_file_path(),
        env_prefix="FASTAPI_",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    host: str = Field(
        default="0.0.0.0",  # noqa: S104
        description="FastAPI host",
    )
    port: int = Field(
        default=8000,
        description="FastAPI port",
    )
    cors_origins: list[str] = Field(
        default=["*"],
        description="CORS allowed origins",
    )
    debug: bool = Field(
        default=False,
        description="Enable debug mode",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level",
    )


class LLMSettings(BaseSettings):
    """LLM settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=get_env_file_path(),
        env_prefix="LLM_",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    endpoint: str = Field(
        default="",
        validation_alias=AliasChoices("OPENAI_ENDPOINT"),
        description=(
            "OpenAI-compatible base URL for chat and embeddings "
            "(e.g. https://api.openai.com/v1 or an Azure APIM proxy). "
            "The chat client appends /chat/completions; the embeddings client appends /embeddings."
        ),
    )
    api_key: str = Field(
        default="",
        description="API key (LLM_API_KEY).",
    )
    api_version: str = Field(
        default="",
        description="API version string, required only for native Azure OpenAI (LLM_API_VERSION).",
    )
    deployment_name: str = Field(
        default="",
        description="Model / deployment name (LLM_DEPLOYMENT_NAME).",
    )
    openai_base_url: str = Field(
        default="",
        description=(
            "If set, chat uses OpenAI v1-compatible Chat Completions at this base URL "
            "(e.g. Azure APIM .../plc/openai/v1). LLM_DEPLOYMENT_NAME is the model id. "
            "Auth uses the api-key header (APIM subscription key)."
        ),
    )
    temperature: float = Field(
        default=1,
        description="Sampling temperature (LLM_TEMPERATURE).",
    )
    reasoning_effort: str = Field(
        default="",
        description=(
            "Reasoning effort for OpenAI reasoning models (gpt-5 family, o-series). "
            "Allowed values: 'none', 'low', 'medium', 'high'."
            "it can be different for different models, please check docs https://developers.openai.com/api/docs/guides/reasoning#reasoning-effort"
        ),
    )
    embeddings_endpoint: str = Field(
        default="",
        validation_alias=AliasChoices("OPENAI_EMBEDDINGS_ENDPOINT"),
        description=(
            "OpenAI-compatible base URL for the embeddings model. Defaults to OPENAI_ENDPOINT when empty."
        ),
    )
    embeddings_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("OPENAI_EMBEDDINGS_API_KEY"),
        description=(
            "API key for the embeddings endpoint. Defaults to LLM_API_KEY when empty."
        ),
    )
    embedding_deployment_name: str = Field(
        default="text-embedding-ada-002",
        description="Embeddings model / deployment name (LLM_EMBEDDING_DEPLOYMENT_NAME).",
    )
    embedding_dimensions: int = Field(
        default=1536,
        description="Embedding vector dimensions (LLM_EMBEDDING_DIMENSIONS).",
    )


@lru_cache
def get_fastapi_settings() -> FastAPISettings:
    """Get FastAPI settings."""
    return FastAPISettings()


@lru_cache
def get_app_settings() -> AppSettings:
    """Get application settings."""
    return AppSettings()


class LangfuseSettings(BaseSettings):
    """Langfuse observability settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=get_env_file_path(),
        env_prefix="LANGFUSE_",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    public_key: str = Field(
        default="",
        description="Langfuse public key",
    )
    secret_key: str = Field(
        default="",
        description="Langfuse secret key",
    )
    host: str = Field(
        default="https://cloud.langfuse.com",
        description="Langfuse host URL",
    )
    enabled: bool = Field(
        default=True,
        description="Enable Langfuse tracing",
    )


@lru_cache
def get_llm_settings() -> LLMSettings:
    """Get LLM settings."""
    return LLMSettings()


@lru_cache
def get_langfuse_settings() -> LangfuseSettings:
    """Get Langfuse settings."""
    return LangfuseSettings()


class VectorDBSettings(BaseSettings):
    """Vector database settings."""

    model_config = SettingsConfigDict(
        env_file=get_env_file_path(),
        env_prefix="VECTOR_DB_",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database type: "sqlite" or "mongodb"
    type: str = Field(
        default="mongodb",
        description="Database type: 'sqlite' or 'mongodb'",
    )

    # SQLite settings
    sqlite_url: str = Field(
        default="http://localhost:8001",
        description="SQLite database service URL",
    )

    # MongoDB settings
    mongodb_uri: str = Field(
        default="mongodb://localhost:27017",
        description="MongoDB connection URI (for Atlas: mongodb+srv://...)",
    )
    mongodb_api_url: str = Field(
        default="http://localhost:8002",
        description="MongoDB vector database API service URL (HTTP endpoint)",
    )
    mongodb_database: str = Field(
        default="products",
        description="MongoDB database name",
    )
    mongodb_collection: str = Field(
        default="products",
        description="MongoDB collection name",
    )

    # Common settings
    timeout: int = Field(
        default=30,
        description="Request timeout in seconds",
    )


@lru_cache
def get_vector_db_settings() -> VectorDBSettings:
    """Get vector database settings."""
    return VectorDBSettings()


class PersistenceSettings(BaseSettings):
    """Chat history persistence (async SQLAlchemy engine URL)."""

    model_config = SettingsConfigDict(
        env_file=get_env_file_path(),
        env_prefix="PERSISTENCE_",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str | None = Field(
        default=None,
        description=(
            "Async SQLAlchemy URL: ``<dialect>+<async_driver>://…`` "
            "(e.g. sqlite+aiosqlite, postgresql+asyncpg, mysql+aiomysql). "
            "When unset, chat history persistence is disabled and no messages are stored. "
            "Run ``make migrate`` after setting or changing this value."
        ),
    )


@lru_cache
def get_persistence_settings() -> PersistenceSettings:
    """Get persistence settings."""
    return PersistenceSettings()


class TitleGenerationSettings(BaseSettings):
    """Conversation title generation provider settings."""

    model_config = SettingsConfigDict(
        env_file=get_env_file_path(),
        env_prefix="TITLE_GENERATION_",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    provider: str = Field(
        default="openai",
        description=(
            "Title generation provider: openai, fallback, or custom. Use fallback to disable external model calls."
        ),
    )
    custom_class: str = Field(
        default="",
        description=(
            "When provider is custom, class path in module.path:ClassName format."
        ),
    )


@lru_cache
def get_title_generation_settings() -> TitleGenerationSettings:
    """Get title generation settings."""
    return TitleGenerationSettings()


class RateLimitSettings(BaseSettings):
    """Rate limiting settings."""

    model_config = SettingsConfigDict(
        env_file=get_env_file_path(),
        env_prefix="RATE_LIMIT_",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    enabled: bool = Field(
        default=False,
        description="Enable Redis-backed rate limiting (RATE_LIMIT_ENABLED).",
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL (RATE_LIMIT_REDIS_URL).",
    )
    max_messages: int = Field(
        default=10,
        ge=1,
        description="Max LLM messages allowed per IP per window (RATE_LIMIT_MAX_MESSAGES).",
    )
    window_seconds: int = Field(
        default=86400,
        ge=1,
        description="Fixed window length in seconds (RATE_LIMIT_WINDOW_SECONDS). Default: 24 h.",
    )
    trust_proxy: bool = Field(
        default=False,
        description=(
            "When True, extract the real client IP from the X-Forwarded-For or X-Real-IP "
            "header instead of the direct TCP connection address. "
            "Enable only when the app is behind a trusted reverse proxy (RATE_LIMIT_TRUST_PROXY)."
        ),
    )


@lru_cache
def get_rate_limit_settings() -> RateLimitSettings:
    """Get rate limit settings."""
    return RateLimitSettings()


class DoclingSettings(BaseSettings):
    """Document ingestion (Docling) upload endpoint settings."""

    model_config = SettingsConfigDict(
        env_file=get_env_file_path(),
        env_prefix="DOCLING_",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    enabled: bool = Field(
        default=True,
        description="Enable POST /process-document (DOCLING_ENABLED).",
    )
    max_file_size_bytes: int = Field(
        default=20 * 1024 * 1024,
        ge=1,
        description="Maximum upload size in bytes (DOCLING_MAX_FILE_SIZE_BYTES).",
    )
    picture_description_enabled: bool = Field(
        default=False,
        description=(
            "Enable VLM-based image description for pictures found in documents "
            "(DOCLING_PICTURE_DESCRIPTION_ENABLED). Requires a vision-capable model "
            "and DOCLING_PICTURE_DESCRIPTION_URL to be set."
        ),
    )
    picture_description_url: str = Field(
        default="",
        description=(
            "Full OpenAI-compatible chat completions URL used to describe images, "
            "e.g. https://api.openai.com/v1/chat/completions or an Azure deployment URL "
            "(DOCLING_PICTURE_DESCRIPTION_URL). Required when DOCLING_PICTURE_DESCRIPTION_ENABLED=true."
        ),
    )
    picture_description_api_key: str = Field(
        default="",
        description=(
            "API key for the picture description endpoint. Falls back to LLM_API_KEY when empty "
            "(DOCLING_PICTURE_DESCRIPTION_API_KEY)."
        ),
    )


@lru_cache
def get_docling_settings() -> DoclingSettings:
    """Get Docling / document upload settings."""
    return DoclingSettings()
