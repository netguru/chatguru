# Document RAG Repository

## Overview

Document retrieval follows the same modular pattern as chat persistence:

- Port (`Protocol`) for a stable retrieval contract
- Typed domain models for retrieval hits and source references
- Factory-based adapter selection
- Process-wide lifecycle bootstrap (`init/get/shutdown`)

This is intentionally **document RAG only**. Product RAG remains on its current runtime path and is not refactored here.

## Package layout

```
src/document_rag/
├── __init__.py
├── models.py                 # Domain dataclasses (hits, sources, ingestion models)
├── repository.py             # Port (Protocol)
├── factory.py                # Composition root (backend selection)
├── bootstrap.py              # Lifecycle singleton (init/get/shutdown)
├── embeddings.py             # Embedding provider abstraction (openai/custom)
├── ingestion/
│   ├── cli.py                # Local-folder ingestion command
│   ├── factory.py            # Ingestion adapter selection
│   ├── repository.py         # Ingestion port
│   └── adapters/
│       └── mongodb.py        # MongoDB chunk + GridFS file ingestion
└── adapters/
├── __init__.py
    └── mongodb.py            # MongoDB vector-search adapter (search-only)
```

## Public contract

`document_rag/repository.py` defines the retrieval-only interface:

```python
class DocumentRagRepository(Protocol):
    async def connect(self) -> None: ...
    async def search(self, query: str, limit: int = 5) -> list[DocumentRetrievalHit]: ...
    async def close(self) -> None: ...
```

The response model is typed and backend-agnostic:

- `DocumentRetrievalHit`
  - `snippet: str`
  - `score: float | None`
  - `source: DocumentSourceReference`
- `DocumentSourceReference`
  - `source_id: str`
  - `source_type: str | None`
  - `source_uri: str | None`
  - `title: str | None`
  - `chunk_id: str | None`
  - `page: int | None`

## Lifecycle and startup behavior

The FastAPI lifespan now includes document RAG bootstrap:

1. `init_document_rag()` on startup
2. `get_document_rag_repository()` during request handling/tool execution
3. `shutdown_document_rag()` on shutdown

Behavior policy:

- `DOCUMENT_RAG_ENABLED=false` (default): startup continues, document RAG is disabled.
- `DOCUMENT_RAG_ENABLED=true` and initialization fails: startup fails fast.
- `get_document_rag_repository()` returns:
  - `None` when disabled
  - initialized repository when enabled and ready
  - `RuntimeError` when enabled but not initialized

## Agent tool

When document RAG is enabled and initialized, the agent registers:

- `search_documents(query: str, limit: int = 5)`

Tool output is formatted plain text with two sections:

1. **Snippets** — one block per retrieved chunk, prefixed with its citation number, optional page, and filename:
   ```
   [1] (page 3) report.pdf:
   The actual chunk text here…

   [2] guide.pdf:
   Another chunk of text…
   ```

2. **Citation metadata** — a trailing block the model uses for inline references:
   ```
   ---
   Citation metadata (use these numbers for inline references):
   - [1] report.pdf, page 3
   - [2] guide.pdf
   ```

Citation numbers are stable across multi-turn tool calls: chunks from the same
document share a single number, and documents already tracked from a previous
call keep their existing number.

The existing `search_products` flow remains active and unchanged.

## Chat response contract

Chat flow for a document-grounded answer:

1. user message arrives
2. model may call `search_documents` (agentic loop)
3. model streams the final answer as incremental `token` frames (same as non-RAG turns)
4. backend sends an `end` frame with `sources` attached

Token streaming works identically for all turns — document-grounded or not.
The only difference is that the `end` frame includes a `sources` array when
documents were retrieved.

Example end frame:

```json
{
  "type": "end",
  "session_id": "abc",
  "sources": [
    {
      "source_id": "guide.pdf",
      "source_uri": "guide.pdf",
      "title": "Guide",
      "chunk_id": "guide.pdf#3:abcd1234",
      "source_type": "pdf",
      "page": null
    }
  ]
}
```

Frontend renders inline citation links from `[N]` markers in the streamed
content and shows cited sources in the sources sidebar.

## Fetch full documents for source panel

Use:

- `GET /documents/{source_path}`

This serves source files from MongoDB GridFS bucket configured by
`DOCUMENT_RAG_MONGODB_FILES_BUCKET`.

For PDFs, use iframe URL fragments for page navigation when `page` is known:

- `/documents/guide.pdf#page=12`

## Configuration

