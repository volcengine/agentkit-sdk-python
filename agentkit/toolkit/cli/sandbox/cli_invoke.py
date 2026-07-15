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

"""A2A invoke command for sandbox CLI."""

from __future__ import annotations

import os
from typing import Any, Optional

import typer

from agentkit.toolkit.cli.sandbox.a2a_client import (
    DEFAULT_A2A_HISTORY_LENGTH,
    DEFAULT_A2A_PATH,
    DEFAULT_A2A_POLL_INTERVAL_SECONDS,
    DEFAULT_A2A_TIMEOUT_SECONDS,
    A2AApiError,
    poll_task_until_terminal,
    send_message_nonblocking,
    task_context_id,
    task_result_text,
    task_state,
)
from agentkit.toolkit.cli.sandbox.config_store import (
    SandboxConfigError,
    config_default_int,
    config_default_str,
    configured_sandbox_config,
    param_was_provided,
)
from agentkit.toolkit.cli.sandbox.env_config import (
    MODEL_AGENT_ENV_KEYS as _MODEL_AGENT_ENV_KEYS,
    build_invoke_session_envs as build_invoke_model_agent_envs,
)
from agentkit.toolkit.cli.sandbox.agentkit_client import AgentkitToolsClient
from agentkit.toolkit.cli.sandbox.session_create import (
    SANDBOX_TOOL_ID_ENV,
    ensure_sandbox_session,
)
from agentkit.toolkit.cli.sandbox.sandbox_client import echo_json, error
from agentkit.toolkit.cli.sandbox.tool_resolve import (
    SandboxToolType,
    resolve_existing_sandbox_tool_id,
)

MODEL_AGENT_ENV_KEYS = _MODEL_AGENT_ENV_KEYS


def _resolve_invoke_tool_id(
    *,
    tool_id: Optional[str],
    tool_name: Optional[str],
    tool_type: SandboxToolType,
) -> str:
    explicit_tool_id = (tool_id or "").strip()
    explicit_tool_name = (tool_name or "").strip()
    if explicit_tool_id and explicit_tool_name:
        error("Specify only one of --tool-id or --tool-name.")
    if explicit_tool_id:
        return explicit_tool_id
    if explicit_tool_name:
        resolved_tool_id = resolve_existing_sandbox_tool_id(
            tool_id=None,
            tool_name=explicit_tool_name,
            tool_type=tool_type,
            client=AgentkitToolsClient(),
            env_var_name=SANDBOX_TOOL_ID_ENV,
        )
        if not resolved_tool_id:
            error(f"Sandbox tool not found by name: {explicit_tool_name}")
        return resolved_tool_id

    env_tool_id = (os.getenv(SANDBOX_TOOL_ID_ENV) or "").strip()
    if env_tool_id:
        return env_tool_id

    return tool_type.value


def _task_failure_error(task: dict[str, Any]) -> dict[str, str]:
    state = task_state(task) or "unknown"
    message = _status_message_text(task) or f"Sandbox task ended with state: {state}"
    return {
        "type": "SandboxTaskFailed",
        "message": message,
    }


def _status_message_text(task: dict[str, Any]) -> str:
    status = task.get("status")
    if not isinstance(status, dict):
        return ""
    message = status.get("message")
    if not isinstance(message, dict):
        return ""
    parts = message.get("parts")
    if not isinstance(parts, list):
        return ""
    texts = [
        part["text"]
        for part in parts
        if isinstance(part, dict)
        and part.get("kind") == "text"
        and isinstance(part.get("text"), str)
        and part["text"]
    ]
    return "\n".join(texts)


def _task_output(
    *,
    task: dict[str, Any],
    session: dict[str, object],
    source: str,
) -> dict[str, Any]:
    state = task_state(task)
    output: dict[str, Any] = {
        "ok": state == "completed",
        "task_state": state,
        "error": None,
        "task_id": task.get("id"),
        "context_id": task_context_id(task),
        "final_result": task_result_text(task),
        "session_id": session.get("session_id"),
        "tool_id": session.get("tool_id"),
        "sandbox": {
            "available": True,
            "endpoint": session.get("endpoint"),
        },
        "source": source,
    }
    if state != "completed":
        output["error"] = _task_failure_error(task)
        if not output["final_result"]:
            output["final_result"] = None
    return output


