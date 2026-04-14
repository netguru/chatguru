# chatguru Agent - Development Makefile
# =====================================
#
# This Makefile provides convenient commands for development, testing, and deployment.
# Run 'make help' to see all available commands with descriptions.
#
# Quick Start:
#   1. make setup          # Complete development setup
#   2. make env-setup      # Copy environment template
#   3. make dev            # Start backend development server

.PHONY: help install setup test coverage rag-eval ragas-llm-eval rag_dashboard dev run docker-build docker-run docker-run-detached docker-stop docker-down docker-logs docker-logs-backend docker-clean pre-commit-install pre-commit promptfoo-eval promptfoo-view promptfoo-test env-setup version clean migrate db-downgrade db-revision ingest-docs

# ============================================================================
# Default Target
# ============================================================================

help: ## Show this help message with all available commands
	@echo "chatguru Agent - Development Commands"
	@echo "=================================="
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-25s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "For detailed documentation, see README.md and CONTRIBUTING.md"

# ============================================================================
# Installation & Setup Commands
# ============================================================================
# These commands set up the development environment and install dependencies.

install: ## Install production dependencies using uv
	@echo "📦 Installing production dependencies..."
	uv sync

setup: install pre-commit-install ## Complete development setup (installs deps + pre-commit hooks)
	@echo "🎉 Development setup completed!"
	@echo ""
	@echo "Next steps:"
	@echo "1. Run 'make env-setup' to copy environment template"
	@echo "2. Edit .env with your credentials"
	@echo "3. Run 'make dev' to start the backend development server"
	@echo "4. (Optional) Run your external frontend separately and point it to ws://localhost:8000/ws"
	@echo "5. Visit http://localhost:8000/ for the minimal test UI"
	@echo "6. Visit http://localhost:8000/docs for API documentation"

env-setup: ## Copy environment template from env.example to .env
	@echo "⚙️  Setting up environment..."
	@if [ ! -f .env ]; then \
		cp env.example .env; \
		echo "✅ Created .env from env.example"; \
		echo "📝 Please edit .env with your credentials"; \
	else \
		echo "⚠️  .env already exists, skipping..."; \
	fi

# ============================================================================
# Development Commands
# ============================================================================
# Commands for running the application in development and production modes.

dev: ## Run the backend development server with auto-reload
	@echo "🚀 Starting backend development server with auto-reload..."
	@echo "📡 WebSocket streaming enabled at ws://localhost:8000/ws"
	@echo "🌐 API docs available at http://localhost:8000/docs"
	uv run --directory src uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

run: ## Run the production server (no auto-reload)
	@echo "🚀 Starting production server..."
	@echo "📡 WebSocket streaming enabled at ws://localhost:8000/ws"
	@echo "🌐 Web interface available at http://localhost:8000"
	uv run python src/main.py

# ============================================================================
# Database migrations (Alembic — uses PERSISTENCE_DATABASE_URL from .env)
# Schema columns/indexes: keep src/persistence/tables.py in sync with alembic/versions/.
# ============================================================================

ALEMBIC_INI := src/persistence/sqlalchemy/alembic.ini

migrate: ## Apply all pending Alembic migrations (alembic upgrade head)
	@echo "📦 Applying database migrations (PERSISTENCE_DATABASE_URL)..."
	uv run alembic -c $(ALEMBIC_INI) upgrade head

db-downgrade: ## Roll back one migration revision
	uv run alembic -c $(ALEMBIC_INI) downgrade -1

db-revision: ## Autogenerate a new revision from persistence/sqlalchemy/tables.py (requires MESSAGE=...)
	@test -n "$(MESSAGE)" || (echo "Usage: make db-revision MESSAGE='describe change'" && exit 1)
	uv run alembic -c $(ALEMBIC_INI) revision --autogenerate -m "$(MESSAGE)"

# ============================================================================
# Testing Commands
# ============================================================================
# Commands for running tests and generating coverage reports.

test: ## Run all tests with pytest
	@echo "🧪 Running tests..."
	uv run pytest

coverage: ## Run tests with coverage report (HTML + terminal output)
	@echo "🧪 Running tests with coverage..."
	uv run pytest --cov=src --cov-report=html --cov-report=term

rag-eval: ## Run Rag evaluation for RAG system quality assessment
	@echo "🔍 Running Rag evaluation..."
	PYTHONPATH=src uv run python -m evaluation.rag_eval.run_rag_eval

ragas-llm-eval: ## Run LLM-based Ragas evaluation (requires OpenAI API, takes longer)
	@echo "🤖 Running LLM-based Ragas evaluation..."
	PYTHONPATH=src uv run python -m evaluation.ragas.run_ragas_llm_eval

rag-dashboard: ## Launch Streamlit dashboard to visualize RAG evaluation results
	@echo "📊 Launching RAG evaluation dashboard..."
	uv run streamlit run evaluation/rag_eval/streamlit_rag_eval.py

