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

"""AgentKit CLI - Runtime commands.

Manage AgentKit Runtimes: create/get/update/delete/list/release/version/versions
"""

from typing import Optional
import json
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from agentkit.sdk.runtime.client import AgentkitRuntimeClient
from agentkit.sdk.runtime import types as rt

console = Console()

runtime_app = typer.Typer(
    name="runtime",
    help="Manage AgentKit Runtimes",
    add_completion=False,
)


@runtime_app.command("create")
def create_runtime_command(
    name: str = typer.Option(..., "--name", help="Runtime name"),
    role_name: str = typer.Option(..., "--role-name", help="IAM role name"),
    artifact_type: str = typer.Option(
        ..., "--artifact-type", help="Artifact type (e.g., DockerImage)"
    ),
    artifact_url: str = typer.Option(
        ..., "--artifact-url", help="Artifact URL (image URL)"
    ),
    description: Optional[str] = typer.Option(
        None, "--description", help="Description"
    ),
    project_name: Optional[str] = typer.Option(
        None, "--project-name", help="Project name"
    ),
    memory_id: Optional[str] = typer.Option(None, "--memory-id", help="Memory ID"),
    knowledge_id: Optional[str] = typer.Option(
        None, "--knowledge-id", help="Knowledge ID"
    ),
    tool_id: Optional[str] = typer.Option(None, "--tool-id", help="Tool ID"),
    model_agent_name: Optional[str] = typer.Option(
        None, "--model-agent-name", help="Model agent name"
    ),
    vpc_id: Optional[str] = typer.Option(None, "--vpc-id", help="VPC ID"),
    subnet_ids: Optional[str] = typer.Option(
        None, "--subnet-ids", help="Subnet IDs (comma-separated)"
    ),
    enable_private_network: bool = typer.Option(
        False, "--enable-private-network", help="Enable private network"
    ),
    enable_public_network: bool = typer.Option(
        True, "--enable-public-network", help="Enable public network"
    ),
    api_key_name: Optional[str] = typer.Option(
        None, "--apikey-name", help="API key name"
    ),
    api_key_location: Optional[str] = typer.Option(
        None, "--apikey-location", help="API key location"
    ),
    jwt_discovery_url: Optional[str] = typer.Option(
        None, "--jwt-discovery-url", help="JWT discovery URL"
    ),
    jwt_allowed_clients: Optional[str] = typer.Option(
        None, "--jwt-allowed-clients", help="JWT allowed clients (comma-separated)"
    ),
    envs_json: Optional[str] = typer.Option(
        None, "--envs-json", help="JSON array of envs [{Key,Value}]"
    ),
    tags_json: Optional[str] = typer.Option(
        None, "--tags-json", help="JSON array of tags [{Key,Value?}]"
    ),
    json_body: Optional[str] = typer.Option(
        None, "--json", help="Full JSON body for CreateRuntime"
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
    """Create a Runtime."""
    try:
        client = AgentkitRuntimeClient(region=(region or "").strip())
        if json_body:
            payload = json.loads(json_body)
            req = rt.CreateRuntimeRequest(**payload)
        else:
            authorizer = None
            if any([api_key_name, api_key_location, jwt_discovery_url]):
                authorizer = rt.AuthorizerForCreateRuntime(
                    key_auth=rt.AuthorizerKeyAuthForCreateRuntime(
                        api_key_name=api_key_name,
                        api_key_location=api_key_location,
                    )
                    if (api_key_name or api_key_location)
                    else None,
                    custom_jwt_authorizer=rt.AuthorizerCustomJwtAuthorizerForCreateRuntime(
                        discovery_url=jwt_discovery_url,
                        allowed_clients=[
                            c.strip()
                            for c in (jwt_allowed_clients or "").split(",")
                            if c.strip()
                        ]
                        or None,
                    )
                    if jwt_discovery_url
                    else None,
                )

            network = None
            if vpc_id or enable_private_network or enable_public_network:
                vpc = None
                if vpc_id:
                    subs = [
                        s.strip() for s in (subnet_ids or "").split(",") if s.strip()
                    ] or None
                    vpc = rt.NetworkVpcForCreateRuntime(vpc_id=vpc_id, subnet_ids=subs)
                network = rt.NetworkForCreateRuntime(
                    vpc_configuration=vpc,
                    enable_private_network=enable_private_network,
                    enable_public_network=enable_public_network,
                )

            envs = None
            if envs_json:
                arr = json.loads(envs_json)
                envs = [
                    rt.EnvsItemForCreateRuntime(key=e.get("Key"), value=e.get("Value"))
                    for e in arr
                ]

            tags = None
            if tags_json:
                arr = json.loads(tags_json)
                tags = [
                    rt.TagsItemForCreateRuntime(key=t.get("Key"), value=t.get("Value"))
                    for t in arr
                ]

            req = rt.CreateRuntimeRequest(
                name=name,
                role_name=role_name,
                artifact_type=artifact_type,
                artifact_url=artifact_url,
                description=description,
                project_name=project_name,
                memory_id=memory_id,
                knowledge_id=knowledge_id,
                tool_id=tool_id,
                model_agent_name=model_agent_name,
                authorizer_configuration=authorizer,
                network_configuration=network,
                envs=envs,
                tags=tags,
            )
        resp = client.create_runtime(req)
        console.print(
            Panel.fit(
                f"[green]✅ Created[/green]\nRuntimeId: {resp.runtime_id}",
                title="CreateRuntime",
                border_style="green",
            )
        )
    except Exception as e:
        console.print(f"[red]❌ Create runtime failed: {e}[/red]")
        raise typer.Exit(1)


@runtime_app.command("get")
def get_runtime_command(
    runtime_id: str = typer.Option(..., "--runtime-id", "-r", help="Runtime ID"),
    output: str = typer.Option("yaml", "--output", help="Output format: json|yaml"),
    region: Optional[str] = typer.Option(
        None,
        "--region",
        help=(
            "Region override for this command (e.g. cn-beijing, cn-shanghai). "
            "Defaults to VOLCENGINE_AGENTKIT_REGION/VOLCENGINE_REGION/global config."
        ),
    ),
):
    """Get runtime details."""
    try:
        client = AgentkitRuntimeClient(region=(region or "").strip())
        req = rt.GetRuntimeRequest(runtime_id=runtime_id)
        resp = client.get_runtime(req)
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
        console.print(f"[red]❌ Get runtime failed: {e}[/red]")
        raise typer.Exit(1)


@runtime_app.command("update")
def update_runtime_command(
    runtime_id: str = typer.Option(..., "--runtime-id", "-r", help="Runtime ID"),
    description: Optional[str] = typer.Option(
        None, "--description", help="Description"
    ),
    memory_id: Optional[str] = typer.Option(None, "--memory-id", help="Memory ID"),
    knowledge_id: Optional[str] = typer.Option(
        None, "--knowledge-id", help="Knowledge ID"
    ),
    tool_id: Optional[str] = typer.Option(None, "--tool-id", help="Tool ID"),
    envs_json: Optional[str] = typer.Option(
        None, "--envs-json", help="JSON array of envs [{Key,Value}]"
    ),
    tags_json: Optional[str] = typer.Option(
        None, "--tags-json", help="JSON array of tags [{Key,Value?}]"
    ),
    json_body: Optional[str] = typer.Option(
        None, "--json", help="Full JSON body for UpdateRuntime"
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
    """Update runtime metadata and associations."""
    try:
        client = AgentkitRuntimeClient(region=(region or "").strip())
        if json_body:
            payload = json.loads(json_body)
            req = rt.UpdateRuntimeRequest(**payload)
        else:
            envs = None
            if envs_json:
                arr = json.loads(envs_json)
                envs = [
                    rt.EnvsItemForUpdateRuntime(key=e.get("Key"), value=e.get("Value"))
                    for e in arr
                ]
            tags = None
            if tags_json:
                arr = json.loads(tags_json)
                tags = [
                    rt.TagsItemForUpdateRuntime(key=t.get("Key"), value=t.get("Value"))
                    for t in arr
                ]
            req = rt.UpdateRuntimeRequest(
                runtime_id=runtime_id,
                description=description,
                memory_id=memory_id,
                knowledge_id=knowledge_id,
                tool_id=tool_id,
                envs=envs,
                tags=tags,
            )
        resp = client.update_runtime(req)
        console.print(
            Panel.fit(
                f"[green]✅ Updated[/green]\nRuntimeId: {resp.runtime_id}",
                title="UpdateRuntime",
                border_style="green",
            )
        )
    except Exception as e:
        console.print(f"[red]❌ Update runtime failed: {e}[/red]")
        raise typer.Exit(1)


@runtime_app.command("delete")
def delete_runtime_command(
    runtime_id: str = typer.Option(..., "--runtime-id", "-r", help="Runtime ID"),
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
    """Delete runtime."""
    try:
        if not force:
            typer.confirm("Are you sure you want to delete this runtime?", abort=True)
        client = AgentkitRuntimeClient(region=(region or "").strip())
        req = rt.DeleteRuntimeRequest(runtime_id=runtime_id)
        resp = client.delete_runtime(req)
        console.print(
            Panel.fit(
                f"[green]✅ Deleted[/green]\nRuntimeId: {resp.runtime_id}",
                title="DeleteRuntime",
                border_style="green",
            )
        )
    except Exception as e:
        console.print(f"[red]❌ Delete runtime failed: {e}[/red]")
        raise typer.Exit(1)


@runtime_app.command("list")
def list_runtimes_command(
    # Basic filters
    name: Optional[str] = typer.Option(None, "--name", help="Exact name filter"),
    name_contains: Optional[str] = typer.Option(
        None, "--name-contains", help="Substring filter for name"
    ),
    # Advanced filters - supporting the full Filters API
    filter_id: Optional[str] = typer.Option(
        None, "--filter-id", help="Filter by runtime ID (exact match)"
    ),
    filter_id_contains: Optional[str] = typer.Option(
        None, "--filter-id-contains", help="Filter by runtime ID (substring)"
    ),
    filter_description: Optional[str] = typer.Option(
        None, "--filter-description", help="Filter by description (exact match)"
    ),
    filter_description_contains: Optional[str] = typer.Option(
        None, "--filter-description-contains", help="Filter by description (substring)"
    ),
    filter_status: Optional[str] = typer.Option(
        None,
        "--filter-status",
        help="Filter by status: Creating|Error|Releasing|Ready|Deleting|Deleted|Updating|UnReleased",
    ),
    filter_status_in: Optional[str] = typer.Option(
        None, "--filter-status-in", help="Filter by multiple statuses (comma-separated)"
    ),
    # Time-based filters
    create_time_after: Optional[str] = typer.Option(
        None,
        "--create-time-after",
        help="Filter runtimes created after this time (ISO format)",
    ),
    create_time_before: Optional[str] = typer.Option(
        None,
        "--create-time-before",
        help="Filter runtimes created before this time (ISO format)",
    ),
    update_time_after: Optional[str] = typer.Option(
        None,
        "--update-time-after",
        help="Filter runtimes updated after this time (ISO format)",
    ),
    update_time_before: Optional[str] = typer.Option(
        None,
        "--update-time-before",
        help="Filter runtimes updated before this time (ISO format)",
    ),
    # Project filter
    project_name: Optional[str] = typer.Option(
        None, "--project-name", help="Filter by project name"
    ),
    # Sorting options
    sort_by: Optional[str] = typer.Option(
        None, "--sort-by", help="Sort by field: Name|Status|CreatedAt|UpdatedAt"
    ),
    sort_order: Optional[str] = typer.Option(
        None, "--sort-order", help="Sort order: ASC|DESC"
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
    # Output options
    output: str = typer.Option(
        "table", "--output", help="Output format: table|json|yaml"
    ),
    fields: Optional[str] = typer.Option(
        None, "--fields", help="Comma-separated fields for table output"
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
    # Quiet mode support
    quiet: bool = typer.Option(
        False, "--quiet", "-q", help="Print only RuntimeId values"
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
    """List runtimes with advanced filtering and cursor pagination.

    Supports multiple filter types:
    - Basic: --name, --name-contains
    - Advanced: --filter-id, --filter-description, --filter-status
    - Time-based: --create-time-after, --update-time-before
    - Sorting: --sort-by, --sort-order
    """
    try:
        client = AgentkitRuntimeClient(region=(region or "").strip())

        # Build filters array according to API specification
        filters = []

        # Basic name filters (backward compatibility)
        if name:
            # Exact name matching - use Name field
            filters.append(rt.FiltersItemForListRuntimes(name="Name", values=[name]))
        if name_contains:
            # Fuzzy name matching - use NameContains field
            filters.append(
                rt.FiltersItemForListRuntimes(
                    name_contains="Name", values=[name_contains]
                )
            )

        # Advanced ID filters
        if filter_id:
            # Exact ID matching - use Name field
            filters.append(rt.FiltersItemForListRuntimes(name="Id", values=[filter_id]))
        if filter_id_contains:
            # Fuzzy ID matching - use NameContains field
            filters.append(
                rt.FiltersItemForListRuntimes(
                    name_contains="Id", values=[filter_id_contains]
                )
            )

        # Description filters
        if filter_description:
            # Exact description matching - use Name field
            filters.append(
                rt.FiltersItemForListRuntimes(
                    name="Description", values=[filter_description]
                )
            )
        if filter_description_contains:
            # Fuzzy description matching - use NameContains field
            filters.append(
                rt.FiltersItemForListRuntimes(
                    name_contains="Description", values=[filter_description_contains]
                )
            )

        # Status filters
        valid_statuses = [
            "Creating",
            "Error",
            "Releasing",
            "Ready",
            "Deleting",
            "Deleted",
            "Updating",
            "UnReleased",
        ]
        if filter_status:
            # Validate status value
            if filter_status not in valid_statuses:
                raise typer.BadParameter(
                    f"Invalid status '{filter_status}'. Valid values: {', '.join(valid_statuses)}"
                )
            # Exact status matching - use Name field
            filters.append(
                rt.FiltersItemForListRuntimes(name="Status", values=[filter_status])
            )

        if filter_status_in:
            # Multiple status values
            statuses = [s.strip() for s in filter_status_in.split(",") if s.strip()]
            invalid_statuses = [s for s in statuses if s not in valid_statuses]
            if invalid_statuses:
                raise typer.BadParameter(
                    f"Invalid statuses: {', '.join(invalid_statuses)}. Valid values: {', '.join(valid_statuses)}"
                )
            if statuses:
                # Exact status matching - use Name field with multiple values
                filters.append(
                    rt.FiltersItemForListRuntimes(name="Status", values=statuses)
                )

        # Setup console with color control
        local_console = console if not no_color else Console(no_color=True)

        # Build request with all parameters
        def build_request(next_token_val):
            request = rt.ListRuntimesRequest(
                max_results=limit,
                next_token=next_token_val,
                filters=filters if filters else None,
                project_name=project_name,
                create_time_after=create_time_after,
                create_time_before=create_time_before,
                update_time_after=update_time_after,
                update_time_before=update_time_before,
                sort_by=sort_by,
                sort_order=sort_order,
            )
            return request

        # Use unified pagination helper
        from agentkit.toolkit.cli.utils import PaginationHelper

        rts, last_next_token, batch_count = PaginationHelper.fetch_all_pages(
            request_func=client.list_runtimes,
            request_builder=build_request,
            max_results=limit,
            next_token=next_token,
            fetch_all=fetch_all,
            max_batches=max_batches,
            sleep_ms=sleep_ms,
        )

        # Handle quiet mode
        if quiet:
            for rt_item in rts:
                # Handle both dict and model object formats
                if isinstance(rt_item, dict):
                    runtime_id = rt_item.get("RuntimeId", "")
                else:
                    # Handle model objects
                    runtime_id = getattr(
                        rt_item, "runtime_id", getattr(rt_item, "RuntimeId", "")
                    )
                local_console.print(runtime_id)
            return

        # Handle JSON/YAML output
        if output.lower() in ["json", "yaml"]:
            from agentkit.toolkit.cli.utils import OutputFormatter

            meta = {
                "next_token": last_next_token,
                "has_next": bool(last_next_token),
                "batch_count": batch_count,
                "items_count": len(rts),
            }
            if output.lower() == "json":
                local_console.print(
                    OutputFormatter.format_json_output(rts, include_meta, meta)
                )
            else:
                try:
                    local_console.print(
                        OutputFormatter.format_yaml_output(rts, include_meta, meta)
                    )
                except Exception as e:
                    local_console.print(f"[red]YAML output failed: {e}[/red]")
                    raise typer.Exit(1)
            return

        # Handle table output
        from agentkit.toolkit.cli.utils import OutputFormatter, PaginationDisplayHelper

        columns = [
            ("RuntimeId", "RuntimeId", "cyan"),
            ("Name", "Name", "white"),
            ("Status", "Status", "green"),
            ("ProjectName", "ProjectName", "yellow"),
            ("UpdatedAt", "UpdatedAt", "magenta"),
        ]

        table = OutputFormatter.create_table(
            items=rts,
            columns=columns,
            title=f"Runtimes (Count: {len(rts)}, HasNext: {'Yes' if last_next_token else 'No'})",
            fields=fields,
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
        console.print(f"[red]❌ List runtimes failed: {e}[/red]")
        raise typer.Exit(1)


@runtime_app.command("release")
def release_runtime_command(
    runtime_id: str = typer.Option(..., "--runtime-id", "-r", help="Runtime ID"),
    version_number: Optional[int] = typer.Option(
        None, "--version-number", help="Version to release"
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
    """Release a runtime version (make it active)."""
    try:
        client = AgentkitRuntimeClient(region=(region or "").strip())
        req = rt.ReleaseRuntimeRequest(
            runtime_id=runtime_id, version_number=version_number
        )
        resp = client.release_runtime(req)
        console.print(
            Panel.fit(
                f"[green]✅ Released[/green]\nRuntimeId: {resp.runtime_id}",
                title="ReleaseRuntime",
                border_style="green",
            )
        )
    except Exception as e:
        console.print(f"[red]❌ Release runtime failed: {e}[/red]")
        raise typer.Exit(1)


@runtime_app.command("version")
def get_runtime_version_command(
    runtime_id: str = typer.Option(..., "--runtime-id", "-r", help="Runtime ID"),
    version_number: Optional[int] = typer.Option(
        None, "--version-number", help="Version number"
    ),
    output: str = typer.Option("yaml", "--output", help="Output format: json|yaml"),
    region: Optional[str] = typer.Option(
        None,
        "--region",
        help=(
            "Region override for this command (e.g. cn-beijing, cn-shanghai). "
            "Defaults to VOLCENGINE_AGENTKIT_REGION/VOLCENGINE_REGION/global config."
        ),
    ),
):
    """Get a specific runtime version details."""
    try:
        client = AgentkitRuntimeClient(region=(region or "").strip())
        req = rt.GetRuntimeVersionRequest(
            runtime_id=runtime_id, version_number=version_number
        )
        resp = client.get_runtime_version(req)
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
        console.print(f"[red]❌ Get runtime version failed: {e}[/red]")
        raise typer.Exit(1)


@runtime_app.command("versions")
def list_runtime_versions_command(
    runtime_id: str = typer.Option(..., "--runtime-id", "-r", help="Runtime ID"),
    page_number: Optional[int] = typer.Option(
        None, "--page-number", help="Page number"
    ),
    page_size: Optional[int] = typer.Option(None, "--page-size", help="Page size"),
    output: str = typer.Option(
        "table", "--output", help="Output format: table|json|yaml"
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
    """List runtime versions."""
    try:
        client = AgentkitRuntimeClient(region=(region or "").strip())
        req = rt.ListRuntimeVersionsRequest(
            runtime_id=runtime_id, page_number=page_number, page_size=page_size
        )
        resp = client.list_runtime_versions(req)
        versions = resp.agent_kit_runtime_versions or []
        if output.lower() == "json":
            console.print(
                json.dumps(
                    [v.model_dump(by_alias=True, exclude_none=True) for v in versions],
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return
        if output.lower() == "yaml":
            try:
                import yaml

                console.print(
                    yaml.safe_dump(
                        [
                            v.model_dump(by_alias=True, exclude_none=True)
                            for v in versions
                        ],
                        sort_keys=False,
                        allow_unicode=True,
                    )
                )
            except Exception as e:
                console.print(f"[red]YAML output failed: {e}[/red]")
                raise typer.Exit(1)
            return
        table = Table(title="Runtime Versions", show_lines=False)
        cols = [
            ("VersionNumber", "cyan"),
            ("Status", "green"),
            ("CreatedAt", "magenta"),
            ("ArtifactUrl", "blue"),
        ]
        for col, style in cols:
            table.add_column(col, style=style)
        for v in versions:
            data = v.model_dump(by_alias=True, exclude_none=True)
            table.add_row(
                str(data.get("VersionNumber", "")),
                str(data.get("Status", "")),
                str(data.get("CreatedAt", "")),
                str(data.get("ArtifactUrl", "")),
            )
        console.print(table)
    except Exception as e:
        console.print(f"[red]❌ List runtime versions failed: {e}[/red]")
        raise typer.Exit(1)
