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

from typing import Optional, List, Dict
import os
import zipfile
import tempfile
import hashlib
import shutil
import sys

import typer
from rich.console import Console
from rich.panel import Panel

from agentkit.sdk.skills.client import AgentkitSkillsClient
from agentkit.sdk.skills import types as skills_types
from agentkit.toolkit.config import GlobalConfigManager, get_config

console = Console()


def _parse_skill_md_frontmatter(text: str) -> Dict[str, str]:
    lines = (text or "").splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError(
            "SKILL.md must start with a YAML frontmatter block (--- ... ---)"
        )
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        raise ValueError("SKILL.md frontmatter is not closed (missing terminating ---)")

    raw = "\n".join(lines[1:end_idx]).strip()
    data: Dict[str, str] = {}
    for ln in raw.splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        if ":" not in s:
            continue
        k, v = s.split(":", 1)
        key = k.strip()
        val = v.strip()
        if val.startswith(("'", '"')) and val.endswith(("'", '"')) and len(val) >= 2:
            val = val[1:-1]
        data[key] = val
    return data


def _validate_platform_frontmatter_raw(text: str) -> None:
    lines = (text or "").splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md must start with a frontmatter block (--- ... ---)")
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        raise ValueError("SKILL.md frontmatter is not closed (missing terminating ---)")

    raw_lines = lines[1:end_idx]
    for ln in raw_lines:
        s = (ln or "").strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("name:"):
            v = s.split(":", 1)[1].strip()
            if (v.startswith('"') and v.endswith('"')) or (
                v.startswith("'") and v.endswith("'")
            ):
                raise ValueError(
                    "SKILL.md frontmatter 'name' must not be quoted to match platform parsing"
                )
        if s.startswith("description:"):
            v = s.split(":", 1)[1].strip()
            if (v.startswith('"') and v.endswith('"')) or (
                v.startswith("'") and v.endswith("'")
            ):
                raise ValueError(
                    "SKILL.md frontmatter 'description' must not be quoted to match platform parsing"
                )


def _fix_platform_frontmatter_quotes(text: str) -> str:
    lines = (text or "").splitlines()
    if not lines or lines[0].strip() != "---":
        return text
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return text

    raw = lines[1:end_idx]
    fixed: List[str] = []
    for ln in raw:
        s = ln
        stripped = (ln or "").strip()
        if stripped.startswith("name:") or stripped.startswith("description:"):
            key, val = stripped.split(":", 1)
            v = val.strip()
            if (v.startswith('"') and v.endswith('"') and len(v) >= 2) or (
                v.startswith("'") and v.endswith("'") and len(v) >= 2
            ):
                v = v[1:-1]
            s = f"{key}: {v}"
        fixed.append(s)

    rebuilt = []
    rebuilt.extend(lines[:1])
    rebuilt.extend(fixed)
    rebuilt.extend(lines[end_idx:])
    return "\n".join(rebuilt) + ("\n" if text.endswith("\n") else "")


def _validate_skill_name(name: str) -> None:
    import re

    if not name:
        raise ValueError("Skill name is required in SKILL.md frontmatter: name")
    if len(name) > 64:
        raise ValueError("Skill name must be <= 64 characters")
    if "agentkit" in name:
        raise ValueError("Skill name must not contain reserved word: agentkit")
    if not re.fullmatch(r"[a-z0-9-]+", name):
        raise ValueError(
            "Skill name must match: [a-z0-9-]+ (lowercase letters, digits, hyphen)"
        )


def _validate_skill_description(desc: str) -> None:
    import re

    if not desc:
        raise ValueError(
            "Skill description is required in SKILL.md frontmatter: description"
        )
    if len(desc) > 1024:
        raise ValueError("Skill description must be <= 1024 characters")
    if re.search(r"<[^>]+>", desc):
        raise ValueError("Skill description must not contain XML tags")


