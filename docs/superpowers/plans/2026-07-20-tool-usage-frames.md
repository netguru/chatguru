# Tool-usage Frames Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emit `tool_call`/`tool_result` frames and per-turn `usage`/`model` on the `/ws` stream, and render tool calls in the React frontend, both behind feature flags.

**Architecture:** `Agent.astream()` changes from yielding bare token strings to yielding structured event dicts (`token`/`tool_call`/`tool_result`); usage and resolved model are exposed as post-stream properties. The `/ws` route serializes each event to a WS frame and augments the `end` frame, gated by a backend flag. The frontend collects tool events into per-message `toolCalls` and renders collapsible chips, gated by a Vite flag.

**Tech Stack:** Python 3 / FastAPI / LangChain (`ChatLiteLLM`) / pytest; React 19 / TypeScript / Zustand / Vitest + React Testing Library.

## Global Constraints

- **Additive only:** existing `token`/`end`/`error` frame shapes are unchanged; only new frames and new `end` fields are added. Verbatim from spec.
- **Frame contract (do not rename):** `{type:"tool_call", name, args, session_id}`, `{type:"tool_result", name, result, session_id}`; `end` gains `model` (string), `usage` (`{prompt_tokens, completion_tokens, total_tokens}`), optional `cost_usd` (number).
- **Never** log, persist, or echo the forwarded `auth_token`/`${user_token}` in any frame.
- **Don't buffer the whole turn:** emit tool frames as events happen.
- Both flags default **on**: backend `TOOL_FRAMES_ENABLED=true`, frontend `VITE_TOOL_CALLS_ENABLED` enabled unless `="false"`.
- Backend commands: `uv run pytest`, lint `uv run pre-commit run --all-files`. Frontend: `cd frontend && npm run test`, lint `cd frontend && npx biome check`.

---

### Task 1: Agent yields structured events (token / tool_call / tool_result)

Change `Agent.astream()` and `_run_agentic_loop()` to yield event dicts instead of strings, and migrate the existing agent tests that consume them.

**Files:**
- Modify: `src/agent/service.py` (`_run_agentic_loop`, `_process_tool_calls`, `astream`)
- Test: `tests/test_agent.py`

**Interfaces:**
- Produces: `Agent.astream(...) -> AsyncIterator[dict[str, Any]]` yielding one of:
  - `{"type": "token", "content": str}`
  - `{"type": "tool_call", "name": str, "args": dict[str, Any]}`
  - `{"type": "tool_result", "name": str, "result": Any}`
- Consumes: nothing new.

- [ ] **Step 1: Write the failing test** — append to `tests/test_agent.py`:

```python
@pytest.mark.asyncio
async def test_astream_yields_structured_events_for_tool_call() -> None:
    """astream yields token/tool_call/tool_result event dicts in order."""
    call_count = {"count": 0}

    async def mock_astream(
        messages: list, *, config: dict | None = None
    ) -> AsyncIterator[AIMessageChunk]:
        call_count["count"] += 1
        if call_count["count"] == 1:
            chunk = AIMessageChunk(content="Searching...")
            chunk.tool_calls = [
                {"name": "search_products", "args": {"query": "red jeans"}, "id": "c1"}
            ]
            yield chunk
        else:
            yield AIMessageChunk(content="Done")

    mock_db = MagicMock()
    mock_db.search = AsyncMock(return_value=[])
    mock_db.format_products.return_value = "No products found."

    with patch("src.agent.service._build_chat_llm") as mock_build:
        mock_instance = GenericFakeChatModel(messages=iter([]))
        object.__setattr__(mock_instance, "bind_tools", lambda tools: mock_instance)
        object.__setattr__(mock_instance, "astream", mock_astream)
        mock_build.return_value = mock_instance
        agent = Agent(vector_database=mock_db)

        events = [
            e async for e in agent.astream([{"role": "user", "content": "red jeans"}])
        ]

    types = [e["type"] for e in events]
    assert "token" in types
    tool_call = next(e for e in events if e["type"] == "tool_call")
    assert tool_call["name"] == "search_products"
    assert tool_call["args"] == {"query": "red jeans"}
    tool_result = next(e for e in events if e["type"] == "tool_result")
    assert tool_result["name"] == "search_products"
    assert isinstance(tool_result["result"], str)
    # tool_call must precede its tool_result
    assert types.index("tool_call") < types.index("tool_result")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_agent.py::test_astream_yields_structured_events_for_tool_call -v`
Expected: FAIL — events are strings (`TypeError: string indices must be integers` or `KeyError`).

- [ ] **Step 3: Refactor the loop to yield events.** In `src/agent/service.py`, replace `_process_tool_calls` with an event-yielding generator and update `_run_agentic_loop`:

```python
    @staticmethod
    async def _process_tool_calls(
        full_response: AIMessageChunk | AIMessage,
        messages: list[BaseMessage],
        tool_registry: dict[str, BaseTool],
        config: RunnableConfig | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Execute tool calls, append results to messages, and yield tool events."""
        logger.info("Processing %d tool call(s)", len(full_response.tool_calls))
        messages.append(full_response)

        for tool_call in full_response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_call_id = tool_call["id"]

            yield {"type": "tool_call", "name": tool_name, "args": tool_args}

            result, _ = await _execute_tool(
                tool_name, tool_args, tool_registry, config=config
            )
            messages.append(ToolMessage(content=result, tool_call_id=tool_call_id))
            yield {"type": "tool_result", "name": tool_name, "result": result}
```

