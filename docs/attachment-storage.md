# Attachment Storage

## Overview

Attachment storage persists the raw binary files that users upload during a chat session — images and documents — so they remain accessible when the conversation is replayed from history. It is a separate concern from *chat history persistence* (which stores text messages) and from *document processing* (which converts PDFs to markdown for the LLM).

The layer uses a ports-and-adapters design: application code depends on the abstract `AttachmentStorage` interface; the concrete backend is selected at startup by the factory.

## Feature flag

Attachment storage is **optional**. Set `ATTACHMENT_STORAGE_ENABLED=false` to disable the entire subsystem:

- `init_attachment_storage()` becomes a no-op.
- Upload endpoints (`POST /upload-attachment`, `POST /process-document`) still accept files and return a response, but `attachment_id` will be `null` — files are not saved.
- The retrieval endpoint (`GET /attachments/{id}`) returns `503`.
- The LLM never receives image data from stored attachments.

When the flag is omitted or set to `true`, the subsystem initialises normally using the configured backend.

## Enabling in production (filesystem backend)

The only currently shipped backend stores files on the local filesystem.

### Required environment variables

| Variable | Default | Description |
|---|---|---|
| `ATTACHMENT_STORAGE_ENABLED` | `true` | Set to `false` to disable. |
| `ATTACHMENT_STORAGE_TYPE` | `filesystem` | Backend type. Only `filesystem` is supported today. |
| `ATTACHMENT_STORAGE_BASE_PATH` | `./attachments` | Directory where files are stored. **Use an absolute path in production.** |

### Docker / container deployments

The backend container writes attachments to `ATTACHMENT_STORAGE_BASE_PATH`. This path **must be backed by a persistent volume** — if it is not, all uploaded files are lost when the container restarts.

In the default `docker-compose.yml` the path is `/data/attachments`, which lives inside the `/data` mount point backed by a named volume:

- **MongoDB profile** (`chatguru-agent`): `/data` is mounted from the `chatguru-data` volume.
- **SQLite profile** (`chatguru-agent-sqlite`): `/data` is mounted from the `vector-db-data` volume.

To override the path (e.g. to a dedicated volume mount) set `ATTACHMENT_STORAGE_BASE_PATH` in your environment before running `docker compose up`. The directory is created automatically at startup; only the parent mount point needs to exist.

```bash
# Example: mount a separate volume for attachments
ATTACHMENT_STORAGE_BASE_PATH=/mnt/attachments docker compose up
```

### File permissions

The backend process must have read/write access to `ATTACHMENT_STORAGE_BASE_PATH`. The directory is created with `mkdir -p` semantics at startup; a health-check write probe runs to verify writability.

If the health check fails you will see:

```
WARNING Attachment storage health check failed — uploads may not work
```

The application continues to start, but upload requests will fail at runtime.

## Disabling in production

```bash
ATTACHMENT_STORAGE_ENABLED=false
```

No volume, directory, or permissions are needed when disabled.

## HTTP endpoints

These endpoints exist regardless of whether attachment storage is enabled, but their behaviour changes:

### `POST /upload-attachment`

Accepts a raw image file (JPEG, PNG, WEBP, GIF). When storage is enabled and `visitor_id` is provided, the file is saved and `attachment_id` is returned. Pass this ID in the subsequent WebSocket message as part of `attachment_ids` so it is linked to the persisted chat message.

**Query parameters:**

| Parameter | Required | Description |
|---|---|---|
| `visitor_id` | No | Scopes the stored file to one user/device. Required for the file to be persisted. |

**Response:**

```json
{ "attachment_id": "3f2504e0-4f89-11d3-9a0c-0305e82c3301" }
```

`attachment_id` is `null` when storage is disabled or `visitor_id` was not provided.

### `POST /process-document`

Converts a document (PDF, DOCX, etc.) to markdown via Docling and optionally stores the original file. `attachment_id` follows the same rules as above.

**Response:**

```json
{
  "markdown": "...",
  "filename": "report.pdf",
  "attachment_id": "3f2504e0-4f89-11d3-9a0c-0305e82c3301"
}
```

### `GET /attachments/{attachment_id}`

Streams the raw file for the given ID. Only the visitor that uploaded the file can retrieve it (`visitor_id` query parameter is mandatory).

Returns `503` when attachment storage is disabled, `404` when the file does not exist or does not belong to the requesting visitor.

## Package layout

```
src/attachment_storage/
├── __init__.py          # Public re-exports
├── base.py              # AttachmentStorage abstract interface
├── bootstrap.py         # Process-wide singleton lifecycle (init / shutdown / get)
├── factory.py           # Reads ATTACHMENT_STORAGE_TYPE and instantiates the backend
└── filesystem.py        # FilesystemAttachmentStorage implementation
```

## Adding a new backend

1. Create `src/attachment_storage/<backend>.py` implementing `AttachmentStorage`:
   - `store(data, attachment_id) -> str` — persist bytes, return an opaque storage key.
   - `retrieve(storage_key) -> AsyncIterator[bytes]` — stream bytes; raise `FileNotFoundError` if missing.
   - `is_healthy() -> bool` — verify the backend is reachable and writable.
2. Add a branch in `factory.py` keyed on a new value for `ATTACHMENT_STORAGE_TYPE`.
3. Add any new dependencies to `pyproject.toml`.
4. Write tests covering store/retrieve roundtrip, health check, and path traversal safety.
