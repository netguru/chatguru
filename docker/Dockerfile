# ============================================================================
# chatguru Agent - Backend Dockerfile
# ============================================================================
# Multi-stage build optimized for production deployment.
# Uses uv for fast, reproducible Python dependency management.

# ----------------------------------------------------------------------------
# Base Image Setup
# ----------------------------------------------------------------------------
FROM python:3.12-slim

# Install system dependencies:
#   curl                    — Docker healthchecks and uv installer
#   libgl1, libglib2.0-0    — OpenCV core (used by docling for PDF layout detection)
#   libxcb1, libx11-6,
#   libxext6, libxrender1,
#   libsm6, libice6         — Full X11 stack required by opencv-python even headless;
#                             opencv-python (not -headless) links against these at load time
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        libgl1 \
        libglib2.0-0 \
        libxcb1 \
        libx11-6 \
        libxext6 \
        libxrender1 \
        libsm6 \
        libice6 \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package installer)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    mv /root/.local/bin/uv /bin/uv && \
    mv /root/.local/bin/uvx /bin/uvx

# ----------------------------------------------------------------------------
# Environment Configuration
# ----------------------------------------------------------------------------
# PYTHONUNBUFFERED: Ensure Python output is sent straight to terminal/logs
# PYTHONDONTWRITEBYTECODE: Prevent Python from writing .pyc files
# PYTHONPATH: Set Python path to find application modules
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

# ----------------------------------------------------------------------------
# Dependency Installation
# ----------------------------------------------------------------------------
# Copy dependency files first (for better layer caching)
# uv.lock ensures reproducible builds with exact dependency versions
WORKDIR /app
COPY pyproject.toml uv.lock ./

# Install dependencies using frozen lockfile for reproducibility
# This layer is cached unless dependency files change
RUN uv sync --frozen

# ----------------------------------------------------------------------------
# Application Code
# ----------------------------------------------------------------------------
# Copy application source code (including API templates and Alembic migrations)
# This is done after dependencies to leverage Docker layer caching
COPY src/ ./src/
COPY rag_data/ /app/rag_data/
COPY docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# ----------------------------------------------------------------------------
# Runtime Configuration
# ----------------------------------------------------------------------------
# Expose FastAPI application port
EXPOSE 8000

# Set working directory to source code location
WORKDIR /app/src

# entrypoint.sh runs `alembic upgrade head` when PERSISTENCE_DATABASE_URL is set,
# then execs the CMD below. Migrations are idempotent — safe to run on every start.
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