Then in `_run_agentic_loop`, change the return type to `AsyncIterator[dict[str, Any]]` and replace the yields:

```python
    async def _run_agentic_loop(
        self,
        messages: list[BaseMessage],
        config: RunnableConfig,
        llm: Runnable[Any, BaseMessage],
        tool_registry: dict[str, BaseTool],
    ) -> AsyncIterator[dict[str, Any]]:
        """Run the agentic loop until no more tool calls or max iterations."""
        for iteration in range(MAX_TOOL_ITERATIONS):
            full_response: AIMessageChunk | None = None

            async for chunk in llm.astream(messages, config=config):
                chunk_msg = chunk if isinstance(chunk, AIMessageChunk) else None
                if chunk_msg:
                    full_response = (
                        chunk_msg
                        if full_response is None
                        else full_response + chunk_msg
                    )

                content: Any = getattr(chunk, "content", "")
                if content:
                    yield {"type": "token", "content": str(content)}

            if full_response is None or not full_response.tool_calls:
                logger.info("Agentic loop completed after %d iterations", iteration + 1)
                return

            async for event in self._process_tool_calls(
                full_response, messages, tool_registry, config=config
            ):
                yield event
        logger.warning("Reached maximum tool iterations (%d)", MAX_TOOL_ITERATIONS)
        yield {
            "type": "token",
            "content": "\n\n⚠️ Reached maximum tool call limit. Please rephrase your question.",
        }
```

Change `astream`'s return annotation to `AsyncIterator[dict[str, Any]]` (its docstring "Yields" section too) — its body already just re-yields loop events, so no other change:

```python
    async def astream(
        self,
        messages: list[dict[str, str]],
        *,
        session_id: str | None = None,
        visitor_id: str | None = None,
        model: str | None = None,
        auth_token: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
```

- [ ] **Step 4: Migrate existing astream-consuming tests.** In `tests/test_agent.py`, the tests below consume `astream` expecting strings. Update each to extract token content. Replace the consumption + assertions:

`test_agent_astream` (lines ~72-77):
```python
        received = [
            e["content"]
            async for e in agent.astream([{"role": "user", "content": "Hello"}])
            if e["type"] == "token"
        ]
        assert len(received) == len(chunks)
        assert "".join(received) == "".join(chunks)
```

`test_agent_astream_empty_response` (lines ~99-104):
```python
        received = [
            e async for e in agent.astream([{"role": "user", "content": "Hello"}])
            if e["type"] == "token"
        ]
        assert len(received) == 0
```

`test_agent_astream_single_chunk` (lines ~125-130):
```python
        received = [
            e["content"]
            async for e in agent.astream([{"role": "user", "content": "Hello"}])
            if e["type"] == "token"
        ]
        assert len(received) == 1
        assert received[0] == "Single response"
```

`test_agent_with_tool_call` (lines ~172-182):
```python
        received = [
            e["content"]
            async for e in agent.astream(
                [{"role": "user", "content": "Show me red jeans"}]
            )
            if e["type"] == "token"
        ]
        full_response = "".join(received)
        assert "Let me search for that..." in full_response
        assert "Here are the results!" in full_response
        mock_db.search.assert_called_once()
        assert call_count["count"] == 2
```

`test_agent_collects_structured_sources_from_document_tool` (lines ~234-237): the list comprehension result is discarded (`_ = [...]`), so it still works with dicts — no change needed. `test_last_trace_id_is_none_without_langfuse` and `test_last_trace_id_resets_between_calls` iterate with `async for _ in ...: pass` — no change needed.

- [ ] **Step 5: Run the full agent test file**

Run: `uv run pytest tests/test_agent.py -v`
Expected: PASS (all, including the new test).

- [ ] **Step 6: Commit**

```bash
git add src/agent/service.py tests/test_agent.py
git commit -m "feat(agent): yield structured events from astream"
```

---

### Task 2: Accumulate per-turn usage and expose model/usage

Track token usage across every loop iteration and expose the resolved model, mirroring the existing `last_trace_id` property.

**Files:**
- Modify: `src/agent/service.py` (`__init__`, `astream`, `_run_agentic_loop`, new properties/helper)
- Test: `tests/test_agent.py`

**Interfaces:**
- Produces:
  - `Agent.last_usage -> dict[str, int] | None` — `{"prompt_tokens", "completion_tokens", "total_tokens"}`, or `None` if no usage metadata was seen this turn.
  - `Agent.last_model -> str | None` — the model id resolved for the most recent `astream` turn.
- Consumes: Task 1's event-yielding loop.

- [ ] **Step 1: Write the failing test** — append to `tests/test_agent.py`:

