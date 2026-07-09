"""FastAPI application for chatguru Agent."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from agent.service import resolve_default_model
from api.routes.chat import await_background_tasks
from api.routes.chat import router as chat_router
from api.routes.documents import router as documents_router
from api.routes.history import persistence_router
from attachment_storage import init_attachment_storage, shutdown_attachment_storage
from config import (
    get_app_settings,
    get_docling_settings,
    get_fastapi_settings,
    get_litellm_models_config,
    get_llm_settings,
    get_logger,
)
from document_processing.service import prewarm_converter
from document_rag import init_document_rag, shutdown_document_rag
from mcp_integration import init_mcp, shutdown_mcp
from persistence import init_persistence, is_persistence_enabled, shutdown_persistence
from rate_limiting import init_rate_limiting, shutdown_rate_limiting
from title_generation import init_title_generation, shutdown_title_generation
from tracing import init_langfuse

logger = get_logger(__name__)
app_settings = get_app_settings()
fastapi_settings = get_fastapi_settings()


def _model_provider(model_id: str) -> str:
    """Return the LiteLLM provider a model id routes to (bare ids → openai)."""
    return model_id.split("/", 1)[0] if "/" in model_id else "openai"


def _warn_on_shared_key_across_providers(llm: object, models_config: object) -> None:
    """Warn when one LLM_API_KEY would be sent to several direct providers.

    The shared key is only forwarded for an explicit single-model deployment
    (LLM_MODEL set). With no gateway (LLM_API_BASE empty), LiteLLM then routes
    each picked model straight to its provider, so that one key reaches every
    provider in the picker — leaking it to providers it doesn't belong to. The
    safe multi-provider setup is to leave LLM_MODEL and LLM_API_KEY empty and
    give each provider its own standard env var (OPENAI_API_KEY,
    ANTHROPIC_API_KEY, …).
    """
    if not (llm.api_key and llm.model and not llm.api_base and models_config):  # type: ignore[attr-defined]
        return
    providers = {
        _model_provider(m.id)
        for p in models_config.providers  # type: ignore[attr-defined]
        for m in p.models
    }
    if len(providers) > 1:
        logger.warning(
            "LLM_API_KEY is set with no LLM_API_BASE, but the models config spans "
            "multiple providers (%s). That single key would be sent to each provider "
            "directly. Leave LLM_API_KEY/LLM_API_BASE empty and set per-provider env "
            "vars (OPENAI_API_KEY, ANTHROPIC_API_KEY, …), or point LLM_API_BASE at a "
            "gateway that holds each provider's credentials.",
            ", ".join(sorted(providers)),
        )


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager.

    Handles startup and shutdown logic for the FastAPI application.
    """
    logger.info("Starting API server...")
    logger.info("Debug mode: %s", app_settings.debug)

    llm = get_llm_settings()
    # Fail fast on a missing or malformed models config file.
    models_config = get_litellm_models_config()
    model_count = (
        sum(len(p.models) for p in models_config.providers) if models_config else 0
    )
    logger.info(
        "LLM config — model: %s | api_base: %s | api_version: %s | "
        "models_configured: %d | api_key_configured: %s",
        resolve_default_model() or "(none configured)",
        llm.api_base or "(provider default endpoint)",
        llm.api_version or "(n/a)",
        model_count,
        bool(llm.api_key),
    )
    _warn_on_shared_key_across_providers(llm, models_config)

    init_langfuse()
    await init_persistence()
    await init_attachment_storage()
    await init_document_rag()
    init_mcp()
    await init_title_generation()
    await init_rate_limiting()

    if get_docling_settings().enabled:
        logger.info("Pre-warming Docling converter (loading ML models)…")
        await prewarm_converter()
        logger.info("Docling converter ready.")

    yield

    await await_background_tasks()
    await shutdown_persistence()
    await shutdown_attachment_storage()
    await shutdown_document_rag()
    shutdown_mcp()
    await shutdown_title_generation()
    await shutdown_rate_limiting()
    logger.info("Shutting down API server...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title=f"{app_settings.app_name} API",
        description="Whitelabel chatbot with RAG capabilities and agentic commerce integration",
        version="0.1.0",
        debug=app_settings.debug,
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=fastapi_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(chat_router)
    if get_docling_settings().enabled:
        app.include_router(documents_router)
    if is_persistence_enabled():
        app.include_router(persistence_router)

    # Root route - serve HTML chat interface
    @app.get("/", response_class=HTMLResponse)
    async def root() -> str:
        """Serve the HTML chat interface."""
        html_path = Path(__file__).parent / "templates" / "index.html"
        return html_path.read_text(encoding="utf-8")

    # Health check endpoint
    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Health check endpoint."""
        return {
            "status": "healthy",
            "service": app_settings.app_name,
            "version": "0.1.0",
        }

    return app


# Create the app instance
app = create_app()
