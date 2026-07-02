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

import json
import os
from pathlib import Path
from typing import Any, Optional

import typer

from agentkit.sdk.tools import types as tools_types
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
from agentkit.toolkit.cli.sandbox.session_create import (
    SANDBOX_TOOL_ID_ENV,
    ensure_sandbox_session,
)
from agentkit.toolkit.cli.sandbox.sandbox_client import echo_json, error
from agentkit.toolkit.cli.sandbox.tool_resolve import SandboxToolType

MODEL_AGENT_ENV_KEYS = (
    "MODEL_AGENT_API_BASE",
    "MODEL_AGENT_API_KEY",
    "MODEL_AGENT_PROVIDER",
    "MODEL_AGENT_NAME",
    "MODEL_AGENT_EXTRA_HEADERS",
)
REQUIRED_MODEL_AGENT_ENV_KEYS = (
    "MODEL_AGENT_API_BASE",
    "MODEL_AGENT_API_KEY",
    "MODEL_AGENT_PROVIDER",
    "MODEL_AGENT_NAME",
)
OPENCLAW_CONFIG_FILE = Path("/root/.openclaw/openclaw.json")
OPENCLAW_MODEL_CONFIG_ROOTS = (
    ("models",),
    ("model",),
    ("modelProviders",),
    ("model_providers",),
    ("providers",),
    ("agents", "defaults", "model"),
)
OPENCLAW_API_BASE_KEYS = (
    "api_base_url",
    "apiBaseUrl",
    "api_base",
    "apiBase",
    "base_url",
    "baseURL",
    "baseUrl",
    "baseurl",
)
OPENCLAW_API_KEY_KEYS = (
    "api_key",
    "apiKey",
    "apikey",
    "key",
    "model_key",
    "modelKey",
)
OPENCLAW_PROVIDER_API_KEYS = (
    "api",
    "model_api",
    "modelApi",
    "api_type",
    "apiType",
)
OPENCLAW_MODEL_HEADER_KEYS = (
    "headers",
    "extra_headers",
    "extraHeaders",
)
OPENCLAW_PROVIDER_API_ROUTES = {
    "openai-completions": "openai",
    "openai-responses": "openai/responses",
    "openai-codex-responses": "openai/responses",
    "anthropic-messages": "anthropic",
    "google-generative-ai": "gemini",
    "github-copilot": "github_copilot",
    "bedrock-converse-stream": "bedrock/converse",
    "ollama": "ollama_chat",
    "azure-openai-responses": "azure/responses",
}


def _resolve_invoke_tool_id(
    *,
    tool_id: Optional[str],
    tool_type: SandboxToolType,
) -> str:
    explicit_tool_id = (tool_id or "").strip()
    if explicit_tool_id:
        return explicit_tool_id

    env_tool_id = (os.getenv(SANDBOX_TOOL_ID_ENV) or "").strip()
    if env_tool_id:
        return env_tool_id

    return tool_type.value


def build_invoke_model_agent_envs(
    *,
    model_name: Optional[str] = None,
    model_provider: Optional[str] = None,
    model_base_url: Optional[str] = None,
    model_api_key: Optional[str] = None,
    openclaw_config_file: Path = OPENCLAW_CONFIG_FILE,
) -> list[tools_types.EnvsItemForCreateSession]:
    cli_values = {
        "MODEL_AGENT_API_BASE": (model_base_url or "").strip(),
        "MODEL_AGENT_API_KEY": (model_api_key or "").strip(),
        "MODEL_AGENT_PROVIDER": (model_provider or "").strip(),
        "MODEL_AGENT_NAME": (model_name or "").strip(),
    }
    env_values = _collect_model_agent_envs_from_env()
    openclaw_values = _collect_openclaw_model_agent_envs(openclaw_config_file)

    values: dict[str, str] = {}
    for key in MODEL_AGENT_ENV_KEYS:
        values[key] = (
            cli_values.get(key) or env_values.get(key) or openclaw_values.get(key) or ""
        )

    return [
        tools_types.EnvsItemForCreateSession(key=key, value=values[key])
        for key in MODEL_AGENT_ENV_KEYS
        if key in REQUIRED_MODEL_AGENT_ENV_KEYS or values[key]
    ]


def _collect_model_agent_envs_from_env() -> dict[str, str]:
    values: dict[str, str] = {}
    for key in MODEL_AGENT_ENV_KEYS:
        value = os.getenv(key, "").strip()
        if value:
            values[key] = value
    return values


def _collect_openclaw_model_agent_envs(path: Path) -> dict[str, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}

    primary = _get_nested(data, ("agents", "defaults", "model", "primary"))
    if not isinstance(primary, str):
        return {}

    provider, model_name = _parse_openclaw_primary(primary)
    if not provider or not model_name:
        return {}

    model_config = _find_openclaw_model_config(data, provider, model_name)
    if not model_config:
        return {}

    api_base = _pick_openclaw_text(model_config, OPENCLAW_API_BASE_KEYS)
    api_key = _pick_openclaw_text(model_config, OPENCLAW_API_KEY_KEYS)
    provider_api = _pick_openclaw_text(model_config, OPENCLAW_PROVIDER_API_KEYS)
    if not api_base or not api_key or not provider_api:
        return {}

    litellm_provider, model_agent_name = _resolve_openclaw_provider_api_route(
        provider_api,
        model_name,
    )
    if not litellm_provider or not model_agent_name:
        return {}

    values = {
        "MODEL_AGENT_API_BASE": api_base,
        "MODEL_AGENT_API_KEY": api_key,
        "MODEL_AGENT_PROVIDER": litellm_provider,
        "MODEL_AGENT_NAME": model_agent_name,
    }
    extra_headers = _pick_openclaw_headers_json(model_config)
    if extra_headers:
        values["MODEL_AGENT_EXTRA_HEADERS"] = extra_headers
    return values