```python
@pytest.mark.asyncio
async def test_last_usage_sums_across_iterations() -> None:
    """last_usage sums usage_metadata across every agentic-loop iteration."""
    call_count = {"count": 0}

    async def mock_astream(
        messages: list, *, config: dict | None = None
    ) -> AsyncIterator[AIMessageChunk]:
        call_count["count"] += 1
        if call_count["count"] == 1:
            chunk = AIMessageChunk(content="Searching...")
            chunk.tool_calls = [
                {"name": "search_products", "args": {"query": "x"}, "id": "c1"}
            ]
            chunk.usage_metadata = {
                "input_tokens": 100,
                "output_tokens": 20,
                "total_tokens": 120,
            }
            yield chunk
        else:
            final = AIMessageChunk(content="Done")
            final.usage_metadata = {
                "input_tokens": 200,
                "output_tokens": 30,
                "total_tokens": 230,
            }
            yield final

    mock_db = MagicMock()
    mock_db.search = AsyncMock(return_value=[])
    mock_db.format_products.return_value = "none"

    with patch("src.agent.service._build_chat_llm") as mock_build:
        mock_instance = GenericFakeChatModel(messages=iter([]))
        object.__setattr__(mock_instance, "bind_tools", lambda tools: mock_instance)
        object.__setattr__(mock_instance, "astream", mock_astream)
        mock_build.return_value = mock_instance
        agent = Agent(vector_database=mock_db)

        async for _ in agent.astream(
            [{"role": "user", "content": "x"}], model="openai/gpt-5-mini"
        ):
            pass

    assert agent.last_usage == {
        "prompt_tokens": 300,
        "completion_tokens": 50,
        "total_tokens": 350,
    }
    assert agent.last_model == "openai/gpt-5-mini"


@pytest.mark.asyncio
async def test_last_usage_is_none_without_metadata() -> None:
    """last_usage is None when the model reports no usage_metadata."""

    async def mock_astream(
        messages: list, *, config: dict | None = None
    ) -> AsyncIterator[AIMessageChunk]:
        yield AIMessageChunk(content="Hi")

    with patch("src.agent.service._build_chat_llm") as mock_build:
        mock_instance = GenericFakeChatModel(messages=iter([]))
        object.__setattr__(mock_instance, "bind_tools", lambda tools: mock_instance)
        object.__setattr__(mock_instance, "astream", mock_astream)
        mock_build.return_value = mock_instance
        agent = Agent()
        async for _ in agent.astream([{"role": "user", "content": "Hello"}]):
            pass

    assert agent.last_usage is None
    assert agent.last_model == agent._default_model
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_agent.py::test_last_usage_sums_across_iterations tests/test_agent.py::test_last_usage_is_none_without_metadata -v`
Expected: FAIL — `AttributeError: 'Agent' object has no attribute 'last_usage'`.

- [ ] **Step 3: Implement usage accumulation.** In `src/agent/service.py`:

Add a module-level helper near `_execute_tool`:

```python
def _accumulate_usage(running: dict[str, int], message: AIMessageChunk | AIMessage) -> bool:
    """Add a message's usage_metadata into *running*. Returns True if any was found."""
    usage = getattr(message, "usage_metadata", None)
    if not usage:
        return False
    running["prompt_tokens"] += int(usage.get("input_tokens", 0) or 0)
    running["completion_tokens"] += int(usage.get("output_tokens", 0) or 0)
    running["total_tokens"] += int(usage.get("total_tokens", 0) or 0)
    return True
```

In `Agent.__init__`, after `self._last_langfuse_handler = None`, initialise:

```python
        self._last_usage: dict[str, int] | None = None
        self._last_model: str | None = None
```

In `astream`, right after `self._last_langfuse_handler = None` at the top, reset and record the resolved model:

```python
        self._last_usage = None
        self._last_model = model or self._default_model
```

Change `_run_agentic_loop` to accumulate into a per-call running total and store it on `self`. At the top of the method:

```python
        running_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
```

After each inner `async for chunk` stream completes (right after the streaming loop, before the tool-call check), accumulate from the aggregated response and publish the running total whenever any metadata was found:

```python
            if full_response is not None and _accumulate_usage(running_usage, full_response):
                self._last_usage = dict(running_usage)
```

(Publishing inside the loop keeps `last_usage` correct across iterations; `self._last_usage` stays `None` when no metadata ever arrives.)

Add the properties near `last_trace_id`:

```python
    @property
    def last_usage(self) -> dict[str, int] | None:
        """Token usage summed across the most recent astream() turn, or None."""
        return self._last_usage

    @property
    def last_model(self) -> str | None:
        """Model id resolved for the most recent astream() turn."""
        return self._last_model
```

- [ ] **Step 4: Enable streaming usage on the LiteLLM client.** In `_build_chat_llm`, pass `stream_usage=True` so `ChatLiteLLM` requests per-chunk usage:

```python
def _build_chat_llm(model: str | None = None) -> BaseChatModel:
    """Build a LiteLLM chat client for the configured model."""
    settings = get_llm_settings()
    return ChatLiteLLM(
        model=model or settings.model,
        streaming=True,
        stream_usage=True,
        temperature=settings.temperature,
        **_build_llm_kwargs(settings),
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_agent.py -v`
Expected: PASS.