def _load_skill_metadata(skill_dir: str) -> Dict[str, str]:
    skill_md_path = os.path.join(skill_dir, "SKILL.md")
    if not os.path.exists(skill_md_path):
        raise FileNotFoundError(f"SKILL.md not found: {skill_md_path}")
    with open(skill_md_path, "r", encoding="utf-8") as f:
        text = f.read()
    _validate_platform_frontmatter_raw(text)
    meta = _parse_skill_md_frontmatter(text)
    name = (meta.get("name") or "").strip()
    description = (meta.get("description") or "").strip()
    _validate_skill_name(name)
    _validate_skill_description(description)
    return {"name": name, "description": description}


def _zip_skill_dir(skill_dir: str, skill_name: str, out_zip: str) -> str:
    base_dir = os.path.abspath(skill_dir)
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(base_dir):
            for fn in files:
                src = os.path.join(root, fn)
                rel = os.path.relpath(src, base_dir)
                arc = os.path.join(skill_name, rel)
                zf.write(src, arcname=arc)
    return out_zip


def _sha256_file_hex(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _make_content_hashed_zip_copy(zip_abs: str, skill_name: str, out_dir: str) -> str:
    digest = _sha256_file_hex(zip_abs)[:8]
    out_zip = os.path.join(out_dir, f"{skill_name}-{digest}.zip")
    shutil.copyfile(zip_abs, out_zip)
    return out_zip


def _is_interactive() -> bool:
    if os.environ.get("CI"):
        return False
    try:
        return sys.stdin.isatty()
    except Exception:
        return False


def _render_bucket_template_or_raise(bucket_name: str) -> str:
    if not bucket_name:
        return bucket_name
    if "{{" not in bucket_name or "}}" not in bucket_name:
        return bucket_name
    from agentkit.utils.template_utils import render_template

    rendered = render_template(bucket_name)
    if "{{" in rendered and "}}" in rendered:
        raise ValueError(
            f"TOS bucket name template not fully rendered, contains unresolved variables: {rendered}"
        )
    return rendered


def _ensure_bucket_ready(
    *,
    bucket_name: str,
    prefix: str,
    region: str,
    auto_bucket: bool,
    assume_yes: bool,
    assume_no: bool,
) -> None:
    from agentkit.toolkit.volcengine.services.tos_service import (
        TOSService,
        TOSServiceConfig,
    )

    service = TOSService(
        TOSServiceConfig(
            region=(region or "").strip(),
            bucket=bucket_name.strip(),
            prefix=(prefix or "").strip(),
        )
    )

    exists = service.bucket_exists()
    created_in_this_run = False
    if not exists:
        if assume_no:
            raise typer.BadParameter(f"TOS bucket not found: {bucket_name}")
        if auto_bucket or assume_yes:
            service.create_bucket()
            created_in_this_run = True
        else:
            if _is_interactive():
                typer.confirm(
                    f"TOS bucket '{bucket_name}' not found. Create it in current account?",
                    abort=True,
                )
                service.create_bucket()
                created_in_this_run = True
            else:
                raise typer.BadParameter(
                    f"TOS bucket '{bucket_name}' not found. Use -y/--yes to create it automatically."
                )

    def check_owned() -> bool:
        try:
            return service.bucket_is_owned(bucket_name)
        except Exception as e:
            raise typer.BadParameter(
                "Failed to determine TOS bucket ownership via ListBuckets. "
                "Upload has been blocked for security reasons. "
                "Please ensure your credentials have TOS ListBuckets permission, or configure a bucket you own."
            ) from e

    if created_in_this_run:
        import time

        deadline = time.time() + 10
        while time.time() < deadline:
            if check_owned():
                break
            time.sleep(2)
        else:
            raise typer.BadParameter(
                f"Failed to verify ownership for newly created TOS bucket: {bucket_name}"
            )
    else:
        if not check_owned():
            raise typer.BadParameter(
                f"Security notice: The configured TOS bucket '{bucket_name}' is not owned by the current account. "
                "To prevent uploading your code to a bucket you do not own, this upload has been blocked."
            )


def _tos_upload(
    zip_abs: str,
    bucket: str,
    prefix: str,
    region: str,
    *,
    verify_bucket: bool = True,
) -> str:
    try:
        from agentkit.toolkit.volcengine.services.tos_service import (
            TOSService,
            TOSServiceConfig,
        )
    except ImportError as e:
        raise typer.BadParameter(str(e))

    effective_prefix = (prefix or "").strip() or "agentkit/skills"
    basename = os.path.basename(zip_abs)
    key = f"{effective_prefix.rstrip('/')}/{basename}"

    service = TOSService(
        TOSServiceConfig(
            region=(region or "").strip(),
            bucket=bucket.strip(),
            prefix=effective_prefix,
        )
    )
    if verify_bucket:
        if not service.bucket_exists():
            raise typer.BadParameter(f"Bucket not found: {bucket}")
        if not service.bucket_is_owned(bucket):
            raise typer.BadParameter(
                f"Bucket is not owned by current credentials: {bucket}"
            )
    return service.upload_file(zip_abs, key)


def _pick_latest_version(
    items: List[skills_types.SkillVersionWithRelation],
) -> skills_types.SkillVersionWithRelation:
    if not items:
        raise ValueError("No Skill versions found")
    latest = items[0]
    for v in items[1:]:
        try:
            if int(v.update_time_stamp) > int(latest.update_time_stamp):
                latest = v
        except Exception:
            if (v.update_time_stamp or "") > (latest.update_time_stamp or ""):
                latest = v
    return latest


def _wait_for_running_version(
    client: AgentkitSkillsClient,
    skill_id: str,
    timeout_seconds: int,
    poll_interval_seconds: int,
) -> skills_types.SkillVersionWithRelation:
    import time

    start = time.time()
    while True:
        resp = client.list_skill_versions(
            skills_types.ListSkillVersionsRequest(
                id=skill_id, page_number=1, page_size=50
            )
        )
        latest = _pick_latest_version(resp.items or [])
        status = (latest.status or "").lower()
        if status == "running":
            return latest
        if status == "failed":
            raise ValueError(latest.error_message or "Skill version failed")
        if time.time() - start >= timeout_seconds:
            raise TimeoutError(
                f"Timed out waiting for Skill version to become running. Last status: {latest.status} ({latest.version})"
            )
        time.sleep(max(1, int(poll_interval_seconds)))


def add_workflow_commands(app: typer.Typer) -> None:
    @app.command("init", help="Initialize a local Skill directory (creates SKILL.md).")
    def init_skill_command(
        skill_name: str = typer.Argument(
            ..., help="Skill directory name and Skill name"
        ),
        description: str = typer.Option(
            "A reusable skill for AgentKit agents.",
            "--description",
            help="Default description to write into SKILL.md",
        ),
        path: str = typer.Option(
            ".", "--path", help="Base directory to create the Skill in"
        ),
    ):
        """Initialize a local Skill directory and generate a platform-compatible SKILL.md."""
        skill_name_clean = (skill_name or "").strip()
        _validate_skill_name(skill_name_clean)
        _validate_skill_description((description or "").strip())

        base = os.path.abspath(path)
        target = os.path.join(base, skill_name_clean)
        os.makedirs(target, exist_ok=False)

        desc_clean = (description or "").strip()
        skill_md = "\n".join(
            [
                "---",
                f"name: {skill_name_clean}",
                f"description: {desc_clean}",
                "---",
                "",
                f"# {skill_name_clean}",
                "",
                "Describe what this Skill does and how the agent should use it.",
                "",
            ]
        )
        with open(os.path.join(target, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write(skill_md)

        console.print(
            Panel.fit(
                f"[green]✅ Initialized[/green]\nPath: {target}",
                title="Skills Init",
                border_style="green",
            )
        )

    @app.command("validate", help="Validate a local Skill directory (checks SKILL.md).")
    def validate_skill_command(
        path: str = typer.Option(".", "--path", help="Local Skill directory path"),
        fix_frontmatter: bool = typer.Option(
            False,
            "--fix-frontmatter",
            help="Fix quoted name/description in SKILL.md frontmatter to match platform parsing",
        ),
        allow_root_mismatch: bool = typer.Option(
            False,
            "--allow-root-mismatch",
            help="Allow directory name to differ from SKILL.md name",
        ),
    ):
        """Validate SKILL.md frontmatter and local directory layout for AgentKit Skills."""
        skill_dir = os.path.abspath(path)
        if fix_frontmatter:
            skill_md_path = os.path.join(skill_dir, "SKILL.md")
            with open(skill_md_path, "r", encoding="utf-8") as f:
                original = f.read()
            fixed = _fix_platform_frontmatter_quotes(original)
            if fixed != original:
                with open(skill_md_path, "w", encoding="utf-8") as f:
                    f.write(fixed)
        meta = _load_skill_metadata(skill_dir)
        dir_name = os.path.basename(skill_dir)
        if not allow_root_mismatch and dir_name != meta["name"]:
            raise typer.BadParameter(
                f"Skill directory name must match SKILL.md name: dir='{dir_name}', name='{meta['name']}'"
            )
        console.print(
            Panel.fit(
                f"[green]✅ Valid[/green]\nName: {meta['name']}\nDescription: {meta['description']}",
                title="Skills Validate",
                border_style="green",
            )
        )

    @app.command("pack", help="Package a local Skill directory into a ZIP file.")
    def pack_skill_command(
        path: str = typer.Option(".", "--path", help="Local Skill directory path"),
        out: Optional[str] = typer.Option(None, "--out", help="Output zip path"),
        allow_root_mismatch: bool = typer.Option(
            False,
            "--allow-root-mismatch",
            help="Allow directory name to differ from SKILL.md name",
        ),
    ):
        """Create a Skill ZIP with a single root directory (skill-name/...)."""
        skill_dir = os.path.abspath(path)
        meta = _load_skill_metadata(skill_dir)
        dir_name = os.path.basename(skill_dir)
        if not allow_root_mismatch and dir_name != meta["name"]:
            raise typer.BadParameter(
                f"Skill directory name must match SKILL.md name: dir='{dir_name}', name='{meta['name']}'"
            )
        out_zip = (
            os.path.abspath(out)
            if out
            else os.path.join(os.getcwd(), f"{meta['name']}.zip")
        )
        _zip_skill_dir(skill_dir, meta["name"], out_zip)
        console.print(
            Panel.fit(
                f"[green]✅ Packed[/green]\nZip: {out_zip}",
                title="Skills Pack",
                border_style="green",
            )
        )

    @app.command("upload", help="Upload a Skill ZIP to TOS and print its TOS URL.")
    def upload_skill_command(
        zip_path: str = typer.Option(..., "--zip", help="Skill ZIP file path"),
        bucket: Optional[str] = typer.Option(None, "--bucket", help="TOS bucket name"),
        prefix: Optional[str] = typer.Option(
            None, "--prefix", help="TOS object key prefix"
        ),
        region: Optional[str] = typer.Option(
            None,
            "--region",
            help=(
                "Region override for this command (e.g. cn-beijing, cn-shanghai). "
                "Defaults to VOLCENGINE_REGION/global config."
            ),
        ),
    ):
        """Upload a ZIP to TOS after verifying bucket existence and ownership."""
        global_cfg = GlobalConfigManager().load()
        effective_bucket = (bucket or global_cfg.tos.bucket or "").strip()
        effective_prefix = (prefix or global_cfg.tos.prefix or "").strip()
        if not effective_bucket:
            raise typer.BadParameter(
                "--bucket is required (or configure ~/.agentkit/config.yaml tos.bucket)"
            )
        zip_abs = os.path.abspath(zip_path)
        tos_url = _tos_upload(
            zip_abs, effective_bucket, effective_prefix, (region or "").strip()
        )
        console.print(tos_url)

    @app.command(
        "push",
        help="Package, upload to TOS, create/update the Skill, and publish it to SkillSpaces.",
    )
    def push_skill_command(
        path: str = typer.Option(".", "--path", help="Local Skill directory path"),
        space_ids: List[str] = typer.Option(
            ..., "--space-id", help="Repeatable. SkillSpace ID to publish to"
        ),
        project_name: Optional[str] = typer.Option(
            None, "--project-name", help="Project"
        ),
        skill_id: Optional[str] = typer.Option(
            None, "--skill-id", help="Skill ID (update)"
        ),
        create_only: bool = typer.Option(
            False, "--create-only", help="Fail if Skill exists"
        ),
        update_only: bool = typer.Option(
            False, "--update-only", help="Fail if Skill does not exist"
        ),
        bucket: Optional[str] = typer.Option(
            None,
            "--bucket",
            help="TOS bucket name (optional). Defaults to agentkit-platform-{{account_id}} when not configured.",
        ),
        prefix: Optional[str] = typer.Option(
            None, "--prefix", help="TOS object key prefix"
        ),
        region: Optional[str] = typer.Option(
            None,
            "--region",
            help=(
                "Region override for this command (e.g. cn-beijing, cn-shanghai). "
                "Defaults to VOLCENGINE_AGENTKIT_REGION/VOLCENGINE_REGION/global config."
            ),
        ),
        wait_timeout: int = typer.Option(
            300,
            "--wait-timeout",
            help="Wait timeout seconds for the latest Skill version to become running before publish",
        ),
        poll_interval: int = typer.Option(
            5,
            "--poll-interval",
            help="Polling interval seconds when waiting for Skill version status",
        ),
        assume_yes: bool = typer.Option(
            False,
            "--yes",
            "-y",
            help="Assume yes for prompts (e.g., create missing bucket). Useful for automation.",
        ),
        assume_no: bool = typer.Option(
            False,
            "--no",
            "--assume-no",
            help="Assume no for prompts (never create missing bucket).",
        ),
    ):
        """End-to-end flow: validate, zip, upload, create/update, wait running, and publish."""
        if create_only and update_only:
            raise typer.BadParameter(
                "--create-only and --update-only cannot be used together"
            )
        if assume_yes and assume_no:
            raise typer.BadParameter("--yes and --no cannot be used together")

        skill_dir = os.path.abspath(path)
        meta = _load_skill_metadata(skill_dir)
        dir_name = os.path.basename(skill_dir)
        if dir_name != meta["name"]:
            raise typer.BadParameter(
                f"Skill directory name must match SKILL.md name: dir='{dir_name}', name='{meta['name']}'"
            )

        global_cfg = GlobalConfigManager().load()
        raw_bucket = (bucket or global_cfg.tos.bucket or "").strip()
        effective_prefix = (prefix or global_cfg.tos.prefix or "").strip()
        auto_bucket = False
        if raw_bucket:
            try:
                effective_bucket = _render_bucket_template_or_raise(raw_bucket)
            except Exception as e:
                raise typer.BadParameter(str(e)) from e
        else:
            auto_bucket = True
            try:
                from agentkit.toolkit.volcengine.services.tos_service import TOSService

                effective_bucket = TOSService.generate_bucket_name()
            except Exception as e:
                raise typer.BadParameter(
                    f"Failed to auto-generate TOS bucket name from template: {e}"
                ) from e

        _ensure_bucket_ready(
            bucket_name=effective_bucket,
            prefix=effective_prefix,
            region=(region or "").strip(),
            auto_bucket=auto_bucket,
            assume_yes=assume_yes,
            assume_no=assume_no,
        )

        with tempfile.TemporaryDirectory() as td:
            zip_out = os.path.join(td, f"{meta['name']}.zip")
            _zip_skill_dir(skill_dir, meta["name"], zip_out)
            zip_hashed = _make_content_hashed_zip_copy(zip_out, meta["name"], td)
            tos_url = _tos_upload(
                zip_hashed,
                effective_bucket,
                effective_prefix,
                (region or "").strip(),
                verify_bucket=False,
            )

            client = AgentkitSkillsClient(region=(region or "").strip())
            effective_skill_id = (skill_id or "").strip() or None

            if not effective_skill_id:
                resp = client.list_skills(
                    skills_types.ListSkillsRequest(
                        page_number=1,
                        page_size=50,
                        filter=skills_types.SkillFilter(name=meta["name"]),
                        project_name=project_name,
                    )
                )
                matches = resp.items or []
                if create_only and matches:
                    raise typer.BadParameter(
                        f"Skill already exists with name '{meta['name']}'. Use --skill-id to update or omit --create-only."
                    )
                if update_only and not matches:
                    raise typer.BadParameter(
                        f"Skill not found with name '{meta['name']}'. Omit --update-only to create."
                    )
                if len(matches) > 1:
                    raise typer.BadParameter(
                        f"Multiple Skills found with name '{meta['name']}'. Use --skill-id."
                    )
                if len(matches) == 1:
                    effective_skill_id = matches[0].id

            if effective_skill_id:
                client.update_skill(
                    skills_types.UpdateSkillRequest(
                        id=effective_skill_id,
                        name=meta["name"],
                        description=meta["description"],
                        tos_url=tos_url,
                        skill_spaces=space_ids,
                        bucket_name=effective_bucket,
                    )
                )
            else:
                created = client.create_skill(
                    skills_types.CreateSkillRequest(
                        name=meta["name"],
                        description=meta["description"],
                        tos_url=tos_url,
                        skill_spaces=space_ids,
                        bucket_name=effective_bucket,
                        project_name=project_name,
                    )
                )
                effective_skill_id = created.id

            latest = _wait_for_running_version(
                client=client,
                skill_id=effective_skill_id,
                timeout_seconds=int(wait_timeout),
                poll_interval_seconds=int(poll_interval),
            )

            client.publish_skill_to_skill_space(
                skills_types.PublishSkillToSkillSpaceRequest(
                    skill_spaces=space_ids,
                    skills=[
                        skills_types.SkillBasicInfo(
                            skill_id=effective_skill_id, version=latest.version
                        )
                    ],
                )
            )

            console.print(
                Panel.fit(
                    "\n".join(
                        [
                            "[green]✅ Pushed[/green]",
                            f"SkillId: {effective_skill_id}",
                            f"Version: {latest.version}",
                            f"SkillSpaces: {len(space_ids)}",
                            f"TosUrl: {tos_url}",
                        ]
                    ),
                    title="Skills Push",
                    border_style="green",
                )
            )

    @app.command("bind", help="Bind a SkillSpace ID into agentkit.yaml runtime_envs.")
    def bind_skillspace_command(
        space_id: str = typer.Option(..., "--space-id", help="SkillSpace ID"),
        tool_id: Optional[str] = typer.Option(
            None, "--tool-id", help="Skills Sandbox Tool ID (AGENTKIT_TOOL_ID)"
        ),
        config_path: str = typer.Option(
            "agentkit.yaml", "--config", help="Path to agentkit.yaml"
        ),
    ):
        """Write SKILL_SPACE_ID (and optional AGENTKIT_TOOL_ID) into agentkit.yaml runtime_envs."""
        mgr = get_config(config_path, force_reload=True)
        runtime_envs = mgr.get_raw_value("common.runtime_envs", default={}) or {}
        if not isinstance(runtime_envs, dict):
            raise typer.BadParameter(
                "common.runtime_envs must be a mapping in agentkit.yaml"
            )
        runtime_envs = runtime_envs.copy()
        runtime_envs["SKILL_SPACE_ID"] = space_id.strip()
        if tool_id:
            runtime_envs["AGENTKIT_TOOL_ID"] = tool_id.strip()
        mgr.set_raw_value("common.runtime_envs", runtime_envs)
        console.print(
            Panel.fit(
                f"[green]✅ Bound[/green]\nSKILL_SPACE_ID={space_id.strip()}",
                title="Skills Bind",
                border_style="green",
            )
        )
