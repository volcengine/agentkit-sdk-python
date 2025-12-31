# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
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

"""AgentKit CLI - Tools commands.

Provides commands for managing Tools and Sessions.

Mapping to SDK:
- tools: create/get/update/delete/list
- sessions: create/get/delete/list/logs/set-ttl
"""

from typing import Optional, List
import time
import json
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from agentkit.sdk.tools.client import AgentkitToolsClient
from agentkit.sdk.tools import types as tools_types

console = Console()

tools_app = typer.Typer(
    name="tools",
    help="Manage AgentKit Tools and Sessions",
    add_completion=False,
)

# Sub-group for sessions to reduce long command names
session_app = typer.Typer(
    name="session", help="Manage tool sessions", add_completion=False
)


def _print_api_error(action: str, exc: Exception, hints: Optional[List[str]] = None):
    """Pretty-print API errors by extracting server code/message when possible."""
    msg = str(exc)
    code = None
    server_message = None
    try:
        start = msg.find("{")
        end = msg.rfind("}")
        if start != -1 and end != -1 and end > start:
            payload = json.loads(msg[start : end + 1])
            metadata = payload.get("ResponseMetadata", {})
            err = metadata.get("Error", {})
            code = err.get("Code")
            server_message = err.get("Message")
    except Exception:
        pass

    lines = []
    if code:
        lines.append(f"Code: [yellow]{code}[/yellow]")
    lines.append(f"Message: [red]{server_message or msg}[/red]")
    if hints:
        lines.append("")
        lines.append("Hints:")
        for h in hints:
            lines.append(f"- {h}")

    console.print(
        Panel.fit("\n".join(lines), title=f"{action} Error", border_style="red")
    )


def _normalize_ttl_unit(value: Optional[str]) -> Optional[str]:
    """Normalize TTL unit to API-accepted values ('second' or 'minute').

    Accepts common aliases: s/sec/second/seconds -> 'second'; m/min/minute/minutes -> 'minute'.
    If None, default to 'minute' to improve UX.
    """
    if value is None or str(value).strip() == "":
        return "minute"
    raw = str(value).strip().lower()
    if raw in {"s", "sec", "second", "seconds"}:
        return "second"
    if raw in {"m", "min", "minute", "minutes"}:
        return "minute"
    raise typer.BadParameter(
        "Invalid --ttl-unit. Allowed: second|minute (aliases: s/sec/seconds, m/min/minutes)"
    )


