"""Configuration management for chatguru Agent."""

import json
import logging
from functools import lru_cache
from logging import Logger
from logging.config import dictConfig
from pathlib import Path

from pydantic import AliasChoices, BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LiteLLMModel(BaseModel):
    label: str
    id: str


class LiteLLMProvider(BaseModel):
    name: str
    models: list[LiteLLMModel]


class LiteLLMModelsConfig(BaseModel):
    providers: list[LiteLLMProvider]


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
    """LLM settings loaded from environment variables.

    The app is provider-agnostic: chat runs through LiteLLM, which routes
    ``provider/model`` ids (``openai/gpt-4o``, ``azure/<deployment>``,
    ``anthropic/claude-...``, ``ollama/llama3``, …) to the right backend, and
    embeddings run against any OpenAI-compatible endpoint. When ``api_base`` /
    ``api_key`` are set they are forwarded to every provider (covering gateways
    such as Azure APIM); when empty, LiteLLM falls back to each provider's own
    default endpoint and standard credential env vars. Legacy ``OPENAI_*`` /
    ``LLM_DEPLOYMENT_NAME`` names remain accepted as aliases.
    """

    model_config = SettingsConfigDict(
        env_file=get_env_file_path(),
        env_prefix="LLM_",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    api_base: str = Field(
        default="",
        validation_alias=AliasChoices(
            "LLM_API_BASE", "LLM_OPENAI_BASE_URL", "OPENAI_ENDPOINT"
        ),
        description=(
            "Base URL for the chat/embeddings API. Point it at an OpenAI-compatible "
            "endpoint or a gateway (e.g. an Azure APIM proxy). Leave empty to use each "
            "provider's default endpoint via LiteLLM. (LLM_API_BASE)"
        ),
    )
    api_key: str = Field(
        default="",
        description="API key forwarded to the provider/gateway (LLM_API_KEY).",
    )
    api_version: str = Field(
        default="",
        description="API version string, required by some gateways such as Azure (LLM_API_VERSION).",
    )
    model: str = Field(
        default="",
        validation_alias=AliasChoices("LLM_MODEL", "LLM_DEPLOYMENT_NAME"),
        description=(
            "Default model id in LiteLLM form, e.g. 'openai/gpt-4o', "
            "'azure/<deployment>', 'anthropic/claude-3-5-sonnet'. (LLM_MODEL)"
        ),
    )
    temperature: float = Field(
        default=1,
        description="Sampling temperature (LLM_TEMPERATURE).",
    )
    reasoning_effort: str = Field(
        default="",
        description=(
            "Reasoning effort for models that support it. "
            "Allowed values: 'none', 'low', 'medium', 'high'. "
            "Leave empty to use the model default; supported values vary by model. "
            "(LLM_REASONING_EFFORT)"
        ),
    )
    embeddings_api_base: str = Field(
        default="",
        validation_alias=AliasChoices(
            "LLM_EMBEDDINGS_API_BASE", "OPENAI_EMBEDDINGS_ENDPOINT"
        ),
        description=(
            "Base URL for the embeddings API. Falls back to LLM_API_BASE when empty. "
            "(LLM_EMBEDDINGS_API_BASE)"
        ),
    )
    embeddings_api_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "LLM_EMBEDDINGS_API_KEY", "OPENAI_EMBEDDINGS_API_KEY"
        ),
        description="API key for the embeddings endpoint. Falls back to LLM_API_KEY when empty.",
    )
    embedding_model: str = Field(
        default="text-embedding-ada-002",
        validation_alias=AliasChoices(
            "LLM_EMBEDDING_MODEL", "LLM_EMBEDDING_DEPLOYMENT_NAME"
        ),
        description="Embeddings model id (LLM_EMBEDDING_MODEL).",
    )
    embedding_dimensions: int = Field(
        default=1536,
        description="Embedding vector dimensions (LLM_EMBEDDING_DIMENSIONS).",
    )
    litellm_models_config_path: str = Field(
        default="",
        validation_alias=AliasChoices("LLM_LITELLM_MODELS_CONFIG"),
        description=(
            "Path to the JSON file listing selectable models; powers the model picker "
            "(LLM_LITELLM_MODELS_CONFIG)."
        ),
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
def get_litellm_models_config() -> LiteLLMModelsConfig | None:
    """Load and cache the LiteLLM models config from the JSON file.

    Returns None when LLM_LITELLM_MODELS_CONFIG is not set.
    Raises FileNotFoundError / ValueError on invalid config.
    """
    settings = get_llm_settings()
    if not settings.litellm_models_config_path:
        return None
    path = Path(settings.litellm_models_config_path)
    if not path.exists():
        msg = (
            f"LiteLLM models config file not found: {path}. "
            "Set LLM_LITELLM_MODELS_CONFIG to a valid path."
        )
        raise FileNotFoundError(msg)
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return LiteLLMModelsConfig(**data)


def resolve_default_model() -> str | None:
    """Pick the default model used when a request doesn't override it.

    An explicit ``LLM_MODEL`` always wins so operators keep a single source of
    truth for the deployment's model. The first entry in the models config is
    only a fallback for when ``LLM_MODEL`` is unset.
    """
    model = get_llm_settings().model
    if model:
        return model
    config = get_litellm_models_config()
    if config and config.providers and config.providers[0].models:
        return str(config.providers[0].models[0].id)
    return None


@lru_cache
def get_langfuse_settings() -> LangfuseSettings:
    """Get Langfuse settings."""
    return LangfuseSettings()


class AgentSettings(BaseSettings):
    """Chat agent settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=get_env_file_path(),
        env_prefix="AGENT_",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    system_prompt_fallback_file: str = Field(
        default="",
        description=(
            "Path to a local .md file used as the chat system prompt fallback "
            "when the Langfuse fetch is unavailable. Falls back to the built-in "
            "prompt when unset or unreadable. (AGENT_SYSTEM_PROMPT_FALLBACK_FILE)"
        ),
    )


@lru_cache
def get_agent_settings() -> AgentSettings:
    """Get chat agent settings."""
    return AgentSettings()


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


class DocumentRagSettings(BaseSettings):
    """Document RAG repository settings."""

    model_config = SettingsConfigDict(
        env_file=get_env_file_path(),
        env_prefix="DOCUMENT_RAG_",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    enabled: bool = Field(
        default=False,
        description="Enable document RAG repository bootstrap.",
    )
    backend: str = Field(
        default="mongodb",
        description="Document RAG backend. Supported: mongodb (Atlas), cosmos (Cosmos DB for MongoDB vCore).",
    )
    mongodb_uri: str = Field(
        default="mongodb://localhost:27017",
        description="MongoDB URI for document RAG.",
    )
    mongodb_database: str = Field(
        default="chatguru",
        description="MongoDB database for document RAG documents.",
    )
    mongodb_collection: str = Field(
        default="documents",
        description="MongoDB collection for document chunks.",
    )
    mongodb_index_name: str = Field(
        default="document_vector_index",
        description="MongoDB vector search index name for document retrieval.",
    )
    search_limit_default: int = Field(
        default=5,
        description="Default result count for document search.",
    )
    mongodb_connection_timeout_ms: int = Field(
        default=5000,
        description="MongoDB server selection timeout in milliseconds.",
    )
    embedding_provider: str = Field(
        default="openai",
        description="Embedding provider for document retrieval: openai or custom.",
    )
    embedding_custom_class: str = Field(
        default="",
        description="Custom embedding provider class path (module.path:ClassName).",
    )
    mongodb_files_bucket: str = Field(
        default="document_sources",
        description="MongoDB GridFS bucket name for storing full source documents.",
    )
    # Cosmos DB for MongoDB vCore vector index tuning (backend=cosmos only).
    # Cosmos vCore uses createIndexes + cosmosSearchOptions rather than the
    # Atlas search-index API; these control how that vector index is built.
    cosmos_vector_index_kind: str = Field(
        default="vector-ivf",
        description="Cosmos vCore vector index kind: vector-ivf or vector-hnsw.",
    )
    cosmos_vector_num_lists: int = Field(
        default=1,
        ge=1,
        description="IVF list count (cosmos_vector_index_kind=vector-ivf).",
    )
    cosmos_vector_m: int = Field(
        default=16,
        ge=2,
        description="HNSW connections per layer (cosmos_vector_index_kind=vector-hnsw).",
    )
    cosmos_vector_ef_construction: int = Field(
        default=64,
        ge=4,
        description="HNSW efConstruction (cosmos_vector_index_kind=vector-hnsw).",
    )
    cosmos_vector_similarity: str = Field(
        default="COS",
        description="Cosmos vCore vector similarity metric: COS, L2, or IP.",
    )

    @field_validator("cosmos_vector_index_kind")
    @classmethod
    def _validate_cosmos_vector_index_kind(cls, value: str) -> str:
        allowed = {"vector-ivf", "vector-hnsw"}
        if value not in allowed:
            msg = (
                f"cosmos_vector_index_kind must be one of {sorted(allowed)}, "
                f"got '{value}'"
            )
            raise ValueError(msg)
        return value

    @field_validator("cosmos_vector_similarity")
    @classmethod
    def _validate_cosmos_vector_similarity(cls, value: str) -> str:
        allowed = {"COS", "L2", "IP"}
        if value not in allowed:
            msg = (
                f"cosmos_vector_similarity must be one of {sorted(allowed)}, "
                f"got '{value}'"
            )
            raise ValueError(msg)
        return value


@lru_cache
def get_document_rag_settings() -> DocumentRagSettings:
    """Get document RAG settings."""
    return DocumentRagSettings()


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
    max_uploads: int = Field(
        default=10,
        ge=1,
        description=(
            "Max file uploads (POST /process-document) allowed per IP per window "
            "(RATE_LIMIT_MAX_UPLOADS). Uses the same window as max_messages."
        ),
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
            "API key for the picture description endpoint. Falls back to LLM_API_KEY when empty (DOCLING_PICTURE_DESCRIPTION_API_KEY)."
        ),
    )


@lru_cache
def get_docling_settings() -> DoclingSettings:
    """Get Docling / document upload settings."""
    return DoclingSettings()


class AttachmentStorageSettings(BaseSettings):
    """Attachment binary storage settings."""

    model_config = SettingsConfigDict(
        env_file=get_env_file_path(),
        env_prefix="ATTACHMENT_STORAGE_",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    enabled: bool = Field(
        default=True,
        description=(
            "Enable attachment binary storage (ATTACHMENT_STORAGE_ENABLED). "
            "Set to false to disable file uploads and attachment retrieval entirely. "
            "When disabled, upload endpoints still accept files but return no attachment_id."
        ),
    )
    type: str = Field(
        default="filesystem",
        description=(
            "Storage backend for uploaded attachments. Supported: 'filesystem'. Future: 'azure_blob', 's3'."
        ),
    )
    base_path: str = Field(
        default="./attachments",
        description=(
            "Base directory for filesystem attachment storage "
            "(ATTACHMENT_STORAGE_BASE_PATH). "
            "Created automatically if it does not exist. "
            "Use an absolute path or one relative to the working directory."
        ),
    )


@lru_cache
def get_attachment_storage_settings() -> AttachmentStorageSettings:
    """Get attachment storage settings."""
    return AttachmentStorageSettings()


class McpSettings(BaseSettings):
    """Model Context Protocol (MCP) server integration settings."""

    model_config = SettingsConfigDict(
        env_file=get_env_file_path(),
        env_prefix="MCP_",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    enabled: bool = Field(
        default=False,
        description="Enable loading tools from remote MCP servers (MCP_ENABLED).",
    )
    config_path: str = Field(
        default="",
        description=(
            "Path to a JSON file declaring remote MCP servers (MCP_CONFIG_PATH). "
            'Claude-Desktop style: {"mcpServers": {"<name>": {"url": "https://...", '
            '"transport": "streamable_http", "headers": {"Authorization": "Bearer ${TOKEN}"}}}}. '
            "Only the streamable_http and sse transports are supported; ${VAR} placeholders "
            "in string values are expanded from the environment at load time."
        ),
    )


@lru_cache
def get_mcp_settings() -> McpSettings:
    """Get MCP integration settings."""
    return McpSettings()
