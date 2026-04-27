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

Tool output is internal JSON containing:

- retrieved snippets
- source reference metadata (`source_id`, `source_uri`, `title`)
- chunk/page metadata when available
- score when available

The existing `search_products` flow remains active and unchanged.

## Chat response contract (single-pass structured grounding)

Chat flow for a document-grounded answer is now single-pass:

1. user message arrives
2. model may call `search_documents`
3. model returns one structured object with answer + selected sources
4. backend sends one `end` frame containing those fields

Example end frame:

```json
{
  "type": "end",
  "content": "...assistant answer...",
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

Frontend can render source chips/links from `sources` and open selected files.

Note: because this is single-pass structured output, the final answer is emitted
in the `end` frame (not incremental `token` chunks) for document-grounded turns.

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

When running via Docker Compose, the backend image bundles the contents of `rag_data/`
at `/app/rag_data` and automatically ingests them on first startup when
`DOCUMENT_RAG_ENABLED=true`.

### How it works

The `docker/entrypoint.sh` runs the ingestion CLI before starting the server:

1. **First start** — no sentinel exists → ingestion runs → sentinel written to the
   `rag-ingest-state` Docker volume at `/app/rag_ingest_state/.ingested`.
2. **Subsequent starts** — sentinel found → ingestion skipped, container boots
   immediately. The indexed data is persisted in the `mongodb-data` volume.
3. **Force re-ingest** — set `DOCUMENT_RAG_INGEST_FULL_REPLACE=1` → sentinel is
   ignored, existing chunks and GridFS files are deleted, everything in `rag_data/`
   is re-embedded and re-indexed. The sentinel is updated on success.

### Configuration

| Variable | Description | Default |
|---|---|---|
| `DOCUMENT_RAG_ENABLED` | Enable startup ingestion and retrieval | `false` |
| `DOCUMENT_RAG_INGEST_FULL_REPLACE` | Set to any non-empty value to force a full re-ingest on next start | *(unset)* |

### Force a full re-ingest from scratch

```bash
# In .env, set:
DOCUMENT_RAG_INGEST_FULL_REPLACE=1

# Then restart:
docker compose up --build
```

Remove `DOCUMENT_RAG_INGEST_FULL_REPLACE=1` from `.env` afterwards to restore
the skip-if-done behavior.

### Adding new documents

Place new files in `rag_data/`, rebuild the image, and set
`DOCUMENT_RAG_INGEST_FULL_REPLACE=1` for one run to pick up the changes:

```bash
DOCUMENT_RAG_INGEST_FULL_REPLACE=1 docker compose up --build
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