# --------------------- Tools Commands ---------------------
@tools_app.command("create")
def create_tool_command(
    name: str = typer.Option(..., "--name", "-n", help="Tool name"),
    tool_type: str = typer.Option(..., "--tool-type", help="Tool type"),
    description: Optional[str] = typer.Option(
        None, "--description", help="Description"
    ),
    project_name: Optional[str] = typer.Option(
        None, "--project-name", help="Project name"
    ),
    role_name: Optional[str] = typer.Option(None, "--role-name", help="Role name"),
    api_key_name: Optional[str] = typer.Option(
        None, "--apikey-name", help="API key name"
    ),
    api_key_location: Optional[str] = typer.Option(
        None, "--apikey-location", help="API key location"
    ),
    api_key: Optional[str] = typer.Option(None, "--apikey", help="API key value"),
    vpc_id: Optional[str] = typer.Option(None, "--vpc-id", help="VPC ID"),
    subnet_ids: Optional[str] = typer.Option(
        None, "--subnet-ids", help="Subnet IDs (comma-separated)"
    ),
    sec_group_ids: Optional[str] = typer.Option(
        None, "--sec-group-ids", help="Security group IDs (comma-separated)"
    ),
    enable_private_network: bool = typer.Option(
        False, "--enable-private-network", help="Enable private network"
    ),
    enable_public_network: bool = typer.Option(
        True, "--enable-public-network", help="Enable public network"
    ),
    tags_json: Optional[str] = typer.Option(
        None, "--tags-json", help="JSON array of tags [{Key,Value?}]"
    ),
    tags: Optional[List[str]] = typer.Option(
        None, "--tag", help="Repeatable. Tag as 'Key=Value' or 'Key'"
    ),
    json_body: Optional[str] = typer.Option(
        None, "--json", help="Full JSON body for CreateTool"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Build request only, do not call API"
    ),
    print_json: bool = typer.Option(
        False, "--print-json", help="Print final JSON payload"
    ),
    region: Optional[str] = typer.Option(
        None,
        "--region",
        help=(
            "Region override for this command (e.g. cn-beijing, cn-shanghai). "
            "Defaults to VOLCENGINE_AGENTKIT_REGION/VOLCENGINE_REGION/global config."
        ),
    ),
):
    """Create a tool."""
    try:
        client = AgentkitToolsClient(region=(region or "").strip())

        if json_body:
            payload = json.loads(json_body)
        else:
            authorizer = None
            if any([api_key_name, api_key_location, api_key]):
                # Validate API key location
                if api_key_location and api_key_location not in {
                    "Header",
                    "Query",
                    "Body",
                }:
                    raise typer.BadParameter(
                        "Invalid --apikey-location. Allowed: Header|Query|Body"
                    )
                authorizer = tools_types.AuthorizerForCreateTool(
                    key_auth=tools_types.AuthorizerKeyAuthForCreateTool(
                        api_key_name=api_key_name,
                        api_key_location=api_key_location,
                        api_key=api_key,
                    )
                )

            network = None
            if vpc_id or enable_private_network or enable_public_network:
                if enable_private_network and not vpc_id:
                    raise typer.BadParameter(
                        "--enable-private-network requires --vpc-id"
                    )
                vpc = None
                if vpc_id:
                    subs = [
                        s.strip() for s in (subnet_ids or "").split(",") if s.strip()
                    ] or None
                    secs = [
                        s.strip() for s in (sec_group_ids or "").split(",") if s.strip()
                    ] or None
                    vpc = tools_types.NetworkVpcForCreateTool(
                        vpc_id=vpc_id,
                        subnet_ids=subs,
                        security_group_ids=secs,
                    )
                network = tools_types.NetworkForCreateTool(
                    vpc_configuration=vpc,
                    enable_private_network=enable_private_network,
                    enable_public_network=enable_public_network,
                )

            tags_list = []
            if tags_json:
                tag_items = json.loads(tags_json)
                tags_list.extend(
                    [
                        tools_types.TagsItemForCreateTool(
                            key=t.get("Key"), value=t.get("Value")
                        )
                        for t in tag_items
                    ]
                )
            if tags:
                for t in tags:
                    if "=" in t:
                        k, v = t.split("=", 1)
                        tags_list.append(
                            tools_types.TagsItemForCreateTool(
                                key=k.strip(), value=v.strip() or None
                            )
                        )
                    else:
                        tags_list.append(
                            tools_types.TagsItemForCreateTool(key=t.strip(), value=None)
                        )

            payload = tools_types.CreateToolRequest(
                name=name,
                tool_type=tool_type,
                description=description,
                project_name=project_name,
                role_name=role_name,
                authorizer_configuration=authorizer,
                network_configuration=network,
                tags=tags_list or None,
            ).model_dump(by_alias=True, exclude_none=True)

        if print_json:
            console.print(json.dumps(payload, indent=2, ensure_ascii=False))
        if dry_run:
            return

        req = tools_types.CreateToolRequest(**payload)
        resp = client.create_tool(req)
        console.print(
            Panel.fit(
                f"[green]✅ Created[/green]\nToolId: {resp.tool_id}",
                title="CreateTool",
                border_style="green",
            )
        )
    except Exception as e:
        _print_api_error("CreateTool", e)
        raise typer.Exit(1)


