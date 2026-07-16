"""Behavior tests for the MCP integration (config loading, sessions, bootstrap)."""

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.tools import BaseTool, tool

from config import McpSettings
from mcp_integration import bootstrap as mcp_bootstrap
from mcp_integration import session as mcp_session
from mcp_integration import load_mcp_connections, open_mcp_tools


def _write_config(tmp_path: Path, document: dict) -> str:
    path = tmp_path / "mcp.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return str(path)


# --- config_loader ---------------------------------------------------------


def test_load_expands_env_placeholders(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MCP_TEST_TOKEN", "s3cret")
    config_path = _write_config(
        tmp_path,
        {
            "mcpServers": {
                "github": {
                    "url": "https://example.com/mcp/",
                    "transport": "streamable_http",
                    "headers": {"Authorization": "Bearer ${MCP_TEST_TOKEN}"},
                }
            }
        },
    )

    connections = load_mcp_connections(config_path)

    assert connections == {
        "github": {
            "transport": "streamable_http",
            "url": "https://example.com/mcp/",
            "headers": {"Authorization": "Bearer s3cret"},
        }
    }


def test_load_defaults_transport_to_streamable_http(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        {"mcpServers": {"svc": {"url": "https://example.com/mcp/"}}},
    )

    connections = load_mcp_connections(config_path)

    assert connections["svc"]["transport"] == "streamable_http"


def test_load_skips_server_with_missing_env_var(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        {
            "mcpServers": {
                "github": {
                    "url": "https://example.com/mcp/",
                    "headers": {"Authorization": "Bearer ${DEFINITELY_UNSET_VAR}"},
                }
            }
        },
    )

    assert load_mcp_connections(config_path) == {}


def test_load_rejects_stdio_transport(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        {
            "mcpServers": {
                "local": {"command": "npx", "args": ["-y", "some-server"]},
                "remote": {"url": "https://example.com/mcp/"},
            }
        },
    )

    connections = load_mcp_connections(config_path)

    assert "local" not in connections
    assert "remote" in connections


def test_load_rejects_unsupported_transport(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        {"mcpServers": {"ws": {"url": "wss://example.com", "transport": "websocket"}}},
    )

    assert load_mcp_connections(config_path) == {}


def test_load_skips_entry_without_url(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        {"mcpServers": {"broken": {"transport": "sse"}}},
    )

    assert load_mcp_connections(config_path) == {}


def test_load_missing_file_returns_empty(tmp_path: Path) -> None:
    assert load_mcp_connections(str(tmp_path / "nope.json")) == {}


def test_load_invalid_json_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")

    assert load_mcp_connections(str(path)) == {}


def test_load_without_mcp_servers_key_returns_empty(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path, {"something_else": {}})

    assert load_mcp_connections(config_path) == {}


def test_load_preserves_user_token_placeholder(tmp_path: Path) -> None:
    # ${user_token} is expanded per request, not at load time, so it must
    # survive loading untouched rather than skipping the server.
    config_path = _write_config(
        tmp_path,
        {
            "mcpServers": {
                "internal": {
                    "url": "https://example.com/mcp/",
                    "headers": {"Authorization": "Bearer ${user_token}"},
                }
            }
        },
    )

    connections = load_mcp_connections(config_path)

    assert connections["internal"]["headers"] == {
        "Authorization": "Bearer ${user_token}"
    }


@pytest.mark.parametrize(
    "server",
    [
        # In the URL rather than a header value.
        {"url": "https://example.com/mcp?token=${user_token}"},
        # In a header *name* rather than a header value — neither expanded nor
        # gated, so it would otherwise be sent literally over the wire.
        {
            "url": "https://example.com/mcp/",
            "headers": {"${user_token}": "x"},
        },
    ],
)
def test_load_rejects_user_token_outside_header_value(
    tmp_path: Path, server: dict
) -> None:
    # ${user_token} is only expanded in header values; anywhere else it would
    # be sent as a literal string, so the entry is rejected at load time.
    config_path = _write_config(tmp_path, {"mcpServers": {"internal": server}})

    assert load_mcp_connections(config_path) == {}


# --- session (open_mcp_tools) ----------------------------------------------


@pytest.fixture(autouse=True)
def _clear_failure_cooldown() -> None:
    mcp_session._recent_failures.clear()


@tool
def _fake_tool(query: str) -> str:
    """A fake MCP tool."""
    return query


def _client_factory_by_name(failing: set[str]) -> Callable[[dict], object]:
    """Build a MultiServerMCPClient stub whose session() fails for named servers."""

    def factory(connections: dict) -> object:
        name = next(iter(connections))
        client = MagicMock()

        @asynccontextmanager
        async def _session(server_name: str) -> AsyncIterator[str]:
            if name in failing:
                raise RuntimeError("unreachable")
            yield f"session-{name}"

        client.session = _session
        return client

    return factory


@pytest.mark.asyncio
async def test_open_mcp_tools_empty_connections_yields_empty() -> None:
    async with open_mcp_tools({}) as tools:
        assert tools == []


@pytest.mark.asyncio
async def test_open_mcp_tools_loads_tools_from_session() -> None:
    conns = {"good": {"transport": "streamable_http", "url": "https://x/mcp/"}}

    async def _fake_load(session: object) -> list[BaseTool]:
        return [_fake_tool]

    with (
        patch(
            "mcp_integration.session.MultiServerMCPClient",
            side_effect=_client_factory_by_name(set()),
        ),
        patch("mcp_integration.session.load_mcp_tools", _fake_load),
    ):
        async with open_mcp_tools(conns) as tools:
            assert [t.name for t in tools] == ["_fake_tool"]


@pytest.mark.asyncio
async def test_open_mcp_tools_isolates_per_server_failure() -> None:
    conns = {
        "good": {"transport": "streamable_http", "url": "https://good/mcp/"},
        "bad": {"transport": "streamable_http", "url": "https://bad/mcp/"},
    }

    async def _fake_load(session: object) -> list[BaseTool]:
        return [_fake_tool]

    with (
        patch(
            "mcp_integration.session.MultiServerMCPClient",
            side_effect=_client_factory_by_name({"bad"}),
        ),
        patch("mcp_integration.session.load_mcp_tools", _fake_load),
    ):
        async with open_mcp_tools(conns) as tools:
            # 'bad' session fails to open and is skipped; 'good' still yields tools.
            assert [t.name for t in tools] == ["_fake_tool"]


@pytest.mark.asyncio
async def test_open_mcp_tools_skips_slow_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conns = {"slow": {"transport": "streamable_http", "url": "https://slow/mcp/"}}
    # Shrink the timeout so the test doesn't actually wait the real 10s.
    monkeypatch.setattr("mcp_integration.session._SESSION_OPEN_TIMEOUT_SECONDS", 0.05)

    async def _hanging_load(session: object) -> list[BaseTool]:
        await asyncio.sleep(1)  # longer than the (patched) timeout
        return [_fake_tool]

    with (
        patch(
            "mcp_integration.session.MultiServerMCPClient",
            side_effect=_client_factory_by_name(set()),
        ),
        patch("mcp_integration.session.load_mcp_tools", _hanging_load),
    ):
        # The slow server times out and is skipped rather than blocking the turn.
        async with open_mcp_tools(conns) as tools:
            assert tools == []


@pytest.mark.asyncio
async def test_open_mcp_tools_skips_server_in_failure_cooldown() -> None:
    conns = {"bad": {"transport": "streamable_http", "url": "https://bad/mcp/"}}
    factory = MagicMock(side_effect=_client_factory_by_name({"bad"}))

    async def _fake_load(session: object) -> list[BaseTool]:
        return [_fake_tool]

    with (
        patch("mcp_integration.session.MultiServerMCPClient", factory),
        patch("mcp_integration.session.load_mcp_tools", _fake_load),
    ):
        async with open_mcp_tools(conns) as tools:
            assert tools == []
        calls_after_first = factory.call_count
        # Within the cooldown window the down server is not retried.
        async with open_mcp_tools(conns) as tools:
            assert tools == []
        assert factory.call_count == calls_after_first


@pytest.mark.asyncio
async def test_open_mcp_tools_token_gated_failure_skips_cooldown() -> None:
    # A token-gated server's failure may be one user's bad token, so it must
    # not enter the shared cooldown and block other users' valid tokens.
    conns = {
        "internal": {
            "transport": "streamable_http",
            "url": "https://internal/mcp/",
            "headers": {"Authorization": "Bearer ${user_token}"},
        }
    }
    factory = MagicMock(side_effect=_client_factory_by_name({"internal"}))

    async def _fake_load(session: object) -> list[BaseTool]:
        return [_fake_tool]

    with (
        patch("mcp_integration.session.MultiServerMCPClient", factory),
        patch("mcp_integration.session.load_mcp_tools", _fake_load),
    ):
        async with open_mcp_tools(conns, user_token="bad-token") as tools:
            assert tools == []
        calls_after_first = factory.call_count
        # The next turn retries instead of finding the server in cooldown.
        async with open_mcp_tools(conns, user_token="good-token") as tools:
            assert tools == []
        assert factory.call_count == calls_after_first + 1


@pytest.mark.asyncio
async def test_open_mcp_tools_injects_user_token() -> None:
    conns = {
        "internal": {
            "transport": "streamable_http",
            "url": "https://x/mcp/",
            "headers": {"Authorization": "Bearer ${user_token}"},
        }
    }
    seen: dict[str, dict] = {}

    def factory(connections: dict) -> object:
        seen.update(connections)
        client = MagicMock()

        @asynccontextmanager
        async def _session(server_name: str) -> AsyncIterator[str]:
            yield "session"

        client.session = _session
        return client

    async def _fake_load(session: object) -> list[BaseTool]:
        return [_fake_tool]

    with (
        patch("mcp_integration.session.MultiServerMCPClient", side_effect=factory),
        patch("mcp_integration.session.load_mcp_tools", _fake_load),
    ):
        async with open_mcp_tools(conns, user_token="tok-123") as tools:
            assert [t.name for t in tools] == ["_fake_tool"]

    assert seen["internal"]["headers"] == {"Authorization": "Bearer tok-123"}


@pytest.mark.asyncio
async def test_open_mcp_tools_skips_server_requiring_token_when_missing() -> None:
    conns = {
        "internal": {
            "transport": "streamable_http",
            "url": "https://x/mcp/",
            "headers": {"Authorization": "Bearer ${user_token}"},
        }
    }

    async def _fake_load(session: object) -> list[BaseTool]:
        return [_fake_tool]

    with (
        patch(
            "mcp_integration.session.MultiServerMCPClient",
            side_effect=_client_factory_by_name(set()),
        ),
        patch("mcp_integration.session.load_mcp_tools", _fake_load),
    ):
        # No user_token supplied -> the token-gated server is skipped.
        async with open_mcp_tools(conns) as tools:
            assert tools == []


@pytest.mark.asyncio
async def test_open_mcp_tools_leaves_non_token_server_unaffected() -> None:
    conns = {"public": {"transport": "streamable_http", "url": "https://x/mcp/"}}

    async def _fake_load(session: object) -> list[BaseTool]:
        return [_fake_tool]

    with (
        patch(
            "mcp_integration.session.MultiServerMCPClient",
            side_effect=_client_factory_by_name(set()),
        ),
        patch("mcp_integration.session.load_mcp_tools", _fake_load),
    ):
        # A server that doesn't reference ${user_token} loads even without one.
        async with open_mcp_tools(conns, user_token=None) as tools:
            assert [t.name for t in tools] == ["_fake_tool"]


# --- bootstrap -------------------------------------------------------------


def test_bootstrap_disabled_yields_no_connections() -> None:
    with patch.object(
        mcp_bootstrap, "get_mcp_settings", return_value=McpSettings(enabled=False)
    ):
        mcp_bootstrap.init_mcp()
        assert mcp_bootstrap.get_mcp_connections() == {}
        mcp_bootstrap.shutdown_mcp()


def test_bootstrap_caches_connections_then_clears(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        {"mcpServers": {"svc": {"url": "https://example.com/mcp/"}}},
    )
    settings = McpSettings(enabled=True, config_path=config_path)
    try:
        with patch.object(mcp_bootstrap, "get_mcp_settings", return_value=settings):
            mcp_bootstrap.init_mcp()
            conns = mcp_bootstrap.get_mcp_connections()
            assert list(conns) == ["svc"]
            assert conns["svc"]["url"] == "https://example.com/mcp/"
    finally:
        mcp_bootstrap.shutdown_mcp()
    assert mcp_bootstrap.get_mcp_connections() == {}


def test_bootstrap_enabled_without_path_caches_empty() -> None:
    settings = McpSettings(enabled=True, config_path="")
    try:
        with patch.object(mcp_bootstrap, "get_mcp_settings", return_value=settings):
            mcp_bootstrap.init_mcp()
            assert mcp_bootstrap.get_mcp_connections() == {}
    finally:
        mcp_bootstrap.shutdown_mcp()


# --- agent collision guard -------------------------------------------------


def _named_tool(tool_name: str) -> BaseTool:
    @tool
    def _t(query: str) -> str:
        """Tool."""
        return query

    _t.name = tool_name
    return _t


def test_agent_filter_mcp_tools_drops_builtin_collisions() -> None:
    from agent.service import Agent

    existing = [_named_tool("search_documents")]
    mcp = [
        _named_tool("search_documents"),  # collides with built-in -> dropped
        _named_tool("github_create_issue"),  # unique -> kept
        _named_tool("github_create_issue"),  # duplicate MCP -> dropped
    ]

    accepted = Agent._filter_mcp_tools(mcp, existing)

    assert [t.name for t in accepted] == ["github_create_issue"]


# --- prompt augmentation ---------------------------------------------------


def test_augment_system_prompt_appends_mcp_tool_block() -> None:
    from langchain_core.messages import HumanMessage, SystemMessage

    from agent.service import Agent

    messages = [SystemMessage(content="Base persona."), HumanMessage(content="hi")]
    augmented = Agent._augment_system_prompt(
        messages, [_named_tool("browser_navigate")]
    )

    system_text = augmented[0].content
    assert "Base persona." in system_text
    assert "ADDITIONAL TOOLS AVAILABLE THIS TURN" in system_text
    assert "browser_navigate" in system_text
    # Original messages untouched; history preserved.
    assert messages[0].content == "Base persona."
    assert augmented[1] is messages[1]


def test_augment_system_prompt_noop_without_mcp_tools() -> None:
    from langchain_core.messages import SystemMessage

    from agent.service import Agent

    messages = [SystemMessage(content="Base persona.")]
    assert Agent._augment_system_prompt(messages, []) is messages
