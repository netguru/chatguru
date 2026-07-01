"""Load and validate remote MCP server connections from a JSON config file.

The config file uses the Claude-Desktop style ``mcpServers`` shape but is
restricted to remote transports (``streamable_http`` / ``sse``).  String
values may contain ``${VAR}`` placeholders that are expanded from the
environment at load time so secrets never live in the committed file::

    {
      "mcpServers": {
        "github": {
          "url": "https://api.githubcopilot.com/mcp/",
          "transport": "streamable_http",
          "headers": {"Authorization": "Bearer ${MCP_GITHUB_TOKEN}"}
        }
      }
    }

Each returned value is a connection dict ready to hand to
``langchain_mcp_adapters.client.MultiServerMCPClient``.
"""

import json
import os
import re
from pathlib import Path
from typing import Any

from config import get_logger

logger = get_logger(__name__)

# Remote transports only — stdio/websocket entries are rejected (out of scope).
_SUPPORTED_TRANSPORTS = frozenset({"streamable_http", "sse"})
_DEFAULT_TRANSPORT = "streamable_http"

# Matches ${VAR} placeholders inside string values.
_PLACEHOLDER = re.compile(r"\$\{([^}]+)\}")


class _MissingEnvVarError(ValueError):
    """Raised when a ${VAR} placeholder has no matching environment variable."""


def _expand_placeholders(value: Any) -> Any:
    """Recursively expand ``${VAR}`` placeholders in string values.

    Raises ``_MissingEnvVarError`` when a referenced variable is unset so the
    caller can skip the offending server rather than send a literal ``${...}``.
    """
    if isinstance(value, str):

        def _replace(match: re.Match[str]) -> str:
            name = match.group(1)
            env_value = os.environ.get(name)
            if env_value is None:
                raise _MissingEnvVarError(name)
            return env_value

        return _PLACEHOLDER.sub(_replace, value)
    if isinstance(value, dict):
        return {k: _expand_placeholders(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_placeholders(v) for v in value]
    return value


def _build_connection(name: str, raw: Any) -> dict[str, Any] | None:
    """Validate and normalize a single server entry into a connection dict.

    Returns ``None`` (after logging) when the entry is unusable so loading can
    continue for the remaining servers.
    """
    if not isinstance(raw, dict):
        logger.warning("MCP server %r is not an object; skipping", name)
        return None

    if "command" in raw or raw.get("transport") == "stdio":
        logger.warning(
            "MCP server %r uses an unsupported stdio/command transport; "
            "only streamable_http and sse are supported. Skipping.",
            name,
        )
        return None

    transport = str(raw.get("transport") or _DEFAULT_TRANSPORT).strip()
    if transport not in _SUPPORTED_TRANSPORTS:
        logger.warning(
            "MCP server %r has unsupported transport %r; skipping.", name, transport
        )
        return None

    url = raw.get("url")
    if not url or not isinstance(url, str):
        logger.warning("MCP server %r is missing a string 'url'; skipping.", name)
        return None

    try:
        expanded = _expand_placeholders(raw)
    except _MissingEnvVarError as exc:
        logger.warning(
            "MCP server %r references unset environment variable ${%s}; skipping.",
            name,
            exc.args[0],
        )
        return None

    connection: dict[str, Any] = {
        "transport": transport,
        "url": expanded["url"],
    }
    headers = expanded.get("headers")
    if headers:
        connection["headers"] = headers
    return connection


def load_mcp_connections(config_path: str) -> dict[str, dict[str, Any]]:
    """Read the MCP config file and return ``{name: connection_dict}``.

    Returns an empty mapping (after logging a warning) when the file is missing,
    unreadable, or malformed. Individual invalid server entries are skipped
    without discarding the valid ones.
    """
    path = Path(config_path).expanduser()
    if not path.is_file():
        logger.warning("MCP config file not found at %s; no MCP tools loaded.", path)
        return {}

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception("Failed to read or parse MCP config file at %s", path)
        return {}

    servers = document.get("mcpServers") if isinstance(document, dict) else None
    if not isinstance(servers, dict):
        logger.warning(
            "MCP config file %s has no 'mcpServers' object; no MCP tools loaded.",
            path,
        )
        return {}

    connections: dict[str, dict[str, Any]] = {}
    for name, raw in servers.items():
        connection = _build_connection(str(name), raw)
        if connection is not None:
            connections[str(name)] = connection

    logger.info("Loaded %d MCP server connection(s) from %s", len(connections), path)
    return connections
