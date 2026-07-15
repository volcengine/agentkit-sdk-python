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

"""Tool resolution helpers for sandbox CLI commands."""

from __future__ import annotations

import json
import os
from enum import Enum
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table

from agentkit.sdk.tools import types as tools_types
from agentkit.toolkit.cli.sandbox.agentkit_client import (
    AgentkitToolsClient,
    is_tip_agentkit_client,
)
from agentkit.toolkit.cli.sandbox.model_config import (
    MODEL_PROVIDER_ENV,
    model_provider_from_env_value,
)
from agentkit.toolkit.cli.sandbox.sandbox_client import error

SANDBOX_TOOL_STORE_PATH = Path(".agentkit") / "sandbox" / "tools.json"
DEFAULT_SANDBOX_TOOL_TYPE = "CodeEnv"
VALID_SANDBOX_TOOL_TYPES = ("CodeEnv", "SkillEnv", "Private")
READY_TOOL_STATUS = "Ready"
TOOL_NOT_FOUND_ERROR_CODE = "InvalidResource.NotFound"

console = Console()


class SandboxToolType(str, Enum):
    CODE_ENV = "CodeEnv"
    SKILL_ENV = "SkillEnv"
    PRIVATE = "Private"


def normalize_tool_type(tool_type: str | SandboxToolType | None) -> str:
    value = tool_type.value if isinstance(tool_type, SandboxToolType) else tool_type
    resolved = (value or DEFAULT_SANDBOX_TOOL_TYPE).strip()
    if resolved not in VALID_SANDBOX_TOOL_TYPES:
        error("--tool-type must be one of: " + ", ".join(VALID_SANDBOX_TOOL_TYPES))
    return resolved


def is_resolvable_tool_type(tool_type: str | SandboxToolType | None) -> bool:
    value = tool_type.value if isinstance(tool_type, SandboxToolType) else tool_type
    resolved = (value or DEFAULT_SANDBOX_TOOL_TYPE).strip()
    return resolved in VALID_SANDBOX_TOOL_TYPES


def _get_tool_store_path() -> Path:
    return Path.cwd() / SANDBOX_TOOL_STORE_PATH