def _task_created_output(
    *,
    task: dict[str, Any],
    task_id: str,
    context_id: str | None,
    session: dict[str, object],
) -> dict[str, Any]:
    return {
        "ok": True,
        "status": "success",
        "task_id": task_id,
        "task_state": task_state(task),
        "context_id": context_id,
        "session_id": session.get("session_id"),
        "tool_id": session.get("tool_id"),
        "sandbox": {
            "available": True,
            "endpoint": session.get("endpoint"),
        },
        "source": "sandbox-invoke",
    }


def _error_payload(exc: Exception) -> dict[str, Any]:
    error_payload: dict[str, Any] = {
        "type": type(exc).__name__,
        "message": str(exc),
    }
    if isinstance(exc, A2AApiError):
        error_payload = {
            "type": type(exc).__name__,
            "operation": exc.operation,
            "message": str(exc),
            "status_code": exc.status_code,
        }
        if exc.response_json is not None:
            error_payload["response"] = exc.response_json
        elif exc.response_text is not None:
            error_payload["response"] = exc.response_text
    return {
        "ok": False,
        "status": "error",
        "error": error_payload,
        "task_id": None,
        "sandbox": {"available": False, "endpoint": None},
        "source": "sandbox-invoke",
    }


def _normalize_timeout(timeout: int) -> int:
    if timeout <= 0:
        error("--timeout must be greater than 0")
    return timeout


def _normalize_interval(interval: float) -> float:
    if interval <= 0:
        error("--interval must be greater than 0")
    return interval


def _resolve_async_mode(ctx: typer.Context, async_mode: bool) -> bool:
    args = list(ctx.args)
    if not args:
        return async_mode
    if len(args) == 1 and async_mode:
        value = args[0].strip().lower()
        if value in {"true", "1", "yes", "y", "on"}:
            return True
        if value in {"false", "0", "no", "n", "off"}:
            return False
    error(f"Unexpected argument: {args[0]}")


