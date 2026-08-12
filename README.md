<div align="center">
  <img src="frontend/public/branding/chatguru-logotype.svg" alt="chatguru" width="320" />
  <h1>chatguru AI Agent</h1>
</div>

<div align="center">
  <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+"/>
  <img src="https://img.shields.io/badge/FastAPI-0.104+-green.svg" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"/>
  <img src="https://img.shields.io/badge/langfuse-3.0.0+-red.svg" alt="Langfuse"/>
</div>

<div align="center">
  <a href="#Docs">Documentation</a> &nbsp;|&nbsp; <a href="#Preview">Preview</a> &nbsp;|&nbsp; <a href="#Installation">Installation</a> &nbsp;|&nbsp; <a href="#Contributing">Contributing</a>
</div>

<br/>

<p align="center">
  chatguru Agent is a production-ready whitelabel chatbot with RAG capabilities and agentic commerce integration, built with FastAPI and LangChain. It is provider-agnostic via LiteLLM — use OpenAI, Azure, Anthropic, Google, local models, or any LiteLLM-supported backend.
</p>

<div align="center">
  <br/><em>Brought with</em> &nbsp;❤️ <em>by</em> &nbsp; <a href="https://www.netguru.com">Netguru</a>
</div>


## Documentation <a name="Docs"></a>

Read the full Docs at: <a href="https://github.com/netguru/chatguru">https://github.com/netguru/chatguru</a>

## Preview <a name="Preview"></a>

chatguru Agent ships with WebSocket streaming, RAG capabilities, and comprehensive observability!

**Key Features:**
- Real-time WebSocket streaming for instant responses
- RAG-powered answers grounded in a document knowledge base
- Comprehensive API documentation with Swagger UI

## Installation <a name="Installation"></a>

### Installation & requirements

#### Install latest library version

:information_source: Library supports Python 3.12+

#### Install library's dependencies

```bash
# Clone the repository
git clone <repository-url>
cd chatguru

# Complete development setup
make setup
```

After installation:

```bash
# Configure environment variables
make env-setup
# Edit .env with your credentials

# Start the development server
make dev
```

## In Use

This is how you can use the WebSocket API in your app:

```python
import asyncio
import websockets
import json

async def chat():
    uri = "ws://localhost:8000/ws"
    async with websockets.connect(uri) as websocket:
        # Send message
        await websocket.send(json.dumps({
            "messages": [
                {"role": "user", "content": "Hello, how are you?"},
            ],
            "session_id": None
        }))

        # Receive streaming response
        async for message in websocket:
            data = json.loads(message)
            if data["type"] == "token":
                print(data["content"], end="", flush=True)
            elif data["type"] == "end":
                print("\n")
                break
            elif data["type"] == "error":
                print(f"Error: {data['content']}")
                break

asyncio.run(chat())
```

## ✨ Features

- **🚀 WebSocket Streaming**: Real-time streaming chat responses via WebSocket
- **🎨 Whitelabel Design**: Easily customizable for different brands and tenants
- **🧠 RAG Capabilities**: Semantic document retrieval with MongoDB Atlas Vector Search or sqlite-vec
- **🛒 Agentic Commerce**: Ready for MCP (Model Context Protocol) integration
- **📊 Observability**: Built-in Langfuse tracing and monitoring
- **✅ Testing**: Comprehensive test suite with promptfoo LLM evaluation
- **🐳 Production Ready**: Docker containerization with health checks
- **🔒 Rate Limiting**: Redis-backed per-IP message quota (opt-in, atomic Lua enforcement)

## 🏗️ Architecture

Simple, modular architecture designed for whitelabel deployment:

```mermaid
graph LR
    subgraph "Current Implementation"
        UI[React/Vite Frontend<br/>frontend/] -->|WebSocket| API[FastAPI API]
        API -->|Streaming| AGENT[Agent Service]
        AGENT -->|ChatLiteLLM| LLM[LLM<br/>any provider]
        AGENT -->|search_documents| DOCRAG[Document RAG<br/>MongoDB]
        AGENT --> LANGFUSE[Langfuse<br/>Tracing]
        AGENT -.->|MCP tools, opt-in| MCP[MCP Servers<br/>remote tools]
        AGENT -.->|search_products, available but disabled| VECTORDB[Product Vector DB<br/>MongoDB / sqlite-vec]
    end
```

For detailed architecture documentation, see [docs/architecture.md](docs/architecture.md).