def _load_tool_store(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        error(f"Invalid sandbox tool store {path}: {exc}")

    if not isinstance(data, dict):
        error(f"Invalid sandbox tool store {path}: expected JSON object")

    return data


def _get_field_value(source: object, *keys: str) -> object:
    for key in keys:
        if isinstance(source, dict):
            value = source.get(key)
        else:
            value = getattr(source, key, None)
        if value is not None:
            return value
    return None


def _get_string_field(source: object, *keys: str) -> str | None:
    value = _get_field_value(source, *keys)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _get_tool_payload(response: object) -> object:
    if isinstance(response, dict) and isinstance(response.get("Result"), dict):
        return response["Result"]
    return response


def _get_tool_env_value(payload: object, key: str) -> object:
    envs = _get_field_value(payload, "Envs", "envs") or []
    if not isinstance(envs, list):
        return None

    for env in envs:
        env_key = _get_field_value(env, "Key", "key")
        if env_key == key:
            return _get_field_value(env, "Value", "value")
    return None


def _get_tool_model_provider(payload: object) -> str | None:
    return model_provider_from_env_value(
        _get_tool_env_value(payload, MODEL_PROVIDER_ENV)
    )


def _build_tool_record(tool: object, tool_type: str) -> dict[str, object] | None:
    payload = _get_tool_payload(tool)
    tool_id = _get_string_field(payload, "ToolId", "tool_id")
    if not isinstance(tool_id, str) or not tool_id.strip():
        return None
    record: dict[str, object] = {
        "ToolId": tool_id.strip(),
        "ToolType": _get_field_value(payload, "ToolType", "tool_type") or tool_type,
        "Name": _get_field_value(payload, "Name", "name"),
        "Status": _get_field_value(payload, "Status", "status"),
    }
    model_provider = _get_tool_model_provider(payload)
    if model_provider:
        record["ModelProvider"] = model_provider
    enable_snapshot = _get_field_value(payload, "EnableSnapshot", "enable_snapshot")
    if enable_snapshot is True:
        record["EnableSnapshot"] = True
    role_name = _get_string_field(payload, "RoleName", "role_name")
    if isinstance(role_name, str) and role_name.strip():
        record["RoleName"] = role_name.strip()
    envs = _get_field_value(payload, "Envs", "envs")
    if isinstance(envs, list):
        for env_item in envs:
            key = _get_field_value(env_item, "Key", "key") or ""
            if key == "WEB_SEARCH_API_KEY":
                val = _get_field_value(env_item, "Value", "value") or ""
                if isinstance(val, str) and val.strip():
                    record["WebSearchApiKeySet"] = True
                break
    return record


def _get_string_value(result: dict[str, object], *keys: str) -> str | None:
    for key in keys:
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _is_ready_tool_record(result: dict[str, object]) -> bool:
    return _get_string_value(result, "Status", "status") == READY_TOOL_STATUS


def _get_response_error(response: object) -> tuple[str, str] | None:
    metadata = _get_field_value(response, "ResponseMetadata", "response_metadata")
    if not isinstance(metadata, dict):
        return None

    api_error = metadata.get("Error")
    if not isinstance(api_error, dict):
        return None

    code = str(api_error.get("Code") or "")
    message = str(api_error.get("Message") or "Unknown error")
    return code, message


def _is_tool_not_found_error(exc: Exception) -> bool:
    message = str(exc)
    return (
        TOOL_NOT_FOUND_ERROR_CODE in message
        or "specified resource does not exist" in message.lower()
        or "not found" in message.lower()
        or "not exist" in message.lower()
        or "不存在" in message
    )


def _tool_not_found(tool_id: str, detail: object = None) -> None:
    message = f"Sandbox tool not found: {tool_id}"
    if detail:
        message = f"{message}. {detail}"
    error(message)


def _tool_unavailable(tool_id: str, status: str | None) -> None:
    error(
        f"Sandbox tool is not available: {tool_id}. "
        f"Status: {status or 'Unknown'}. Expected: {READY_TOOL_STATUS}"
    )


def _validate_existing_tool_id(
    client: AgentkitToolsClient,
    tool_id: str,
    *,
    tool_type: str | SandboxToolType | None,
    save_result: bool = False,
) -> str:
    if is_tip_agentkit_client(client):
        return tool_id

    try:
        response = client.get_tool(tools_types.GetToolRequest(tool_id=tool_id))
    except Exception as exc:
        if _is_tool_not_found_error(exc):
            _tool_not_found(tool_id, exc)
        error(f"Failed to get sandbox tool {tool_id}: {exc}")

    response_error = _get_response_error(response)
    if response_error:
        code, message = response_error
        if code == TOOL_NOT_FOUND_ERROR_CODE:
            _tool_not_found(tool_id, message)
        error(f"Failed to get sandbox tool {tool_id}: {message}")

    resolved_tool_type = normalize_tool_type(tool_type)
    record = _build_tool_record(response, resolved_tool_type)
    if not record:
        error(f"GetTool response missing ToolId: {tool_id}")
    if record["ToolId"] != tool_id:
        error(f"GetTool response ToolId mismatch: {tool_id}")

    status = _get_string_value(record, "Status", "status")
    if status != READY_TOOL_STATUS:
        _tool_unavailable(tool_id, status)

    if save_result:
        save_tool_result(resolved_tool_type, record)
    return tool_id


def _normalize_tool_record(
    tool_type: str,
    result: dict[str, object],
) -> dict[str, object]:
    resolved_tool_type = normalize_tool_type(
        _get_string_value(result, "ToolType", "tool_type") or tool_type
    )
    tool_id = _get_string_value(result, "ToolId", "tool_id")
    if not tool_id:
        error("Tool result missing ToolId")

    stored: dict[str, object] = {
        "ToolId": tool_id,
        "Name": _get_string_value(result, "Name", "name") or "",
        "Status": _get_string_value(result, "Status", "status") or "",
        "ToolType": resolved_tool_type,
    }
    model_provider = model_provider_from_env_value(
        _get_string_value(result, "ModelProvider", "model_provider")
    )
    if model_provider:
        stored["ModelProvider"] = model_provider
    enable_snapshot = result.get("EnableSnapshot")
    if enable_snapshot is None:
        enable_snapshot = result.get("enable_snapshot")
    if enable_snapshot is True:
        stored["EnableSnapshot"] = True
    role_name = _get_string_value(result, "RoleName", "role_name")
    if role_name:
        stored["RoleName"] = role_name
    websearch_set = result.get("WebSearchApiKeySet") or result.get(
        "websearch_apikey_set"
    )
    if websearch_set:
        stored["WebSearchApiKeySet"] = True
    return stored


def save_tool_result(tool_type: str, result: dict[str, object]) -> None:
    stored = _normalize_tool_record(tool_type, result)
    resolved_tool_type = stored["ToolType"]
    path = _get_tool_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    data = _load_tool_store(path)
    data[resolved_tool_type] = stored
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def save_tool_result_if_resolvable(
    tool_type: str | SandboxToolType | None,
    result: dict[str, object],
) -> bool:
    result_tool_type = _get_string_value(result, "ToolType", "tool_type")
    if result_tool_type and not is_resolvable_tool_type(result_tool_type):
        return False

    save_tool_result(normalize_tool_type(tool_type), result)
    return True


def find_tool_result(tool_type: str) -> dict[str, object] | None:
    resolved_tool_type = normalize_tool_type(tool_type)
    data = _load_tool_store(_get_tool_store_path())

    result = data.get(resolved_tool_type)
    if result is None:
        return None
    if not isinstance(result, dict):
        error(f"Invalid sandbox tool record: {resolved_tool_type}")

    return result


def is_tool_snapshot_enabled(
    *,
    tool_id: Optional[str],
    tool_type: str | SandboxToolType | None,
) -> bool:
    result = find_tool_result(normalize_tool_type(tool_type))
    if not result:
        return False

    cached_tool_id = _get_string_value(result, "ToolId", "tool_id")
    if tool_id and cached_tool_id != tool_id:
        return False
    return result.get("EnableSnapshot") is True


def find_tool_model_provider(
    *,
    tool_id: Optional[str],
    tool_type: str | SandboxToolType | None,
) -> str | None:
    result = find_tool_result(normalize_tool_type(tool_type))
    if not result:
        return None

    cached_tool_id = _get_string_value(result, "ToolId", "tool_id")
    if tool_id and cached_tool_id != tool_id:
        return None
    return model_provider_from_env_value(
        _get_string_value(result, "ModelProvider", "model_provider")
    )


def get_tool_websearch_config(
    *,
    tool_id: Optional[str],
    tool_type: str | SandboxToolType | None,
) -> dict[str, object] | None:
    resolved_tool_type = normalize_tool_type(tool_type)
    result = find_tool_result(resolved_tool_type)

    if result:
        cached_tool_id = _get_string_value(result, "ToolId", "tool_id")
        if not tool_id or cached_tool_id == tool_id:
            return {
                "has_role": bool(_get_string_value(result, "RoleName", "role_name")),
                "websearch_apikey_set": bool(result.get("WebSearchApiKeySet")),
                "role_name": _get_string_value(result, "RoleName", "role_name"),
            }

    if not tool_id:
        return None

    try:
        client = AgentkitToolsClient()
        response = client.get_tool(tools_types.GetToolRequest(tool_id=tool_id))
    except Exception:
        return None

    record = _build_tool_record(response, resolved_tool_type)
    if not record:
        return None
    save_tool_result_if_resolvable(resolved_tool_type, record)
    return {
        "has_role": bool(_get_string_value(record, "RoleName", "role_name")),
        "websearch_apikey_set": bool(record.get("WebSearchApiKeySet")),
        "role_name": _get_string_value(record, "RoleName", "role_name"),
    }


def get_remote_tool_model_provider(
    client: AgentkitToolsClient,
    tool_id: str,
    *,
    tool_type: str | SandboxToolType | None,
) -> str | None:
    response = client.get_tool(tools_types.GetToolRequest(tool_id=tool_id))
    record = _build_tool_record(response, normalize_tool_type(tool_type))
    if record:
        save_tool_result_if_resolvable(tool_type, record)
        return model_provider_from_env_value(
            _get_string_value(record, "ModelProvider", "model_provider")
        )
    return None


def _get_cached_tool_id(tool_type: str) -> str | None:
    result = find_tool_result(tool_type)
    if not result:
        return None

    tool_id = _get_string_value(result, "ToolId", "tool_id")
    if tool_id and _is_ready_tool_record(result):
        return tool_id
    return None


def _list_first_tool(
    client: AgentkitToolsClient,
    tool_type: str,
) -> str | None:
    request = tools_types.ListToolsRequest(
        filters=[
            tools_types.FiltersItemForListTools(
                name="ToolType",
                values=[tool_type],
            )
        ]
    )
    response = client.list_tools(request)
    for tool in response.tools or []:
        record = _build_tool_record(tool, tool_type)
        if not record or not _is_ready_tool_record(record):
            continue
        save_tool_result(tool_type, record)
        tool_id = record["ToolId"]
        if isinstance(tool_id, str):
            return tool_id
    return None


def _list_tools_by_name(client: AgentkitToolsClient, tool_name: str) -> list[object]:
    request = tools_types.ListToolsRequest(
        filters=[
            tools_types.FiltersItemForListTools(
                name="Name",
                values=[tool_name],
            )
        ],
        max_results=100,
    )
    try:
        response = client.list_tools(request)
    except Exception as exc:
        error(f"Failed to list sandbox tools by name {tool_name}: {exc}")
    return list(response.tools or [])


def _print_tool_name_matches(tool_name: str, matches: list[object]) -> None:
    table = Table(title=f"Multiple sandbox tools matched: {tool_name}")
    table.add_column("ToolId", style="cyan")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("ToolType")
    for item in matches:
        table.add_row(
            _get_string_field(item, "ToolId", "tool_id") or "",
            _get_string_field(item, "Name", "name") or "",
            _get_string_field(item, "Status", "status") or "",
            _get_string_field(item, "ToolType", "tool_type") or "",
        )
    console.print(table)


def _resolve_tool_id_by_name(
    client: AgentkitToolsClient,
    tool_name: str,
) -> str:
    matches = _list_tools_by_name(client, tool_name)
    if not matches:
        error(f"Sandbox tool not found by name: {tool_name}")
    if len(matches) > 1:
        _print_tool_name_matches(tool_name, matches)
        error("Multiple sandbox tools matched --tool-name. Retry with --tool-id.")

    resolved_tool_id = _get_string_field(matches[0], "ToolId", "tool_id")
    if not resolved_tool_id:
        error(f"ListTools response missing ToolId for name: {tool_name}")
    return resolved_tool_id


def _create_tool(tool_type: str) -> str:
    from agentkit.toolkit.cli.sandbox.config_store import (
        config_default_bool,
        config_default_int,
        config_default_str,
        configured_network_payload,
        configured_sandbox_config,
    )
    from agentkit.toolkit.cli.sandbox.cli_create import create_tool

    config_defaults = configured_sandbox_config()
    role_name = config_default_str("role-name", data=config_defaults)
    network_payload = configured_network_payload(data=config_defaults)
    result = create_tool(
        tool_type=tool_type,
        tool_name=config_default_str("tool-name", data=config_defaults),
        cpu=config_default_int("cpu", data=config_defaults) or 4,
        model_name=config_default_str("model-name", data=config_defaults),
        model_api_key=config_default_str("model-api-key", data=config_defaults),
        model_provider=config_default_str("model-provider", data=config_defaults),
        model_base_url=config_default_str("model-base-url", data=config_defaults),
        skill_role_name=role_name,
        skill_role_name_provided=bool(role_name),
        websearch_apikey=config_default_str(
            "websearch-apikey",
            data=config_defaults,
        ),
        image_url=config_default_str("image-url", data=config_defaults),
        enable_snapshot=bool(
            config_default_bool("enable-snapshot", data=config_defaults)
        ),
        network_config=json.dumps(network_payload) if network_payload else None,
    )
    save_tool_result(tool_type, result)
    tool_id = _get_string_value(result, "ToolId", "tool_id")
    if not tool_id:
        error("CreateTool response missing ToolId")
    return tool_id


def resolve_sandbox_tool_id(
    *,
    tool_id: Optional[str],
    tool_type: str | SandboxToolType | None,
    tool_name: Optional[str] = None,
    default_tool_id: object = None,
    client: AgentkitToolsClient,
    env_var_name: str,
) -> str:
    resolved_tool_id = resolve_existing_sandbox_tool_id(
        tool_id=tool_id,
        tool_name=tool_name,
        tool_type=tool_type,
        default_tool_id=default_tool_id,
        client=client,
        env_var_name=env_var_name,
    )
    if resolved_tool_id:
        return resolved_tool_id

    resolved_tool_type = normalize_tool_type(tool_type)
    if is_tip_agentkit_client(client):
        error(
            "TIP sandbox auth requires an existing sandbox tool ID. "
            f"Set --tool-id or {env_var_name}."
        )
    return _create_tool(resolved_tool_type)


def resolve_existing_sandbox_tool_id(
    *,
    tool_id: Optional[str],
    tool_type: str | SandboxToolType | None,
    tool_name: Optional[str] = None,
    default_tool_id: object = None,
    client: AgentkitToolsClient,
    env_var_name: str,
) -> str | None:
    explicit_tool_id = (tool_id or "").strip()
    explicit_tool_name = (tool_name or "").strip()
    if tool_name is not None and not explicit_tool_name:
        error("--tool-name cannot be empty")
    if explicit_tool_id and explicit_tool_name:
        error("Specify only one of --tool-id or --tool-name.")
    if explicit_tool_id:
        return _validate_existing_tool_id(
            client,
            explicit_tool_id,
            tool_type=tool_type,
            save_result=True,
        )
    if explicit_tool_name:
        resolved_tool_id = _resolve_tool_id_by_name(client, explicit_tool_name)
        return _validate_existing_tool_id(
            client,
            resolved_tool_id,
            tool_type=tool_type,
            save_result=True,
        )

    env_tool_id = (os.getenv(env_var_name) or "").strip()
    if env_tool_id:
        return _validate_existing_tool_id(
            client,
            env_tool_id,
            tool_type=tool_type,
            save_result=True,
        )

    if isinstance(default_tool_id, str) and default_tool_id.strip():
        return _validate_existing_tool_id(
            client,
            default_tool_id.strip(),
            tool_type=tool_type,
            save_result=True,
        )

    resolved_tool_type = normalize_tool_type(tool_type)
    cached_tool_id = _get_cached_tool_id(resolved_tool_type)
    if cached_tool_id:
        return _validate_existing_tool_id(
            client,
            cached_tool_id,
            tool_type=resolved_tool_type,
            save_result=True,
        )

    if is_tip_agentkit_client(client):
        return None

    listed_tool_id = _list_first_tool(client, resolved_tool_type)
    if listed_tool_id:
        return listed_tool_id

    return None
