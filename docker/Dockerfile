# ============================================================================
# chatguru Agent - Backend Dockerfile
# ============================================================================
# Multi-stage build:
#   1. builder  — installs Python deps with uv (has curl + build tools)
#   2. runtime  — slim image with just the venv; no uv, no curl, no X11 stack
#
# Build arguments
# ---------------
#   TORCH_DEVICE   Controls which PyTorch build is installed (default: "cpu").
#                  CPU-only wheels are ~750 MB vs ~2.5 GB for the GPU build.
#                  Override only if the host has an NVIDIA GPU:
#                  docker build --build-arg TORCH_DEVICE=gpu .

# ----------------------------------------------------------------------------
# Stage 1: builder — dependency installation
# ----------------------------------------------------------------------------
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && mv /root/.local/bin/uv /bin/uv \
    && mv /root/.local/bin/uvx /bin/uvx

WORKDIR /app
COPY pyproject.toml uv.lock ./

# CPU-only PyTorch is handled by uv.lock via [tool.uv.sources] in pyproject.toml
# (pytorch-cpu index, Linux-only marker) — no post-install swap needed.
#
# opencv-python ships X11 libs we don't need in a headless container.
# Uninstall it first, then install the headless variant (same cv2 API, no X11).
RUN uv sync --frozen --no-dev \
    && uv pip uninstall opencv-python \
    && uv pip install opencv-python-headless

# ----------------------------------------------------------------------------
# Stage 2: runtime — minimal production image
# ----------------------------------------------------------------------------
FROM python:3.12-slim

# Only what OpenCV-headless actually needs at runtime (no X11 stack):
#   libgl1          — OpenCV links against libGL.so.1
#   libglib2.0-0    — GLib used internally by OpenCV
#   curl            — Docker healthcheck (CMD curl -f http://localhost/health)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Copy only the pre-built virtualenv — no uv, no lockfile, no build tools
COPY --from=builder /app/.venv ./.venv

COPY src/ ./src/
COPY rag_data/ /app/rag_data/
COPY docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000
WORKDIR /app/src

ENTRYPOINT ["/app/entrypoint.sh"]
# Call uvicorn directly from the venv (PATH above makes this work without uv)
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
