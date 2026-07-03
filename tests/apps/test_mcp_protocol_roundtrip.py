# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Offline protocol-level round-trip tests for ``AgentkitMCPApp``.

Unlike ``test_mcp_app.py`` (which swaps the FastMCP server for a capturing fake
and asserts on telemetry call shapes), these tests keep the REAL ``FastMCP``
instance that ``AgentkitMCPApp`` builds and drive it through fastmcp's
in-memory transport: ``fastmcp.Client(server)`` connects directly to the server
object, so a full MCP session (initialize, tools/list, tools/call) runs with
real protocol serialization and zero network.

Contract assertions are anchored on the official ``mcp.types`` models that the
client returns (``mcp.types.Tool`` with its JSON-Schema ``inputSchema``,
content blocks from ``tools/call``), so a serialization regression in
fastmcp/mcp surfaces here even when agentkit's own wrapper code is untouched.

Covered protocol surface (fastmcp 2.12.3 / mcp 1.26.0):
  * tools/list: registered sync + async tools and the built-in env-detect tool
    are advertised with name, description, and complete input schemas derived
    from the ORIGINAL function signatures (the telemetry wrapper must stay
    transparent via functools.wraps/__wrapped__).
  * tools/call: real invocations of a sync tool, an async tool, and the
    env-detect tool, asserting both unstructured text content and structured
    output.

Tests follow this repo's convention of driving coroutines with ``asyncio.run``
from synchronous test functions (no pytest-asyncio markers).
"""

from __future__ import annotations

import asyncio

import mcp.types
import pytest
from fastmcp import Client, FastMCP

from agentkit.apps.mcp_app.mcp_app import AgentkitMCPApp


@pytest.fixture
def app() -> AgentkitMCPApp:
    """A real AgentkitMCPApp with one sync tool, one async tool, and the
    env-detect tool registered through the production decorators."""
    instance = AgentkitMCPApp()

    @instance.tool
    def add(a: int, b: int) -> int:
        """Add two integers."""
        return a + b

    @instance.tool
    async def greet(name: str) -> str:
        """Greet someone by name."""
        return f"Hello, {name}!"

    instance.add_env_detect_tool()
    return instance


def _run_session(server: FastMCP, scenario):
    """Open an in-memory MCP session against the real server and run the
    given async scenario inside it."""

    async def runner():
        async with Client(server) as client:
            return await scenario(client)

    return asyncio.run(runner())


# ---------------------------------------------------------------------------
# tools/list -- schema contract
# ---------------------------------------------------------------------------


def test_tools_list_advertises_all_registered_tools(app):
    tools = _run_session(app._mcp_server, lambda client: client.list_tools())

    # Contract: the client hands back official mcp.types.Tool models.
    assert all(isinstance(tool, mcp.types.Tool) for tool in tools)
    assert {tool.name for tool in tools} == {"add", "greet", "get_env"}


def test_tools_list_exposes_complete_input_schema_for_sync_tool(app):
    tools = _run_session(app._mcp_server, lambda client: client.list_tools())
    add_tool = next(tool for tool in tools if tool.name == "add")

    assert add_tool.description == "Add two integers."
    # The schema must reflect the ORIGINAL signature, not the (*args, **kwargs)
    # telemetry wrapper -- this pins that @wraps keeps the wrapper transparent
    # to FastMCP's schema derivation.
    schema = add_tool.inputSchema
    assert schema["type"] == "object"
    assert set(schema["required"]) == {"a", "b"}
    assert schema["properties"]["a"]["type"] == "integer"
    assert schema["properties"]["b"]["type"] == "integer"


def test_tools_list_exposes_complete_input_schema_for_async_tool(app):
    tools = _run_session(app._mcp_server, lambda client: client.list_tools())
    greet_tool = next(tool for tool in tools if tool.name == "greet")

    assert greet_tool.description == "Greet someone by name."
    schema = greet_tool.inputSchema
    assert schema["type"] == "object"
    assert schema["required"] == ["name"]
    assert schema["properties"]["name"]["type"] == "string"


# ---------------------------------------------------------------------------
# tools/call -- real invocations through the protocol
# ---------------------------------------------------------------------------


def test_tools_call_sync_tool_returns_text_and_structured_content(app):
    result = _run_session(
        app._mcp_server,
        lambda client: client.call_tool("add", {"a": 2, "b": 3}),
    )

    assert result.is_error is False
    # Contract: unstructured content is a list of official content blocks.
    assert isinstance(result.content[0], mcp.types.TextContent)
    assert result.content[0].text == "5"
    # Contract: fastmcp also returns structured output for typed returns.
    assert result.structured_content == {"result": 5}
    assert result.data == 5


def test_tools_call_async_tool_executes_and_returns_content(app):
    result = _run_session(
        app._mcp_server,
        lambda client: client.call_tool("greet", {"name": "world"}),
    )

    assert result.is_error is False
    assert isinstance(result.content[0], mcp.types.TextContent)
    assert result.content[0].text == "Hello, world!"
    assert result.data == "Hello, world!"


def test_tools_call_env_detect_tool_reports_runtime_over_the_protocol(
    app, monkeypatch
):
    monkeypatch.setenv("RUNTIME_IAM_ROLE_TRN", "trn:some:role")

    result = _run_session(
        app._mcp_server,
        lambda client: client.call_tool("get_env", {}),
    )

    assert result.is_error is False
    assert result.data == {"env": "agentkit"}
