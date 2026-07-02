# LiteLLM Integration Design

**Date:** 2026-07-02
**Branch:** feat/litellm
**Status:** Approved

## Overview

Add LiteLLM as a third provider mode alongside the existing `azure` and `openai` modes. When LiteLLM is active, users can choose a model per request from a configured list via a dropdown in the chat input area. The selected model persists in `localStorage`.

## Configuration

Two new env vars:

```
LLM_PROVIDER=litellm                        # "azure" | "openai" | "litellm"
LLM_LITELLM_MODELS_CONFIG=/path/to/models.json
```

### Backward Compatibility

`LLM_PROVIDER` is explicit but the existing implicit detection logic (if `LLM_OPENAI_BASE_URL` is set → `openai`, else → `azure`) stays as a fallback. Existing deployments require no changes.

### Models JSON File

The file at `LLM_LITELLM_MODELS_CONFIG` uses this structure:

```json
{
  "providers": [
    {
      "name": "Anthropic",
      "models": [
        { "label": "Sonnet 3.5", "id": "anthropic/claude-3-5-sonnet-20241022" }
      ]
    },
    {
      "name": "OpenAI",
      "models": [
        { "label": "GPT-4o", "id": "gpt-4o" }
      ]
    }
  ]
}
```

- `id` is the LiteLLM model string passed directly to `ChatLiteLLM`
- `label` is the human-friendly name shown in the UI dropdown
- Provider API keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.) are standard env vars; LiteLLM picks them up automatically — no new key fields in `LLMSettings`
- Missing file or invalid JSON at startup raises an error (fail fast)

### Pydantic Models (new, in `src/config.py`)

```python
class LiteLLMModel(BaseModel):
    label: str
    id: str

class LiteLLMProvider(BaseModel):
    name: str
    models: list[LiteLLMModel]

class LiteLLMModelsConfig(BaseModel):
    providers: list[LiteLLMProvider]
```

`LLMSettings` gets:
- `LLM_PROVIDER: str | None` — explicit provider override
- `LLM_LITELLM_MODELS_CONFIG: str | None` — path to the JSON file
- A `@model_validator` that loads and validates the JSON file when both fields are set and provider is `litellm`

## Backend Changes

### `src/agent/service.py`

`_build_chat_llm()` gains a third branch:

```python
elif provider == "litellm":
    return ChatLiteLLM(model=model, streaming=True, temperature=temperature)
```

- `Agent.__init__` and `Agent.run()` (or equivalent) accept an optional `model: str | None` parameter
- If `model` is `None` and provider is LiteLLM, defaults to the first model in the config list
- `langchain-litellm` added to `pyproject.toml` dependencies

### `src/api/routes/chat.py`

**New endpoint:**

```
GET /api/models
```

Returns the provider/model list when `LLM_PROVIDER=litellm`, otherwise returns `{"providers": []}`. Frontend uses emptiness to decide whether to render the dropdown.

**WebSocket payload** — adds an optional `model` field:

```json
{
  "messages": [...],
  "model": "anthropic/claude-3-5-sonnet-20241022"
}
```

The value is validated against the configured model IDs on the backend (unknown model ID → error response). It is then passed through to the agent.

## Frontend Changes

### `useModels` hook (`frontend/src/hooks/useModels.ts`)

- Fetches `GET /api/models` once on mount
- Returns the provider/model list; empty list means LiteLLM is not active
- No dropdown rendered when list is empty — zero visual change for non-LiteLLM deployments

### Model Selector Component (`frontend/src/components/chat/ModelSelector.tsx`)

- Dropdown placed in the chat input area
- Groups models by provider name
- Selected model stored in `localStorage` under key `chatguru_selected_model`
- Defaults to the first model in the list on first load

### WebSocket message

The `model` field is included in the outbound message payload when a model is selected. When LiteLLM is not active, `model` is never sent.

## Data Flow

```
User selects model → stored in localStorage
User sends message → model ID added to WebSocket payload
Backend validates model ID against config
Agent builds ChatLiteLLM(model=<id>)
LiteLLM routes request to underlying provider
Response streamed back via existing SSE mechanism
```

## Error Handling

- Unknown `model` ID in request → `400` error response before agent is called
- `LLM_PROVIDER=litellm` set but `LLM_LITELLM_MODELS_CONFIG` missing or invalid → startup error
- LiteLLM provider API error → propagates through existing agent error handling

## Testing

- Unit test: `_build_chat_llm()` with `provider=litellm` returns `ChatLiteLLM` instance
- Unit test: config loading rejects missing file / malformed JSON
- Unit test: `GET /api/models` returns correct shape for litellm and non-litellm providers
- Unit test: unknown model ID in WebSocket payload returns error
- Manual: end-to-end with a real LiteLLM-supported model (e.g., `gpt-4o` via `OPENAI_API_KEY`)
