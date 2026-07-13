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

# Reserved placeholder name. Unlike ${ENV_VAR} placeholders (expanded from the
# environment at load time), ``${user_token}`` is expanded per chat turn with
# the calling user's token — see ``apply_user_token``. A server references it to
# opt in to receiving the user's token in a header.
USER_TOKEN_NAME = "user_token"  # noqa: S105 - placeholder name, not a secret
_USER_TOKEN_PLACEHOLDER = "${" + USER_TOKEN_NAME + "}"


class _MissingEnvVarError(ValueError):
    """Raised when a ${VAR} placeholder has no matching environment variable."""


def _expand_placeholders(value: Any) -> Any:
    """Recursively expand ``${VAR}`` placeholders in string values.

    Raises ``_MissingEnvVarError`` when a referenced variable is unset so the
    caller can skip the offending server rather than send a literal ``${...}``.
    The reserved ``${user_token}`` placeholder is left untouched here; it is
    expanded per request instead (see ``apply_user_token``).
    """
    if isinstance(value, str):

        def _replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name == USER_TOKEN_NAME:
                return match.group(0)
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


def _misplaced_user_token(expanded: dict[str, Any]) -> str | None:
    """Return where ``${user_token}`` illegally appears, or ``None`` if valid.

    ``${user_token}`` is only substituted into header *values* (see
    ``apply_user_token``). Anywhere else — the URL or a header *name* — it is
    never expanded and would be sent literally over the wire, so such an entry
    must be rejected at load time.
    """
    url = expanded.get("url")
    if isinstance(url, str) and _USER_TOKEN_PLACEHOLDER in url:
        return "its URL"
    headers = expanded.get("headers")
    if isinstance(headers, dict) and any(
        isinstance(k, str) and _USER_TOKEN_PLACEHOLDER in k for k in headers
    ):
        return "a header name"
    return None


def connection_requires_user_token(connection: dict[str, Any]) -> bool:
    """Return True when any header value references ``${user_token}``."""
    headers = connection.get("headers")
    if not isinstance(headers, dict):
        return False
    return any(
        isinstance(v, str) and _USER_TOKEN_PLACEHOLDER in v for v in headers.values()
    )


def apply_user_token(connection: dict[str, Any], user_token: str) -> dict[str, Any]:
    """Return a copy of ``connection`` with ``${user_token}`` expanded in headers."""
    headers = connection.get("headers")
    if not isinstance(headers, dict):
        return connection
    expanded_headers = {
        k: v.replace(_USER_TOKEN_PLACEHOLDER, user_token) if isinstance(v, str) else v
        for k, v in headers.items()
    }
    return {**connection, "headers": expanded_headers}


def _build_connection(name: str, raw: Any) -> dict[str, Any] | None:  # noqa: PLR0911
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

    misplaced = _misplaced_user_token(expanded)
    if misplaced is not None:
        logger.warning(
            "MCP server %r references ${%s} in %s; it is only supported in "
            "header values. Skipping.",
            name,
            USER_TOKEN_NAME,
            misplaced,
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