- [ ] **Step 6: Manual runtime verification of streaming usage.** With a real LLM configured, run a WS turn and confirm `usage.total_tokens > 0` on the `end` frame (see the probe in Task 6's manual check). If `ChatLiteLLM` rejects `stream_usage` or returns no metadata, instead pass `model_kwargs={"stream_options": {"include_usage": True}}` to the `ChatLiteLLM` constructor in `_build_chat_llm`. Record which worked in the commit message.

- [ ] **Step 7: Commit**

```bash
git add src/agent/service.py tests/test_agent.py
git commit -m "feat(agent): accumulate per-turn token usage and expose model"
```

---

### Task 3: Route emits tool frames + end-frame usage/model behind a flag

Add the backend feature flag, serialize agent events to WS frames, and augment the `end` frame with sanitization/truncation.

**Files:**
- Modify: `src/config.py` (`AppSettings`)
- Modify: `src/api/routes/chat.py` (`_stream_assistant_response`, `_send_end_frame`, `_handle_chat_turn`, new helpers)
- Modify: `env.example`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `Agent.astream` events (Task 1), `Agent.last_usage`/`last_model` (Task 2).
- Produces: `get_app_settings().tool_frames_enabled: bool`; new WS frames `tool_call`/`tool_result`; `end` frame fields `usage`/`model`/`cost_usd`.

- [ ] **Step 1: Add the config flag.** In `src/config.py`, add to `AppSettings` (after `log_level`):

```python
    tool_frames_enabled: bool = Field(
        default=True,
        description=(
            "Emit tool_call/tool_result WS frames and attach usage/model to the "
            "end frame. Disable to revert /ws to the pre-tool-frames behavior "
            "(TOOL_FRAMES_ENABLED)."
        ),
    )
```

- [ ] **Step 2: Write the failing test.** In `tests/test_api.py`, first update the shared `_mock_astream` helper to yield event dicts (the route now consumes events), then add tool-frame tests. Replace `_mock_astream` (lines 16-30):

```python
def _mock_astream(chunks: list[str]) -> Callable[..., AsyncIterator[dict]]:
    """Create a mock astream yielding token event dicts."""

    async def _gen(
        messages: list[dict[str, str]],
        *,
        session_id: str | None = None,
        visitor_id: str | None = None,
        model: str | None = None,
        auth_token: str | None = None,
    ) -> AsyncIterator[dict]:
        for chunk in chunks:
            yield {"type": "token", "content": chunk}

    return _gen
```

Add near the other websocket tests:

```python
def _mock_astream_with_tool() -> Callable[..., AsyncIterator[dict]]:
    async def _gen(
        messages: list[dict[str, str]],
        *,
        session_id: str | None = None,
        visitor_id: str | None = None,
        model: str | None = None,
        auth_token: str | None = None,
    ) -> AsyncIterator[dict]:
        yield {"type": "token", "content": "Let me check. "}
        yield {"type": "tool_call", "name": "search_documents",
               "args": {"query": "pricing", "auth_token": "SECRET"}}
        yield {"type": "tool_result", "name": "search_documents", "result": "3 docs"}
        yield {"type": "token", "content": "Done."}

    return _gen


def test_websocket_emits_tool_frames_and_usage(async_app: TestClient) -> None:
    with patch("api.routes.chat.Agent") as mock_agent_class:
        mock_agent_instance = MagicMock()
        mock_agent_instance.last_trace_id = None
        mock_agent_instance.get_last_used_sources.return_value = []
        mock_agent_instance.last_usage = {
            "prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15,
        }
        mock_agent_instance.last_model = "openai/gpt-5-mini"
        mock_agent_instance.astream = _mock_astream_with_tool()
        mock_agent_class.return_value = mock_agent_instance

        with async_app.websocket_connect("/ws") as websocket:
            websocket.send_json({
                "session_id": "s1",
                "visitor_id": "v1",
                "messages": [{"role": "user", "content": "hi"}],
            })
            frames = []
            while True:
                data = websocket.receive_json()
                frames.append(data)
                if data["type"] == "end":
                    break

    types = [f["type"] for f in frames]
    assert types.index("tool_call") < types.index("tool_result")
    call = next(f for f in frames if f["type"] == "tool_call")
    assert call["name"] == "search_documents"
    assert call["args"]["query"] == "pricing"
    assert call["args"]["auth_token"] == "[redacted]"   # sanitized
    result = next(f for f in frames if f["type"] == "tool_result")
    assert result["result"] == "3 docs"
    end = frames[-1]
    assert end["model"] == "openai/gpt-5-mini"
    assert end["usage"]["total_tokens"] == 15
    # No frame anywhere leaks the raw secret.
    assert "SECRET" not in str(frames)


def test_websocket_flag_off_hides_tool_frames(async_app: TestClient) -> None:
    from config import get_app_settings

    get_app_settings.cache_clear()
    with patch.dict("os.environ", {"TOOL_FRAMES_ENABLED": "false"}), \
         patch("api.routes.chat.Agent") as mock_agent_class:
        mock_agent_instance = MagicMock()
        mock_agent_instance.last_trace_id = None
        mock_agent_instance.get_last_used_sources.return_value = []
        mock_agent_instance.last_usage = {
            "prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15,
        }
        mock_agent_instance.last_model = "openai/gpt-5-mini"
        mock_agent_instance.astream = _mock_astream_with_tool()
        mock_agent_class.return_value = mock_agent_instance

        with async_app.websocket_connect("/ws") as websocket:
            websocket.send_json({
                "session_id": "s1",
                "visitor_id": "v1",
                "messages": [{"role": "user", "content": "hi"}],
            })
            frames = []
            while True:
                data = websocket.receive_json()
                frames.append(data)
                if data["type"] == "end":
                    break

    get_app_settings.cache_clear()
    types = [f["type"] for f in frames]
    assert "tool_call" not in types
    assert "tool_result" not in types
    end = frames[-1]
    assert "usage" not in end
    assert "model" not in end
```

Add `import os` if not present (the flag-off test patches `os.environ`).

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_api.py::test_websocket_emits_tool_frames_and_usage tests/test_api.py::test_websocket_flag_off_hides_tool_frames -v`
Expected: FAIL — tool frames absent / `KeyError` on `usage`.

- [ ] **Step 4: Implement sanitization helpers + frame emission.** In `src/api/routes/chat.py`, add near the top-level constants (after `_MAX_ATTACHMENTS_PER_MESSAGE`):

```python
_REDACT_TOOL_ARG_KEYS = frozenset(
    {"auth_token", "user_token", "token", "authorization", "api_key"}
)
_MAX_FRAME_VALUE_CHARS = 10_000


def _truncate_frame_value(value: Any) -> Any:
    """Cap long string values so frames stay small; non-strings pass through."""
    if isinstance(value, str) and len(value) > _MAX_FRAME_VALUE_CHARS:
        return value[:_MAX_FRAME_VALUE_CHARS] + "…[truncated]"
    return value


def _sanitize_tool_args(args: Any) -> Any:
    """Redact auth-bearing keys and truncate long values in tool args."""
    if not isinstance(args, dict):
        return _truncate_frame_value(args)
    return {
        k: ("[redacted]" if k.lower() in _REDACT_TOOL_ARG_KEYS else _truncate_frame_value(v))
        for k, v in args.items()
    }
```

Rewrite `_stream_assistant_response` to switch on event type and emit frames (gated by the flag), still returning the accumulated assistant text:

```python
async def _stream_assistant_response(  # noqa: PLR0913
    websocket: WebSocket,
    agent: Agent,
    transcript: list[dict[str, Any]],
    *,
    session_id: str,
    visitor_id: str,
    model: str | None = None,
    auth_token: str | None = None,
) -> str:
    """Stream the assistant reply to *websocket*, emitting token and (when enabled)
    tool_call/tool_result frames, and return the accumulated assistant text.
    """
    frames_enabled = get_app_settings().tool_frames_enabled
    full_response = ""
    async for event in agent.astream(
        transcript,
        session_id=session_id,
        visitor_id=visitor_id,
        model=model,
        auth_token=auth_token,
    ):
        etype = event["type"]
        if etype == "token":
            full_response += event["content"]
            await websocket.send_json(
                {"type": "token", "content": event["content"], "session_id": session_id}
            )
        elif etype == "tool_call" and frames_enabled:
            await websocket.send_json(
                {
                    "type": "tool_call",
                    "name": event["name"],
                    "args": _sanitize_tool_args(event["args"]),
                    "session_id": session_id,
                }
            )
        elif etype == "tool_result" and frames_enabled:
            await websocket.send_json(
                {
                    "type": "tool_result",
                    "name": event["name"],
                    "result": _truncate_frame_value(event["result"]),
                    "session_id": session_id,
                }
            )
    return full_response
```

- [ ] **Step 5: Augment the end frame.** Update `_send_end_frame` to accept and attach usage/model, and update its caller. Change the signature and body:

```python
async def _send_end_frame(  # noqa: PLR0913
    websocket: WebSocket,
    *,
    session_id: str,
    resolved_answer: str,
    sources: list[Any],
    stored_user_attachments: list[dict[str, str]],
    trace_id: str | None,
    usage: dict[str, int] | None = None,
    model: str | None = None,
) -> None:
    """Send the terminating ``end`` frame for a chat turn."""
    end_frame: dict[str, Any] = {
        "type": "end",
        "content": resolved_answer,
        "session_id": session_id,
        "sources": sources,
        "user_attachments": stored_user_attachments,
    }
    if get_app_settings().tool_frames_enabled:
        if model is not None:
            end_frame["model"] = model
        if usage is not None:
            end_frame["usage"] = usage
    safe_trace_id = (
        trace_id.replace("\n", "\\n").replace("\r", "\\r")
        if trace_id is not None
        else None
    )
    logger.info(
        "Streaming completed, trace_id=%s, langfuse_initialized=%s",
        safe_trace_id,
        is_langfuse_initialized(),
    )
    if trace_id is not None:
        end_frame["trace_id"] = trace_id
    await websocket.send_json(end_frame)
    logger.info("Streaming completed for session: %s", session_id)
```

In `_handle_chat_turn`, after `trace_id = agent.last_trace_id`, read usage/model and pass them:

```python
    sources = agent.get_last_used_sources()
    trace_id = agent.last_trace_id
    usage = agent.last_usage
    model = agent.last_model

    await _send_end_frame(
        websocket,
        session_id=session_id,
        resolved_answer=resolved_answer,
        sources=sources,
        stored_user_attachments=stored_user_attachments,
        trace_id=trace_id,
        usage=usage,
        model=model,
    )
```

- [ ] **Step 6: Document the flag.** In `env.example`, add under the app-settings section:

```
# Emit tool_call/tool_result WS frames and usage/model on the end frame (default: true)
TOOL_FRAMES_ENABLED=true
```

- [ ] **Step 7: Run the API tests + full backend suite**

Run: `uv run pytest tests/test_api.py -v && uv run pytest`
Expected: PASS.

- [ ] **Step 8: Lint**

Run: `uv run pre-commit run --all-files`
Expected: PASS (fix any ruff/mypy findings).

- [ ] **Step 9: Commit**

```bash
git add src/config.py src/api/routes/chat.py env.example tests/test_api.py
git commit -m "feat(api): emit tool frames and end-frame usage/model behind TOOL_FRAMES_ENABLED"
```

---

### Task 4: Frontend types for tool events and usage

Add the frame/usage/tool-call TypeScript types.

**Files:**
- Modify: `frontend/src/types/chat.ts`

**Interfaces:**
- Produces: `ToolCall`, `TokenUsage`, `WsToolCallEvent`, `WsToolResultEvent` types; extended `WsEndEvent`, `ChatMessage`, `WsEventType`, `WsEvent`.

- [ ] **Step 1: Add the types.** In `frontend/src/types/chat.ts`:

Add after the `Source` interface:

```ts
/** A tool invocation surfaced during a streamed assistant turn. */
export interface ToolCall {
  name: string;
  args: Record<string, unknown>;
  result?: unknown;
  status: "running" | "done";
}

/** Token usage for a turn. Matches backend end-frame `usage`. */
export interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}
```

Add `toolCalls?: ToolCall[];` to the `ChatMessage` interface (after `storedAttachments`).

Change `WsEventType` to:

```ts
export type WsEventType = "token" | "end" | "error" | "tool_call" | "tool_result";
```

Add the two event interfaces after `WsTokenEvent`:

```ts
export interface WsToolCallEvent extends WsBaseEvent {
  type: "tool_call";
  name: string;
  args: Record<string, unknown>;
}