Document RAG uses `DOCUMENT_RAG_*` environment variables:

| Variable | Description | Default |
|---|---|---|
| `DOCUMENT_RAG_ENABLED` | Enable document repository bootstrap | `false` |
| `DOCUMENT_RAG_BACKEND` | Backend selector (currently only `mongodb`) | `mongodb` |
| `DOCUMENT_RAG_MONGODB_URI` | MongoDB URI | `mongodb://localhost:27017` |
| `DOCUMENT_RAG_MONGODB_DATABASE` | MongoDB database for document chunks | `chatguru` |
| `DOCUMENT_RAG_MONGODB_COLLECTION` | MongoDB collection for document chunks | `documents` |
| `DOCUMENT_RAG_MONGODB_INDEX_NAME` | Vector search index name | `document_vector_index` |
| `DOCUMENT_RAG_SEARCH_LIMIT_DEFAULT` | Default search limit | `5` |
| `DOCUMENT_RAG_MONGODB_CONNECTION_TIMEOUT_MS` | Mongo client connection timeout (ms) | `5000` |
| `DOCUMENT_RAG_EMBEDDING_PROVIDER` | Embedding provider (`openai` or `custom`) | `openai` |
| `DOCUMENT_RAG_EMBEDDING_CUSTOM_CLASS` | Custom provider class path (`module.path:ClassName`) when provider is `custom` | *(empty)* |
| `DOCUMENT_RAG_MONGODB_FILES_BUCKET` | GridFS bucket used for full source document storage | `document_sources` |

### Custom embedding providers

To use a non-OpenAI embedding provider, set:

- `DOCUMENT_RAG_EMBEDDING_PROVIDER=custom`
- `DOCUMENT_RAG_EMBEDDING_CUSTOM_CLASS=your.module:YourProvider`

Your provider class must expose:

```python
class YourProvider:
    def embed_query(self, query: str) -> list[float]:
        ...
```

The repository calls `embed_query` and uses the returned vector in MongoDB `$vectorSearch`.

## Notes and scope

- Retrieval API is separate from ingestion API.
- MongoDB is the first-class backend in this release.
- Additional adapters can be added without changing application layers; update
  `document_rag/factory.py` and `document_rag/ingestion/factory.py`.

## Local ingestion script (Docling)

This repo includes a local-folder ingestion CLI using Docling:

- Script: `src/document_rag/ingestion/cli.py`
- Input: local directory (recursive)
- Output: chunked document records in MongoDB + full source files in GridFS
- Adapter selection: uses `DOCUMENT_RAG_BACKEND` via ingestion factory

Install dependencies first:

```bash
make setup
```

Docling is the only PDF parsing path used by the ingestion CLI.

Example usage:

```bash
make ingest-docs \
  SOURCE_DIR=./docs \
  BACKEND=mongodb \
  MONGODB_URI="mongodb://localhost:27017/?directConnection=true" \
  DATABASE=chatguru \
  COLLECTION=documents \
  INDEX_NAME=document_vector_index
```

Full replace mode (delete all existing chunks and source files before ingest):

```bash
make ingest-docs SOURCE_DIR=./docs BACKEND=mongodb FULL_REPLACE=1
```

Dry run (parse/chunk/embed without writing):

```bash
make ingest-docs SOURCE_DIR=./docs BACKEND=mongodb DRY_RUN=1
```

Supported file extensions by default:

- `.md`, `.txt`, `.pdf`, `.docx`, `.html`, `.htm`

You can override with `--extensions` (comma-separated).

Current ingestion adapter support:

- `mongodb` (implemented)
- any other backend returns a clear unsupported-backend error until an adapter is added

## Quick start (new users)

1. Enable document RAG in `.env`:

```env
DOCUMENT_RAG_ENABLED=true
DOCUMENT_RAG_BACKEND=mongodb
DOCUMENT_RAG_MONGODB_URI=mongodb://localhost:27017/?directConnection=true
DOCUMENT_RAG_MONGODB_DATABASE=chatguru
DOCUMENT_RAG_MONGODB_COLLECTION=documents
DOCUMENT_RAG_MONGODB_INDEX_NAME=document_vector_index
DOCUMENT_RAG_MONGODB_FILES_BUCKET=document_sources
```

2. Ingest your docs:

```bash
make ingest-docs SOURCE_DIR=./rag_data BACKEND=mongodb
```

3. Ask a question over `/ws` and read `sources` from the `end` frame.

4. On source click in UI, open `GET /documents/{source_path}` in an iframe.