ingest-docs: ## Ingest local docs into configured document RAG backend (usage: make ingest-docs SOURCE_DIR=./docs [BACKEND=mongodb COLLECTION=documents FULL_REPLACE=1])
	@test -n "$(SOURCE_DIR)" || (echo "Usage: make ingest-docs SOURCE_DIR=./docs" && exit 1)
	PYTHONPATH=src uv run python -m document_rag.ingestion.cli --source-dir "$(SOURCE_DIR)" $(if $(BACKEND),--backend "$(BACKEND)",) $(if $(MONGODB_URI),--mongodb-uri "$(MONGODB_URI)",) $(if $(DATABASE),--database "$(DATABASE)",) $(if $(COLLECTION),--collection "$(COLLECTION)",) $(if $(INDEX_NAME),--index-name "$(INDEX_NAME)",) $(if $(FULL_REPLACE),--full-replace,) $(if $(DRY_RUN),--dry-run,)

# ============================================================================
# Docker Commands
# ============================================================================
# Commands for building and running the application with Docker.
# Note: Only the backend lives here; run your frontend separately.

docker-build: ## Build backend Docker image
	@echo "🐳 Building backend Docker image..."
	docker build -f docker/Dockerfile -t chatguru-agent .
	@echo "✅ Backend image built successfully"

docker-run: ## Run with Docker Compose (builds and starts in foreground)
	@echo "🐳 Starting with Docker Compose..."
	@echo "🔧 Backend API at http://localhost:8000"
	@echo "📡 WebSocket endpoint at ws://localhost:8000/ws"
	@echo "🧪 Minimal test UI at http://localhost:8000/"
	docker-compose up --build

docker-run-detached: ## Run with Docker Compose in background (detached mode)
	@echo "🐳 Starting with Docker Compose (detached)..."
	docker-compose up --build -d
	@echo "🔧 Backend API at http://localhost:8000"
	@echo "📡 WebSocket endpoint at ws://localhost:8000/ws"
	@echo "🧪 Minimal test UI at http://localhost:8000/"

docker-stop: ## Stop Docker Compose services (keeps containers)
	@echo "🛑 Stopping Docker Compose services..."
	docker-compose stop

docker-down: ## Stop and remove Docker Compose containers
	@echo "🗑️  Stopping and removing Docker Compose containers..."
	docker-compose down

docker-logs: ## View all Docker Compose logs (follow mode)
	@echo "📋 Viewing Docker Compose logs..."
	docker-compose logs -f

docker-logs-backend: ## View backend service logs only
	@echo "📋 Viewing backend logs..."
	docker-compose logs -f chatguru-agent

docker-clean: docker-down ## Clean Docker resources (containers, volumes, networks)
	@echo "🧹 Cleaning Docker resources..."
	@docker-compose down -v 2>/dev/null || true
	@echo "✅ Cleanup complete"

# ============================================================================
# Code Quality Commands
# ============================================================================
# Commands for code formatting, linting, and quality checks.

pre-commit-install: ## Install pre-commit hooks (runs on git commit)
	@echo "🔧 Installing pre-commit hooks..."
	@# Ensure dev extras (including pre-commit) are installed
	uv sync --extra dev
	uv run python -m pre_commit install

pre-commit: ## Run pre-commit checks on all files manually
	@echo "🔧 Running pre-commit on all files..."
	uv run python -m pre_commit run --all-files

# ============================================================================
# LLM Evaluation Commands
# ============================================================================
# Commands for running promptfoo LLM evaluation tests.

promptfoo-eval: ## Run all promptfoo evaluation tests
	@echo "📊 Running promptfoo evaluation..."
	@echo "📝 Using Python provider to call agent directly (no Docker required)"
	@mkdir -p promptfoo/results
	cd promptfoo && npx promptfoo@latest eval

promptfoo-view: ## View promptfoo evaluation results in browser
	@echo "📊 Viewing promptfoo results..."
	cd promptfoo && npx promptfoo@latest view

promptfoo-test: ## Run promptfoo with specific test file (usage: make promptfoo-test TEST=tests/basic_greeting.yaml)
	@echo "📊 Running promptfoo with specific tests..."
	@if [ -z "$(TEST)" ]; then \
		echo "Usage: make promptfoo-test TEST=tests/basic_greeting.yaml"; \
		exit 1; \
	fi
	cd promptfoo && npx promptfoo@latest eval --tests $(TEST)

# ============================================================================
# Utility Commands
# ============================================================================
# Miscellaneous utility commands for project management.

version: ## Show current project version from pyproject.toml
	@echo "📋 Current version:"
	@grep 'version = ' pyproject.toml

clean: ## Clean Python cache files and build artifacts
	@echo "🧹 Cleaning Python cache files..."
	find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -r {} + 2>/dev/null || true
	@echo "✅ Cleanup complete"

# Default target when no argument is provided
.DEFAULT_GOAL := help
