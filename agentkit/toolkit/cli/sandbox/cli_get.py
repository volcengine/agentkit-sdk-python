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

"""Get command for sandbox CLI."""

from __future__ import annotations

from typing import Optional

import typer

from agentkit.toolkit.cli.sandbox.agentkit_client import AgentkitToolsClient
from agentkit.toolkit.cli.sandbox.config_store import (
    SandboxConfigError,
    config_default_str,
    configured_sandbox_config,
    param_was_provided,
)
from agentkit.toolkit.cli.sandbox.session_create import SANDBOX_TOOL_ID_ENV
from agentkit.toolkit.cli.sandbox.session_sync import sync_remote_sessions
from agentkit.toolkit.cli.sandbox.tool_resolve import SandboxToolType
from agentkit.toolkit.cli.sandbox.sandbox_client import (
    echo_json,
    error,
    find_session_result,
    get_all_session_results,
)


def _session_not_found_result(
    *,
    session_id: str,
    tool_id: object,
) -> dict[str, object]:
    return {
        "tool_id": tool_id,
        "session_id": session_id,
        "error_msg": f"Sandbox session not found: {session_id}",
    }


def get_command(
    ctx: typer.Context,
    session_id: Optional[str] = typer.Option(
        None,
        "--session-id",
        "--sid",
        "-s",
        help=(
            "Sandbox session ID to look up. Omit to return all local "
            "sandbox sessions after syncing the current tool."
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
) -> None:
    """Get a sandbox session after syncing remote sessions for the current tool."""
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
        resolved_tool_id = sync_remote_sessions(
            session_id=session_id,
            tool_id=tool_id,
            tool_name=tool_name,
            tool_type=tool_type,
            client=AgentkitToolsClient(),
            env_var_name=SANDBOX_TOOL_ID_ENV,
        )
        result = (
            find_session_result(resolved_tool_id, session_id)
            if session_id and resolved_tool_id
            else None
        )
        if not session_id:
            result = get_all_session_results()
    except typer.Exit:
        raise
    except (SandboxConfigError, ValueError) as exc:
        error(str(exc))
    except Exception as exc:
        error(str(exc))

    if session_id and result is None:
        echo_json(
            _session_not_found_result(
                session_id=session_id,
                tool_id=resolved_tool_id or tool_id,
            )
        )
        raise typer.Exit(1)

    if session_id and resolved_tool_id and result.get("tool_id") != resolved_tool_id:
        echo_json(
            _session_not_found_result(
                session_id=session_id,
                tool_id=resolved_tool_id,
            )
        )
        raise typer.Exit(1)

    echo_json(result)
