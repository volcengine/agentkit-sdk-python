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

from __future__ import annotations

from typing import Optional, List
import json

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agentkit.sdk.skills.client import AgentkitSkillsClient
from agentkit.sdk.skills import types as skills_types
from agentkit.toolkit.cli.utils import ParameterHelper
from agentkit.toolkit.cli.cli_skills_workflow import add_workflow_commands

console = Console()

skills_app = typer.Typer(
    name="skills",
    help="Manage AgentKit Skills and SkillSpaces",
    add_completion=False,
)

space_app = typer.Typer(
    name="space",
    help="Manage AgentKit SkillSpaces",
    add_completion=False,
)


def _validate_skill_space_name(name: str) -> None:
    import re

    if not name:
        raise typer.BadParameter("SkillSpace name is required")
    if len(name) > 64:
        raise typer.BadParameter("SkillSpace name must be <= 64 characters")
    if not re.fullmatch(r"[a-z0-9_]+", name):
        raise typer.BadParameter(
            "Invalid SkillSpace name. It must be underscore style: [a-z0-9_]+"
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

    lines: List[str] = []
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


def _dump_output(data: dict, output: str):
    fmt = (output or "yaml").lower().strip()
    if fmt == "yaml":
        try:
            import yaml

            console.print(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
        except Exception as e:
            console.print(f"[red]YAML output failed: {e}[/red]")
            raise typer.Exit(1)
    else:
        console.print(json.dumps(data, indent=2, ensure_ascii=False))


def _parse_tags(
    tags_json: Optional[str], tags: Optional[List[str]]
) -> Optional[List[skills_types.TagForSkill]]:
    tags_list: List[skills_types.TagForSkill] = []
    if tags_json:
        arr = json.loads(tags_json)
        for t in arr:
            tags_list.append(
                skills_types.TagForSkill(
                    key=t.get("Key") or t.get("key"),
                    value=t.get("Value") or t.get("value"),
                )
            )
    if tags:
        for t in tags:
            raw = (t or "").strip()
            if not raw:
                continue
            if "=" in raw:
                k, v = raw.split("=", 1)
                tags_list.append(
                    skills_types.TagForSkill(key=k.strip(), value=v.strip())
                )
            else:
                tags_list.append(skills_types.TagForSkill(key=raw, value=""))
    return tags_list or None


def _parse_skill_filter(
    skill_id: Optional[str],
    name: Optional[str],
    status: Optional[str],
    name_contains: Optional[str],
    status_contains: Optional[str],
) -> Optional[skills_types.SkillFilter]:
    f = skills_types.SkillFilter()
    has_any = False

    if skill_id:
        f.id = ParameterHelper.parse_comma_separated(skill_id)[0]
        has_any = True
    if name:
        f.name = ParameterHelper.parse_comma_separated(name)[0]
        has_any = True
    if status:
        f.status = ParameterHelper.parse_comma_separated(status)
        has_any = True

    if not skill_id and name_contains:
        f.name = name_contains.strip()
        has_any = True
    if not status and status_contains:
        f.status = [status_contains.strip()]
        has_any = True

    return f if has_any else None


def _parse_space_filter(
    space_id: Optional[str],
    name: Optional[str],
    status: Optional[str],
    name_contains: Optional[str],
    status_contains: Optional[str],
) -> Optional[skills_types.SkillSpaceFilter]:
    f = skills_types.SkillSpaceFilter()
    has_any = False

    if space_id:
        f.id = ParameterHelper.parse_comma_separated(space_id)[0]
        has_any = True
    if name:
        f.name = ParameterHelper.parse_comma_separated(name)[0]
        has_any = True
    if status:
        f.status = ParameterHelper.parse_comma_separated(status)
        has_any = True

    if not space_id and name_contains:
        f.name = name_contains.strip()
        has_any = True
    if not status and status_contains:
        f.status = [status_contains.strip()]
        has_any = True

    return f if has_any else None


@skills_app.command("create")
def create_skill_command(
    tos_url: str = typer.Option(..., "--tos-url", help="Skill ZIP TOS URL"),
    name: Optional[str] = typer.Option(None, "--name", help="Skill name"),
    description: Optional[str] = typer.Option(
        None, "--description", help="Description"
    ),
    skill_spaces: Optional[List[str]] = typer.Option(
        None,
        "--space-id",
        help="Repeatable. SkillSpace ID to join at creation",
    ),
    bucket_name: Optional[str] = typer.Option(
        None, "--bucket-name", help="BucketName (optional, advanced)"
    ),
    project_name: Optional[str] = typer.Option(None, "--project-name", help="Project"),
    tags_json: Optional[str] = typer.Option(
        None, "--tags-json", help="JSON array of tags [{Key,Value}]"
    ),
    tags: Optional[List[str]] = typer.Option(
        None, "--tag", help="Repeatable. Tag as 'Key=Value' or 'Key'"
    ),
    output: str = typer.Option("yaml", "--output", "-o", help="Output: json|yaml"),
    region: Optional[str] = typer.Option(
        None,
        "--region",
        help=(
            "Region override for this command (e.g. cn-beijing, cn-shanghai). "
            "Defaults to VOLCENGINE_AGENTKIT_REGION/VOLCENGINE_REGION/global config."
        ),
    ),
):
    """Create a Skill from a ZIP stored in TOS."""
    try:
        client = AgentkitSkillsClient(region=(region or "").strip())
        req = skills_types.CreateSkillRequest(
            name=name,
            description=description,
            tos_url=tos_url,
            skill_spaces=skill_spaces,
            bucket_name=bucket_name,
            project_name=project_name,
            tags=_parse_tags(tags_json, tags),
        )
        resp = client.create_skill(req)
        _dump_output(resp.model_dump(by_alias=True, exclude_none=True), output)
    except Exception as e:
        _print_api_error(
            "CreateSkill",
            e,
            hints=[
                "Ensure the TOS URL is accessible and points to a valid Skill ZIP",
                "Use 'agentkit skills space list' to find valid Space IDs",
            ],
        )
        raise typer.Exit(1)


@skills_app.command("list")
def list_skills_command(
    skill_id: Optional[str] = typer.Option(None, "--skill-id", help="Exact SkillId"),
    name: Optional[str] = typer.Option(None, "--name", help="Exact name"),
    status: Optional[str] = typer.Option(
        None, "--status", help="Exact status (comma-separated for multiple)"
    ),
    name_contains: Optional[str] = typer.Option(
        None, "--name-contains", help="Substring filter for name"
    ),
    status_contains: Optional[str] = typer.Option(
        None, "--status-contains", help="Substring filter for status"
    ),
    project_name: Optional[str] = typer.Option(None, "--project-name", help="Project"),
    tags: Optional[List[str]] = typer.Option(
        None, "--tag", help="Repeatable. Tag filter as 'Key=Value'"
    ),
    page_number: int = typer.Option(1, "--page-number", help="Page number (1-based)"),
    page_size: int = typer.Option(20, "--page-size", help="Page size"),
    all_pages: bool = typer.Option(False, "--all", help="Fetch all pages"),
    output: str = typer.Option(
        "table", "--output", "-o", help="Output: table|json|yaml"
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
    """List Skills."""
    try:
        client = AgentkitSkillsClient(region=(region or "").strip())

        tag_filters: Optional[List[skills_types.TagFilterForSkill]] = None
        if tags:
            tag_filters = []
            for t in tags:
                raw = (t or "").strip()
                if not raw:
                    continue
                if "=" not in raw:
                    raise typer.BadParameter("--tag filter must be in 'Key=Value' form")
                k, v = raw.split("=", 1)
                tag_filters.append(
                    skills_types.TagFilterForSkill(key=k.strip(), values=[v.strip()])
                )

        skill_filter = _parse_skill_filter(
            skill_id=skill_id,
            name=name,
            status=status,
            name_contains=name_contains,
            status_contains=status_contains,
        )

        items: List[skills_types.Skill] = []
        pn = max(1, int(page_number))
        ps = max(1, int(page_size))
        while True:
            resp = client.list_skills(
                skills_types.ListSkillsRequest(
                    page_number=pn,
                    page_size=ps,
                    filter=skill_filter,
                    tag_filters=tag_filters,
                    project_name=project_name,
                )
            )
            batch = resp.items or []
            items.extend(batch)
            total = resp.total_count or 0
            if not all_pages:
                break
            if len(items) >= total:
                break
            pn += 1

        fmt = (output or "table").lower().strip()
        if fmt in {"json", "yaml"}:
            data = {
                "TotalCount": len(items),
                "Items": [
                    i.model_dump(by_alias=True, exclude_none=True) for i in items
                ],
            }
            _dump_output(data, fmt)
            return

        table = Table(title="Skills")
        table.add_column("Id", style="cyan", no_wrap=True)
        table.add_column("Name", style="green")
        table.add_column("Status")
        table.add_column("Versions")
        table.add_column("Project")
        table.add_column("UpdatedAt")
        for s in items:
            table.add_row(
                s.id,
                s.name,
                s.status,
                ",".join(s.versions or []),
                s.project_name,
                s.update_time_stamp,
            )
        console.print(table)
    except Exception as e:
        _print_api_error(
            "ListSkills",
            e,
            hints=[
                "Remove filters to view all Skills",
                "Use --all to fetch all pages",
            ],
        )
        raise typer.Exit(1)


@skills_app.command("show")
def show_skill_command(
    skill_id: str = typer.Option(..., "--skill-id", "-s", help="Skill ID"),
    output: str = typer.Option("yaml", "--output", "-o", help="Output: json|yaml"),
    region: Optional[str] = typer.Option(
        None,
        "--region",
        help=(
            "Region override for this command (e.g. cn-beijing, cn-shanghai). "
            "Defaults to VOLCENGINE_AGENTKIT_REGION/VOLCENGINE_REGION/global config."
        ),
    ),
):
    """Show Skill details."""
    try:
        client = AgentkitSkillsClient(region=(region or "").strip())
        resp = client.get_skill(skills_types.GetSkillRequest(id=skill_id))
        _dump_output(resp.model_dump(by_alias=True, exclude_none=True), output)
    except Exception as e:
        _print_api_error(
            "GetSkill",
            e,
            hints=[
                "Verify the SkillId exists",
                "Use 'agentkit skills list' to view valid IDs",
            ],
        )
        raise typer.Exit(1)


@skills_app.command("update")
def update_skill_command(
    skill_id: str = typer.Option(..., "--skill-id", "-s", help="Skill ID"),
    tos_url: str = typer.Option(..., "--tos-url", help="New Skill ZIP TOS URL"),
    name: Optional[str] = typer.Option(None, "--name", help="Skill name (optional)"),
    description: Optional[str] = typer.Option(
        None, "--description", help="Description"
    ),
    skill_spaces: Optional[List[str]] = typer.Option(
        None,
        "--space-id",
        help="Repeatable. SkillSpace ID list (optional)",
    ),
    bucket_name: Optional[str] = typer.Option(
        None, "--bucket-name", help="BucketName (optional, advanced)"
    ),
    output: str = typer.Option("yaml", "--output", "-o", help="Output: json|yaml"),
    region: Optional[str] = typer.Option(
        None,
        "--region",
        help=(
            "Region override for this command (e.g. cn-beijing, cn-shanghai). "
            "Defaults to VOLCENGINE_AGENTKIT_REGION/VOLCENGINE_REGION/global config."
        ),
    ),
):
    """Update Skill package (requires re-publish to take effect in spaces)."""
    try:
        client = AgentkitSkillsClient(region=(region or "").strip())
        resp = client.update_skill(
            skills_types.UpdateSkillRequest(
                id=skill_id,
                name=name,
                description=description,
                tos_url=tos_url,
                skill_spaces=skill_spaces,
                bucket_name=bucket_name,
            )
        )
        _dump_output(resp.model_dump(by_alias=True, exclude_none=True), output)
    except Exception as e:
        _print_api_error(
            "UpdateSkill",
            e,
            hints=[
                "Ensure the SkillId exists",
                "After update, publish the desired version to your SkillSpace",
            ],
        )
        raise typer.Exit(1)


@skills_app.command("delete")
def delete_skill_command(
    skill_id: str = typer.Option(..., "--skill-id", "-s", help="Skill ID"),
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
    """Delete a Skill."""
    if not force:
        typer.confirm(
            f"Delete Skill {skill_id}? This cannot be undone.",
            abort=True,
        )
    try:
        client = AgentkitSkillsClient(region=(region or "").strip())
        client.delete_skill(skills_types.DeleteSkillRequest(id=skill_id))
        console.print(
            Panel.fit(
                f"[green]✅ Deleted[/green]\nSkillId: {skill_id}",
                title="DeleteSkill",
                border_style="green",
            )
        )
    except Exception as e:
        _print_api_error("DeleteSkill", e)
        raise typer.Exit(1)


@skills_app.command("versions")
def list_versions_command(
    skill_id: str = typer.Option(..., "--skill-id", "-s", help="Skill ID"),
    page_number: int = typer.Option(1, "--page-number", help="Page number (1-based)"),
    page_size: int = typer.Option(20, "--page-size", help="Page size"),
    all_pages: bool = typer.Option(False, "--all", help="Fetch all pages"),
    output: str = typer.Option(
        "table", "--output", "-o", help="Output: table|json|yaml"
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
    """List Skill versions."""
    try:
        client = AgentkitSkillsClient(region=(region or "").strip())
        items: List[skills_types.SkillVersionWithRelation] = []
        pn = max(1, int(page_number))
        ps = max(1, int(page_size))
        while True:
            resp = client.list_skill_versions(
                skills_types.ListSkillVersionsRequest(
                    id=skill_id, page_number=pn, page_size=ps
                )
            )
            batch = resp.items or []
            items.extend(batch)
            total = resp.total_count or 0
            if not all_pages:
                break
            if len(items) >= total:
                break
            pn += 1

        fmt = (output or "table").lower().strip()
        if fmt in {"json", "yaml"}:
            data = {
                "TotalCount": len(items),
                "Items": [
                    i.model_dump(by_alias=True, exclude_none=True) for i in items
                ],
            }
            _dump_output(data, fmt)
            return

        table = Table(title=f"Skill Versions ({skill_id})")
        table.add_column("Version", style="cyan", no_wrap=True)
        table.add_column("Status")
        table.add_column("CreatedAt")
        table.add_column("UpdatedAt")
        table.add_column("ErrorMessage")
        for v in items:
            table.add_row(
                v.version,
                v.status,
                v.create_time_stamp,
                v.update_time_stamp,
                v.error_message or "",
            )
        console.print(table)
    except Exception as e:
        _print_api_error(
            "ListSkillVersions",
            e,
            hints=["Verify the SkillId exists", "Use 'agentkit skills show' first"],
        )
        raise typer.Exit(1)


@skills_app.command("version")
def get_version_command(
    skill_id: str = typer.Option(..., "--skill-id", "-s", help="Skill ID"),
    skill_version: Optional[str] = typer.Option(None, "--version", help="Version"),
    output: str = typer.Option("yaml", "--output", "-o", help="Output: json|yaml"),
    region: Optional[str] = typer.Option(
        None,
        "--region",
        help=(
            "Region override for this command (e.g. cn-beijing, cn-shanghai). "
            "Defaults to VOLCENGINE_AGENTKIT_REGION/VOLCENGINE_REGION/global config."
        ),
    ),
):
    """Show a Skill version detail."""
    try:
        client = AgentkitSkillsClient(region=(region or "").strip())
        resp = client.get_skill_version(
            skills_types.GetSkillVersionRequest(
                id=skill_id, skill_version=skill_version
            )
        )
        _dump_output(resp.model_dump(by_alias=True, exclude_none=True), output)
    except Exception as e:
        _print_api_error(
            "GetSkillVersion",
            e,
            hints=[
                "Verify SkillId and version",
                "Use 'agentkit skills versions' to list versions",
            ],
        )
        raise typer.Exit(1)


@skills_app.command("spaces")
def list_spaces_by_skill_command(
    skill_id: str = typer.Option(..., "--skill-id", "-s", help="Skill ID"),
    skill_version: Optional[str] = typer.Option(
        None, "--version", help="Skill version"
    ),
    page_number: int = typer.Option(1, "--page-number", help="Page number (1-based)"),
    page_size: int = typer.Option(20, "--page-size", help="Page size"),
    all_pages: bool = typer.Option(False, "--all", help="Fetch all pages"),
    output: str = typer.Option(
        "table", "--output", "-o", help="Output: table|json|yaml"
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
    """List SkillSpaces that a Skill is published to."""
    try:
        client = AgentkitSkillsClient(region=(region or "").strip())
        items: List[skills_types.Relation] = []
        pn = max(1, int(page_number))
        ps = max(1, int(page_size))
        while True:
            resp = client.list_skill_spaces_by_skill(
                skills_types.ListSkillSpacesBySkillRequest(
                    skill_id=skill_id,
                    skill_version=skill_version,
                    page_number=pn,
                    page_size=ps,
                )
            )
            batch = resp.items or []
            items.extend(batch)
            total = resp.total_count or 0
            if not all_pages:
                break
            if len(items) >= total:
                break
            pn += 1

        fmt = (output or "table").lower().strip()
        if fmt in {"json", "yaml"}:
            data = {
                "TotalCount": len(items),
                "Items": [
                    i.model_dump(by_alias=True, exclude_none=True) for i in items
                ],
            }
            _dump_output(data, fmt)
            return

        table = Table(title=f"SkillSpaces for Skill ({skill_id})")
        table.add_column("SpaceId", style="cyan", no_wrap=True)
        table.add_column("SpaceName", style="green")
        table.add_column("SkillStatus")
        table.add_column("Version")
        for r in items:
            table.add_row(
                r.skill_space_id,
                r.skill_space_name or "",
                r.skill_status or "",
                r.version or "",
            )
        console.print(table)
    except Exception as e:
        _print_api_error("ListSkillSpacesBySkill", e)
        raise typer.Exit(1)


@skills_app.command("info")
def get_skill_info_command(
    skill_name: str = typer.Option(..., "--skill-name", help="Skill name"),
    skill_space_id: str = typer.Option(..., "--space-id", help="SkillSpace ID"),
    skill_space_name: str = typer.Option("", "--space-name", help="SkillSpace name"),
    output: str = typer.Option("yaml", "--output", "-o", help="Output: json|yaml"),
    region: Optional[str] = typer.Option(
        None,
        "--region",
        help=(
            "Region override for this command (e.g. cn-beijing, cn-shanghai). "
            "Defaults to VOLCENGINE_AGENTKIT_REGION/VOLCENGINE_REGION/global config."
        ),
    ),
):
    """Get Skill execution metadata in a SkillSpace (includes SkillMd)."""
    try:
        client = AgentkitSkillsClient(region=(region or "").strip())
        resp = client.get_skill_info(
            skills_types.GetSkillInfoRequest(
                skill_name=skill_name,
                skill_space_name=skill_space_name,
                skill_space_id=skill_space_id,
            )
        )
        _dump_output(resp.model_dump(by_alias=True, exclude_none=True), output)
    except Exception as e:
        _print_api_error(
            "GetSkillInfo",
            e,
            hints=[
                "Ensure the Skill is available in the SkillSpace",
                "Use 'agentkit skills space skills' to confirm relations",
            ],
        )
        raise typer.Exit(1)


@space_app.command("create")
def create_space_command(
    name: str = typer.Option(..., "--name", "-n", help="SkillSpace name"),
    description: Optional[str] = typer.Option(
        None, "--description", help="Description"
    ),
    skills_json: Optional[str] = typer.Option(
        None, "--skills-json", help="JSON array of skills [{SkillId,Version}]"
    ),
    project_name: Optional[str] = typer.Option(None, "--project-name", help="Project"),
    tags_json: Optional[str] = typer.Option(
        None, "--tags-json", help="JSON array of tags [{Key,Value}]"
    ),
    tags: Optional[List[str]] = typer.Option(
        None, "--tag", help="Repeatable. Tag as 'Key=Value' or 'Key'"
    ),
    output: str = typer.Option("yaml", "--output", "-o", help="Output: json|yaml"),
    region: Optional[str] = typer.Option(
        None,
        "--region",
        help=(
            "Region override for this command (e.g. cn-beijing, cn-shanghai). "
            "Defaults to VOLCENGINE_AGENTKIT_REGION/VOLCENGINE_REGION/global config."
        ),
    ),
):
    """Create a SkillSpace."""
    try:
        _validate_skill_space_name(name)
        client = AgentkitSkillsClient(region=(region or "").strip())
        skills_list: Optional[List[skills_types.SkillBasicInfo]] = None
        if skills_json:
            arr = json.loads(skills_json)
            skills_list = [
                skills_types.SkillBasicInfo(
                    skill_id=i.get("SkillId"), version=i.get("Version")
                )
                for i in arr
            ]
        resp = client.create_skill_space(
            skills_types.CreateSkillSpaceRequest(
                name=name,
                description=description,
                skills=skills_list,
                project_name=project_name,
                tags=_parse_tags(tags_json, tags),
            )
        )
        _dump_output(resp.model_dump(by_alias=True, exclude_none=True), output)
    except Exception as e:
        _print_api_error("CreateSkillSpace", e)
        raise typer.Exit(1)


@space_app.command("list")
def list_spaces_command(
    space_id: Optional[str] = typer.Option(None, "--space-id", help="Exact SpaceId"),
    name: Optional[str] = typer.Option(None, "--name", help="Exact name"),
    status: Optional[str] = typer.Option(
        None, "--status", help="Exact status (comma-separated for multiple)"
    ),
    name_contains: Optional[str] = typer.Option(
        None, "--name-contains", help="Substring filter for name"
    ),
    status_contains: Optional[str] = typer.Option(
        None, "--status-contains", help="Substring filter for status"
    ),
    project_name: Optional[str] = typer.Option(None, "--project-name", help="Project"),
    tags: Optional[List[str]] = typer.Option(
        None, "--tag", help="Repeatable. Tag filter as 'Key=Value'"
    ),
    page_number: int = typer.Option(1, "--page-number", help="Page number (1-based)"),
    page_size: int = typer.Option(20, "--page-size", help="Page size"),
    all_pages: bool = typer.Option(False, "--all", help="Fetch all pages"),
    output: str = typer.Option(
        "table", "--output", "-o", help="Output: table|json|yaml"
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
    """List SkillSpaces."""
    try:
        client = AgentkitSkillsClient(region=(region or "").strip())

        tag_filters: Optional[List[skills_types.TagFilterForSkill]] = None
        if tags:
            tag_filters = []
            for t in tags:
                raw = (t or "").strip()
                if not raw:
                    continue
                if "=" not in raw:
                    raise typer.BadParameter("--tag filter must be in 'Key=Value' form")
                k, v = raw.split("=", 1)
                tag_filters.append(
                    skills_types.TagFilterForSkill(key=k.strip(), values=[v.strip()])
                )

        space_filter = _parse_space_filter(
            space_id=space_id,
            name=name,
            status=status,
            name_contains=name_contains,
            status_contains=status_contains,
        )

        items: List[skills_types.SkillSpace] = []
        pn = max(1, int(page_number))
        ps = max(1, int(page_size))
        while True:
            resp = client.list_skill_spaces(
                skills_types.ListSkillSpacesRequest(
                    page_number=pn,
                    page_size=ps,
                    filter=space_filter,
                    project_name=project_name,
                    tag_filters=tag_filters,
                )
            )
            batch = resp.items or []
            items.extend(batch)
            total = resp.total_count or 0
            if not all_pages:
                break
            if len(items) >= total:
                break
            pn += 1

        fmt = (output or "table").lower().strip()
        if fmt in {"json", "yaml"}:
            data = {
                "TotalCount": len(items),
                "Items": [
                    i.model_dump(by_alias=True, exclude_none=True) for i in items
                ],
            }
            _dump_output(data, fmt)
            return

        table = Table(title="SkillSpaces")
        table.add_column("Id", style="cyan", no_wrap=True)
        table.add_column("Name", style="green")
        table.add_column("Status")
        table.add_column("Skills")
        table.add_column("Project")
        table.add_column("UpdatedAt")
        for sp in items:
            table.add_row(
                sp.id,
                sp.name,
                sp.status,
                str(len(sp.relations or [])),
                sp.project_name,
                sp.update_time_stamp,
            )
        console.print(table)
    except Exception as e:
        _print_api_error("ListSkillSpaces", e)
        raise typer.Exit(1)


@space_app.command("show")
def show_space_command(
    space_id: str = typer.Option(..., "--space-id", "-i", help="SkillSpace ID"),
    output: str = typer.Option("yaml", "--output", "-o", help="Output: json|yaml"),
    region: Optional[str] = typer.Option(
        None,
        "--region",
        help=(
            "Region override for this command (e.g. cn-beijing, cn-shanghai). "
            "Defaults to VOLCENGINE_AGENTKIT_REGION/VOLCENGINE_REGION/global config."
        ),
    ),
):
    """Show SkillSpace details."""
    try:
        client = AgentkitSkillsClient(region=(region or "").strip())
        resp = client.get_skill_space(skills_types.GetSkillSpaceRequest(id=space_id))
        _dump_output(resp.model_dump(by_alias=True, exclude_none=True), output)
    except Exception as e:
        _print_api_error("GetSkillSpace", e)
        raise typer.Exit(1)


@space_app.command("update")
def update_space_command(
    space_id: str = typer.Option(..., "--space-id", "-i", help="SkillSpace ID"),
    name: Optional[str] = typer.Option(None, "--name", help="Name"),
    description: Optional[str] = typer.Option(
        None, "--description", help="Description"
    ),
    output: str = typer.Option("yaml", "--output", "-o", help="Output: json|yaml"),
    region: Optional[str] = typer.Option(
        None,
        "--region",
        help=(
            "Region override for this command (e.g. cn-beijing, cn-shanghai). "
            "Defaults to VOLCENGINE_AGENTKIT_REGION/VOLCENGINE_REGION/global config."
        ),
    ),
):
    """Update SkillSpace."""
    try:
        if name is not None:
            _validate_skill_space_name(name)
        client = AgentkitSkillsClient(region=(region or "").strip())
        resp = client.update_skill_space(
            skills_types.UpdateSkillSpaceRequest(
                id=space_id, name=name, description=description
            )
        )
        _dump_output(resp.model_dump(by_alias=True, exclude_none=True), output)
    except Exception as e:
        _print_api_error("UpdateSkillSpace", e)
        raise typer.Exit(1)


@space_app.command("delete")
def delete_space_command(
    space_id: str = typer.Option(..., "--space-id", "-i", help="SkillSpace ID"),
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
    """Delete a SkillSpace."""
    if not force:
        typer.confirm(
            f"Delete SkillSpace {space_id}? This cannot be undone.",
            abort=True,
        )
    try:
        client = AgentkitSkillsClient(region=(region or "").strip())
        client.delete_skill_space(skills_types.DeleteSkillSpaceRequest(id=space_id))
        console.print(
            Panel.fit(
                f"[green]✅ Deleted[/green]\nSkillSpaceId: {space_id}",
                title="DeleteSkillSpace",
                border_style="green",
            )
        )
    except Exception as e:
        _print_api_error("DeleteSkillSpace", e)
        raise typer.Exit(1)


@space_app.command("skills")
def list_space_skills_command(
    space_id: str = typer.Option(..., "--space-id", "-i", help="SkillSpace ID"),
    status: Optional[str] = typer.Option(
        None, "--status", help="Filter relation status (comma-separated)"
    ),
    name: Optional[str] = typer.Option(None, "--name", help="Filter by skill name"),
    skill_id: Optional[str] = typer.Option(
        None, "--skill-id", help="Filter by skill id"
    ),
    page_number: int = typer.Option(1, "--page-number", help="Page number (1-based)"),
    page_size: int = typer.Option(20, "--page-size", help="Page size"),
    all_pages: bool = typer.Option(False, "--all", help="Fetch all pages"),
    output: str = typer.Option(
        "table", "--output", "-o", help="Output: table|json|yaml"
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
    """List Skills in a SkillSpace (relation view)."""
    try:
        client = AgentkitSkillsClient(region=(region or "").strip())

        relation_filter = skills_types.SkillRelationFilter()
        has_any = False
        if status:
            relation_filter.status = ParameterHelper.parse_comma_separated(status)
            has_any = True
        if name:
            relation_filter.name = name.strip()
            has_any = True
        if skill_id:
            relation_filter.id = skill_id.strip()
            has_any = True

        items: List[skills_types.Relation] = []
        pn = max(1, int(page_number))
        ps = max(1, int(page_size))
        while True:
            resp = client.list_skills_by_skill_space(
                skills_types.ListSkillsBySkillSpaceRequest(
                    skill_space_id=space_id,
                    filter=relation_filter if has_any else None,
                    page_number=pn,
                    page_size=ps,
                )
            )
            batch = resp.items or []
            items.extend(batch)
            total = resp.total_count or 0
            if not all_pages:
                break
            if len(items) >= total:
                break
            pn += 1

        fmt = (output or "table").lower().strip()
        if fmt in {"json", "yaml"}:
            data = {
                "TotalCount": len(items),
                "Items": [
                    i.model_dump(by_alias=True, exclude_none=True) for i in items
                ],
            }
            _dump_output(data, fmt)
            return

        table = Table(title=f"Skills in SkillSpace ({space_id})")
        table.add_column("SkillId", style="cyan", no_wrap=True)
        table.add_column("SkillName", style="green")
        table.add_column("Status")
        table.add_column("Version")
        for r in items:
            table.add_row(
                r.skill_id,
                r.skill_name or "",
                r.skill_status or "",
                r.version or "",
            )
        console.print(table)
    except Exception as e:
        _print_api_error("ListSkillsBySkillSpace", e)
        raise typer.Exit(1)


@space_app.command("skills-basic")
def list_space_skills_basic_command(
    space_id: Optional[str] = typer.Option(None, "--space-id", help="SkillSpace ID"),
    space_name: Optional[str] = typer.Option(
        None, "--space-name", help="SkillSpace name"
    ),
    output: str = typer.Option(
        "table", "--output", "-o", help="Output: table|json|yaml"
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
    """List Skills in a SkillSpace (agent view: name/description)."""
    if not space_id and not space_name:
        raise typer.BadParameter("--space-id or --space-name is required")
    if space_id and space_name:
        raise typer.BadParameter("Provide only one of --space-id or --space-name")
    try:
        client = AgentkitSkillsClient(region=(region or "").strip())
        if space_id:
            resp = client.list_skills_by_space_id(
                skills_types.ListSkillsBySpaceIdRequest(
                    skill_space_id=space_id,
                    skill_space_name="",
                )
            )
        else:
            resp = client.list_skills_by_space_name(
                skills_types.ListSkillsBySpaceNameRequest(
                    skill_space_name=space_name or ""
                )
            )
        items = resp.items or []

        fmt = (output or "table").lower().strip()
        if fmt in {"json", "yaml"}:
            data = {
                "TotalCount": len(items),
                "Items": [
                    i.model_dump(by_alias=True, exclude_none=True) for i in items
                ],
            }
            _dump_output(data, fmt)
            return

        table = Table(title="SkillSpace Skills (Basic)")
        table.add_column("Name", style="green")
        table.add_column("Description")
        for s in items:
            table.add_row(s.name, s.description)
        console.print(table)
    except Exception as e:
        _print_api_error("ListSkillsBySpaceId/Name", e)
        raise typer.Exit(1)


@space_app.command("publish")
def publish_to_space_command(
    space_ids: List[str] = typer.Option(..., "--space-id", help="Repeatable. Space ID"),
    skill_id: str = typer.Option(..., "--skill-id", help="Skill ID"),
    version: str = typer.Option(..., "--version", help="Skill version to publish"),
    region: Optional[str] = typer.Option(
        None,
        "--region",
        help=(
            "Region override for this command (e.g. cn-beijing, cn-shanghai). "
            "Defaults to VOLCENGINE_AGENTKIT_REGION/VOLCENGINE_REGION/global config."
        ),
    ),
):
    """Publish a Skill version to one or more SkillSpaces."""
    try:
        client = AgentkitSkillsClient(region=(region or "").strip())
        client.publish_skill_to_skill_space(
            skills_types.PublishSkillToSkillSpaceRequest(
                skill_spaces=space_ids,
                skills=[
                    skills_types.SkillBasicInfo(skill_id=skill_id, version=version)
                ],
            )
        )
        console.print(
            Panel.fit(
                f"[green]✅ Published[/green]\nSkillId: {skill_id}\nVersion: {version}\nSpaces: {len(space_ids)}",
                title="PublishSkillToSkillSpace",
                border_style="green",
            )
        )
    except Exception as e:
        _print_api_error("PublishSkillToSkillSpace", e)
        raise typer.Exit(1)


@space_app.command("remove")
def remove_from_space_command(
    space_id: str = typer.Option(..., "--space-id", help="SkillSpace ID"),
    skill_id: str = typer.Option(..., "--skill-id", help="Skill ID"),
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
    """Remove a Skill from a SkillSpace."""
    if not force:
        typer.confirm(
            f"Remove Skill {skill_id} from SkillSpace {space_id}?",
            abort=True,
        )
    try:
        client = AgentkitSkillsClient(region=(region or "").strip())
        client.remove_skill_from_skill_space(
            skills_types.RemoveSkillFromSkillSpaceRequest(
                skill_id=skill_id,
                skill_space_id=space_id,
            )
        )
        console.print(
            Panel.fit(
                f"[green]✅ Removed[/green]\nSkillId: {skill_id}\nSkillSpaceId: {space_id}",
                title="RemoveSkillFromSkillSpace",
                border_style="green",
            )
        )
    except Exception as e:
        _print_api_error("RemoveSkillFromSkillSpace", e)
        raise typer.Exit(1)


skills_app.add_typer(space_app, name="space")
add_workflow_commands(skills_app)
