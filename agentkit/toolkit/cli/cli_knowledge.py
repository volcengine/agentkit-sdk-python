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

"""AgentKit CLI - Knowledge commands.

Mapping to SDK:
- add     -> AddKnowledgeBase
- list    -> ListKnowledgeBases
- show    -> GetKnowledgeBase
- update  -> UpdateKnowledgeBase
- delete  -> DeleteKnowledgeBase
- conn    -> GetKnowledgeConnectionInfo
"""

from typing import Optional, List
import json
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from agentkit.sdk.knowledge.client import AgentkitKnowledgeClient
from agentkit.sdk.knowledge import types as knowledge_types

console = Console()

knowledge_app = typer.Typer(
    name="knowledge",
    help="Manage AgentKit Knowledge bases",
    add_completion=False,
)


# ---- ProviderType normalization and validation for knowledge ----
ALLOWED_KNOWLEDGE_PROVIDER_TYPES = {"VIKINGDB_KNOWLEDGE"}
KNOWLEDGE_PROVIDER_ALIASES = {
    "vikingdb": "VIKINGDB_KNOWLEDGE",
    "vikingdb_knowledge": "VIKINGDB_KNOWLEDGE",
    "vikingdb-knowledge": "VIKINGDB_KNOWLEDGE",
    "VIKINGDB_KNOWLEDGE": "VIKINGDB_KNOWLEDGE",
}


def _normalize_knowledge_provider_type(value: Optional[str]) -> str:
    if not value:
        raise typer.BadParameter("--provider-type is required for knowledge operations")
    raw = value.strip()
    if raw in ALLOWED_KNOWLEDGE_PROVIDER_TYPES:
        return raw
    key = raw.replace("-", "_").lower()
    if key in KNOWLEDGE_PROVIDER_ALIASES:
        return KNOWLEDGE_PROVIDER_ALIASES[key]
    upper = raw.upper()
    if upper in ALLOWED_KNOWLEDGE_PROVIDER_TYPES:
        return upper
    raise typer.BadParameter(
        "Invalid --provider-type. Allowed: VIKINGDB_KNOWLEDGE (aliases: vikingdb, vikingdb_knowledge)"
    )


def _print_api_error(action: str, exc: Exception, hints: Optional[List[str]] = None):
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