## 🛠️ Technology Stack

- **Backend**: FastAPI + Uvicorn (async)
- **AI/ML**: LangChain + LiteLLM
- **LLM Provider**: Provider-agnostic via LiteLLM (OpenAI, Azure, Anthropic, Google, Ollama, …)
- **Vector Search**: MongoDB Atlas Vector Search (default) or sqlite-vec
- **Rate Limiting**: Redis 7 + hiredis (atomic Lua per-IP quotas)
- **Observability**: Langfuse
- **Testing**: pytest + promptfoo + GenericFakeChatModel
- **Code Quality**: mypy + ruff + pre-commit
- **Frontend**: React 19 + Vite (`frontend/`)
- **CSS**: Tailwind CSS v4 (via `@tailwindcss/vite`)
- **Containerization**: Docker + Docker Compose
- **Package Management**: uv (Python) + npm (Node.js)
- **Development**: Makefile for task automation

## 🌐 Frontend

A React + Vite frontend lives in the `frontend/` directory.

Run it locally:

```bash
make frontend-dev   # Vite dev server → http://localhost:5173
```

Or via Docker Compose — the `frontend` service is **opt-in** behind the `frontend` profile. Add `--profile frontend` (or run `make docker-run`) to serve it; `docker compose up` alone starts the backend only.

Copy the env template before running:

```bash
cp frontend/.env.example frontend/.env
```

