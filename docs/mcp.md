# MCP Server Integration

ChatGuru can expose tools from remote [Model Context Protocol](https://modelcontextprotocol.io)
(MCP) servers to the agent. Server *connections* are parsed once at startup;
their tools are discovered **per chat turn** over a live session via
[`langchain-mcp-adapters`](https://github.com/langchain-ai/langchain-mcp-adapters)
and added alongside the built-in tools (`search_products`, `search_documents`).

Only **remote** transports are supported: `streamable_http` (default) and
`sse`. Local stdio/`command` servers are intentionally out of scope — a
containerized FastAPI deployment should not be spawning subprocesses.

## Configuration

Two environment variables control the integration (see `env.example`):

| Variable          | Default | Description                                              |
| ----------------- | ------- | -------------------------------------------------------- |
| `MCP_ENABLED`     | `false` | Master switch. When `false`, no MCP tools are loaded.    |
| `MCP_CONFIG_PATH` | `""`    | Path to the JSON file declaring servers. Required when enabled. |

The config file uses the familiar Claude-Desktop `mcpServers` shape, restricted
to remote entries. See `mcp.servers.example.json`:

```json
{
  "mcpServers": {
    "github": {
      "url": "https://api.githubcopilot.com/mcp/",
      "transport": "streamable_http",
      "headers": { "Authorization": "Bearer ${MCP_GITHUB_TOKEN}" }
    }
  }
}
```

- `url` — **required**, the server endpoint.
- `transport` — optional, `streamable_http` (default) or `sse`.
- `headers` — optional map of HTTP headers (typically auth).

### Secrets via `${VAR}` interpolation

Any `${VAR}` placeholder in a string value is expanded from the process
environment when the file is loaded, so secrets never live in the committed
file. Set the referenced variable (e.g. `MCP_GITHUB_TOKEN`) in your `.env` or
deployment environment. If a referenced variable is unset, that server is
skipped with a logged warning rather than sending a literal `${...}` token.

## Failure behavior

Everything degrades gracefully — the app always starts:

| Situation                                   | Result                                  |
| ------------------------------------------- | --------------------------------------- |
| `MCP_CONFIG_PATH` missing / file not found  | Warning logged, no MCP tools loaded.    |
| Invalid JSON / no `mcpServers` key          | Warning logged, no MCP tools loaded.    |
| `${VAR}` placeholder unset                  | That server skipped.                    |
| stdio/`command` or unsupported transport    | That server skipped.                    |
| A server is unreachable or slow to connect  | Skipped after a 10s timeout; others still load. |
| MCP tool name collides with a built-in tool | The MCP tool is dropped (built-in wins).|

Each server is opened through its own session, so one slow or broken server
never prevents the others' tools from loading.

## Per-turn sessions (stateful servers)

Tools are **not** loaded once at startup. Instead, each chat turn opens a live
MCP session per server, keeps it open for the whole agentic loop, and closes it
when the turn ends. This matters for **stateful** servers such as browser
automation: e.g. `browser_navigate` and a subsequent `browser_snapshot` must
reach the same browser. A sessionless "one session per tool call" model would
give each call a fresh browser (`about:blank`), losing all state.

Per-turn sessions also isolate concurrent users — each turn gets its own
session, so two users browsing at once never clobber each other's page state.

Trade-off: opening a session per turn adds some connection latency, bounded by a
10s per-server timeout. This is the cost of correctness for stateful tools.

## Architecture

The integration follows the project's standard **settings → loader →
bootstrap → inject** pattern, living in `src/mcp_integration/`:

- `config_loader.py` — reads/validates the JSON file, expands `${VAR}`,
  filters out unsupported transports, returns `{name: connection_dict}`.
- `session.py` — `open_mcp_tools(connections)`, an async context manager that
  opens one live session per server and yields their combined tools, isolating
  per-server failures. Sessions close on exit.
- `bootstrap.py` — process-wide connection cache (`init_mcp` /
  `get_mcp_connections` / `shutdown_mcp`), wired into the FastAPI lifespan in
  `src/api/main.py`. Parsing the config does no network I/O, so startup never
  depends on an MCP server being reachable.

The connections are injected into `Agent` via the `mcp_connections` argument in
`src/api/routes/chat.py`; `Agent.astream` opens the per-turn session and binds
the tools for that turn. The collision guard lives in `Agent._filter_mcp_tools`.

> **Note on the system prompt:** MCP tools are bound to the model, but whether
> the model *uses* them depends on the chat system prompt (managed in Langfuse
> as `CHAT_SYSTEM_PROMPT`, with a local fallback in `src/agent/prompt.py`). If
> the prompt only describes `search_products`/`search_documents` and mandates
> "grounded answers only," the model may not invoke MCP tools. Update the prompt
> to mention the new capabilities (e.g. web browsing) so the model knows to use
> them.
