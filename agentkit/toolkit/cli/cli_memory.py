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

"""AgentKit CLI - Memory commands.

Mapping to SDK:
- create -> CreateMemoryCollection
- add    -> AddMemoryCollection
- list   -> ListMemoryCollections
- show   -> GetMemoryCollection
- update -> UpdateMemoryCollection
- delete -> DeleteMemoryCollection
- conn   -> GetMemoryConnectionInfo
"""

from typing import Optional, List, Any
import json
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from agentkit.sdk.memory.client import AgentkitMemoryClient
from agentkit.sdk.memory import types as memory_types

console = Console()

memory_app = typer.Typer(
    name="memory",
    help="Manage AgentKit Memory collections",
    add_completion=False,
)


# ---- ProviderType normalization and validation ----
ALLOWED_PROVIDER_TYPES = {"MEM0", "VIKINGDB_MEMORY"}
PROVIDER_TYPE_ALIASES = {
    "mem0": "MEM0",
    "MEM0": "MEM0",
    "vikingdb": "VIKINGDB_MEMORY",
    "vikingdb_memory": "VIKINGDB_MEMORY",
    "vikingdb-memory": "VIKINGDB_MEMORY",
    "VIKINGDB_MEMORY": "VIKINGDB_MEMORY",
}


def _normalize_provider_type(value: Optional[str]) -> str:
    """Normalize provider type to canonical enum, defaulting to MEM0.

    Accepts case-insensitive aliases and raises a helpful error on invalid values.
    """
    if not value:
        return "MEM0"
    raw = value.strip()
    if raw in ALLOWED_PROVIDER_TYPES:
        return raw
    # alias lookup by case-insensitive
    alias_key = raw.lower()
    if alias_key in PROVIDER_TYPE_ALIASES:
        return PROVIDER_TYPE_ALIASES[alias_key]
    # try upper-case direct
    upper = raw.upper()
    if upper in ALLOWED_PROVIDER_TYPES:
        return upper
    raise typer.BadParameter(
        f"Invalid --provider-type '{value}'. Allowed: MEM0, VIKINGDB_MEMORY. "
        "Examples: --provider-type MEM0 | --provider-type vikingdb"
    )


def _validate_collection_name(name: Optional[str]):
    """Validate memory collection name: 1-48 chars, [A-Za-z0-9_]."""
    if not name:
        raise typer.BadParameter("--name is required")
    import re

    if not re.fullmatch(r"[A-Za-z0-9_]{1,48}", name):
        raise typer.BadParameter(
            "Invalid --name. Only a-z, A-Z, 0-9, '_' are allowed, max length 48."
        )


def _parse_json_list_str(value: Optional[str]) -> Optional[List[Any]]:
    if not value:
        return None
    if isinstance(value, list):
        return value
    try:
        return json.loads(value)
    except Exception as e:
        raise typer.BadParameter(f"Invalid JSON list: {e}")


def _parse_csv(value: Optional[str]) -> Optional[List[str]]:
    """Use unified parameter helper for CSV parsing"""
    from agentkit.toolkit.cli.utils import ParameterHelper

    return ParameterHelper.parse_comma_separated(value)


def _print_api_error(action: str, exc: Exception, hints: Optional[List[str]] = None):
    """Pretty-print API errors by extracting server code/message when possible."""
    msg = str(exc)
    code = None
    server_message = None
    # Try to extract JSON payload from exception text
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
    if server_message:
        lines.append(f"Message: [red]{server_message}[/red]")
    else:
        lines.append(f"Message: [red]{msg}[/red]")
    if hints:
        lines.append("")
        lines.append("Hints:")
        for h in hints:
            lines.append(f"- {h}")

    console.print(
        Panel.fit(
            "\n".join(lines),
            title=f"{action} Error",
            border_style="red",
        )
    )