@knowledge_app.command("add")
def add_command(
    name: Optional[str] = typer.Option(None, "--name", help="Knowledge base name"),
    provider_knowledge_id: Optional[str] = typer.Option(
        None, "--provider-knowledge-id", help="External provider knowledge ID"
    ),
    provider_type: Optional[str] = typer.Option(
        None,
        "--provider-type",
        help="Provider type: VIKINGDB_KNOWLEDGE",
    ),
    description: Optional[str] = typer.Option(
        None, "--description", help="Description"
    ),
    project_name: Optional[str] = typer.Option(
        None, "--project-name", help="Project name"
    ),
    knowledge_bases_json: Optional[str] = typer.Option(
        None, "--knowledge-bases-json", help="JSON array of knowledge bases to add"
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
    """Add external knowledge bases."""
    try:
        client = AgentkitKnowledgeClient(region=(region or "").strip())

        items: List[knowledge_types.KnowledgeBasesItemForAddKnowledgeBase] = []
        if knowledge_bases_json:
            arr = json.loads(knowledge_bases_json)
            for item in arr:
                items.append(
                    knowledge_types.KnowledgeBasesItemForAddKnowledgeBase(
                        name=item.get("Name"),
                        provider_knowledge_id=item.get("ProviderKnowledgeId"),
                        provider_type=_normalize_knowledge_provider_type(
                            item.get("ProviderType")
                        ),
                        description=item.get("Description"),
                    )
                )
        else:
            if not (name and provider_knowledge_id and provider_type):
                raise typer.BadParameter(
                    "--name, --provider-knowledge-id and --provider-type are required when --knowledge-bases-json is not provided"
                )
            items.append(
                knowledge_types.KnowledgeBasesItemForAddKnowledgeBase(
                    name=name,
                    provider_knowledge_id=provider_knowledge_id,
                    provider_type=_normalize_knowledge_provider_type(provider_type),
                    description=description,
                )
            )

        req = knowledge_types.AddKnowledgeBaseRequest(
            project_name=project_name,
            knowledge_bases=items,
        )
        resp = client.add_knowledge_base(req)
        console.print(
            Panel.fit(
                f"[green]✅ Connected[/green]\nKnowledgeBases: {len(resp.knowledge_bases or [])}",
                title="AddKnowledgeBase",
                border_style="green",
            )
        )
    except Exception as e:
        _print_api_error(
            "AddKnowledgeBase",
            e,
            hints=[
                "Ensure provider-type is VIKINGDB_KNOWLEDGE",
                "Check provider-knowledge-id validity at the provider side",
            ],
        )
        raise typer.Exit(1)


@knowledge_app.command("list")
def list_command(
    # Exact filters
    knowledge_id: Optional[str] = typer.Option(
        None,
        "--knowledge-id",
        help="Exact KnowledgeId filter (comma-separated for multiple)",
    ),
    name: Optional[str] = typer.Option(
        None, "--name", help="Exact name filter (comma-separated for multiple)"
    ),
    status: Optional[str] = typer.Option(
        None,
        "--status",
        help="Exact status filter: Importing|ImportFailed|Ready|Deleting|DeleteFailed|Deleted|Error (comma-separated for multiple)",
    ),
    provider_type: Optional[str] = typer.Option(
        None,
        "--provider-type",
        help="Exact provider type filter: VIKINGDB_KNOWLEDGE (comma-separated for multiple)",
    ),
    # Contains filters
    knowledge_id_contains: Optional[str] = typer.Option(
        None, "--knowledge-id-contains", help="Substring filter for KnowledgeId"
    ),
    name_contains: Optional[str] = typer.Option(
        None, "--name-contains", help="Substring filter for name"
    ),
    status_contains: Optional[str] = typer.Option(
        None, "--status-contains", help="Substring filter for status"
    ),
    provider_type_contains: Optional[str] = typer.Option(
        None, "--provider-type-contains", help="Substring filter for provider type"
    ),
    # Cursor pagination
    limit: int = typer.Option(
        20, "--limit", "-l", help="Items per batch (MaxResults, max: 100)"
    ),
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
    region: Optional[str] = typer.Option(
        None,
        "--region",
        help=(
            "Region override for this command (e.g. cn-beijing, cn-shanghai). "
            "Defaults to VOLCENGINE_AGENTKIT_REGION/VOLCENGINE_REGION/global config."
        ),
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
    quiet: bool = typer.Option(
        False, "--quiet", "-q", help="Print only KnowledgeId values"
    ),
    no_color: bool = typer.Option(
        False, "--no-color", "-nc", help="Disable colored output for tables/panels"
    ),
):
    """List knowledge bases with cursor pagination (limit/next-token).

    Examples:
      agentkit knowledge list                          # Default list
      agentkit knowledge list --limit 50              # 50 items per page
      agentkit knowledge list --status Ready          # Filter by status
      agentkit knowledge list --name-contains test     # Filter by name contains
      agentkit knowledge list -nt TOKEN               # Continue cursor (NextToken)
      agentkit knowledge list --all                   # Fetch all batches
      agentkit knowledge list -q                      # Print only KnowledgeId values
      agentkit knowledge list -pto                  # Print only NextToken (single batch only)
      agentkit knowledge list --output json          # Output in JSON format
    """
    try:
        client = AgentkitKnowledgeClient(region=(region or "").strip())

        # Allowed status values for knowledge bases
        allowed_status = {
            "Importing",
            "ImportFailed",
            "Ready",
            "Deleting",
            "DeleteFailed",
            "Deleted",
            "Error",
        }

        # Allowed provider type values
        allowed_provider_types = {"VIKINGDB_KNOWLEDGE"}

        from agentkit.toolkit.cli.utils import ParameterHelper

        filters: List[knowledge_types.FiltersItemForListKnowledgeBases] = []

        # Parse all exact filter values
        knowledge_id_vals = ParameterHelper.parse_comma_separated(knowledge_id)
        name_vals = ParameterHelper.parse_comma_separated(name)
        status_vals = ParameterHelper.parse_comma_separated(status)
        provider_type_vals = ParameterHelper.parse_comma_separated(provider_type)

        # Validate status values
        if status_vals:
            ParameterHelper.validate_values(status_vals, allowed_status, "--status")

        # Validate provider type values
        if provider_type_vals:
            ParameterHelper.validate_values(
                provider_type_vals, allowed_provider_types, "--provider-type"
            )

        # Apply exact filters (take precedence over contains filters)
        if knowledge_id_vals:
            filters.append(
                knowledge_types.FiltersItemForListKnowledgeBases(
                    name="knowledge_id", values=knowledge_id_vals
                )
            )
        if name_vals:
            filters.append(
                knowledge_types.FiltersItemForListKnowledgeBases(
                    name="name", values=name_vals
                )
            )
        if status_vals:
            filters.append(
                knowledge_types.FiltersItemForListKnowledgeBases(
                    name="status", values=status_vals
                )
            )
        if provider_type_vals:
            filters.append(
                knowledge_types.FiltersItemForListKnowledgeBases(
                    name="provider_type", values=provider_type_vals
                )
            )

        # Apply contains filters only if corresponding exact filter not provided
        if (not knowledge_id_vals) and knowledge_id_contains:
            filters.append(
                knowledge_types.FiltersItemForListKnowledgeBases(
                    name_contains="knowledge_id", values=[knowledge_id_contains]
                )
            )
        if (not name_vals) and name_contains:
            filters.append(
                knowledge_types.FiltersItemForListKnowledgeBases(
                    name_contains="name", values=[name_contains]
                )
            )
        if (not status_vals) and status_contains:
            filters.append(
                knowledge_types.FiltersItemForListKnowledgeBases(
                    name_contains="status", values=[status_contains]
                )
            )
        if (not provider_type_vals) and provider_type_contains:
            filters.append(
                knowledge_types.FiltersItemForListKnowledgeBases(
                    name_contains="provider_type", values=[provider_type_contains]
                )
            )
        # Setup console with color control
        local_console = console if not no_color else Console(no_color=True)

        # Use unified pagination helper
        from agentkit.toolkit.cli.utils import PaginationHelper

        bases, last_next_token, batch_count = PaginationHelper.fetch_all_pages(
            request_func=client.list_knowledge_bases,
            request_builder=lambda t: knowledge_types.ListKnowledgeBasesRequest(
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
            for b in bases:
                data = b.model_dump(by_alias=True, exclude_none=True)
                local_console.print(data.get("KnowledgeId", ""))
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
                "items_count": len(bases),
            }
            if output.lower() == "json":
                local_console.print(
                    OutputFormatter.format_json_output(bases, include_meta, meta)
                )
            else:
                try:
                    local_console.print(
                        OutputFormatter.format_yaml_output(bases, include_meta, meta)
                    )
                except Exception as e:
                    local_console.print(f"[red]YAML output failed: {e}[/red]")
                    raise typer.Exit(1)
            return

        # Handle table output
        from agentkit.toolkit.cli.utils import OutputFormatter, PaginationDisplayHelper

        columns = [
            ("KnowledgeId", "KnowledgeId", "cyan"),
            ("Name", "Name", "white"),
            ("Status", "Status", "green"),
            ("ProviderType", "ProviderType", "yellow"),
            ("Region", "Region", "blue"),
            ("LastUpdateTime", "LastUpdateTime", "magenta"),
        ]

        table = OutputFormatter.create_table(
            items=bases,
            columns=columns,
            title=f"Knowledge Bases (Count: {len(bases)}, HasNext: {'Yes' if last_next_token else 'No'})",
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
            "ListKnowledgeBases",
            e,
            hints=[
                "Check filter values (knowledge-id, name, status, provider-type and their -contains variants)",
                "Use --status with valid values: Importing|ImportFailed|Ready|Deleting|DeleteFailed|Deleted|Error",
                "Use --provider-type with valid values: VIKINGDB_KNOWLEDGE",
                "Remove filters to view all knowledge bases",
                "Use --all to fetch all pages if you expect more results",
            ],
        )
        raise typer.Exit(1)


@knowledge_app.command("show")
def show_command(
    knowledge_id: str = typer.Option(..., "--knowledge-id", "-k", help="Knowledge ID"),
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
    """Show knowledge base details."""
    try:
        client = AgentkitKnowledgeClient(region=(region or "").strip())
        req = knowledge_types.GetKnowledgeBaseRequest(knowledge_id=knowledge_id)
        resp = client.get_knowledge_base(req)
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
            "GetKnowledgeBase",
            e,
            hints=[
                "Verify the KnowledgeId exists",
                "Use 'agentkit knowledge list' to view valid IDs",
            ],
        )
        raise typer.Exit(1)


@knowledge_app.command("update")
def update_command(
    knowledge_id: str = typer.Option(..., "--knowledge-id", "-k", help="Knowledge ID"),
    description: Optional[str] = typer.Option(
        None, "--description", help="Description"
    ),
    vpc_id: Optional[str] = typer.Option(None, "--vpc-id", help="VPC ID"),
    subnet_ids: Optional[str] = typer.Option(
        None, "--subnet-ids", help="Subnet IDs (comma-separated)"
    ),
    json_body: Optional[str] = typer.Option(
        None, "--json", help="Full JSON body for UpdateKnowledgeBase"
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
    """Update knowledge base (description, VPC)."""
    try:
        client = AgentkitKnowledgeClient(region=(region or "").strip())

        if json_body:
            payload = json.loads(json_body)
            req = knowledge_types.UpdateKnowledgeBaseRequest(**payload)
        else:
            vpc = None
            if vpc_id:
                subs = [
                    s.strip() for s in (subnet_ids or "").split(",") if s.strip()
                ] or None
                vpc = knowledge_types.VpcForUpdateKnowledgeBase(
                    vpc_id=vpc_id,
                    subnet_ids=subs,
                )
            req = knowledge_types.UpdateKnowledgeBaseRequest(
                knowledge_id=knowledge_id,
                description=description,
                vpc_config=vpc,
            )

        resp = client.update_knowledge_base(req)
        console.print(
            Panel.fit(
                f"[green]✅ Updated[/green]\nKnowledgeId: {resp.knowledge_id}",
                title="UpdateKnowledgeBase",
                border_style="green",
            )
        )
    except Exception as e:
        _print_api_error(
            "UpdateKnowledgeBase",
            e,
            hints=[
                "Check VPC id and subnet ids",
                "Ensure description length and characters are valid",
            ],
        )
        raise typer.Exit(1)


@knowledge_app.command("delete")
def delete_command(
    knowledge_id: str = typer.Option(..., "--knowledge-id", "-k", help="Knowledge ID"),
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
    """Delete knowledge base."""
    try:
        if not force:
            typer.confirm(
                "Are you sure you want to delete this knowledge base?", abort=True
            )
        client = AgentkitKnowledgeClient(region=(region or "").strip())
        req = knowledge_types.DeleteKnowledgeBaseRequest(knowledge_id=knowledge_id)
        resp = client.delete_knowledge_base(req)
        console.print(
            Panel.fit(
                f"[green]✅ Deleted[/green]\nKnowledgeId: {resp.knowledge_id}",
                title="DeleteKnowledgeBase",
                border_style="green",
            )
        )
    except Exception as e:
        _print_api_error(
            "DeleteKnowledgeBase",
            e,
            hints=[
                "Ensure the KnowledgeId is correct and the resource exists",
                "Verify with 'agentkit knowledge show -k <id>' before deleting",
            ],
        )
        raise typer.Exit(1)


@knowledge_app.command("conn")
def conn_command(
    knowledge_id: str = typer.Option(..., "--knowledge-id", "-k", help="Knowledge ID"),
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
    """Get connection info for a knowledge base."""
    try:
        client = AgentkitKnowledgeClient(region=(region or "").strip())
        req = knowledge_types.GetKnowledgeConnectionInfoRequest(
            knowledge_id=knowledge_id
        )
        resp = client.get_knowledge_connection_info(req)
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
            "GetKnowledgeConnectionInfo",
            e,
            hints=[
                "Ensure the KnowledgeId is correct and the resource status is Ready",
                "Run 'agentkit knowledge show -k <id>' to check the current status",
            ],
        )
        raise typer.Exit(1)


@knowledge_app.command("provider-types")
def provider_types_command():
    """List allowed knowledge ProviderType values and aliases."""
    try:
        table = Table(title="Allowed Knowledge Provider Types")
        table.add_column("Value", style="cyan")
        table.add_column("Aliases", style="magenta")
        table.add_row(
            "VIKINGDB_KNOWLEDGE", "vikingdb, vikingdb_knowledge, vikingdb-knowledge"
        )
        console.print(table)
    except Exception as e:
        _print_api_error("ProviderTypes", e)
        raise typer.Exit(1)
