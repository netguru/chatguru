"""Per-turn MCP session management.

Stateful MCP servers (e.g. browser automation) require the same
session across successive tool calls — ``browser_navigate`` then
``browser_snapshot`` must hit the same browser. ``MultiServerMCPClient``'s
sessionless ``get_tools()`` opens a fresh session per call, which loses that
state. ``open_mcp_tools`` instead opens one live session per server, binds the
tools to it, and keeps it open for the caller's whole turn.

Each server gets its own session; a server that fails to connect is logged and
skipped so the others still yield tools. Sessions are torn down when the
context manager exits.
"""

import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any, cast

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import Connection, MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

from config import get_logger

logger = get_logger(__name__)

# Bound how long connecting to and discovering tools from a single server may
# take. ``open_mcp_tools`` runs on every chat turn, so without this an
# unreachable or slow server (e.g. MCP_ENABLED=true while the server is down)
# would add its full connect latency to every user message. On timeout the
# server is logged and skipped, exactly like any other connection failure.
_SESSION_OPEN_TIMEOUT_SECONDS = 10.0

# After a server fails to open, skip it for this long instead of re-paying the
# connect timeout on every turn.
_FAILURE_COOLDOWN_SECONDS = 60.0

# Monotonic timestamp of each server's most recent connection failure.
_recent_failures: dict[str, float] = {}


def _in_cooldown(name: str, now: float) -> bool:
    """Return True while ``name`` is inside its post-failure cooldown window."""
    failed_at = _recent_failures.get(name)
    return failed_at is not None and (now - failed_at) < _FAILURE_COOLDOWN_SECONDS


@asynccontextmanager
async def open_mcp_tools(
    connections: dict[str, dict[str, Any]],
) -> AsyncIterator[list[BaseTool]]:
    """Open a live session per server and yield their combined tools.

    The sessions stay open for the duration of the ``async with`` block, so
    stateful tool sequences work. On exit every session is closed. Yields an
    empty list when ``connections`` is empty.
    """
    if not connections:
        yield []
        return

    tools: list[BaseTool] = []
    now = time.monotonic()
    async with AsyncExitStack() as stack:
        for name, connection in connections.items():
            if _in_cooldown(name, now):
                logger.debug("Skipping MCP server %r (in failure cooldown)", name)
                continue
            try:
                client = MultiServerMCPClient({name: cast("Connection", connection)})
                async with asyncio.timeout(_SESSION_OPEN_TIMEOUT_SECONDS):
                    session = await stack.enter_async_context(client.session(name))
                    server_tools = await load_mcp_tools(session)
            except Exception as exc:  # noqa: BLE001 - isolate any per-server failure
                # CancelledError is a BaseException, so cancellation still propagates.
                _recent_failures[name] = now
                logger.warning(
                    "Failed to open MCP session for server %r (%s: %s); skipping.",
                    name,
                    type(exc).__name__,
                    exc,
                )
                continue
            _recent_failures.pop(name, None)
            logger.info(
                "Opened MCP session %r with %d tool(s)", name, len(server_tools)
            )
            tools.extend(server_tools)
        yield tools