## 📋 Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.12+** ([Download](https://www.python.org/downloads/))
- **Node.js 20+** and npm — required by React 19 ([Download](https://nodejs.org/))
- **uv** - Fast Python package installer ([Installation guide](https://github.com/astral-sh/uv))
- **Docker** and Docker Compose (optional, for containerized deployment)
- **An LLM provider account** with API access (OpenAI, Azure, Anthropic, Google, a local model, …)
- **Langfuse account** (for observability and tracing)

## 🚀 Quick Start

### Option 1: Local Development (Recommended for Development)

#### 1. Clone the Repository

```bash
git clone <repository-url>
cd chatguru
```

#### 2. Complete Development Setup

```bash
# Install dependencies and set up pre-commit hooks
make setup
```

This command will:
- Install Python dependencies using `uv`
- Install and configure pre-commit hooks
- Set up the development environment

#### 3. Configure Environment Variables

```bash
# Copy environment template
make env-setup

# Edit .env with your credentials
# Required: LLM_* and LANGFUSE_* variables (see Configuration section below)
```

#### 4. Start the Development Server

```bash
make dev
```

#### 5. Access the Application

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **WebSocket Endpoint**: ws://localhost:8000/ws

### Option 2: Docker Deployment (Recommended for Production)

#### 1. Clone and Configure

```bash
git clone <repository-url>
cd chatguru

# Copy and configure environment variables
make env-setup
# Edit .env with your credentials
```

#### 2. Build and Run

```bash
# Build and start all services (incl. frontend UI)
make docker-run

# Or run in background
make docker-run-detached

# Backend only, no frontend UI
make docker-run-backend
# equivalently:
docker compose up --build
```

#### 3. Access the Application

- **Frontend** (with `--profile frontend`): http://localhost:${FRONTEND_PORT:-80}
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **WebSocket Endpoint**: ws://localhost:8000/ws

## 🔧 Configuration

The application uses environment variables for configuration. Copy `env.example` to `.env` and configure the following:

### Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `LLM_MODEL` | Model id in LiteLLM `<provider>/<model>` form | `openai/gpt-4o-mini` |
| `LLM_API_KEY` | API key for the provider/gateway | `your-api-key-here` |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key | `pk-lf-...` |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key | `sk-lf-...` |
| `LANGFUSE_HOST` | Langfuse host URL | `https://cloud.langfuse.com` |

### Optional Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `FASTAPI_HOST` | API host address | `0.0.0.0` |
| `FASTAPI_PORT` | API port | `8000` |
| `FASTAPI_CORS_ORIGINS` | CORS allowed origins (JSON array) | `["*"]` |
| `APP_NAME` | Application name | `chatguru Agent` |
| `DEBUG` | Enable debug mode | `false` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `VECTOR_DB_TYPE` | Database type (`sqlite` or `mongodb`) | `mongodb` |
| `VECTOR_DB_SQLITE_URL` | SQLite service URL (used when `VECTOR_DB_TYPE=sqlite`) | `http://localhost:8001` |
| `VECTOR_DB_MONGODB_URI` | MongoDB connection URI (used when `VECTOR_DB_TYPE=mongodb`) | `mongodb://localhost:27017` |
| `VECTOR_DB_MONGODB_API_URL` | MongoDB vector-DB API service URL | `http://localhost:8002` |
| `VECTOR_DB_MONGODB_DATABASE` | MongoDB database name | `products` |
| `VECTOR_DB_MONGODB_COLLECTION` | MongoDB collection name | `products` |
| `PERSISTENCE_DATABASE_URL` | Async SQLAlchemy URL for chat history storage | *(unset — disabled)* |
| `LLM_API_BASE` | Base URL for chat + embeddings (OpenAI-compatible endpoint or gateway, e.g. Azure APIM); empty = provider default | *(empty)* |
| `LLM_API_VERSION` | API version, required by some gateways such as Azure | *(empty)* |
| `LLM_TEMPERATURE` | Sampling temperature | `1` |
| `LLM_REASONING_EFFORT` | Reasoning effort (`none`/`low`/`medium`/`high`) for models that support it; empty = model default | *(empty)* |
| `LLM_EMBEDDING_MODEL` | Embeddings model id | `text-embedding-ada-002` |
| `LLM_EMBEDDING_DIMENSIONS` | Embedding vector dimensions | `1536` |
| `LLM_EMBEDDINGS_API_BASE` | Embeddings endpoint base URL; falls back to `LLM_API_BASE` when empty | *(empty)* |
| `LLM_EMBEDDINGS_API_KEY` | Embeddings API key; falls back to `LLM_API_KEY` when empty | *(empty)* |
| `AGENT_SYSTEM_PROMPT_FALLBACK_FILE` | Local `.md` used as the system-prompt fallback when Langfuse is unavailable | *(empty)* |
| `TITLE_GENERATION_PROVIDER` | Title provider: `llm`, `fallback`, `custom` | `llm` |
| `TITLE_GENERATION_CUSTOM_CLASS` | Custom class path (`module.path:ClassName`) when provider is `custom` | *(empty)* |
| `RATE_LIMIT_ENABLED` | Enable Redis-backed per-IP rate limiting | `false` |
| `RATE_LIMIT_REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| `RATE_LIMIT_MAX_MESSAGES` | Max LLM messages per IP per fixed window | `10` |
| `RATE_LIMIT_MAX_UPLOADS` | Max document uploads per IP per window | `10` |
| `RATE_LIMIT_WINDOW_SECONDS` | Fixed window length in seconds (86400 = 24 h) | `86400` |
| `RATE_LIMIT_TRUST_PROXY` | Read real IP from `X-Forwarded-For` / `X-Real-IP` (only when behind a trusted proxy) | `false` |
| `DOCLING_ENABLED` | Enable `POST /process-document` document uploads | `true` |
| `DOCLING_MAX_FILE_SIZE_BYTES` | Maximum upload size in bytes (20 MiB) | `20971520` |
| `DOCLING_PICTURE_DESCRIPTION_ENABLED` | VLM image descriptions for pictures in documents | `false` |
| `ATTACHMENT_STORAGE_ENABLED` | Enable attachment binary storage | `true` |
| `ATTACHMENT_STORAGE_TYPE` | Storage backend (`filesystem`) | `filesystem` |
| `ATTACHMENT_STORAGE_BASE_PATH` | Base directory for filesystem attachment storage | `./attachments` |
| `DOCUMENT_RAG_ENABLED` | Enable the document-RAG repository and startup ingestion | `false` |
| `DOCUMENT_RAG_BACKEND` | Document-RAG backend (`mongodb` / `cosmos`) | `mongodb` |
| `MCP_ENABLED` | Load tools from remote MCP servers | `false` |
| `MCP_CONFIG_PATH` | Path to the MCP servers JSON config (see [docs/mcp.md](docs/mcp.md)) | *(empty)* |

#### Rate limiting (Docker)

Redis is **not** started by default. Add `--profile rate-limiting` to include it:

```bash
# MongoDB + rate limiting
docker compose --profile rate-limiting up

# SQLite + rate limiting
docker compose --profile sqlite --profile rate-limiting up
```

Set `RATE_LIMIT_ENABLED=true` in `.env` alongside the profile. When `RATE_LIMIT_ENABLED=false` (the default), the profile is not needed — the agent starts without Redis.

#### Chat history persistence

`PERSISTENCE_DATABASE_URL` is the single toggle for server-side chat history:

- **Unset (default)** — persistence is disabled. The server is stateless: no database is required and no messages are stored. The `/history` and `/conversations` endpoints are not registered at all (they won't appear in `/docs` or return 404).
- **Set** — persistence is enabled. Messages and conversations are stored per `visitor_id` / `session_id`. Run `make migrate` once after setting the URL to create the schema.

```bash
# SQLite (local dev / single-node)
PERSISTENCE_DATABASE_URL=sqlite+aiosqlite:///data/chatguru.db

# PostgreSQL
PERSISTENCE_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/chatguru
```

See [docs/persistence.md](docs/persistence.md) for the full architecture and instructions on adding new database adapters.

**Provider selection:** the backend is chosen by the `LLM_MODEL` id (`openai/gpt-4o`, `azure/<deployment>`, `anthropic/…`, `ollama/…`); `LLM_API_BASE` optionally points at a gateway. See [docs/design-decisions.md](docs/design-decisions.md#llm-endpoint-modes).

See [env.example](env.example) for a complete template with detailed comments.

## 📡 API Documentation

### WebSocket API

The primary interface for chat is via WebSocket at `ws://localhost:8000/ws`.

#### Request Format

```json
{
  "message": "Your message here",
  "session_id": "optional-session-id",
  "messages": [
    {"role": "user", "content": "previous user message"},
    {"role": "assistant", "content": "previous assistant response"}
  ]
}
```

#### Response Format

Responses are streamed as JSON messages:

```json
// Token chunk (streamed multiple times)
{"type": "token", "content": "chunk of text", "session_id": "session-id"}

// End of stream (includes the full response as safety)
{"type": "end", "content": "full assistant response", "session_id": "session-id"}

// Error response
{"type": "error", "content": "error message", "session_id": "session-id"}
```

### REST API

Always available:

- **`GET /health`** — health check
- **`GET /docs`** — Swagger UI; **`GET /openapi.json`** — OpenAPI schema
- **`GET /models`** — selectable chat models for the picker (empty list hides the picker)
- **`POST /feedback`** — record a thumbs-up/down score for an assistant message (via Langfuse)
- **`GET /documents/{source_path}`** — stream a source document from the document-RAG store

Registered only when `DOCLING_ENABLED=true` (the default):

- **`POST /process-document`** — upload and ingest a document
- **`POST /upload-attachment`** — store a chat attachment

Registered only when `PERSISTENCE_DATABASE_URL` is set:

- **`GET /history`** — returns stored messages for a `visitor_id` + `session_id` pair, oldest first.
  - Query params: `visitor_id` (required), `session_id` (default: `"default"`)
- **`GET /conversations`** — returns all conversations for a `visitor_id`, newest first.
  - Query params: `visitor_id` (required)
- **`POST /conversations/title`** — generate and persist a title for an existing conversation.
- **`GET /attachments/{attachment_id}`** — download a stored attachment.

## 🛠️ Development

### Available Commands

Run `make help` to see all available commands. Key commands:

#### Installation & Setup
```bash
make setup          # Complete development setup
make env-setup      # Copy environment template
make install        # Install production dependencies
```

#### Development Servers
```bash
make dev            # Start backend development server (auto-reload)
make frontend-dev   # Start frontend development server (Vite, port 5173)
make run            # Start production server (no auto-reload)
```

#### Testing
```bash
make test           # Run all tests
make coverage       # Run tests with coverage report
make promptfoo-eval # Run LLM evaluation tests
make promptfoo-view # View evaluation results
```

#### Code Quality
```bash
make pre-commit-install  # Install pre-commit hooks
make pre-commit          # Run pre-commit checks manually
```

#### Docker
```bash
make docker-build        # Build Docker images
make docker-run          # Run with Docker Compose (foreground)
make docker-run-detached # Run with Docker Compose (background)
make docker-stop         # Stop services
make docker-down         # Stop and remove containers
make docker-logs         # View logs
make docker-clean        # Clean all Docker resources
```

#### Utilities
```bash
make version        # Show current version
make clean          # Clean Python cache files
```

### Project Structure

```
chatguru/
├── frontend/                # React + Vite frontend
│   ├── src/                 # Source code (components, hooks, pages)
│   ├── public/              # Static assets
│   ├── .env.example         # Frontend env template
│   └── package.json
├── src/                     # Main application code
│   ├── api/                 # FastAPI application
│   │   ├── main.py         # FastAPI app setup
│   │   └── routes/         # API routes
│   │       ├── chat.py     # WebSocket chat, /models, /feedback
│   │       ├── documents.py # Document upload + attachments
│   │       └── history.py  # Chat history (persistence)
│   ├── agent/              # Agent implementation
│   │   ├── service.py      # LangChain agent with streaming
│   │   ├── prompt.py       # System prompts
│   │   └── __init__.py
│   ├── vector_db/           # Vector database (sqlite-vec / MongoDB)
│   │   ├── api.py          # FastAPI service
│   │   ├── store.py        # sqlite-vec store with embeddings
│   │   ├── sqlite.py       # sqlite-vec HTTP client for agent
│   │   ├── mongodb_store.py # MongoDB Atlas vector store
│   │   ├── mongodb.py      # MongoDB HTTP client for agent
│   │   ├── base.py         # Abstract interface
│   │   └── factory.py      # Database factory
│   ├── document_rag/        # Document RAG retrieval (MongoDB / Cosmos)
│   ├── document_processing/ # Document ingestion (Docling)
│   ├── attachment_storage/  # Uploaded-attachment storage
│   ├── persistence/         # Chat history persistence (SQLAlchemy)
│   ├── rate_limiting/       # Redis-backed per-IP rate limiting
│   ├── title_generation/    # Conversation title providers
│   ├── mcp_integration/     # Remote MCP tool servers
│   ├── rag/                # RAG components
│   │   ├── documents.py    # Document handling
│   │   ├── simple_retriever.py  # Retriever interface
│   │   └── products.json   # Sample products data
│   ├── embeddings.py        # Embedding client
│   ├── tracing.py           # Langfuse tracing setup
│   ├── config.py           # Configuration management
│   └── main.py             # Application entry point
├── tests/                  # Test suite
│   ├── test_api.py         # API endpoint tests
│   ├── test_agent.py       # Agent tests
│   └── conftest.py         # Test configuration
├── docs/                   # Documentation
│   └── architecture.md      # Architecture documentation
├── promptfoo/              # LLM evaluation config
│   ├── provider.py         # Python provider adapter
│   └── promptfooconfig.yaml
├── docker/                 # Docker configuration
│   ├── Dockerfile          # Backend Dockerfile
│   ├── Dockerfile.db       # SQLite vector DB Dockerfile
│   ├── Dockerfile.mongodb  # MongoDB vector DB Dockerfile
│   ├── Dockerfile.frontend # Frontend (nginx) Dockerfile
│   ├── entrypoint.sh       # Backend container entrypoint
│   └── nginx.conf          # Frontend nginx config
├── .pre-commit-config.yaml # Pre-commit hooks
├── docker-compose.yml      # Docker Compose setup
├── Makefile                # Development commands
├── pyproject.toml          # Python project configuration
├── env.example             # Environment template
└── README.md               # This file
```

## 🧪 Testing

### Unit Tests

```bash
# Run all tests
make test

# Run with coverage report
make coverage
```

Tests use `GenericFakeChatModel` from LangChain for reliable, deterministic testing without API calls.

### LLM Evaluation with Promptfoo

```bash
# Run evaluation suite
make promptfoo-eval

# View results in browser
make promptfoo-view

# Run specific test file
make promptfoo-test TEST=tests/basic_greeting.yaml
```

Promptfoo tests evaluate response quality, helpfulness, and boundary conditions.

### RAG Evaluation with RAGAS and RAG Evaluator

RAGAS (Retrieval-Augmented Generation Assessment) and RAG Evaluator are frameworks/tools for evaluating the performance of Retrieval-Augmented Generation (RAG) systems. They provide metrics to assess aspects like faithfulness, answer relevance, context precision, and retrieval quality in RAG pipelines.

For detailed information on RAG testing and evaluation using RAGAS and RAG Evaluator, see [docs/rag_eval_readme.md](docs/rag_eval_readme.md).

## 🐳 Docker Deployment

### Quick Start

```bash
# Build and run backend with Docker Compose
make docker-run
```

### Manual Docker Commands

```bash
# Build backend image
docker build -f docker/Dockerfile -t chatguru-agent .

# Run backend container
docker run -p 8000:8000 --env-file .env chatguru-agent
```

### Ports

- **Backend API**: `8000` (host) → `8000` (container)
- **Vector DB (MongoDB API, default)**: `8002` (host) → `8002` (container)
- **Vector DB (sqlite-vec, `--profile sqlite`)**: `8001` (host) → `8001` (container)
- **Frontend (`--profile frontend`)**: `${FRONTEND_PORT:-80}` (host) → `80` (container)
- **WebSocket**: `ws://localhost:8000/ws`

### Frontend Service

The `frontend` service is **opt-in** behind the `frontend` profile — add `--profile frontend`
(or run `make docker-run`) to start it; `docker compose up` alone runs the backend only. It builds
the React app and serves the static bundle via nginx (`docker/Dockerfile.frontend`) on
`FRONTEND_PORT` (default `80`), proxying `/ws`, `/conversations`, and `/history` to the backend.

For local development the Vite dev server (`make frontend-dev`, port 5173) proxies the same routes;
override its backend target with `API_PROXY_TARGET` / `WS_PROXY_TARGET`
(default: `http://localhost:8000`).

## 🐛 Troubleshooting

### Common Issues

#### 1. "Module not found" errors

**Solution**: Ensure dependencies are installed:
```bash
make install
```

#### 2. WebSocket connection fails

**Solution**:
- Verify backend is running: `curl http://localhost:8000/health`
- Check WebSocket endpoint: `ws://localhost:8000/ws`
- Ensure CORS is configured correctly in `.env`

#### 3. LLM authentication errors

**Solution**:
- Verify `LLM_MODEL` is a valid LiteLLM id (`<provider>/<model>`, e.g. `openai/gpt-4o-mini`)
- Check `LLM_API_KEY` is correct for that provider
- If using a gateway, verify `LLM_API_BASE` is a full base URL and `LLM_API_VERSION` is set when required (e.g. Azure)

#### 4. Langfuse connection errors

**Solution**:
- Verify Langfuse credentials in `.env`
- Check `LANGFUSE_HOST` is correct (default: `https://cloud.langfuse.com`)
- Ensure network connectivity to Langfuse

#### 5. Docker build fails

**Solution**:
- Ensure `uv.lock` file exists (run `uv sync` locally first)
- Check Docker has sufficient resources
- Verify all required files are present

#### 6. Port already in use

**Solution**:
- Backend (8000): Stop other services using port 8000 or change `FASTAPI_PORT`
- Frontend: Configure your external frontend to target the correct backend host/port

### Getting Help

- Check [docs/architecture.md](docs/architecture.md) for architecture details
- Review [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines
- Open an issue on GitHub for bugs or feature requests

## 📚 Documentation

- [Architecture Guide](docs/architecture.md) - Detailed architecture documentation
- [Contributing Guide](CONTRIBUTING.md) - How to contribute to the project
- [Getting Started Guide](GETTING_STARTED.md) - Detailed setup instructions

## 🤝 Contributing <a name="Contributing"></a>

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for:

- Development setup instructions
- Code style guidelines
- Testing requirements
- Pull request process
- Issue reporting guidelines

## 🔮 Roadmap

- [x] **Vector Database Integration**: sqlite-vec for semantic search ✅
- [x] **Streaming Responses**: Real-time chat streaming via WebSocket ✅
- [ ] **MCP Tools**: Integration with commerce platforms (PimCore, Strapi, Medusa.js)
- [ ] **Authentication**: JWT-based API authentication
- [x] **Rate Limiting**: Redis-backed per-IP message quota with atomic Lua enforcement ✅
- [x] **Session Management**: Client-side persistent conversation history (localStorage) ✅
- [x] **Server-side Sessions**: Backend-persisted conversation history via `PERSISTENCE_DATABASE_URL` (opt-in) ✅
- [ ] **Multi-tenancy**: Database-backed tenant configuration

## 📄 License

This library is available as open source under the terms of the [MIT License](https://opensource.org/licenses/MIT).

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [LangChain](https://www.langchain.com/) - LLM application framework
- [Langfuse](https://langfuse.com/) - LLM observability platform
- [promptfoo](https://www.promptfoo.dev/) - LLM evaluation framework

## 🆘 Support

For support and questions:

- 📖 Check the [documentation](docs/)
- 🐛 [Open an issue](https://github.com/netguru/chatguru/issues) for bugs
- 💬 [Start a discussion](https://github.com/netguru/chatguru/discussions) for questions
- 📧 Contact the maintainers

---
