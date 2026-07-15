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

"""Delete command for sandbox CLI."""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agentkit.sdk.tools import types as tools_types
from agentkit.toolkit.cli.sandbox.agentkit_client import AgentkitToolsClient
from agentkit.toolkit.cli.sandbox.sandbox_client import delete_session_result, error
from agentkit.toolkit.cli.sandbox.session_create import SANDBOX_TOOL_ID_ENV

console = Console()

TOOL_INFO_FIELDS = (
    ("ToolId", "tool_id"),
    ("Name", "name"),
    ("Status", "status"),
    ("ToolType", "tool_type"),
    ("CreatedAt", "created_at"),
    ("UpdatedAt", "updated_at"),
    ("ImageUrl", "image_url"),
    ("Description", "description"),
)

SESSION_INFO_FIELDS = (
    ("UserSessionId", "user_session_id"),
    ("SessionId", "session_id"),
    ("Status", "status"),
    ("Endpoint", "endpoint"),
    ("CreatedAt", "created_at"),
    ("ExpireAt", "expire_at"),
)


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


def _model_dump(source: object) -> dict[str, object]:
    if isinstance(source, dict):
        return source
    dump = getattr(source, "model_dump", None)
    if callable(dump):
        return dump(by_alias=True, exclude_none=True)
    result: dict[str, object] = {}
    for key, value in vars(source).items():
        if value is not None:
            result[key] = value
    return result


def _print_details(
    title: str,
    fields: tuple[tuple[str, str], ...],
    source: object,
) -> None:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="cyan", no_wrap=True)
    table.add_column()

    has_rows = False
    for alias, attr in fields:
        value = _field_value(source, alias, attr)
        if value is None or value == "":
            continue
        table.add_row(alias, str(value))
        has_rows = True

    if not has_rows:
        table.add_row("Details", str(_model_dump(source)))

    console.print(Panel.fit(table, title=title, border_style="yellow"))


def _is_not_found_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "not found" in message
        or "not exist" in message
        or "does not exist" in message
        or "不存在" in str(exc)
    )


def _get_tool(client: AgentkitToolsClient, tool_id: str) -> object:
    try:
        tool = client.get_tool(tools_types.GetToolRequest(tool_id=tool_id))
    except Exception as exc:
        if _is_not_found_error(exc):
            error(f"Sandbox tool not found: {tool_id}")
        error(f"Failed to get sandbox tool {tool_id}: {exc}")

    resolved_tool_id = _string_field(tool, "ToolId", "tool_id")
    if not resolved_tool_id:
        error(f"GetTool response missing ToolId: {tool_id}")
    return tool


def _list_tools_by_name(client: AgentkitToolsClient, tool_name: str) -> list[object]:
    request = tools_types.ListToolsRequest(
        filters=[
            tools_types.FiltersItemForListTools(
                name="Name",
                values=[tool_name],
            )
        ],
        max_results=100,
    )
    try:
        response = client.list_tools(request)
    except Exception as exc:
        error(f"Failed to list sandbox tools by name {tool_name}: {exc}")
    return list(response.tools or [])


def _resolve_tool(
    client: AgentkitToolsClient,
    *,
    tool_id: Optional[str],
    tool_name: Optional[str],
) -> tuple[str, object]:
    explicit_tool_id = (tool_id or "").strip()
    explicit_tool_name = (tool_name or "").strip()

    if bool(explicit_tool_id) == bool(explicit_tool_name):
        error("Specify exactly one of --tool-id or --tool-name.")

    if explicit_tool_id:
        tool = _get_tool(client, explicit_tool_id)
        return explicit_tool_id, tool

    matches = _list_tools_by_name(client, explicit_tool_name)
    if not matches:
        error(f"Sandbox tool not found by name: {explicit_tool_name}")
    if len(matches) > 1:
        table = Table(title=f"Multiple sandbox tools matched: {explicit_tool_name}")
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
        error("Multiple sandbox tools matched --tool-name. Retry with --tool-id.")

    resolved_tool_id = _string_field(matches[0], "ToolId", "tool_id")
    if not resolved_tool_id:
        error(f"ListTools response missing ToolId for name: {explicit_tool_name}")
    tool = _get_tool(client, resolved_tool_id)
    return resolved_tool_id, tool


def _resolve_tool_id(
    client: AgentkitToolsClient,
    *,
    tool_id: Optional[str],
    tool_name: Optional[str],
) -> str:
    explicit_tool_id = (tool_id or "").strip()
    explicit_tool_name = (tool_name or "").strip()

    if bool(explicit_tool_id) == bool(explicit_tool_name):
        error("Specify exactly one of --tool-id or --tool-name.")

    if explicit_tool_id:
        return explicit_tool_id

    resolved_tool_id, _tool = _resolve_tool(
        client,
        tool_id=None,
        tool_name=explicit_tool_name,
    )
    return resolved_tool_id