@tools_app.command("show")
def show_tool_command(
    tool_id: str = typer.Option(..., "--tool-id", "-t", help="Tool ID"),
    output: str = typer.Option(
        "yaml", "--output", "-o", help="Output format: json|yaml"
    ),
    quiet: bool = typer.Option(
        False, "--quiet", help="Print only ToolId when possible"
    ),
    region: Optional[str] = typer.Option(
        None,
        "--region",
        help=(
            "Region override for this command (e.g. cn-beijing, cn-shanghai). "
            "Defaults to VOLCENGINE_AGENTKIT_REGION/VOLCENGINE_REGION/global config."
        ),
    ),
):
    """Show tool details."""
    try:
        client = AgentkitToolsClient(region=(region or "").strip())
        req = tools_types.GetToolRequest(tool_id=tool_id)
        resp = client.get_tool(req)
        data = resp.model_dump(by_alias=True, exclude_none=True)
        if quiet:
            console.print(data.get("ToolId", ""))
            return
        if output.lower() == "yaml":
            try:
                import yaml

                console.print(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
            except Exception as e:
                console.print(f"[red]YAML output failed: {e}[/red]")
                raise typer.Exit(1)
        else:
            console.print(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception as e:
        _print_api_error("GetTool", e)
        raise typer.Exit(1)


@tools_app.command("update")
def update_tool_command(
    tool_id: str = typer.Option(..., "--tool-id", "-t", help="Tool ID"),
    description: Optional[str] = typer.Option(
        None, "--description", help="Description"
    ),
    json_body: Optional[str] = typer.Option(
        None, "--json", help="Full JSON body for UpdateTool"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Build request only, do not call API"
    ),
    print_json: bool = typer.Option(
        False, "--print-json", help="Print final JSON payload"
    ),
    region: Optional[str] = typer.Option(
        None,
        "--region",
        help=(
            "Region override for this command (e.g. cn-beijing, cn-shanghai). "
            "Defaults to VOLCENGINE_AGENTKIT_REGION/VOLCENGINE_REGION/global config."
        ),
    ),
):
    """Update tool description."""
    try:
        client = AgentkitToolsClient(region=(region or "").strip())
        if json_body:
            payload = json.loads(json_body)
        else:
            payload = tools_types.UpdateToolRequest(
                tool_id=tool_id, description=description
            ).model_dump(by_alias=True, exclude_none=True)

        if print_json:
            console.print(json.dumps(payload, indent=2, ensure_ascii=False))
        if dry_run:
            return

        req = tools_types.UpdateToolRequest(**payload)
        resp = client.update_tool(req)
        console.print(
            Panel.fit(
                f"[green]✅ Updated[/green]\nToolId: {resp.tool_id}",
                title="UpdateTool",
                border_style="green",
            )
        )
    except Exception as e:
        _print_api_error("UpdateTool", e)
        raise typer.Exit(1)


@tools_app.command("delete")
def delete_tool_command(
    tool_id: str = typer.Option(..., "--tool-id", "-t", help="Tool ID"),
    force: bool = typer.Option(False, "--force", help="Skip confirmation"),
    region: Optional[str] = typer.Option(
        None,
        "--region",
        help=(
            "Region override for this command (e.g. cn-beijing, cn-shanghai). "
            "Defaults to VOLCENGINE_AGENTKIT_REGION/VOLCENGINE_REGION/global config."
        ),
    ),
):
    """Delete tool."""
    try:
        if not force:
            typer.confirm("Are you sure you want to delete this tool?", abort=True)
        client = AgentkitToolsClient(region=(region or "").strip())
        req = tools_types.DeleteToolRequest(tool_id=tool_id)
        resp = client.delete_tool(req)
        console.print(
            Panel.fit(
                f"[green]✅ Deleted[/green]\nToolId: {resp.tool_id}",
                title="DeleteTool",
                border_style="green",
            )
        )
    except Exception as e:
        _print_api_error("DeleteTool", e)
        raise typer.Exit(1)


@tools_app.command("list")
def list_tools_command(
    # Exact filters
    id: Optional[str] = typer.Option(
        None, "--id", help="Exact ToolId filter (comma-separated for multiple)"
    ),
    name: Optional[str] = typer.Option(
        None, "--name", help="Exact Name filter (comma-separated for multiple)"
    ),
    description: Optional[str] = typer.Option(
        None,
        "--description",
        help="Exact Description filter (comma-separated for multiple)",
    ),
    status: Optional[str] = typer.Option(
        None,
        "--status",
        help="Exact Status filter: Creating|Error|Ready|Deleting (comma-separated)",
    ),
    # Contains filters
    id_contains: Optional[str] = typer.Option(
        None, "--id-contains", help="Substring filter for ToolId"
    ),
    name_contains: Optional[str] = typer.Option(
        None, "--name-contains", help="Substring filter for Name"
    ),
    description_contains: Optional[str] = typer.Option(
        None, "--description-contains", help="Substring filter for Description"
    ),
    status_contains: Optional[str] = typer.Option(
        None, "--status-contains", help="Substring filter for Status"
    ),
    # Cursor pagination
    limit: int = typer.Option(20, "--limit", "-l", help="Items per batch (MaxResults)"),
    next_token: Optional[str] = typer.Option(
        None, "--next-token", "-nt", help="Continue cursor (NextToken)"
    ),
    fetch_all: bool = typer.Option(
        False, "--all", help="Fetch all batches (iterate by NextToken)"
    ),
    max_batches: Optional[int] = typer.Option(
        None, "--max-batches", help="Max batches when using --all"
    ),
    sleep_ms: int = typer.Option(
        0, "--sleep-ms", help="Sleep milliseconds between batches"
    ),
    # Output controls
    output: str = typer.Option(
        "table", "--output", "-o", help="Output format: table|json|yaml"
    ),
    fields: Optional[str] = typer.Option(
        None, "--fields", "-f", help="Comma-separated fields or preset name"
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Print only ToolId values"),
    include_meta: bool = typer.Option(
        False,
        "--include-meta",
        help="Include meta (next_token, has_next, batch_count, items_count) for json/yaml output",
    ),
    print_next_token: bool = typer.Option(
        False,
        "--print-next-token",
        "-pt",
        help="Print NextToken after output (single batch only)",
    ),
    print_next_token_only: bool = typer.Option(
        False,
        "--print-next-token-only",
        "-pto",
        help="Print only NextToken (no panel, single batch only)",
    ),
    no_color: bool = typer.Option(
        False, "--no-color", "-nc", help="Disable colored output for tables/panels"
    ),
    region: Optional[str] = typer.Option(
        None,
        "--region",
        help=(
            "Region override for this command (e.g. cn-beijing, cn-shanghai). "
            "Defaults to VOLCENGINE_AGENTKIT_REGION/VOLCENGINE_REGION/global config."
        ),
    ),
):
    """List tools with exact and substring filters for Id|Name|Description|Status."""
    try:
        client = AgentkitToolsClient(region=(region or "").strip())
        allowed_status = {"Creating", "Error", "Ready", "Deleting"}

        # Use unified parameter helper
        from agentkit.toolkit.cli.utils import ParameterHelper

        filters: List[tools_types.FiltersItemForListTools] = []

        # Exact filters: when both exact and contains exist for same field, exact takes precedence
        id_vals = ParameterHelper.parse_comma_separated(id)
        name_vals = ParameterHelper.parse_comma_separated(name)
        desc_vals = ParameterHelper.parse_comma_separated(description)
        status_vals = ParameterHelper.parse_comma_separated(status)
        if status_vals:
            ParameterHelper.validate_values(status_vals, allowed_status, "--status")

        if id_vals:
            filters.append(
                tools_types.FiltersItemForListTools(name="Id", values=id_vals)
            )
        if name_vals:
            filters.append(
                tools_types.FiltersItemForListTools(name="Name", values=name_vals)
            )
        if desc_vals:
            filters.append(
                tools_types.FiltersItemForListTools(
                    name="Description", values=desc_vals
                )
            )
        if status_vals:
            filters.append(
                tools_types.FiltersItemForListTools(name="Status", values=status_vals)
            )

        # Contains filters only applied if corresponding exact not provided
        if (not id_vals) and id_contains:
            filters.append(
                tools_types.FiltersItemForListTools(
                    name_contains="Id", values=[id_contains]
                )
            )
        if (not name_vals) and name_contains:
            filters.append(
                tools_types.FiltersItemForListTools(
                    name_contains="Name", values=[name_contains]
                )
            )
        if (not desc_vals) and description_contains:
            filters.append(
                tools_types.FiltersItemForListTools(
                    name_contains="Description", values=[description_contains]
                )
            )
        if (not status_vals) and status_contains:
            filters.append(
                tools_types.FiltersItemForListTools(
                    name_contains="Status", values=[status_contains]
                )
            )

        # Setup console with color control
        local_console = console if not no_color else Console(no_color=True)

        # Use unified pagination helper
        from agentkit.toolkit.cli.utils import PaginationHelper

        tools, last_next_token, batch_count = PaginationHelper.fetch_all_pages(
            request_func=client.list_tools,
            request_builder=lambda t: tools_types.ListToolsRequest(
                max_results=limit, next_token=t, filters=filters or None
            ),
            max_results=limit,
            next_token=next_token,
            fetch_all=fetch_all,
            max_batches=max_batches,
            sleep_ms=sleep_ms,
        )

        # Handle quiet mode - similar to tools module pattern
        if quiet:
            for t in tools:
                data = t.model_dump(by_alias=True, exclude_none=True)
                local_console.print(data.get("ToolId", ""))
            if (not fetch_all) and last_next_token:
                if print_next_token_only:
                    local_console.print(last_next_token)
                elif print_next_token:
                    local_console.print(f"NextToken: {last_next_token}")
            return

        if print_next_token_only and (not fetch_all) and last_next_token:
            local_console.print(last_next_token)
            return

        # Handle JSON/YAML output
        if output.lower() in ["json", "yaml"]:
            from agentkit.toolkit.cli.utils import OutputFormatter

            meta = {
                "next_token": last_next_token,
                "has_next": bool(last_next_token),
                "batch_count": batch_count,
                "items_count": len(tools),
            }
            if output.lower() == "json":
                local_console.print(
                    OutputFormatter.format_json_output(tools, include_meta, meta)
                )
            else:
                try:
                    local_console.print(
                        OutputFormatter.format_yaml_output(tools, include_meta, meta)
                    )
                except Exception as e:
                    local_console.print(f"[red]YAML output failed: {e}[/red]")
                    raise typer.Exit(1)
            return

        # Handle table output
        from agentkit.toolkit.cli.utils import OutputFormatter, PaginationDisplayHelper

        columns = [
            ("ToolId", "ToolId", "cyan"),
            ("Name", "Name", "white"),
            ("Status", "Status", "green"),
            ("ToolType", "ToolType", "yellow"),
            ("UpdatedAt", "UpdatedAt", "magenta"),
        ]

        # Handle fields preset
        selected_fields = None
        if fields:
            if fields.strip().lower() == "core":
                selected_fields = "ToolId,Name,Status"
            else:
                selected_fields = fields

        table = OutputFormatter.create_table(
            items=tools,
            columns=columns,
            title=f"Tools (Count: {len(tools)}, HasNext: {'Yes' if last_next_token else 'No'})",
            fields=selected_fields,
        )

        local_console.print(table)

        # Show pagination info
        PaginationDisplayHelper.show_pagination_info(
            has_next=bool(last_next_token),
            next_token=last_next_token,
            print_next_token=print_next_token,
            print_next_token_only=print_next_token_only,
            quiet=quiet,
            console=local_console,
        )
    except Exception as e:
        _print_api_error("ListTools", e)
        raise typer.Exit(1)


# --------------------- Sessions Commands ---------------------
@session_app.command("create")
def create_session_command(
    tool_id: str = typer.Option(..., "--tool-id", "-t", help="Tool ID"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Session name"),
    ttl: Optional[int] = typer.Option(None, "--ttl", "-l", help="TTL value"),
    ttl_unit: Optional[str] = typer.Option(
        None, "--ttl-unit", "-u", help="TTL unit: second|minute (default: minute)"
    ),
    json_body: Optional[str] = typer.Option(
        None, "--json", help="Full JSON body for CreateSession"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Build request only, do not call API"
    ),
    print_json: bool = typer.Option(
        False, "--print-json", help="Print final JSON payload"
    ),
    region: Optional[str] = typer.Option(
        None,
        "--region",
        help=(
            "Region override for this command (e.g. cn-beijing, cn-shanghai). "
            "Defaults to VOLCENGINE_AGENTKIT_REGION/VOLCENGINE_REGION/global config."
        ),
    ),
):
    """Create a session for a tool."""
    try:
        client = AgentkitToolsClient(region=(region or "").strip())
        if json_body:
            payload = json.loads(json_body)
        else:
            normalized_unit = _normalize_ttl_unit(ttl_unit)
            payload = tools_types.CreateSessionRequest(
                tool_id=tool_id, name=name, ttl=ttl, ttl_unit=normalized_unit
            ).model_dump(by_alias=True, exclude_none=True)

        if print_json:
            console.print(json.dumps(payload, indent=2, ensure_ascii=False))
        if dry_run:
            return

        req = tools_types.CreateSessionRequest(**payload)
        resp = client.create_session(req)
        console.print(
            Panel.fit(
                f"[green]✅ Session Created[/green]\nSessionId: {resp.session_id}\nEndpoint: {resp.endpoint}",
                title="CreateSession",
                border_style="green",
            )
        )
    except Exception as e:
        _print_api_error("CreateSession", e)
        raise typer.Exit(1)


@session_app.command("show")
def get_session_command(
    tool_id: str = typer.Option(..., "--tool-id", "-t", help="Tool ID"),
    session_id: str = typer.Option(..., "--session-id", "-s", help="Session ID"),
    output: str = typer.Option(
        "yaml", "--output", "-o", help="Output format: json|yaml"
    ),
    region: Optional[str] = typer.Option(
        None,
        "--region",
        help=(
            "Region override for this command (e.g. cn-beijing, cn-shanghai). "
            "Defaults to VOLCENGINE_AGENTKIT_REGION/VOLCENGINE_REGION/global config."
        ),
    ),
):
    """Show session details."""
    try:
        client = AgentkitToolsClient(region=(region or "").strip())
        req = tools_types.GetSessionRequest(tool_id=tool_id, session_id=session_id)
        resp = client.get_session(req)
        data = resp.model_dump(by_alias=True, exclude_none=True)
        if output.lower() == "yaml":
            try:
                import yaml

                console.print(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
            except Exception as e:
                console.print(f"[red]YAML output failed: {e}[/red]")
                raise typer.Exit(1)
        else:
            console.print(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception as e:
        _print_api_error("GetSession", e)
        raise typer.Exit(1)


@session_app.command("delete")
def delete_session_command(
    session_id: str = typer.Option(..., "--session-id", "-s", help="Session ID"),
    tool_id: Optional[str] = typer.Option(
        ..., "--tool-id", "-t", help="Tool ID (optional)"
    ),
    force: bool = typer.Option(False, "--force", help="Skip confirmation"),
    region: Optional[str] = typer.Option(
        None,
        "--region",
        help=(
            "Region override for this command (e.g. cn-beijing, cn-shanghai). "
            "Defaults to VOLCENGINE_AGENTKIT_REGION/VOLCENGINE_REGION/global config."
        ),
    ),
):
    """Delete session."""
    try:
        if not force:
            typer.confirm("Are you sure you want to delete this session?", abort=True)
        client = AgentkitToolsClient(region=(region or "").strip())
        req = tools_types.DeleteSessionRequest(session_id=session_id, tool_id=tool_id)
        resp = client.delete_session(req)
        console.print(
            Panel.fit(
                f"[green]✅ Session Deleted[/green]\nSessionId: {resp.session_id}",
                title="DeleteSession",
                border_style="green",
            )
        )
    except Exception as e:
        _print_api_error("DeleteSession", e)
        raise typer.Exit(1)


@session_app.command("list")
def list_sessions_command(
    tool_id: str = typer.Option(..., "--tool-id", "-t", help="Tool ID"),
    # Exact filters
    id: Optional[str] = typer.Option(
        None, "--id", help="Exact SessionId filter (comma-separated)"
    ),
    user_session_id: Optional[str] = typer.Option(
        None, "--user-session-id", help="Exact UserSessionId filter (comma-separated)"
    ),
    status: Optional[str] = typer.Option(
        None,
        "--status",
        help="Exact Status filter: Creating|Error|Ready|Deleting (comma-separated)",
    ),
    # Contains filters
    id_contains: Optional[str] = typer.Option(
        None, "--id-contains", help="Substring filter for SessionId"
    ),
    user_session_id_contains: Optional[str] = typer.Option(
        None, "--user-session-id-contains", help="Substring filter for UserSessionId"
    ),
    status_contains: Optional[str] = typer.Option(
        None, "--status-contains", help="Substring filter for Status"
    ),
    # Cursor pagination
    limit: int = typer.Option(20, "--limit", "-l", help="Items per batch (MaxResults)"),
    next_token: Optional[str] = typer.Option(
        None, "--next-token", "-nt", help="Continue cursor (NextToken)"
    ),
    fetch_all: bool = typer.Option(
        False, "--all", help="Fetch all batches (iterate by NextToken)"
    ),
    max_batches: Optional[int] = typer.Option(
        None, "--max-batches", help="Max batches when using --all"
    ),
    sleep_ms: int = typer.Option(
        0, "--sleep-ms", help="Sleep milliseconds between batches"
    ),
    # Output controls
    output: str = typer.Option(
        "table", "--output", "-o", help="Output format: table|json|yaml"
    ),
    fields: Optional[str] = typer.Option(
        None, "--fields", "-f", help="Comma-separated fields or preset name"
    ),
    quiet: bool = typer.Option(
        False, "--quiet", "-q", help="Print only SessionId values"
    ),
    include_meta: bool = typer.Option(
        False,
        "--include-meta",
        help="Include meta (next_token, has_next, batch_count, items_count) for json/yaml output",
    ),
    print_next_token: bool = typer.Option(
        False,
        "--print-next-token",
        "-pt",
        help="Print NextToken after output (single batch only)",
    ),
    print_next_token_only: bool = typer.Option(
        False,
        "--print-next-token-only",
        "-pto",
        help="Print only NextToken (no panel, single batch only)",
    ),
    no_color: bool = typer.Option(
        False, "--no-color", "-nc", help="Disable colored output for tables/panels"
    ),
    region: Optional[str] = typer.Option(
        None,
        "--region",
        help=(
            "Region override for this command (e.g. cn-beijing, cn-shanghai). "
            "Defaults to VOLCENGINE_AGENTKIT_REGION/VOLCENGINE_REGION/global config."
        ),
    ),
):
    """List sessions with exact/substring filters and cursor pagination (limit/next-token)."""
    try:
        client = AgentkitToolsClient(region=(region or "").strip())
        allowed_status = {"Creating", "Error", "Ready", "Deleting"}

        def _parse_csv(v: Optional[str]) -> Optional[List[str]]:
            if not v:
                return None
            return [
                p.strip()
                for p in (v.split(",") if "," in v else v.split(";"))
                if p.strip()
            ]

        filters: List[tools_types.FiltersItemForListSessions] = []

        # Exact filters
        id_vals = _parse_csv(id)
        usid_vals = _parse_csv(user_session_id)
        status_vals = _parse_csv(status)
        if status_vals:
            invalid = [s for s in status_vals if s not in allowed_status]
            if invalid:
                raise typer.BadParameter(
                    f"Invalid --status values: {', '.join(invalid)}. Allowed: Creating|Error|Ready|Deleting"
                )

        if id_vals:
            filters.append(
                tools_types.FiltersItemForListSessions(name="Id", values=id_vals)
            )
        if usid_vals:
            filters.append(
                tools_types.FiltersItemForListSessions(
                    name="UserSessionId", values=usid_vals
                )
            )
        if status_vals:
            filters.append(
                tools_types.FiltersItemForListSessions(
                    name="Status", values=status_vals
                )
            )

        # Contains filters only if exact not provided
        if (not id_vals) and id_contains:
            filters.append(
                tools_types.FiltersItemForListSessions(
                    name_contains="Id", values=[id_contains]
                )
            )
        if (not usid_vals) and user_session_id_contains:
            filters.append(
                tools_types.FiltersItemForListSessions(
                    name_contains="UserSessionId", values=[user_session_id_contains]
                )
            )
        if (not status_vals) and status_contains:
            filters.append(
                tools_types.FiltersItemForListSessions(
                    name_contains="Status", values=[status_contains]
                )
            )
        # Cursor pagination loop
        collected: List[tools_types.SessionInfosForListSessions] = []
        token = next_token
        batch_count = 0
        last_next_token = ""

        while True:
            req = tools_types.ListSessionsRequest(
                tool_id=tool_id,
                max_results=limit,
                next_token=token,
                filters=filters or None,
            )
            resp = client.list_sessions(req)
            batch = resp.session_infos or []
            collected.extend(batch)
            batch_count += 1
            last_next_token = resp.next_token or ""

            if not fetch_all:
                collected = batch
                break
            if max_batches and batch_count >= max_batches:
                break
            if not last_next_token:
                break
            token = last_next_token
            if sleep_ms > 0:
                time.sleep(sleep_ms / 1000.0)

        sessions = collected
        local_console = console if not no_color else Console(no_color=True)

        if quiet:
            for s in sessions:
                data = s.model_dump(by_alias=True, exclude_none=True)
                local_console.print(data.get("SessionId", ""))
            if (not fetch_all) and last_next_token:
                if print_next_token_only:
                    local_console.print(last_next_token)
                elif print_next_token:
                    local_console.print(f"NextToken: {last_next_token}")
            return
        if output.lower() == "json":
            payload_items = [
                s.model_dump(by_alias=True, exclude_none=True) for s in sessions
            ]
            if include_meta:
                data = {
                    "meta": {
                        "next_token": last_next_token,
                        "has_next": bool(last_next_token),
                        "batch_count": batch_count,
                        "items_count": len(payload_items),
                    },
                    "items": payload_items,
                }
                local_console.print(json.dumps(data, indent=2, ensure_ascii=False))
            else:
                local_console.print(
                    json.dumps(payload_items, indent=2, ensure_ascii=False)
                )
            return
        if output.lower() == "yaml":
            try:
                import yaml

                payload_items = [
                    s.model_dump(by_alias=True, exclude_none=True) for s in sessions
                ]
                if include_meta:
                    data = {
                        "meta": {
                            "next_token": last_next_token,
                            "has_next": bool(last_next_token),
                            "batch_count": batch_count,
                            "items_count": len(payload_items),
                        },
                        "items": payload_items,
                    }
                    local_console.print(
                        yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
                    )
                else:
                    local_console.print(
                        yaml.safe_dump(
                            payload_items, sort_keys=False, allow_unicode=True
                        )
                    )
            except Exception as e:
                local_console.print(f"[red]YAML output failed: {e}[/red]")
                raise typer.Exit(1)
            return
        has_next = bool(last_next_token) and (not fetch_all)
        table = Table(
            title=f"Sessions (Count: {len(sessions)}, HasNext: {'Yes' if has_next else 'No'})",
            show_lines=False,
        )
        cols = [
            ("SessionId", "cyan"),
            ("Status", "green"),
            ("Endpoint", "blue"),
            ("ExpireAt", "magenta"),
        ]
        selected = None
        if fields:
            if fields.strip().lower() == "core":
                selected = ["SessionId", "Status"]
            else:
                selected = [f.strip() for f in fields.split(",") if f.strip()]
        for col, style in cols:
            if (selected is None) or (col in selected):
                table.add_column(col, style=style)
        for s in sessions:
            row = []
            data = s.model_dump(by_alias=True, exclude_none=True)
            for col, _style in cols:
                if (selected is None) or (col in selected):
                    row.append(str(data.get(col, "")))
            table.add_row(*row)
        local_console.print(table)
        # Concise pagination hint
        if (not fetch_all) and last_next_token:
            if print_next_token_only:
                local_console.print(last_next_token)
            elif print_next_token:
                local_console.print(
                    Panel.fit(
                        f"NextToken: {last_next_token}",
                        title="Cursor",
                        border_style="cyan",
                    )
                )
            else:
                # Show command example directly, no need to display token value again
                local_console.print(
                    f"[dim]Next page:[/dim] --next-token '{last_next_token}'"
                )
    except Exception as e:
        _print_api_error("ListSessions", e)
        raise typer.Exit(1)


@session_app.command("logs")
def session_logs_command(
    tool_id: str = typer.Option(..., "--tool-id", "-t", help="Tool ID"),
    session_id: str = typer.Option(..., "--session-id", "-s", help="Session ID"),
    limit: Optional[int] = typer.Option(None, "--limit", help="Max log lines"),
    region: Optional[str] = typer.Option(
        None,
        "--region",
        help=(
            "Region override for this command (e.g. cn-beijing, cn-shanghai). "
            "Defaults to VOLCENGINE_AGENTKIT_REGION/VOLCENGINE_REGION/global config."
        ),
    ),
):
    """Get session logs."""
    try:
        client = AgentkitToolsClient(region=(region or "").strip())
        req = tools_types.GetSessionLogsRequest(
            tool_id=tool_id, session_id=session_id, limit=limit
        )
        resp = client.get_session_logs(req)
        logs = resp.logs or ""
        console.print(Panel.fit(logs, title="Session Logs", border_style="cyan"))
    except Exception as e:
        _print_api_error("GetSessionLogs", e)
        raise typer.Exit(1)


@session_app.command("set-ttl")
def set_session_ttl_command(
    tool_id: str = typer.Option(..., "--tool-id", "-t", help="Tool ID"),
    session_id: str = typer.Option(..., "--session-id", "-s", help="Session ID"),
    ttl: int = typer.Option(..., "--ttl", "-l", help="TTL value"),
    ttl_unit: Optional[str] = typer.Option(
        None, "--ttl-unit", "-u", help="TTL unit: second|minute (default: minute)"
    ),
    region: Optional[str] = typer.Option(
        None,
        "--region",
        help=(
            "Region override for this command (e.g. cn-beijing, cn-shanghai). "
            "Defaults to VOLCENGINE_AGENTKIT_REGION/VOLCENGINE_REGION/global config."
        ),
    ),
):
    """Set session TTL."""
    try:
        client = AgentkitToolsClient(region=(region or "").strip())
        normalized_unit = _normalize_ttl_unit(ttl_unit)
        req = tools_types.SetSessionTtlRequest(
            tool_id=tool_id, session_id=session_id, ttl=ttl, ttl_unit=normalized_unit
        )
        resp = client.set_session_ttl(req)
        console.print(
            Panel.fit(
                f"[green]✅ TTL Updated[/green]\nSessionId: {resp.session_id}\nExpireAt: {resp.expire_at}",
                title="SetSessionTtl",
                border_style="green",
            )
        )
    except Exception as e:
        _print_api_error("SetSessionTtl", e)
        raise typer.Exit(1)


# Register session sub-app
tools_app.add_typer(session_app, name="session")