def invoke_command(
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
    prompt: Optional[str] = typer.Option(
        None,
        "--prompt",
        help="Prompt to send to the sandbox A2A agent.",
    ),
    tool_id: Optional[str] = typer.Option(
        None,
        "--tool-id",
        help=(
            f"Sandbox tool ID. Defaults to {SANDBOX_TOOL_ID_ENV}; when unset, "
            "--tool-type is used as the tool ID."
        ),
    ),
    tool_name: Optional[str] = typer.Option(
        None,
        "--tool-name",
        help="Sandbox tool name. Resolved with ListTools(Name=...).",
    ),
    tool_type: SandboxToolType = typer.Option(
        SandboxToolType.SKILL_ENV,
        "--tool-type",
        help="Sandbox tool type used as the fallback tool ID.",
    ),
    async_mode: bool = typer.Option(
        False,
        "--async",
        help="Return immediately after creating the A2A task.",
    ),
    task_id: Optional[str] = typer.Option(
        None,
        "--task-id",
        help="Poll an existing A2A task ID instead of creating a new task.",
    ),
    ttl: Optional[int] = typer.Option(
        None,
        "--ttl",
        help=(
            "Sandbox session TTL in seconds. Defaults to AGENTKIT_SANDBOX_TTL "
            "or the exec command default."
        ),
    ),
    model_name: Optional[str] = typer.Option(
        None,
        "--model-name",
        help="Model name to inject as MODEL_AGENT_NAME when creating a session.",
    ),
    model_provider: Optional[str] = typer.Option(
        None,
        "--model-provider",
        help="Model provider to inject as MODEL_AGENT_PROVIDER.",
    ),
    model_base_url: Optional[str] = typer.Option(
        None,
        "--model-base-url",
        help="Model API base URL to inject as MODEL_AGENT_API_BASE.",
    ),
    model_api_key: Optional[str] = typer.Option(
        None,
        "--model-api-key",
        help="Model API key to inject as MODEL_AGENT_API_KEY.",
    ),
    timeout: int = typer.Option(
        DEFAULT_A2A_TIMEOUT_SECONDS,
        "--timeout",
        help="Maximum seconds to wait for synchronous invoke or task polling.",
    ),
    interval: float = typer.Option(
        DEFAULT_A2A_POLL_INTERVAL_SECONDS,
        "--interval",
        help="Polling interval in seconds.",
    ),
    history_length: int = typer.Option(
        DEFAULT_A2A_HISTORY_LENGTH,
        "--history-length",
        help="A2A task history length to request.",
    ),
    a2a_path: str = typer.Option(
        DEFAULT_A2A_PATH,
        "--a2a-path",
        help="A2A JSON-RPC path on the sandbox endpoint.",
        hidden=True,
    ),
) -> None:
    """Invoke a sandbox A2A agent."""
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
        if not param_was_provided(ctx, "ttl"):
            ttl = config_default_int("ttl", data=config_defaults) or ttl
        if not param_was_provided(ctx, "model_name"):
            model_name = (
                config_default_str("model-name", data=config_defaults) or model_name
            )
        if not param_was_provided(ctx, "model_provider"):
            model_provider = (
                config_default_str("model-provider", data=config_defaults)
                or model_provider
            )
        if not param_was_provided(ctx, "model_base_url"):
            model_base_url = (
                config_default_str("model-base-url", data=config_defaults)
                or model_base_url
            )
        if not param_was_provided(ctx, "model_api_key"):
            model_api_key = (
                config_default_str("model-api-key", data=config_defaults)
                or model_api_key
            )

        resolved_task_id = (task_id or "").strip()
        resolved_prompt = (prompt or "").strip()
        resolved_async_mode = _resolve_async_mode(ctx, async_mode)
        if not resolved_task_id and not resolved_prompt:
            error("--prompt is required unless --task-id is provided")
        if ttl is not None and ttl <= 0:
            error("--ttl must be greater than 0")
        if history_length < 0:
            error("--history-length must be non-negative")

        resolved_timeout = _normalize_timeout(timeout)
        resolved_interval = _normalize_interval(interval)
        resolved_tool_id = _resolve_invoke_tool_id(
            tool_id=tool_id,
            tool_name=tool_name,
            tool_type=tool_type,
        )
        session = ensure_sandbox_session(
            session_id=session_id,
            tool_id=resolved_tool_id,
            tool_type=tool_type.value,
            ttl=ttl,
            envs=build_invoke_model_agent_envs(
                model_name=model_name,
                model_provider=model_provider,
                model_base_url=model_base_url,
                model_api_key=model_api_key,
            ),
            resolve_tool=False,
            include_tos_mount_points=False,
        )
    except typer.Exit:
        raise
    except (SandboxConfigError, ValueError) as exc:
        error(str(exc))
    except Exception as exc:
        error(str(exc))

    try:
        if resolved_task_id:
            task = poll_task_until_terminal(
                endpoint=session.get("endpoint"),
                task_id=resolved_task_id,
                a2a_path=a2a_path,
                history_length=history_length,
                timeout=resolved_timeout,
                interval=resolved_interval,
            )
            echo_json(_task_output(task=task, session=session, source="sandbox-invoke"))
            return

        task_start = send_message_nonblocking(
            endpoint=session.get("endpoint"),
            prompt=resolved_prompt,
            a2a_path=a2a_path,
            request_metadata={
                "session_id": str(session.get("session_id") or ""),
                "user_id": "agentkit-sandbox-invoke",
            },
            history_length=history_length,
            timeout=min(60, resolved_timeout),
        )
        if resolved_async_mode:
            echo_json(
                _task_created_output(
                    task=task_start.task,
                    task_id=task_start.task_id,
                    context_id=task_start.context_id,
                    session=session,
                )
            )
            return

        task = poll_task_until_terminal(
            endpoint=session.get("endpoint"),
            task_id=task_start.task_id,
            a2a_path=a2a_path,
            history_length=history_length,
            timeout=resolved_timeout,
            interval=resolved_interval,
        )
        echo_json(_task_output(task=task, session=session, source="sandbox-invoke"))
    except typer.Exit:
        raise
    except Exception as exc:
        echo_json(_error_payload(exc))
        raise typer.Exit(1) from exc