export interface WsToolResultEvent extends WsBaseEvent {
  type: "tool_result";
  name: string;
  result: unknown;
}
```

Extend `WsEndEvent` with:

```ts
  model?: string;
  usage?: TokenUsage;
  cost_usd?: number;
```

Extend the `WsEvent` union:

```ts
export type WsEvent =
  | WsBaseEvent
  | WsTokenEvent
  | WsEndEvent
  | WsErrorEvent
  | WsToolCallEvent
  | WsToolResultEvent;
```

- [ ] **Step 2: Verify it type-checks**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS (no type errors).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/chat.ts
git commit -m "feat(frontend): add tool-event and usage types"
```

---

### Task 5: Store actions for tool calls

Add Zustand actions that attach tool calls to the streaming assistant message.

**Files:**
- Modify: `frontend/src/store/appStore.ts`
- Test: `frontend/src/store/appStore.test.ts` (create)

**Interfaces:**
- Consumes: `ToolCall` type (Task 4).
- Produces: `addToolCallToLastMessage(name: string, args: Record<string, unknown>) => void`, `resolveToolResultOnLastMessage(name: string, result: unknown) => void`.

- [ ] **Step 1: Write the failing test** — create `frontend/src/store/appStore.test.ts`:

```ts
import { beforeEach, describe, expect, it } from "vitest";
import { selectCurrentMessages, useAppStore } from "./appStore";

function lastAssistant() {
  const msgs = selectCurrentMessages(useAppStore.getState());
  return msgs[msgs.length - 1];
}

describe("tool-call store actions", () => {
  beforeEach(() => {
    useAppStore.setState({ sessions: [], currentSessionId: null });
    const s = useAppStore.getState();
    s.addUserMessage({ id: "u1", role: "user", content: "hi" });
    s.addAssistantPlaceholder({ id: "a1", role: "assistant", content: "", isStreaming: true });
  });

  it("adds a running tool call then resolves it", () => {
    const s = useAppStore.getState();
    s.addToolCallToLastMessage("search_documents", { query: "pricing" });
    expect(lastAssistant().toolCalls).toEqual([
      { name: "search_documents", args: { query: "pricing" }, status: "running" },
    ]);

    s.resolveToolResultOnLastMessage("search_documents", "3 docs");
    expect(lastAssistant().toolCalls).toEqual([
      { name: "search_documents", args: { query: "pricing" }, result: "3 docs", status: "done" },
    ]);
  });

  it("matches results to calls by name in order", () => {
    const s = useAppStore.getState();
    s.addToolCallToLastMessage("search_documents", { query: "a" });
    s.addToolCallToLastMessage("search_documents", { query: "b" });
    s.resolveToolResultOnLastMessage("search_documents", "first");
    const calls = lastAssistant().toolCalls ?? [];
    expect(calls[0]).toMatchObject({ args: { query: "a" }, result: "first", status: "done" });
    expect(calls[1]).toMatchObject({ args: { query: "b" }, status: "running" });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/store/appStore.test.ts`