@memory_app.command("create")
def create_command(
    name: str = typer.Option(
        ..., "--name", help="Collection name: [A-Za-z0-9_], max 48"
    ),
    description: Optional[str] = typer.Option(
        None, "--description", help="Description"
    ),
    project_name: Optional[str] = typer.Option(
        None, "--project-name", help="Project name"
    ),
    provider_type: Optional[str] = typer.Option(
        None,
        "--provider-type",
        help="Provider type: MEM0 | VIKINGDB_MEMORY (default: MEM0)",
    ),
    vpc_id: Optional[str] = typer.Option(None, "--vpc-id", help="VPC ID"),
    subnet_ids: Optional[str] = typer.Option(
        None, "--subnet-ids", help="Subnet IDs (comma-separated)"
    ),
    strategies_json: Optional[str] = typer.Option(
        None,
        "--strategies-json",
        help=(
            "JSON array of strategies (max 5), items: "
            "[{Type,Name,CustomExtractionInstructions?}], Type in: Summary|Semantic|UserPreference"
        ),
    ),
    strategies: Optional[List[str]] = typer.Option(
        None,
        "--strategy",
        help=(
            "Repeatable. Add strategy as 'Type:Name[:CustomExtractionInstructions]', "
            "Type in: Summary|Semantic|UserPreference (max 5)"
        ),
    ),
    tags_json: Optional[str] = typer.Option(
        None, "--tags-json", help="JSON array of tags [{Key,Value?}]"
    ),
    json_body: Optional[str] = typer.Option(
        None, "--json", help="Full JSON body for CreateMemoryCollection"
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
    """Create a managed memory collection."""
    try:
        client = AgentkitMemoryClient(region=(region or "").strip())

        if json_body:
            payload = json.loads(json_body)
            # Overlay CLI-provided provider_type and normalize/validate
            if provider_type is not None:
                payload["ProviderType"] = provider_type
            # Default and normalize if missing or alias
            payload["ProviderType"] = _normalize_provider_type(
                payload.get("ProviderType")
            )
            # Validate name and add default strategies if missing
            _validate_collection_name(payload.get("Name"))
            lt_cfg = payload.get("LongTermConfiguration") or {}
            strategies = lt_cfg.get("Strategies")
            if not strategies or (
                isinstance(strategies, list) and len(strategies) == 0
            ):
                payload["LongTermConfiguration"] = {
                    "Strategies": [
                        {
                            "Type": "Summary",
                            "Name": "agentkit_summary_default",
                        }
                    ]
                }
            req = memory_types.CreateMemoryCollectionRequest(**payload)
        else:
            _validate_collection_name(name)
            long_term = None
            if strategies_json:
                arr = json.loads(strategies_json)
                strategies = [
                    memory_types.LongTermStrategiesItemForCreateMemoryCollection(
                        name=item.get("Name"),
                        type=item.get("Type"),
                        custom_extraction_instructions=item.get(
                            "CustomExtractionInstructions"
                        ),
                    )
                    for item in arr
                ]
                if len(strategies) > 5:
                    raise typer.BadParameter("At most 5 strategies are allowed")
                # normalize types
                for st in strategies:
                    if st.type:
                        st.type = st.type.strip()
                long_term = memory_types.LongTermForCreateMemoryCollection(
                    strategies=strategies
                )
            elif strategies:
                # parse --strategy entries Type:Name[:CustomExtractionInstructions]
                parsed = []
                for s in strategies:
                    parts = [p.strip() for p in s.split(":", 2)]
                    if len(parts) < 2:
                        raise typer.BadParameter(
                            "Invalid --strategy format. Use 'Type:Name[:CustomExtractionInstructions]'"
                        )
                    type_val = parts[0]
                    name_val = parts[1]
                    custom = parts[2] if len(parts) == 3 else None
                    if type_val.lower() in (
                        "summary",
                        "semantic",
                        "userpreference",
                        "user_preference",
                    ):
                        # normalize
                        type_norm = (
                            "Summary"
                            if type_val.lower() == "summary"
                            else "Semantic"
                            if type_val.lower() == "semantic"
                            else "UserPreference"
                        )
                    else:
                        raise typer.BadParameter(
                            "Invalid strategy Type. Allowed: Summary, Semantic, UserPreference"
                        )
                    if not name_val:
                        raise typer.BadParameter("Strategy Name is required")
                    parsed.append(
                        memory_types.LongTermStrategiesItemForCreateMemoryCollection(
                            name=name_val,
                            type=type_norm,
                            custom_extraction_instructions=custom,
                        )
                    )
                if len(parsed) > 5:
                    raise typer.BadParameter("At most 5 strategies are allowed")
                long_term = memory_types.LongTermForCreateMemoryCollection(
                    strategies=parsed
                )
            else:
                # Provide a safe default strategy to satisfy server requirements
                long_term = memory_types.LongTermForCreateMemoryCollection(
                    strategies=[
                        memory_types.LongTermStrategiesItemForCreateMemoryCollection(
                            name="agentkit_summary_default",
                            type="Summary",
                        )
                    ]
                )

            vpc = None
            if vpc_id:
                vpc = memory_types.VpcForCreateMemoryCollection(
                    vpc_id=vpc_id,
                    subnet_ids=_parse_csv(subnet_ids) or None,
                )

            tags = None
            if tags_json:
                tag_items = json.loads(tags_json)
                tags = [
                    memory_types.TagsItemForCreateMemoryCollection(
                        key=t.get("Key"), value=t.get("Value")
                    )
                    for t in tag_items
                ]

            req = memory_types.CreateMemoryCollectionRequest(
                name=name,
                description=description,
                project_name=project_name,
                provider_type=_normalize_provider_type(provider_type),
                long_term_configuration=long_term,
                vpc_config=vpc,
                tags=tags,
            )

        resp = client.create_memory_collection(req)
        console.print(
            Panel.fit(
                f"[green]✅ Created[/green]\nMemoryId: {resp.memory_id}\nStatus: {resp.status}",
                title="CreateMemoryCollection",
                border_style="green",
            )
        )
    except Exception as e:
        console.print(f"[red]❌ Create failed: {e}[/red]")
        raise typer.Exit(1)


@memory_app.command("add")
def add_command(
    provider_collection_id: Optional[str] = typer.Option(
        None, "--provider-collection-id", help="External provider collection ID"
    ),
    provider_type: Optional[str] = typer.Option(
        None,
        "--provider-type",
        help="Provider type: MEM0 | VIKINGDB_MEMORY (required unless --collections-json)",
    ),
    name: Optional[str] = typer.Option(None, "--name", help="Collection name"),
    description: Optional[str] = typer.Option(
        None, "--description", help="Description"
    ),
    project_name: Optional[str] = typer.Option(
        None, "--project-name", help="Project name"
    ),
    collections_json: Optional[str] = typer.Option(
        None, "--collections-json", help="JSON array of collections to add"
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
    """Add external provider collections."""
    try:
        client = AgentkitMemoryClient(region=(region or "").strip())

        items: List[memory_types.CollectionsItemForAddMemoryCollection] = []
        if collections_json:
            arr = json.loads(collections_json)
            for item in arr:
                if not item.get("ProviderType"):
                    raise typer.BadParameter(
                        "Each collection must include 'ProviderType' when using --collections-json"
                    )
                items.append(
                    memory_types.CollectionsItemForAddMemoryCollection(
                        provider_collection_id=item.get("ProviderCollectionId"),
                        provider_type=_normalize_provider_type(
                            item.get("ProviderType")
                        ),
                        name=item.get("Name"),
                        description=item.get("Description"),
                        project_name=item.get("ProjectName"),
                    )
                )
        else:
            if not provider_collection_id:
                raise typer.BadParameter(
                    "--provider-collection-id is required when --collections-json is not provided"
                )
            if provider_type is None:
                raise typer.BadParameter(
                    "--provider-type is required when --collections-json is not provided. "
                    "Allowed: MEM0, VIKINGDB_MEMORY"
                )
            items.append(
                memory_types.CollectionsItemForAddMemoryCollection(
                    provider_collection_id=provider_collection_id,
                    provider_type=_normalize_provider_type(provider_type),
                    name=name,
                    description=description,
                    project_name=project_name,
                )
            )

        req = memory_types.AddMemoryCollectionRequest(collections=items)
        resp = client.add_memory_collection(req)
        console.print(
            Panel.fit(
                f"[green]✅ Added[/green]\nCollections: {len(resp.collections or [])}",
                title="AddMemoryCollection",
                border_style="green",
            )
        )
    except Exception as e:
        console.print(f"[red]❌ Add failed: {e}[/red]")
        raise typer.Exit(1)


@memory_app.command("provider-types")
def provider_types_command():
    """List allowed ProviderType values and common aliases."""
    try:
        table = Table(title="Allowed Provider Types")
        table.add_column("Value", style="cyan")
        table.add_column("Aliases", style="magenta")
        table.add_row("MEM0", "mem0")
        table.add_row("VIKINGDB_MEMORY", "vikingdb, vikingdb_memory, vikingdb-memory")
        console.print(table)
        console.print(
            "Default for create is [bold]MEM0[/bold]. Use --provider-type to override."
        )
    except Exception as e:
        console.print(f"[red]Failed to list provider types: {e}[/red]")
        raise typer.Exit(1)


@memory_app.command("list")
def list_command(
    name: Optional[str] = typer.Option(None, "--name", help="Exact name filter"),
    name_contains: Optional[str] = typer.Option(
        None, "--name-contains", help="Substring filter for name"
    ),
    collection_id: Optional[str] = typer.Option(
        None, "--id", help="Exact filter by collection_id"
    ),
    collection_id_contains: Optional[str] = typer.Option(
        None, "--id-contains", help="Substring filter for collection_id"
    ),
    description: Optional[str] = typer.Option(
        None, "--description", help="Exact description filter"
    ),
    description_contains: Optional[str] = typer.Option(
        None, "--description-contains", help="Substring filter for description"
    ),
    status: Optional[str] = typer.Option(
        None,
        "--status",
        help=(
            "Exact status filter: Creating|CreateFailed|Ready|Deleting|DeleteFailed|Deleted|Error"
        ),
    ),
    provider_type: Optional[str] = typer.Option(
        None, "--provider-type", help="Exact provider type: MEM0|VIKINGDB_MEMORY"
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
    quiet: bool = typer.Option(
        False, "--quiet", "-q", help="Print only MemoryId values"
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
    """List memory collections with cursor pagination (limit/next-token)."""
    try:
        client = AgentkitMemoryClient(region=(region or "").strip())

        filters: List[memory_types.FiltersItemForListMemoryCollections] = []

        # Build filters according to API: Filters.N.Name / NameContains and Values
        if collection_id:
            filters.append(
                memory_types.FiltersItemForListMemoryCollections(
                    name="collection_id", values=[collection_id]
                )
            )
        if collection_id_contains and not collection_id:
            filters.append(
                memory_types.FiltersItemForListMemoryCollections(
                    name_contains="collection_id", values=[collection_id_contains]
                )
            )
        if name:
            filters.append(
                memory_types.FiltersItemForListMemoryCollections(
                    name="name", values=[name]
                )
            )
        if name_contains and not name:
            filters.append(
                memory_types.FiltersItemForListMemoryCollections(
                    name_contains="name", values=[name_contains]
                )
            )
        if description:
            filters.append(
                memory_types.FiltersItemForListMemoryCollections(
                    name="description", values=[description]
                )
            )
        if description_contains and not description:
            filters.append(
                memory_types.FiltersItemForListMemoryCollections(
                    name_contains="description", values=[description_contains]
                )
            )
        if status:
            filters.append(
                memory_types.FiltersItemForListMemoryCollections(
                    name="status", values=[status]
                )
            )
        if provider_type:
            filters.append(
                memory_types.FiltersItemForListMemoryCollections(
                    name="provider_type",
                    values=[_normalize_provider_type(provider_type)],
                )
            )

        # Setup console with color control
        local_console = console if not no_color else Console(no_color=True)

        # Use unified pagination helper
        from agentkit.toolkit.cli.utils import PaginationHelper

        memories, last_next_token, batch_count = PaginationHelper.fetch_all_pages(
            request_func=client.list_memory_collections,
            request_builder=lambda t: memory_types.ListMemoryCollectionsRequest(
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
            for m in memories:
                data = m.model_dump(by_alias=True, exclude_none=True)
                local_console.print(data.get("MemoryId", ""))
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
                "items_count": len(memories),
            }
            if output.lower() == "json":
                local_console.print(
                    OutputFormatter.format_json_output(memories, include_meta, meta)
                )
            else:
                try:
                    local_console.print(
                        OutputFormatter.format_yaml_output(memories, include_meta, meta)
                    )
                except Exception as e:
                    local_console.print(f"[red]YAML output failed: {e}[/red]")
                    raise typer.Exit(1)
            return

        # Handle table output
        from agentkit.toolkit.cli.utils import OutputFormatter, PaginationDisplayHelper

        columns = [
            ("MemoryId", "MemoryId", "cyan"),
            ("Name", "Name", "white"),
            ("Status", "Status", "green"),
            ("ProviderType", "ProviderType", "yellow"),
            ("Region", "Region", "blue"),
            ("LastUpdateTime", "LastUpdateTime", "magenta"),
            ("Managed", "Managed", "dim"),
        ]

        table = OutputFormatter.create_table(
            items=memories,
            columns=columns,
            title=f"Memory Collections (Count: {len(memories)}, HasNext: {'Yes' if last_next_token else 'No'})",
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
        _print_api_error(
            "ListMemoryCollections",
            e,
            hints=[
                "Check that filter conditions are valid",
                "To view all results, remove --name or --name-contains",
            ],
        )
        raise typer.Exit(1)


@memory_app.command("show")
def show_command(
    memory_id: str = typer.Option(..., "--memory-id", "-m", help="Memory ID"),
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
    """Show memory collection details."""
    try:
        client = AgentkitMemoryClient(region=(region or "").strip())
        req = memory_types.GetMemoryCollectionRequest(memory_id=memory_id)
        resp = client.get_memory_collection(req)
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
        _print_api_error(
            "GetMemoryCollection",
            e,
            hints=[
                "Verify the MemoryId exists and matches the current region",
                "Use 'agentkit memory list' to view valid IDs",
            ],
        )
        raise typer.Exit(1)


@memory_app.command("update")
def update_command(
    memory_id: str = typer.Option(..., "--memory-id", "-m", help="Memory ID"),
    description: Optional[str] = typer.Option(
        None, "--description", help="Description"
    ),
    vpc_id: Optional[str] = typer.Option(None, "--vpc-id", help="VPC ID"),
    subnet_ids: Optional[str] = typer.Option(
        None, "--subnet-ids", help="Subnet IDs (comma-separated)"
    ),
    strategies_json: Optional[str] = typer.Option(
        None,
        "--strategies-json",
        help=(
            "JSON array of strategies (max 5), items: "
            "[{Type,Name,CustomExtractionInstructions?}], Type in: Summary|Semantic|UserPreference"
        ),
    ),
    strategies: Optional[List[str]] = typer.Option(
        None,
        "--strategy",
        help=(
            "Repeatable. Add strategy as 'Type:Name[:CustomExtractionInstructions]', "
            "Type in: Summary|Semantic|UserPreference (max 5)"
        ),
    ),
    json_body: Optional[str] = typer.Option(
        None, "--json", help="Full JSON body for UpdateMemoryCollection"
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
    """Update memory collection (description, strategies, VPC)."""
    try:
        client = AgentkitMemoryClient(region=(region or "").strip())

        if json_body:
            payload = json.loads(json_body)
            req = memory_types.UpdateMemoryCollectionRequest(**payload)
        else:
            long_term = None
            if strategies_json:
                arr = json.loads(strategies_json)
                strategies = []
                for item in arr:
                    type_val = item.get("Type")
                    name_val = item.get("Name")
                    custom = item.get("CustomExtractionInstructions")
                    if not type_val or not name_val:
                        raise typer.BadParameter("Strategy requires both Type and Name")
                    # normalize type
                    type_key = str(type_val).replace("-", "_").lower()
                    if type_key in (
                        "summary",
                        "semantic",
                        "userpreference",
                        "user_preference",
                    ):
                        type_norm = (
                            "Summary"
                            if type_key == "summary"
                            else "Semantic"
                            if type_key == "semantic"
                            else "UserPreference"
                        )
                    else:
                        raise typer.BadParameter(
                            "Invalid strategy Type. Allowed: Summary, Semantic, UserPreference"
                        )
                    strategies.append(
                        memory_types.LongTermStrategiesItemForUpdateMemoryCollection(
                            name=name_val,
                            type=type_norm,
                            custom_extraction_instructions=custom,
                        )
                    )
                if len(strategies) > 5:
                    raise typer.BadParameter("At most 5 strategies are allowed")
                long_term = memory_types.LongTermForUpdateMemoryCollection(
                    strategies=strategies
                )
            elif strategies:
                # parse --strategy entries Type:Name[:CustomExtractionInstructions]
                parsed = []
                for s in strategies:
                    parts = [p.strip() for p in s.split(":", 2)]
                    if len(parts) < 2:
                        raise typer.BadParameter(
                            "Invalid --strategy format. Use 'Type:Name[:CustomExtractionInstructions]'"
                        )
                    type_val = parts[0]
                    name_val = parts[1]
                    custom = parts[2] if len(parts) == 3 else None
                    type_key = type_val.replace("-", "_").lower()
                    if type_key in (
                        "summary",
                        "semantic",
                        "userpreference",
                        "user_preference",
                    ):
                        type_norm = (
                            "Summary"
                            if type_key == "summary"
                            else "Semantic"
                            if type_key == "semantic"
                            else "UserPreference"
                        )
                    else:
                        raise typer.BadParameter(
                            "Invalid strategy Type. Allowed: Summary, Semantic, UserPreference"
                        )
                    if not name_val:
                        raise typer.BadParameter("Strategy Name is required")
                    parsed.append(
                        memory_types.LongTermStrategiesItemForUpdateMemoryCollection(
                            name=name_val,
                            type=type_norm,
                            custom_extraction_instructions=custom,
                        )
                    )
                if len(parsed) > 5:
                    raise typer.BadParameter("At most 5 strategies are allowed")
                long_term = memory_types.LongTermForUpdateMemoryCollection(
                    strategies=parsed
                )

            vpc = None
            if vpc_id:
                vpc = memory_types.VpcForUpdateMemoryCollection(
                    vpc_id=vpc_id,
                    subnet_ids=_parse_csv(subnet_ids) or None,
                )

            req = memory_types.UpdateMemoryCollectionRequest(
                memory_id=memory_id,
                description=description,
                long_term_configuration=long_term,
                vpc_config=vpc,
            )

        resp = client.update_memory_collection(req)
        console.print(
            Panel.fit(
                f"[green]✅ Updated[/green]\nMemoryId: {resp.memory_id}",
                title="UpdateMemoryCollection",
                border_style="green",
            )
        )
    except Exception as e:
        console.print(f"[red]❌ Update failed: {e}[/red]")
        raise typer.Exit(1)


@memory_app.command("delete")
def delete_command(
    memory_id: str = typer.Option(..., "--memory-id", "-m", help="Memory ID"),
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
    """Delete memory collection."""
    try:
        if not force:
            typer.confirm("Are you sure you want to delete this memory?", abort=True)
        client = AgentkitMemoryClient(region=(region or "").strip())
        req = memory_types.DeleteMemoryCollectionRequest(memory_id=memory_id)
        resp = client.delete_memory_collection(req)
        console.print(
            Panel.fit(
                f"[green]✅ Deleted[/green]\nMemoryId: {resp.memory_id}\nStatus: {resp.status}",
                title="DeleteMemoryCollection",
                border_style="green",
            )
        )
    except Exception as e:
        _print_api_error(
            "DeleteMemoryCollection",
            e,
            hints=[
                "Ensure the MemoryId is correct and the resource exists",
                "Verify with 'agentkit memory show -m <id>' before deleting",
            ],
        )
        raise typer.Exit(1)


@memory_app.command("conn")
def conn_command(
    memory_id: str = typer.Option(..., "--memory-id", "-m", help="Memory ID"),
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
    """Get connection info for a memory collection."""
    try:
        client = AgentkitMemoryClient(region=(region or "").strip())
        req = memory_types.GetMemoryConnectionInfoRequest(memory_id=memory_id)
        resp = client.get_memory_connection_info(req)
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
        _print_api_error(
            "GetMemoryConnectionInfo",
            e,
            hints=[
                "Ensure the MemoryId is correct and the resource status is Ready",
                "Run 'agentkit memory show -m <id>' to check the current status",
            ],
        )
        raise typer.Exit(1)