def _resolve_openclaw_provider_api_route(
    provider_api: str,
    model_name: str,
) -> tuple[str, str]:
    litellm_provider = OPENCLAW_PROVIDER_API_ROUTES.get(provider_api)
    if not litellm_provider:
        return "", ""
    return litellm_provider, model_name


def _parse_openclaw_primary(primary: str) -> tuple[str, str]:
    provider, separator, model_name = primary.strip().partition("/")
    if not separator:
        return "", ""
    return provider.strip(), model_name.strip()


def _find_openclaw_model_config(
    data: dict[str, Any],
    provider: str,
    model_name: str,
) -> dict[str, Any] | None:
    for path in OPENCLAW_MODEL_CONFIG_ROOTS:
        root = _get_nested(data, path)
        match = _find_openclaw_model_config_in(root, provider, model_name)
        if match:
            return match
    return _find_openclaw_model_config_in(data, provider, model_name)


def _find_openclaw_model_config_in(
    value: Any,
    provider: str,
    model_name: str,
) -> dict[str, Any] | None:
    if isinstance(value, dict):
        direct = _openclaw_direct_model_config(value, provider, model_name)
        if direct:
            return direct

        if _openclaw_model_config_matches(value, provider, model_name):
            return value

        for child in value.values():
            match = _find_openclaw_model_config_in(child, provider, model_name)
            if match:
                return match
    elif isinstance(value, list):
        for item in value:
            match = _find_openclaw_model_config_in(item, provider, model_name)
            if match:
                return match
    return None


def _openclaw_direct_model_config(
    value: dict[str, Any],
    provider: str,
    model_name: str,
) -> dict[str, Any] | None:
    direct_keys = (
        f"{provider}/{model_name}",
        model_name,
    )
    for key in direct_keys:
        candidate = value.get(key)
        if isinstance(candidate, dict):
            return candidate

    provider_config = value.get(provider)
    if isinstance(provider_config, dict):
        candidate = provider_config.get(model_name)
        if isinstance(candidate, dict):
            return _merge_openclaw_model_config(provider_config, candidate)
        if _openclaw_provider_config_has_model(provider_config, model_name):
            model_item = _find_openclaw_model_item(provider_config, model_name)
            return _merge_openclaw_model_config(provider_config, model_item)
    return None


def _merge_openclaw_model_config(
    provider_config: dict[str, Any],
    model_config: dict[str, Any] | None,
) -> dict[str, Any]:
    merged = {key: value for key, value in provider_config.items() if key != "models"}
    if model_config:
        merged.update(model_config)
        provider_headers = _pick_openclaw_headers(provider_config)
        model_headers = _pick_openclaw_headers(model_config)
        if provider_headers or model_headers:
            headers = {}
            headers.update(provider_headers)
            headers.update(model_headers)
            merged["headers"] = headers
    return merged


def _openclaw_provider_config_has_model(
    provider_config: dict[str, Any],
    model_name: str,
) -> bool:
    return _find_openclaw_model_item(provider_config, model_name) is not None


def _find_openclaw_model_item(
    provider_config: dict[str, Any],
    model_name: str,
) -> dict[str, Any] | None:
    models = provider_config.get("models")
    if isinstance(models, dict):
        candidate = models.get(model_name)
        if isinstance(candidate, dict):
            return candidate
        for item in models.values():
            if isinstance(item, dict) and _openclaw_model_config_matches_model_name(
                item, model_name
            ):
                return item
    if isinstance(models, list):
        for item in models:
            if isinstance(item, dict) and _openclaw_model_config_matches_model_name(
                item, model_name
            ):
                return item
    return None


def _openclaw_model_config_matches_model_name(value: Any, model_name: str) -> bool:
    if isinstance(value, str):
        return value == model_name
    if not isinstance(value, dict):
        return False

    name_value = _pick_openclaw_text(
        value,
        ("id", "name", "model", "model_name", "modelName"),
    )
    return name_value == model_name


def _openclaw_model_config_matches(
    value: dict[str, Any],
    provider: str,
    model_name: str,
) -> bool:
    provider_value = _pick_openclaw_text(
        value,
        ("provider", "provider_name", "providerName", "type"),
    )
    name_value = _pick_openclaw_text(
        value,
        ("name", "model", "model_name", "modelName", "id"),
    )
    return provider_value == provider and name_value in {
        model_name,
        f"{provider}/{model_name}",
    }


def _get_nested(value: Any, path: tuple[str, ...]) -> Any:
    current = value
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _pick_openclaw_text(value: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        item = value.get(key)
        if isinstance(item, str) and item.strip():
            return item.strip()
    return None


def _pick_openclaw_headers_json(value: dict[str, Any]) -> str | None:
    headers = _pick_openclaw_headers(value)
    if not headers:
        return None
    return json.dumps(headers, ensure_ascii=False, sort_keys=True)


def _pick_openclaw_headers(value: dict[str, Any]) -> dict[str, str]:
    for key in OPENCLAW_MODEL_HEADER_KEYS:
        item = value.get(key)
        if not isinstance(item, dict):
            continue
        headers: dict[str, str] = {}
        for header_key, header_value in item.items():
            if (
                isinstance(header_key, str)
                and isinstance(header_value, str)
                and header_key.strip()
                and header_value.strip()
            ):
                headers[header_key.strip()] = header_value.strip()
        if headers:
            return headers
    return {}


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
        tool_type=tool_type,
    )

    try:
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