Expected: FAIL — `addToolCallToLastMessage is not a function`.

- [ ] **Step 3: Implement the actions.** In `frontend/src/store/appStore.ts`:

Import `ToolCall`:

```ts
import type { ChatMessage, HistoryMessage, Source, StoredAttachment, ToolCall, VectorDbType } from "../types/chat";
```

Add to the `AppState` interface (after `markLastMessageError`):

```ts
  addToolCallToLastMessage: (name: string, args: Record<string, unknown>) => void;
  resolveToolResultOnLastMessage: (name: string, result: unknown) => void;
```

Add the implementations in the store (after `markLastMessageError`):

```ts
  addToolCallToLastMessage: (name, args) =>
    set((state) => ({
      sessions: state.sessions.map((s) => {
        if (s.id !== state.currentSessionId) return s;
        const msgs = [...s.messages];
        const last = msgs[msgs.length - 1];
        if (!last?.isStreaming) return s;
        const toolCalls: ToolCall[] = [
          ...(last.toolCalls ?? []),
          { name, args, status: "running" },
        ];
        msgs[msgs.length - 1] = { ...last, toolCalls };
        return { ...s, messages: msgs };
      }),
    })),

  resolveToolResultOnLastMessage: (name, result) =>
    set((state) => ({
      sessions: state.sessions.map((s) => {
        if (s.id !== state.currentSessionId) return s;
        const msgs = [...s.messages];
        const last = msgs[msgs.length - 1];
        if (!last?.isStreaming || !last.toolCalls) return s;
        const toolCalls = [...last.toolCalls];
        // Fill the earliest still-running call with the same name.
        const idx = toolCalls.findIndex((c) => c.name === name && c.status === "running");
        if (idx === -1) return s;
        toolCalls[idx] = { ...toolCalls[idx], result, status: "done" };
        msgs[msgs.length - 1] = { ...last, toolCalls };
        return { ...s, messages: msgs };
      }),
    })),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/store/appStore.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/store/appStore.ts frontend/src/store/appStore.test.ts
git commit -m "feat(frontend): store actions for streamed tool calls"
```

