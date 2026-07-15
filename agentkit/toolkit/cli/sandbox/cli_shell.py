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

"""Shell command for sandbox CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import requests
import typer

from agentkit.toolkit.cli.sandbox.config_store import (
    SandboxConfigError,
    config_default_str,
    configured_sandbox_config,
    param_was_provided,
)
from agentkit.toolkit.cli.sandbox.cli_exec import (
    _collect_exec_upload_sources,
    _upload_source_before_exec,
)
from agentkit.toolkit.cli.sandbox.session_create import (
    SANDBOX_TOOL_ID_ENV,
    ensure_sandbox_session,
)
from agentkit.toolkit.cli.sandbox.git_config import apply_git_config_to_session
from agentkit.toolkit.cli.sandbox.tos_config import DEFAULT_SANDBOX_WORKSPACE
from agentkit.toolkit.cli.sandbox.tool_resolve import SandboxToolType
from agentkit.toolkit.cli.sandbox.sandbox_client import (
    SANDBOX_EXEC_TIMEOUT_SECONDS,
    build_exec_url,
    echo_json,
    error,
    rename_exec_session_id,
)


def shell_command(
    ctx: typer.Context,
    session_id: Optional[str] = typer.Option(
        None,
        "--session-id",
        "--sid",
        "-s",
        help=(
            "Sandbox session ID. Defaults to a generated UUID and creates "
            "a sandbox session when needed."
        ),
    ),
    tool_id: Optional[str] = typer.Option(
        None,
        "--tool-id",
        help=f"Sandbox tool ID. Defaults to {SANDBOX_TOOL_ID_ENV}.",
    ),
    tool_name: Optional[str] = typer.Option(
        None,
        "--tool-name",
        help="Sandbox tool name. Resolved with ListTools(Name=...).",
    ),
    tool_type: SandboxToolType = typer.Option(
        SandboxToolType.CODE_ENV,
        "--tool-type",
        help="Sandbox tool type to resolve when tool id/name is omitted.",
    ),
    command: str = typer.Option(
        ...,
        "--command",
        help="Command to execute.",
    ),
    exec_dir: Optional[str] = typer.Option(
        None,
        "--exec-dir",
        help="Execution directory.",
    ),
    workspace: str = typer.Option(
        DEFAULT_SANDBOX_WORKSPACE,
        "--workspace",
        help=(
            "Sandbox workspace root. Relative --dst-dir values are "
            "resolved inside this directory."
        ),
    ),
    src_dir: Optional[Path] = typer.Option(
        None,
        "--src-dir",
        help=("Local file or directory to upload before executing the command."),
    ),
    dst_dir: Optional[str] = typer.Option(
        None,
        "--dst-dir",
        help=(
            "Relative sandbox destination directory for --src-dir. Defaults "
            "to --workspace."
        ),
    ),
    git_config: Optional[str] = typer.Option(
        None,
        "--git-config",
        help=(
            "Git identity source. Use 'local' to read local git config, or "
            "provide an INI/TOML/JSON file path with user.name and user.email."
        ),
    ),
) -> None:
    """Execute a command in a sandbox shell."""
    try:
        config_defaults = configured_sandbox_config()
        if not param_was_provided(ctx, "session_id"):
            session_id = (
                config_default_str("session-id", data=config_defaults) or session_id
            )
        if not param_was_provided(ctx, "tool_id") and not param_was_provided(
            ctx, "tool_name"
        ):
            tool_id = config_default_str("tool-id", data=config_defaults) or tool_id
        if not param_was_provided(ctx, "tool_type"):
            configured_tool_type = config_default_str(
                "tool-type",
                data=config_defaults,
            )
            if configured_tool_type:
                tool_type = SandboxToolType(configured_tool_type)
        if not param_was_provided(ctx, "workspace"):
            workspace = (
                config_default_str("workspace", data=config_defaults) or workspace
            )
        if not param_was_provided(ctx, "dst_dir"):
            dst_dir = config_default_str("dst-dir", data=config_defaults) or dst_dir
        if not param_was_provided(ctx, "git_config"):
            git_config = (
                config_default_str("git-config", data=config_defaults) or git_config
            )
        session = ensure_sandbox_session(
            session_id=session_id,
            tool_id=tool_id,
            tool_name=tool_name,
            tool_type=tool_type.value,
        )
    except typer.Exit:
        raise
    except (SandboxConfigError, ValueError) as exc:
        error(str(exc))
    except Exception as exc:
        error(str(exc))

    try:
        src_dirs = _collect_exec_upload_sources(ctx, src_dir)
        if src_dirs:
            _upload_source_before_exec(
                session,
                workspace=workspace,
                src_dirs=src_dirs,
                dst_dir=dst_dir,
            )
    except typer.Exit:
        raise
    except Exception as exc:
        error(str(exc))

    try:
        apply_git_config_to_session(
            session,
            git_config,
        )
    except typer.Exit:
        raise
    except Exception as exc:
        error(str(exc))

    url = build_exec_url(session.get("endpoint"))
    body = {
        "id": "",
        "exec_dir": exec_dir or "",
        "command": command,
    }

    try:
        response = requests.post(
            url,
            json=body,
            timeout=SANDBOX_EXEC_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        error(str(exc))

    try:
        payload = response.json()
    except ValueError:
        error(f"Invalid sandbox exec response: {response.text}")

    echo_json(rename_exec_session_id(payload))
