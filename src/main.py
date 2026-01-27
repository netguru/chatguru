"""Application entry point for running the FastAPI server."""

import uvicorn

from config import get_fastapi_settings

if __name__ == "__main__":
    settings = get_fastapi_settings()
    uvicorn.run(
        "api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
