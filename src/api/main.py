"""FastAPI application for chatguru Agent."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from api.routes.chat import await_background_tasks, persistence_router
from api.routes.chat import router as chat_router
from config import get_app_settings, get_fastapi_settings, get_llm_settings, get_logger
from persistence import init_persistence, is_persistence_enabled, shutdown_persistence

logger = get_logger(__name__)
app_settings = get_app_settings()
fastapi_settings = get_fastapi_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager.

    Handles startup and shutdown logic for the FastAPI application.
    """
    logger.info("Starting API server...")
    logger.info("Debug mode: %s", app_settings.debug)

    llm = get_llm_settings()
    _min_key_len = 8
    masked_key = (
        f"{llm.api_key[:4]}***{llm.api_key[-4:]}"
        if len(llm.api_key) > _min_key_len
        else "***"
    )
    logger.info(
        "LLM config — endpoint: %s | deployment: %s | api_version: %s | api_key: %s",
        llm.endpoint,
        llm.deployment_name,
        llm.api_version,
        masked_key,
    )

    await init_persistence()

    yield

    await await_background_tasks()
    await shutdown_persistence()
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
