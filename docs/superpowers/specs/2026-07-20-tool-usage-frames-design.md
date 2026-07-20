# Design: Tool-usage frames on `/ws` + frontend rendering

**Date:** 2026-07-20
**Status:** Approved (pending implementation plan)
**Source task:** `docs/ngos-tool-usage-frames-task.md`

## Goal

Make Chatguru emit, on the existing `WS /ws` stream, machine-readable frames describing
tool activity and token usage inside a turn, so the NGos engine (a separate service that
connects to our backend like another frontend) can drive auto-refresh, citations,
confidence badges, and budget/cost logging. Additionally, render those tool calls in our
own React frontend for end users.

Everything is **additive** and gated by feature flags so it can be fully disabled on both
sides, reverting to today's exact behavior.

## Frame contract (fixed — agreed with NGos, do not rename)

New frames on `/ws`:

```jsonc
{ "type": "tool_call",   "name": "<toolName>", "args":   { /* tool input */ },  "session_id": "<id>" }
{ "type": "tool_result", "name": "<toolName>", "result": <json-serializable>,   "session_id": "<id>" }
```

Additions to the existing `end` frame (existing fields unchanged):

```jsonc
{
  "type": "end",
  "content": "...",
  "sources": [...],
  "trace_id": "...",
  "session_id": "<id>",
  "model": "openai/gpt-5-mini",
  "usage": { "prompt_tokens": 1234, "completion_tokens": 567, "total_tokens": 1801 },
  "cost_usd": 0.0031            // optional, omitted when not computable
}
```

- One `tool_call` (emitted before execution) + one `tool_result` (after it returns) per
  tool invocation.
- Order relative to `token` frames does not matter to NGos, but the natural emission order
  is: tokens → `tool_call` → `tool_result` → tokens (next iteration) → … → `end`.
- `args`/`result` must be JSON-serializable; large values may be truncated.
- Existing `token`/`end`/`error` consumers must keep working unchanged.

## Architecture

### 1. Agent yields structured events (`src/agent/service.py`)

`Agent.astream()` currently yields bare `str` tokens. Change its return type to
`AsyncIterator[dict[str, Any]]` yielding typed events:

```python
{"type": "token",       "content": str}
{"type": "tool_call",   "name": str, "args": dict}
{"type": "tool_result", "name": str, "result": Any}
```

`_run_agentic_loop` already aggregates `full_response.tool_calls` and executes them via the
`_process_tool_calls` helper. Refactor so the loop yields:

- `{"type": "token", ...}` for each streamed content chunk (as today).
- Before executing each tool call: `{"type": "tool_call", "name", "args"}`.
- After each tool returns: `{"type": "tool_result", "name", "result"}`.

`_process_tool_calls` becomes an async generator (or is inlined into the loop) so it can
yield the tool events while still appending `ToolMessage`s to `messages`. Result value is
whatever the tool returned (a `str` for our current tools).

**Usage + model** exposed as post-stream properties, mirroring the existing
`last_trace_id` property and `get_last_used_sources()` method:

- `Agent.last_usage -> dict | None` — `{"prompt_tokens", "completion_tokens", "total_tokens"}`,
  accumulated across every loop iteration.
- `Agent.last_model -> str | None` — the model id resolved for the turn.

Accumulation: after each iteration's stream completes, read `usage_metadata` off the
aggregated `AIMessageChunk` (`input_tokens` / `output_tokens` / `total_tokens`) and add to
a per-turn running total stored on `self` (reset at the top of `astream`, like
`_last_turn_sources`). Map LangChain's `input_tokens`/`output_tokens` to the contract's
`prompt_tokens`/`completion_tokens`.

`cost_usd`: best-effort. If LiteLLM surfaces a per-call cost in `response_metadata`
(e.g. `response_cost`), sum it into `last_usage`/a `last_cost_usd` property; otherwise omit.

**Implementation risk (verify early):** LangChain `ChatLiteLLM` streaming must surface
`usage_metadata`. If it does not by default, set LiteLLM `stream_options={"include_usage":
true}` when building the chat model (`_build_chat_llm`). Verify with a real WS turn before
building the rest.

### 2. Route emits frames (`src/api/routes/chat.py`)

`_stream_assistant_response` iterates the agent's events and switches on `type`:

- `token` → existing token frame (unchanged shape).
- `tool_call` / `tool_result` → new frames, each with `session_id`, **only when the
  backend flag is on**.

It still accumulates and returns the final assistant text (from `token` events) so the rest
of `_handle_chat_turn` (persistence, sources) is unaffected.

`_send_end_frame` gains `model` and `usage` (and optional `cost_usd`), read from
`agent.last_model` / `agent.last_usage`, **only when the backend flag is on**.

**Security / sanitization** (applies to emitted frames only):

- Redact any key in `args` matching (case-insensitive) `auth_token`, `user_token`,
  `token`, `authorization`, `api_key` → replaced with `"[redacted]"`.
- Truncate serialized `args` and `result` to a fixed cap (e.g. 10 KB) to avoid oversized
  frames; append a truncation marker when cut.
- The forwarded `auth_token` travels via MCP headers, never as a tool arg, but redaction is
  applied defensively regardless.

### 3. Backend feature flag (`src/config.py`)

Add `tool_frames_enabled: bool = True` to `AppSettings` (env var `TOOL_FRAMES_ENABLED`).
When **false**:

- No `tool_call` / `tool_result` frames are sent.
- The `end` frame carries no `model` / `usage` / `cost_usd`.
- Output is byte-identical to today's behavior.

