"""Process-wide MCP configuration lifecycle.

The MCP server *connections* are parsed once at startup and cached. Tool
discovery is deferred to request time: each chat turn opens live sessions via
``open_mcp_tools`` so stateful servers retain state within the turn (see
``session.py``). Parsing the config does no network I/O, so startup never
depends on an MCP server being reachable.
"""

from typing import Any

from config import get_logger, get_mcp_settings
from mcp_integration.config_loader import load_mcp_connections

logger = get_logger(__name__)

_mcp_connections: dict[str, dict[str, Any]] | None = None


def is_mcp_enabled() -> bool:
    """Return True when MCP integration is explicitly enabled."""
    return bool(get_mcp_settings().enabled)


def init_mcp() -> None:
    """Parse and cache MCP server connections process-wide."""
    global _mcp_connections  # noqa: PLW0603
    if not is_mcp_enabled():
        logger.info("MCP integration is disabled (MCP_ENABLED=false)")
        return
    if _mcp_connections is not None:
        return
    settings = get_mcp_settings()
    if not settings.config_path.strip():
        logger.warning(
            "MCP enabled but MCP_CONFIG_PATH is empty; no MCP servers loaded."
        )
        _mcp_connections = {}
        return
    _mcp_connections = load_mcp_connections(settings.config_path)
    logger.info("MCP integration initialized with %d server(s)", len(_mcp_connections))


def shutdown_mcp() -> None:
    """Release cached MCP connections."""
    global _mcp_connections  # noqa: PLW0603
    if _mcp_connections is not None:
        _mcp_connections = None
        logger.info("MCP integration shut down")


def get_mcp_connections() -> dict[str, dict[str, Any]]:
    """Return cached MCP connections, or an empty mapping when disabled."""
    if _mcp_connections is None:
        return {}
    return dict(_mcp_connections)
