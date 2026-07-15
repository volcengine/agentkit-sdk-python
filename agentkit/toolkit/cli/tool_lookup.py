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

"""Tool lookup helpers for CLI commands."""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from agentkit.sdk.tools import types as tools_types

console = Console()


def _field_value(source: object, *keys: str) -> object:
    for key in keys:
        if isinstance(source, dict):
            value = source.get(key)
            result = source.get("Result")
            if value is None and isinstance(result, dict):
                value = result.get(key)
        else:
            value = getattr(source, key, None)
        if value is not None:
            return value
    return None


def _string_field(source: object, *keys: str) -> str | None:
    value = _field_value(source, *keys)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _print_tool_matches(tool_name: str, matches: list[object]) -> None:
    table = Table(title=f"Multiple tools matched: {tool_name}")
    table.add_column("ToolId", style="cyan")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("ToolType")
    for item in matches:
        table.add_row(
            _string_field(item, "ToolId", "tool_id") or "",
            _string_field(item, "Name", "name") or "",
            _string_field(item, "Status", "status") or "",
            _string_field(item, "ToolType", "tool_type") or "",
        )
    console.print(table)


def resolve_tool_id_by_name(client: object, tool_name: str) -> str:
    """Resolve a tool name to one ToolId using ListTools exact-name filtering."""
    resolved_tool_name = (tool_name or "").strip()
    if not resolved_tool_name:
        raise typer.BadParameter("--tool-name cannot be empty")

    request = tools_types.ListToolsRequest(
        filters=[
            tools_types.FiltersItemForListTools(
                name="Name",
                values=[resolved_tool_name],
            )
        ],
        max_results=100,
    )
    response = client.list_tools(request)
    matches = list(response.tools or [])
    if not matches:
        raise typer.BadParameter(f"Tool not found by name: {resolved_tool_name}")
    if len(matches) > 1:
        _print_tool_matches(resolved_tool_name, matches)
        raise typer.BadParameter(
            "Multiple tools matched --tool-name. Retry with --tool-id."
        )

    resolved_tool_id = _string_field(matches[0], "ToolId", "tool_id")
    if not resolved_tool_id:
        raise typer.BadParameter(
            f"ListTools response missing ToolId for name: {resolved_tool_name}"
        )
    return resolved_tool_id


def resolve_tool_identifier(
    client: object,
    *,
    tool_id: Optional[str],
    tool_name: Optional[str],
    required: bool,
) -> str | None:
    """Resolve mutually exclusive tool identifier options to a ToolId."""
    explicit_tool_id = (tool_id or "").strip()
    explicit_tool_name = (tool_name or "").strip()

    if explicit_tool_id and explicit_tool_name:
        raise typer.BadParameter("Specify only one of --tool-id or --tool-name.")
    if not explicit_tool_id and not explicit_tool_name:
        if required:
            raise typer.BadParameter("Specify exactly one of --tool-id or --tool-name.")
        return None

    if explicit_tool_id:
        return explicit_tool_id
    return resolve_tool_id_by_name(client, explicit_tool_name)