def _list_sessions_by_user_session_id(
    client: AgentkitToolsClient,
    *,
    tool_id: str,
    session_id: str,
) -> list[object]:
    request = tools_types.ListSessionsRequest(
        tool_id=tool_id,
        filters=[
            tools_types.FiltersItemForListSessions(
                name="UserSessionId",
                values=[session_id],
            )
        ],
        max_results=100,
    )
    try:
        response = client.list_sessions(request)
    except Exception as exc:
        error(f"Failed to list sandbox sessions for {session_id}: {exc}")
    return list(response.session_infos or [])


def _resolve_session_instance(
    client: AgentkitToolsClient,
    *,
    tool_id: str,
    session_id: str,
) -> tuple[str, object]:
    sessions = _list_sessions_by_user_session_id(
        client,
        tool_id=tool_id,
        session_id=session_id,
    )
    if not sessions:
        error(f"Sandbox session not found: {session_id} under tool {tool_id}")
    if len(sessions) > 1:
        table = Table(title=f"Multiple sandbox sessions matched: {session_id}")
        table.add_column("UserSessionId", style="cyan")
        table.add_column("SessionId")
        table.add_column("Status")
        table.add_column("Endpoint")
        for item in sessions:
            table.add_row(
                _string_field(item, "UserSessionId", "user_session_id") or "",
                _string_field(item, "SessionId", "session_id") or "",
                _string_field(item, "Status", "status") or "",
                _string_field(item, "Endpoint", "endpoint") or "",
            )
        console.print(table)
        error("Multiple sandbox sessions matched --session-id. Cannot delete safely.")

    instance_id = _string_field(sessions[0], "SessionId", "session_id")
    if not instance_id:
        error(f"ListSessions response missing instance SessionId for: {session_id}")
    return instance_id, sessions[0]


def _confirm(message: str, force: bool) -> None:
    if force:
        return
    typer.confirm(message, abort=True)


def _delete_tool(
    client: AgentkitToolsClient,
    *,
    tool_id: str,
    tool: object,
    force: bool,
) -> None:
    _print_details("Sandbox Tool To Delete", TOOL_INFO_FIELDS, tool)
    _confirm("Delete this sandbox tool?", force)
    try:
        response = client.delete_tool(tools_types.DeleteToolRequest(tool_id=tool_id))
    except Exception as exc:
        if _is_not_found_error(exc):
            error(f"Sandbox tool not found: {tool_id}")
        error(f"Failed to delete sandbox tool {tool_id}: {exc}")

    deleted_tool_id = _string_field(response, "ToolId", "tool_id") or tool_id
    console.print(
        Panel.fit(
            f"[green]Deleted[/green]\nToolId: {deleted_tool_id}",
            title="DeleteTool",
            border_style="green",
        )
    )


def _delete_session(
    client: AgentkitToolsClient,
    *,
    tool_id: str,
    session_id: str,
    force: bool,
) -> None:
    instance_id, session = _resolve_session_instance(
        client,
        tool_id=tool_id,
        session_id=session_id,
    )
    _print_details("Sandbox Session To Delete", SESSION_INFO_FIELDS, session)
    _confirm("Delete this sandbox session?", force)
    try:
        response = client.delete_session(
            tools_types.DeleteSessionRequest(
                session_id=instance_id,
                tool_id=tool_id,
            )
        )
    except Exception as exc:
        if _is_not_found_error(exc):
            error(f"Sandbox session not found: {session_id} under tool {tool_id}")
        error(f"Failed to delete sandbox session {session_id}: {exc}")

    delete_session_result(tool_id, session_id)
    deleted_instance_id = (
        _string_field(response, "SessionId", "session_id") or instance_id
    )
    console.print(
        Panel.fit(
            "[green]Deleted[/green]\n"
            f"SessionId: {session_id}\n"
            f"InstanceId: {deleted_instance_id}",
            title="DeleteSession",
            border_style="green",
        )
    )


def delete_command(
    tool_id: Optional[str] = typer.Option(
        None,
        "--tool-id",
        help=(
            "Sandbox tool ID. Required unless --tool-name is provided. "
            f"Defaults do not apply; set {SANDBOX_TOOL_ID_ENV} explicitly "
            "with --tool-id if needed."
        ),
    ),
    tool_name: Optional[str] = typer.Option(
        None,
        "--tool-name",
        help="Sandbox tool name. Resolved with ListTools(Name=...) before deletion.",
    ),
    session_id: Optional[str] = typer.Option(
        None,
        "--session-id",
        "--sid",
        "-s",
        help=(
            "Sandbox user session ID. When provided, delete this session "
            "instead of the tool."
        ),
    ),
    force: bool = typer.Option(False, "--force", help="Skip confirmation prompt."),
) -> None:
    """Delete a sandbox tool or one sandbox session after showing target details."""
    client = AgentkitToolsClient()
    resolved_session_id = (session_id or "").strip()
    if resolved_session_id:
        resolved_tool_id = _resolve_tool_id(
            client,
            tool_id=tool_id,
            tool_name=tool_name,
        )
        _delete_session(
            client,
            tool_id=resolved_tool_id,
            session_id=resolved_session_id,
            force=force,
        )
        return

    resolved_tool_id, tool = _resolve_tool(
        client,
        tool_id=tool_id,
        tool_name=tool_name,
    )
    _delete_tool(
        client,
        tool_id=resolved_tool_id,
        tool=tool,
        force=force,
    )
