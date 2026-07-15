from __future__ import annotations

import pytest
import typer

from agentkit.toolkit.cli.tool_lookup import resolve_tool_identifier


class _FakeTool:
    def __init__(
        self,
        tool_id: str | None,
        name: str = "demo-tool",
        status: str = "Ready",
        tool_type: str = "CodeEnv",
    ):
        self.tool_id = tool_id
        self.name = name
        self.status = status
        self.tool_type = tool_type


class _FakeListToolsResponse:
    def __init__(self, tools=None):
        self.tools = [] if tools is None else tools


class _FakeToolsClient:
    def __init__(self, tools=None):
        self.response = _FakeListToolsResponse(tools)
        self.last_request = None

    def list_tools(self, request):
        self.last_request = request
        return self.response


def test_resolve_tool_identifier_trusts_explicit_tool_id() -> None:
    client = _FakeToolsClient()

    assert (
        resolve_tool_identifier(
            client,
            tool_id="tool-1",
            tool_name=None,
            required=True,
        )
        == "tool-1"
    )
    assert client.last_request is None


def test_resolve_tool_identifier_by_name() -> None:
    client = _FakeToolsClient([_FakeTool("tool-from-name", name="demo-tool")])

    assert (
        resolve_tool_identifier(
            client,
            tool_id=None,
            tool_name="demo-tool",
            required=True,
        )
        == "tool-from-name"
    )
    assert [(item.name, item.values) for item in client.last_request.filters] == [
        ("Name", ["demo-tool"])
    ]


def test_resolve_tool_identifier_rejects_id_and_name() -> None:
    with pytest.raises(typer.BadParameter, match="Specify only one"):
        resolve_tool_identifier(
            _FakeToolsClient(),
            tool_id="tool-1",
            tool_name="demo-tool",
            required=True,
        )


def test_resolve_tool_identifier_optional_empty_returns_none() -> None:
    assert (
        resolve_tool_identifier(
            _FakeToolsClient(),
            tool_id=None,
            tool_name=None,
            required=False,
        )
        is None
    )