---

### Task 6: Wire tool frames in useChat behind the flag

Handle `tool_call`/`tool_result` frames in the WS message handler, gated by the frontend flag.

**Files:**
- Modify: `frontend/src/vite-env.d.ts`
- Modify: `frontend/src/hooks/useChat.ts`

**Interfaces:**
- Consumes: store actions (Task 5), `WsToolCallEvent`/`WsToolResultEvent` (Task 4).
- Produces: `VITE_TOOL_CALLS_ENABLED` env flag consumed by frontend.

- [ ] **Step 1: Declare the env flag.** In `frontend/src/vite-env.d.ts`, add inside `ImportMetaEnv`:

```ts
  /** Set to "false" to hide rendered tool-call chips in chat. Defaults to enabled. */
  readonly VITE_TOOL_CALLS_ENABLED?: string;
```

- [ ] **Step 2: Handle the frames.** In `frontend/src/hooks/useChat.ts`:

Add the flag constant near `WS_PATH`:

```ts
const TOOL_CALLS_ENABLED = import.meta.env.VITE_TOOL_CALLS_ENABLED !== "false";
```

Import the event types and pull the store actions. Update the type import:

```ts
import type {
  HistoryMessage,
  WsEndEvent,
  WsErrorEvent,
  WsEvent,
  WsToolCallEvent,
  WsToolResultEvent,
  WsTokenEvent,
} from "../types/chat";
```

Add to the destructured `useAppStore()` call:

```ts
    addToolCallToLastMessage,
    resolveToolResultOnLastMessage,
```

In `onmessage`, add branches after the `token` branch and before `end`:

```ts
      } else if (data.type === "tool_call") {
        if (TOOL_CALLS_ENABLED) {
          const e = data as WsToolCallEvent;
          addToolCallToLastMessage(e.name, e.args);
        }
      } else if (data.type === "tool_result") {
        if (TOOL_CALLS_ENABLED) {
          const e = data as WsToolResultEvent;
          resolveToolResultOnLastMessage(e.name, e.result);
        }
```

Add `addToolCallToLastMessage` and `resolveToolResultOnLastMessage` to the `connect` `useCallback` dependency array.

- [ ] **Step 3: Verify type-check and lint**

Run: `cd frontend && npx tsc --noEmit && npx biome check src/hooks/useChat.ts src/vite-env.d.ts`
Expected: PASS.

- [ ] **Step 4: Manual acceptance probe (backend + frontend together).** Start the backend (`uv run uvicorn src.api.main:app --reload`) with an MCP tool configured and `TOOL_FRAMES_ENABLED=true`, then run this Node probe (from the task doc) and confirm `tool_call`→`tool_result` interleave with `token`, then `end` carries `usage`/`model`, and no frame contains the auth token:

```js
const ws = new WebSocket("ws://localhost:8000/ws");
ws.addEventListener("open", () => ws.send(JSON.stringify({
  session_id:"t", visitor_id:"u", auth_token:"<token>",
  messages:[{role:"user", content:"Call a tool and report the result."}]
})));
ws.addEventListener("message", e => console.log(e.data));
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useChat.ts frontend/src/vite-env.d.ts
git commit -m "feat(frontend): consume tool frames in useChat behind VITE_TOOL_CALLS_ENABLED"
```

---

### Task 7: Render collapsible tool-call chips

Add a `ToolCallList` component and render it above the assistant markdown.

**Files:**
- Create: `frontend/src/components/chat/ToolCallList.tsx`
- Create: `frontend/src/components/chat/ToolCallList.test.tsx`
- Modify: `frontend/src/components/chat/ChatMessage.tsx`

**Interfaces:**
- Consumes: `ToolCall` type (Task 4).
- Produces: `ToolCallList` component (`{ toolCalls: ToolCall[] }`).

- [ ] **Step 1: Write the failing test** — create `frontend/src/components/chat/ToolCallList.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { ToolCall } from "../../types/chat";
import { ToolCallList } from "./ToolCallList";

const calls: ToolCall[] = [
  { name: "search_documents", args: { query: "pricing" }, result: "3 docs", status: "done" },
];

describe("ToolCallList", () => {
  it("renders a chip per tool call and expands to show args and result", async () => {
    render(<ToolCallList toolCalls={calls} />);
    const chip = screen.getByRole("button", { name: /search_documents/ });
    expect(chip).toBeInTheDocument();
    // Collapsed: details not shown.
    expect(screen.queryByText(/pricing/)).not.toBeInTheDocument();
    await userEvent.click(chip);
    // Expanded: args + result visible.
    expect(screen.getByText(/pricing/)).toBeInTheDocument();
    expect(screen.getByText(/3 docs/)).toBeInTheDocument();
  });

  it("renders nothing when there are no tool calls", () => {
    const { container } = render(<ToolCallList toolCalls={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/chat/ToolCallList.test.tsx`