The agent still yields events; the route simply does not serialize the new ones. Document
the var in `env.example`.

### 4. Frontend types (`frontend/src/types/chat.ts`)

- Add `WsEventType` members `"tool_call"` and `"tool_result"`.
- Add interfaces:
  ```ts
  interface WsToolCallEvent extends WsBaseEvent {
    type: "tool_call"; name: string; args: Record<string, unknown>;
  }
  interface WsToolResultEvent extends WsBaseEvent {
    type: "tool_result"; name: string; result: unknown;
  }
  interface TokenUsage { prompt_tokens: number; completion_tokens: number; total_tokens: number; }
  interface ToolCall { name: string; args: Record<string, unknown>; result?: unknown; status: "running" | "done"; }
  ```
- Extend `WsEndEvent` with `model?: string`, `usage?: TokenUsage`, `cost_usd?: number`.
- Extend `ChatMessage` with `toolCalls?: ToolCall[]`.
- Add `WsToolCallEvent | WsToolResultEvent` to the `WsEvent` union.

### 5. Frontend store + hook (`frontend/src/hooks/useChat.ts`, `store/appStore.ts`)

- Add store actions: `addToolCallToLastMessage(name, args)` and
  `resolveToolResultOnLastMessage(name, result)`.
  - `addToolCallToLastMessage`: push `{name, args, status: "running"}` onto the current
    assistant message's `toolCalls`.
  - `resolveToolResultOnLastMessage`: find the **last** `toolCalls` entry with the same
    `name` and `status === "running"`, set `result` and `status: "done"`.
    (Matching by name + order because the fixed frame contract carries no call id.)
- In `useChat.ts` `onmessage`, handle the two new event types by calling those actions —
  **only when the frontend flag is enabled**; otherwise ignore them.

### 6. Frontend rendering (`frontend/src/components/chat/ChatMessage.tsx`)

When the frontend flag is enabled and `message.toolCalls?.length`, render a block of
**collapsible chips above the assistant markdown text**:

- Each chip: `🔧 <name> ▸`, a spinner while `status === "running"`.
- Expanding shows `args` and `result` (JSON-stringified, pretty-printed), scrollable.
- Styled with existing UI primitives (surface/border tokens, `IconButton`), consistent with
  the rest of the chat surface.
- Extract into a small `ToolCallList` / `ToolCallChip` component to keep `ChatMessage` focused.

### 7. Frontend feature flag (`frontend/src/vite-env.d.ts`)

Add `VITE_TOOL_CALLS_ENABLED?: string` to `ImportMetaEnv`. A module-level constant
`TOOL_CALLS_ENABLED = import.meta.env.VITE_TOOL_CALLS_ENABLED !== "false"` (default enabled,
matching `VITE_DOCUMENT_UPLOAD_ENABLED`). Gates both the `useChat` handling and the
`ChatMessage` rendering. Document in `env.example` if frontend vars are listed there.

## Feature-flag semantics summary

| Flag | Off effect |
| --- | --- |
| `TOOL_FRAMES_ENABLED` (backend) | No new frames; `end` carries no `usage`/`model`. Old behavior exactly. |
| `VITE_TOOL_CALLS_ENABLED` (frontend) | Frames ignored client-side; no chips rendered. |

Both default **on**. Backend off ⇒ frontend has nothing to render regardless.

## Testing

Backend (pytest):
- Agentic loop yields the expected event sequence for a tool-calling turn (token →
  tool_call → tool_result → token).
- Route emits ordered `tool_call` then `tool_result` frames with correct `name` and JSON
  `args`/`result`, interleaved with `token`, then `end`.
- `end` includes `model` and `usage` whose `total_tokens ≈ prompt + completion`, summed
  across a multi-iteration (multi-tool) turn.
- No frame contains the auth token; a token-like arg key is redacted.
- `TOOL_FRAMES_ENABLED=false` ⇒ no tool frames, `end` unchanged from today.
- Text-only turn ⇒ `token … end` as before; `end` now also carries `usage`/`model`
  (flag on).

Frontend (vitest / RTL):
- `useChat` reducer: `tool_call` then `tool_result` produce a resolved `toolCalls` entry;
  flag off ⇒ no `toolCalls`.
- `ChatMessage`: chips render, expand/collapse toggles args/result, spinner while running.

Manual acceptance (from the task's probe): raw WS turn that calls a tool produces
`tool_call` → `tool_result` interleaved with `token`, then `end{usage, model}`; no auth
token anywhere.

## Out of scope

- Per-turn system prompt / tool allowlist (resolved elsewhere).
- Any NGos-side changes.
- Persisting tool calls to chat history (frames are live-stream only; not stored or replayed
  on history load).

## Files touched

- `src/agent/service.py` — structured events, usage/model accumulation + properties.
- `src/api/routes/chat.py` — frame emission, end-frame fields, redaction/truncation.
- `src/config.py` — `AppSettings.tool_frames_enabled`.
- `env.example` — document `TOOL_FRAMES_ENABLED` (and `VITE_TOOL_CALLS_ENABLED`).
- `frontend/src/types/chat.ts` — new event/usage/toolcall types.
- `frontend/src/hooks/useChat.ts` — handle new frames behind flag.
- `frontend/src/store/appStore.ts` — tool-call store actions.
- `frontend/src/components/chat/ChatMessage.tsx` (+ new `ToolCallList`/`ToolCallChip`).
- `frontend/src/vite-env.d.ts` — `VITE_TOOL_CALLS_ENABLED`.
- Tests: `tests/` (backend), `frontend/src/**` (frontend).
</content>
</invoke>