## Docker startup ingestion

When running via Docker Compose, the corpus served by document RAG lives in the
`rag-data` Docker volume mounted at `/app/rag_data`. The volume is seeded from
the files bundled in the image (`COPY rag_data/ /app/rag_data/` in
`docker/Dockerfile`) the first time it is created, and is authoritative after
that — operators can update the corpus in production without rebuilding the
image. Ingestion runs automatically on first startup when
`DOCUMENT_RAG_ENABLED=true`.

### Volumes involved

| Volume | Mount | Purpose |
|---|---|---|
| `rag-data` | `/app/rag_data` | Source corpus the entrypoint reads. Seeded once from the image, then authoritative. |
| `rag-ingest-state` | `/app/rag_ingest_state` | Holds the `.ingested` sentinel so ingestion is skipped on subsequent boots. |
| `mongodb-data` | `/data/db` (mongodb service) | Persisted embeddings, chunks, and GridFS source files. |

### How it works

The `docker/entrypoint.sh` runs the ingestion CLI before starting the server:

1. **First start** — `rag-data` is created and seeded from the image's
   `/app/rag_data`; no sentinel exists → ingestion runs → sentinel written to
   the `rag-ingest-state` Docker volume at `/app/rag_ingest_state/.ingested`.
2. **Subsequent starts** — sentinel found → ingestion skipped, container boots
   immediately. The indexed data is persisted in the `mongodb-data` volume and
   the source corpus stays in `rag-data`.
3. **Force re-ingest** — set `DOCUMENT_RAG_INGEST_FULL_REPLACE=1` → sentinel is
   ignored, existing chunks and GridFS files are deleted, everything currently
   in the `rag-data` volume is re-embedded and re-indexed. The sentinel is
   updated on success.

### Configuration

| Variable | Description | Default |
|---|---|---|
| `DOCUMENT_RAG_ENABLED` | Enable startup ingestion and retrieval | `false` |
| `DOCUMENT_RAG_INGEST_FULL_REPLACE` | Set to any non-empty value to force a full re-ingest on next start | *(unset)* |

### Force a full re-ingest from scratch

```bash
# In .env, set:
DOCUMENT_RAG_INGEST_FULL_REPLACE=1

# Then restart (no image rebuild needed — the volume content is what matters):
docker compose up -d
```

Remove `DOCUMENT_RAG_INGEST_FULL_REPLACE=1` from `.env` afterwards to restore
the skip-if-done behavior.

### Adding or updating documents in production

Because the corpus lives in the `rag-data` volume, you do **not** need to
rebuild the image to refresh content. Two supported workflows:

**Option A — copy files into the running volume (recommended for hosting):**

```bash
# Copy a file from the host into the running agent's /app/rag_data
docker compose cp ./new_doc.pdf chatguru-agent:/app/rag_data/

# Re-process everything currently in the volume
DOCUMENT_RAG_INGEST_FULL_REPLACE=1 docker compose up -d --no-deps chatguru-agent
```

**Option B — rebuild the image with new bundled defaults (fresh deployments only):**

Place new files in `rag_data/` in the repo and rebuild. The new content seeds
the `rag-data` volume **only when the volume does not yet exist**. On existing
deployments the volume is authoritative and a rebuild alone will not refresh
the corpus — use Option A instead, or `docker volume rm rag-data` between the
rebuild and the next `up` if you really want to reset.

```bash
DOCUMENT_RAG_INGEST_FULL_REPLACE=1 docker compose up --build
```

### Inspecting / extracting the volume

```bash
# Where the volume lives on the host (Linux / Docker Desktop differ):
docker volume inspect chatguru_rag-data

# List the corpus currently visible to the running agent:
docker compose exec chatguru-agent ls -la /app/rag_data
```

## Troubleshooting

- `sources` arrives empty:
  - verify document RAG is enabled (`DOCUMENT_RAG_ENABLED=true`)
  - verify your query actually triggers `search_documents`
  - confirm chunks exist in `DOCUMENT_RAG_MONGODB_COLLECTION`

- PDF opens on page 1:
  - ensure chunk records have non-null `page`
  - re-ingest PDFs after parser changes (prefer `--full-replace` / `DOCUMENT_RAG_INGEST_FULL_REPLACE=1`)

- Need a clean re-index (local CLI):
  - use `--full-replace` to clear chunks + GridFS source files before ingest

- Need a clean re-index (Docker):
  - set `DOCUMENT_RAG_INGEST_FULL_REPLACE=1` in `.env` and restart