Expected: FAIL — cannot find module `./ToolCallList`.

- [ ] **Step 3: Implement the component** — create `frontend/src/components/chat/ToolCallList.tsx`:

```tsx
import { CaretRightIcon, WrenchIcon } from "@phosphor-icons/react";
import { useState } from "react";
import type { ToolCall } from "../../types/chat";
import { Loader } from "../ui/loader";
import { cn } from "../../utils/utils";

interface Props {
  toolCalls: ToolCall[];
}

function formatValue(value: unknown): string {
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function ToolCallChip({ call }: { call: ToolCall }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-m border border-border-neutral bg-surface-neutral-soft">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-3 py-2 text-t3 text-text-primary"
      >
        <WrenchIcon weight="bold" className="size-3.5 shrink-0 text-text-secondary" />
        <span className="font-medium">{call.name}</span>
        {call.status === "running" ? (
          <Loader className="ms-auto size-3.5" />
        ) : (
          <CaretRightIcon
            weight="bold"
            className={cn("ms-auto size-3.5 transition-transform", open && "rotate-90")}
          />
        )}
      </button>
      {open && (
        <div className="border-t border-border-neutral px-3 py-2 text-t3 text-text-secondary">
          <div className="mb-1 font-medium">args</div>
          <pre className="mb-2 max-h-40 overflow-auto whitespace-pre-wrap break-words">
            {formatValue(call.args)}
          </pre>
          {call.status === "done" && (
            <>
              <div className="mb-1 font-medium">result</div>
              <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-words">
                {formatValue(call.result)}
              </pre>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export function ToolCallList({ toolCalls }: Props) {
  if (!toolCalls.length) return null;
  return (
    <div className="mb-3 flex flex-col gap-1.5">
      {toolCalls.map((call, i) => (
        <ToolCallChip key={`${call.name}-${i}`} call={call} />
      ))}
    </div>
  );
}
```

> If `border-border-neutral` isn't a valid token in this design system, substitute the border token used by other cards (grep an existing component such as `AttachmentChip.tsx` for the class it uses). Match, don't invent.

- [ ] **Step 4: Run the component test to verify it passes**

Run: `cd frontend && npx vitest run src/components/chat/ToolCallList.test.tsx`
Expected: PASS.

- [ ] **Step 5: Render it in ChatMessage.** In `frontend/src/components/chat/ChatMessage.tsx`:

Add the flag constant and import near the top:

```tsx
import { ToolCallList } from "./ToolCallList";

const TOOL_CALLS_ENABLED = import.meta.env.VITE_TOOL_CALLS_ENABLED !== "false";
```

In the assistant branch (the `else` at line ~187, immediately inside the `<div className={markdownProseClass}>` wrapper, before the `{message.content ? (` block), render the list:

```tsx
            <div className={markdownProseClass}>
              {TOOL_CALLS_ENABLED && message.toolCalls?.length ? (
                <ToolCallList toolCalls={message.toolCalls} />
              ) : null}
              {message.content ? (
```

(Leave the existing content/loader logic unchanged after it.)

- [ ] **Step 6: Verify type-check, lint, and full frontend suite**

Run: `cd frontend && npx tsc --noEmit && npx biome check && npm run test`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/chat/ToolCallList.tsx frontend/src/components/chat/ToolCallList.test.tsx frontend/src/components/chat/ChatMessage.tsx
git commit -m "feat(frontend): render collapsible tool-call chips in chat"
```

---

## Self-Review

**Spec coverage:**
- Tool-call frames → Tasks 1 (agent events) + 3 (route emission). ✓
- Usage + model on `end` → Tasks 2 (accumulation) + 3 (frame). ✓
- `cost_usd` optional → left out by default (spec says optional/nice-to-have); Task 2 notes where LiteLLM cost would slot in. Acceptable per spec.
- Never leak auth token → Task 3 sanitization + explicit test asserting `"SECRET" not in str(frames)`. ✓
- Truncation of large values → Task 3 `_truncate_frame_value`. ✓
- Don't buffer the whole turn → Tasks 1/3 stream events as they occur. ✓
- Backend flag disables cleanly → Task 3 flag + `test_websocket_flag_off_hides_tool_frames`. ✓
- Frontend render behind flag → Tasks 6/7 `VITE_TOOL_CALLS_ENABLED`. ✓
- Existing text-only turns unchanged → migrated `test_websocket_chat_success`; token/end path preserved. ✓
- Frontend collapsible-chip rendering → Task 7. ✓
- Not persisted to history (out of scope) → no persistence task added. ✓

**Placeholder scan:** No TBD/TODO; every code step shows full code. The one conditional note (border token in Task 7) instructs grepping an existing component rather than leaving a blank. ✓

**Type consistency:** `astream` yields `{"type","content"|"name"/"args"/"result"}` in Task 1, consumed identically in Task 3. `last_usage`/`last_model` defined in Task 2, consumed in Task 3. `ToolCall`/`WsToolCallEvent`/`WsToolResultEvent` defined in Task 4, used in Tasks 5/6/7. Store actions `addToolCallToLastMessage`/`resolveToolResultOnLastMessage` named identically in Tasks 5 and 6. ✓
</content>
