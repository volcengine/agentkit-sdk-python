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

"""Create Tool command for sandbox CLI."""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, NoReturn, Optional

import typer
import yaml

from agentkit.platform import VolcConfiguration
from agentkit.sdk.tools.client import AgentkitToolsClient
from agentkit.sdk.tools import types as tools_types
from agentkit.toolkit.cli.sandbox.env_config import (
    DEFAULT_CREATE_TOOL_TYPE,
    PRIVATE_TOOL_COMMAND,
    PRIVATE_TOOL_PORT,
    PRIVATE_TOOL_TYPE,
    build_create_tool_envs,
    build_private_tool_envs,
)
from agentkit.toolkit.cli.sandbox.model_config import (
    ModelProviderType,
    infer_model_provider_from_base_url,
    normalize_model_base_url,
    normalize_model_provider,
)
from agentkit.toolkit.cli.sandbox.tool_resolve import save_tool_result_if_resolvable
from agentkit.toolkit.cli.sandbox.tos_config import (
    DEFAULT_TOS_LOCAL_PATH,
    build_create_tool_tos_mount_config,
)
from agentkit.toolkit.cli.sandbox.sandbox_client import error
from agentkit.toolkit.cli.sandbox.sandbox_client import SANDBOX_YAML_PATH
from agentkit.toolkit.volcengine.services.tos_service import (
    TOSService,
    TOSServiceConfig,
)
from agentkit.utils.misc import generate_apikey_name, generate_random_id

SANDBOX_REGION_ENV = "AGENTKIT_SANDBOX_REGION"
SANDBOX_TOS_REGION_ENV = "AGENTKIT_SANDBOX_TOS_REGION"
DEFAULT_CPU = 4
VALID_CPU_VALUES = (2, 4, 8, 16)
VALID_CREATE_TOOL_TYPES = ("CodeEnv", "SkillEnv", "Private")
MEMORY_MB_PER_CPU = 2048
SKILL_ROLE_NAME_OPTION = "--skill-role-name"
TOOL_READY_STATUS = "Ready"
TOOL_FAILED_STATUSES = {"Error", "Failed", "CreateFailed", "Deleting", "Deleted"}
TOOL_WAIT_INTERVAL_SECONDS = 5
TOOL_WAIT_TIMEOUT_SECONDS = 600
NETWORK_CONFIG_FIELDS = (
    "private_access",
    "public_access",
    "vpc_id",
    "subnet_ids",
    "enable_shared_internet_access",
)


def _get_sandbox_yaml_path() -> Path:
    return Path.cwd() / SANDBOX_YAML_PATH


def _load_sandbox_yaml_defaults() -> tuple[str, str] | None:
    path = _get_sandbox_yaml_path()
    if not path.exists():
        return None

    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        error(f"Invalid {SANDBOX_YAML_PATH}: {exc}")
    except OSError as exc:
        error(f"Failed to read {SANDBOX_YAML_PATH}: {exc}")

    if not isinstance(payload, dict):
        error(f"Invalid {SANDBOX_YAML_PATH}: expected a YAML mapping")

    raw_tool_type = payload.get("tool_type")
    raw_image_url = payload.get("image_url")
    if not isinstance(raw_tool_type, str) or not raw_tool_type.strip():
        error(f"Invalid {SANDBOX_YAML_PATH}: tool_type must be a non-empty string")
    if not isinstance(raw_image_url, str) or not raw_image_url.strip():
        error(f"Invalid {SANDBOX_YAML_PATH}: image_url must be a non-empty string")

    tool_type = _validate_tool_type(raw_tool_type)
    image_url = raw_image_url.strip()
    if tool_type == PRIVATE_TOOL_TYPE and not image_url:
        error(f"Invalid {SANDBOX_YAML_PATH}: image_url is required for Private tools")

    return tool_type, image_url


def _resolve_create_tool_image_defaults(
    *,
    tool_type: Optional[str],
    image_url: Optional[str],
) -> tuple[str, Optional[str]]:
    if tool_type is not None or image_url is not None:
        return tool_type or DEFAULT_CREATE_TOOL_TYPE, image_url

    defaults = _load_sandbox_yaml_defaults()
    if defaults is None:
        return DEFAULT_CREATE_TOOL_TYPE, image_url

    return defaults


def _resolve_region(env_var_name: str, service_key: str) -> str:
    env_region = (os.getenv(env_var_name) or "").strip()
    if env_region:
        return env_region
    return VolcConfiguration().get_service_endpoint(service_key).region


def _generate_tool_name(tool_type: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", tool_type.lower()).strip("-")
    if not normalized:
        normalized = "tool"
    return f"agentkit-{normalized}-{generate_random_id(8)}"


def _validate_cpu(value: int) -> int:
    if value not in VALID_CPU_VALUES:
        allowed = ", ".join(str(item) for item in VALID_CPU_VALUES)
        raise typer.BadParameter(f"--cpu must be one of: {allowed}")
    return value


def _validate_tool_type(value: str) -> str:
    resolved = value.strip() or DEFAULT_CREATE_TOOL_TYPE
    if resolved not in VALID_CREATE_TOOL_TYPES:
        allowed = ", ".join(VALID_CREATE_TOOL_TYPES)
        error(f"--tool-type must be one of: {allowed}")
    return resolved


def _cpu_to_resource_shape(cpu: int) -> tuple[int, int]:
    resolved_cpu = _validate_cpu(cpu)
    return resolved_cpu * 1000, resolved_cpu * MEMORY_MB_PER_CPU


def _network_config_error(message: str) -> NoReturn:
    error(f"Invalid --network-config: {message}")


def _load_network_config(value: str) -> dict[str, Any]:
    raw = value.strip()
    if not raw:
        _network_config_error("value must not be empty")

    if raw[0] in "{[":
        source = "inline JSON"
        content = raw
    else:
        path = Path(raw).expanduser()
        source = str(path)
        try:
            content = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            _network_config_error(f"file not found: {source}")
        except OSError as exc:
            _network_config_error(f"failed to read file {source}: {exc}")

    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        _network_config_error(
            f"{source} is not valid JSON at line {exc.lineno}, "
            f"column {exc.colno}: {exc.msg}"
        )

    if not isinstance(payload, dict):
        _network_config_error("expected a JSON object")
    return payload


def _get_network_bool(
    payload: dict[str, Any],
    field: str,
    *,
    default: bool,
) -> bool:
    if field not in payload or payload[field] is None:
        return default
    if not isinstance(payload[field], bool):
        _network_config_error(f"{field} must be a boolean")
    return payload[field]


def _get_network_string(payload: dict[str, Any], field: str) -> Optional[str]:
    if field not in payload or payload[field] is None:
        return None
    value = payload[field]
    if not isinstance(value, str):
        _network_config_error(f"{field} must be a string")
    resolved = value.strip()
    if not resolved:
        _network_config_error(f"{field} must not be empty")
    return resolved


def _get_network_string_list(
    payload: dict[str, Any],
    field: str,
) -> Optional[list[str]]:
    if field not in payload or payload[field] is None:
        return None
    value = payload[field]
    if isinstance(value, str):
        items = [item.strip() for item in value.split(",") if item.strip()]
        if not items:
            _network_config_error(f"{field} must contain at least one value")
        return items
    if not isinstance(value, list):
        _network_config_error(f"{field} must be a string or an array of strings")
    items = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            _network_config_error(f"{field}[{index}] must be a string")
        resolved = item.strip()
        if not resolved:
            _network_config_error(f"{field}[{index}] must not be empty")
        items.append(resolved)
    if not items:
        _network_config_error(f"{field} must contain at least one value")
    return items


def _build_network_configuration(
    network_config: Optional[str] = None,
) -> tools_types.NetworkForCreateTool:
    if not network_config:
        return tools_types.NetworkForCreateTool(
            EnablePublicNetwork=True,
            EnablePrivateNetwork=False,
        )

    payload = _load_network_config(network_config)
    unknown_fields = sorted(set(payload) - set(NETWORK_CONFIG_FIELDS))
    if unknown_fields:
        allowed = ", ".join(NETWORK_CONFIG_FIELDS)
        _network_config_error(
            f"unsupported field {unknown_fields[0]!r}; allowed fields: {allowed}"
        )

    private_access = _get_network_bool(
        payload,
        "private_access",
        default=False,
    )
    public_access = _get_network_bool(payload, "public_access", default=True)
    vpc_id = _get_network_string(payload, "vpc_id")
    subnet_ids = _get_network_string_list(payload, "subnet_ids")
    enable_shared_internet_access = _get_network_bool(
        payload,
        "enable_shared_internet_access",
        default=False,
    )

    if not private_access and not public_access:
        _network_config_error(
            "private_access and public_access cannot both be false"
        )
    if private_access and not vpc_id:
        _network_config_error("vpc_id is required when private_access is true")
    if not private_access and any(
        [
            vpc_id,
            subnet_ids,
            payload.get("enable_shared_internet_access") is not None,
        ]
    ):
        _network_config_error(
            "vpc_id, subnet_ids, and enable_shared_internet_access require "
            "private_access=true"
        )

    vpc_configuration = None
    if private_access:
        vpc_configuration = tools_types.NetworkVpcForCreateTool(
            VpcId=vpc_id,
            SubnetIds=subnet_ids,
            EnableSharedInternetAccess=enable_shared_internet_access,
        )

    return tools_types.NetworkForCreateTool(
        EnablePublicNetwork=public_access,
        EnablePrivateNetwork=private_access,
        VpcConfiguration=vpc_configuration,
    )


def _build_create_tool_request(
    *,
    tool_type: str,
    name: Optional[str],
    tos_bucket: Optional[str],
    tos_region: str,
    tos_mount_path: str = DEFAULT_TOS_LOCAL_PATH,
    cpu: int = DEFAULT_CPU,
    model_name: Optional[str] = None,
    model_api_key: Optional[str] = None,
    model_provider: str | ModelProviderType | None = None,
    model_base_url: Optional[str] = None,
    model_provider_was_provided: Optional[bool] = None,
    model_base_url_was_provided: Optional[bool] = None,
    role_name: Optional[str] = None,
    websearch_apikey: Optional[str] = None,
    image_url: Optional[str] = None,
    network_config: Optional[str] = None,
) -> tools_types.CreateToolRequest:
    resolved_tool_type = _validate_tool_type(tool_type)
    resolved_name = (name or "").strip() or _generate_tool_name(resolved_tool_type)
    is_private_tool = resolved_tool_type == PRIVATE_TOOL_TYPE
    if is_private_tool and not (image_url or "").strip():
        error("--image-url is required when --tool-type Private")
    command = PRIVATE_TOOL_COMMAND if is_private_tool else None
    port = PRIVATE_TOOL_PORT if is_private_tool else None
    envs = (
        build_private_tool_envs(
            model_name=model_name,
            model_api_key=model_api_key,
            model_provider=model_provider,
            model_base_url=model_base_url,
            model_provider_was_provided=model_provider_was_provided,
            model_base_url_was_provided=model_base_url_was_provided,
            websearch_apikey=websearch_apikey,
        )
        if is_private_tool
        else build_create_tool_envs(
            tool_type=resolved_tool_type,
            model_name=model_name,
            model_api_key=model_api_key,
            model_provider=model_provider,
            model_base_url=model_base_url,
            model_provider_was_provided=model_provider_was_provided,
            model_base_url_was_provided=model_base_url_was_provided,
            websearch_apikey=websearch_apikey,
        )
    )
    tos_mount_config = build_create_tool_tos_mount_config(
        tos_bucket,
        tos_region,
        local_mount_path=tos_mount_path,
        tos_service_cls=TOSService,
        tos_service_config_cls=TOSServiceConfig,
    )
    cpu_milli, memory_mb = _cpu_to_resource_shape(cpu)

    return tools_types.CreateToolRequest(
        Name=resolved_name,
        ToolType=resolved_tool_type,
        Command=command,
        ImageUrl=(image_url or "").strip() or None,
        Port=port,
        CpuMilli=cpu_milli,
        MemoryMb=memory_mb,
        RoleName=role_name,
        AuthorizerConfiguration=tools_types.AuthorizerForCreateTool(
            KeyAuth=tools_types.AuthorizerKeyAuthForCreateTool(
                ApiKeyName=generate_apikey_name(),
                ApiKeyLocation="Header",
            )
        ),
        NetworkConfiguration=_build_network_configuration(network_config),
        TosMountConfig=tos_mount_config,
        Envs=envs,
    )


def _format_tool_failure(response: tools_types.GetToolResponse) -> str:
    mount_summary = ""
    tos_config = getattr(response, "tos_mount_config", None)
    if tos_config and tos_config.mount_points:
        mount = tos_config.mount_points[0]
        mount_summary = (
            "\nTOS: "
            f"BucketName={mount.bucket_name or '-'}, "
            f"BucketPath={mount.bucket_path or '-'}, "
            f"LocalMountPath={mount.local_mount_path or '-'}"
        )
    return (
        f"Tool {getattr(response, 'tool_id', None) or '<unknown>'} "
        f"entered terminal status: "
        f"{getattr(response, 'status', None) or 'Unknown'}\n"
        "GetTool did not return a detailed failure reason. "
        "Summary:\n"
        f"Name: {getattr(response, 'name', None) or '-'}\n"
        f"ToolType: {getattr(response, 'tool_type', None) or '-'}\n"
        f"ImageUrl: {getattr(response, 'image_url', None) or '-'}\n"
        f"Command: {getattr(response, 'command', None) or '-'}\n"
        f"Port: {getattr(response, 'port', None) or '-'}"
        f"{mount_summary}"
    )


def _wait_for_tool_ready(
    client: AgentkitToolsClient,
    tool_id: str,
    *,
    timeout_seconds: int = TOOL_WAIT_TIMEOUT_SECONDS,
    interval_seconds: int = TOOL_WAIT_INTERVAL_SECONDS,
) -> tools_types.GetToolResponse:
    deadline = time.monotonic() + timeout_seconds
    last_status = None

    while True:
        response = client.get_tool(tools_types.GetToolRequest(ToolId=tool_id))
        status = response.status or ""
        if status != last_status:
            typer.echo(f"工具状态：{status or 'Unknown'}")
            last_status = status

        if status == TOOL_READY_STATUS:
            return response
        if status in TOOL_FAILED_STATUSES:
            raise RuntimeError(_format_tool_failure(response))
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"Timed out waiting for Tool {tool_id} to become Ready. "
                f"Last status: {status or 'Unknown'}"
            )

        time.sleep(interval_seconds)


def _ensure_sandbox_role(
    role_name: str,
    region: str,
) -> str:
    import json as _json
    from agentkit.toolkit.volcengine.iam import VeIAM

    iam = VeIAM(region=region)
    existing = iam.get_role(role_name)
    if existing is not None:
        return role_name

    agentkit_service_code = (
        (
            os.getenv("VOLCENGINE_AGENTKIT_SERVICE")
            or os.getenv("VOLC_AGENTKIT_SERVICE")
            or os.getenv("BYTEPLUS_AGENTKIT_SERVICE")
            or ""
        )
        .strip()
        .lower()
    )
    service = "vefaas"
    if "stg" in agentkit_service_code:
        service = "vefaas_dev"
    trust_policy = _json.dumps(
        {
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["sts:AssumeRole"],
                    "Principal": {"Service": [service]},
                }
            ]
        }
    )
    iam.create_role(role_name, trust_policy)
    iam.attach_role_policy(
        role_name,
        policy_name="AgentKitSkillsSandboxAccess",
        policy_type="System",
    )
    return role_name


def _generate_default_role_name() -> str:
    return f"agentkit-sandbox-{generate_random_id(8)}"


def _resolve_skill_role(
    skill_role_name: Optional[str],
    skill_role_name_provided: bool,
    region: str,
) -> Optional[str]:
    if not skill_role_name_provided:
        return None
    resolved_name = (skill_role_name or "").strip()
    if not resolved_name:
        resolved_name = _generate_default_role_name()
    _ensure_sandbox_role(resolved_name, region)
    return resolved_name


def _resolve_create_extra_args(
    ctx: typer.Context,
) -> tuple[Optional[str], bool]:
    raw_args = list(ctx.args)
    skill_role_name: Optional[str] = None
    skill_role_name_provided = False
    remaining_args: list[str] = []
    index = 0
    while index < len(raw_args):
        current = raw_args[index]
        if current == SKILL_ROLE_NAME_OPTION:
            if skill_role_name_provided:
                error(f"{SKILL_ROLE_NAME_OPTION} cannot be provided multiple times")
            skill_role_name_provided = True
            if index + 1 < len(raw_args) and not raw_args[index + 1].startswith("-"):
                skill_role_name = raw_args[index + 1]
                index += 2
                continue
            index += 1
            continue
        if current.startswith(f"{SKILL_ROLE_NAME_OPTION}="):
            if skill_role_name_provided:
                error(f"{SKILL_ROLE_NAME_OPTION} cannot be provided multiple times")
            skill_role_name_provided = True
            skill_role_name = current.split("=", 1)[1]
            index += 1
            continue
        remaining_args.append(current)
        index += 1

    if remaining_args:
        unknown = " ".join(remaining_args)
        error(f"Unknown arguments: {unknown}")

    return skill_role_name, skill_role_name_provided


def create_tool(
    *,
    tool_type: str = DEFAULT_CREATE_TOOL_TYPE,
    tool_name: Optional[str] = None,
    tos_bucket: Optional[str] = None,
    tos_mount_path: str = DEFAULT_TOS_LOCAL_PATH,
    cpu: int = DEFAULT_CPU,
    model_name: Optional[str] = None,
    model_api_key: Optional[str] = None,
    model_provider: str | ModelProviderType | None = None,
    model_base_url: Optional[str] = None,
    skill_role_name: Optional[str] = None,
    skill_role_name_provided: bool = False,
    websearch_apikey: Optional[str] = None,
    image_url: Optional[str] = None,
    network_config: Optional[str] = None,
) -> dict[str, object]:
    resolved_model_base_url = normalize_model_base_url(model_base_url)
    raw_model_provider = (
        model_provider.value
        if isinstance(model_provider, ModelProviderType)
        else model_provider
    )
    effective_model_provider = raw_model_provider or infer_model_provider_from_base_url(
        resolved_model_base_url
    )
    resolved_model_provider = normalize_model_provider(effective_model_provider)
    region = _resolve_region(SANDBOX_REGION_ENV, "agentkit")
    tos_region = _resolve_region(SANDBOX_TOS_REGION_ENV, "tos")

    if skill_role_name_provided and websearch_apikey:
        error("--skill-role-name and --websearch-apikey are mutually exclusive")

    resolved_role_name = _resolve_skill_role(
        skill_role_name,
        skill_role_name_provided,
        region,
    )
    resolved_websearch_apikey = (websearch_apikey or "").strip() or None

    request = _build_create_tool_request(
        tool_type=tool_type,
        name=tool_name,
        tos_bucket=tos_bucket,
        tos_region=tos_region,
        tos_mount_path=tos_mount_path,
        cpu=cpu,
        model_name=model_name,
        model_api_key=model_api_key,
        model_provider=effective_model_provider,
        model_base_url=resolved_model_base_url,
        model_provider_was_provided=bool((raw_model_provider or "").strip()),
        model_base_url_was_provided=bool(resolved_model_base_url),
        role_name=resolved_role_name,
        websearch_apikey=resolved_websearch_apikey,
        image_url=image_url,
        network_config=network_config,
    )
    client = AgentkitToolsClient(
        region=region,
    )
    response = client.create_tool(request)
    tool_id = response.tool_id
    if not tool_id:
        raise RuntimeError("CreateTool response missing ToolId")
    final_tool = _wait_for_tool_ready(client, tool_id)
    return {
        "tool_id": tool_id,
        "tool_type": final_tool.tool_type or request.tool_type,
        "name": final_tool.name or request.name,
        "status": final_tool.status or TOOL_READY_STATUS,
        "model_provider": resolved_model_provider,
        "model_base_url": resolved_model_base_url,
        "role_name": resolved_role_name,
        "websearch_apikey_set": bool(resolved_websearch_apikey),
    }


def create_command(
    ctx: typer.Context,
    tool_type: Optional[str] = typer.Option(
        None,
        "--tool-type",
        help="Tool type. Defaults to sandbox.yaml (from sandbox build) or CodeEnv.",
    ),
    tool_name: Optional[str] = typer.Option(
        None,
        "--tool-name",
        help="Tool name. Defaults to an auto-generated name.",
    ),
    tos_bucket: Optional[str] = typer.Option(
        None,
        "--tos-bucket",
        help=("TOS bucket to mount. Omit to create the tool without a TOS mount."),
    ),
    tos_mount: Optional[str] = typer.Option(
        None,
        "--tos-mount",
        help=(
            "Local mount path for the TOS bucket. Requires --tos-bucket. "
            f"Defaults to {DEFAULT_TOS_LOCAL_PATH} when omitted."
        ),
    ),
    cpu: int = typer.Option(
        DEFAULT_CPU,
        "--cpu",
        help="Sandbox vCPU count. Allowed values: 2, 4, 8, 16.",
        callback=_validate_cpu,
    ),
    model_name: Optional[str] = typer.Option(
        None,
        "--model-name",
        help=(
            "Model name to inject into OPENCODE_MODEL, CODEX_MODEL, "
            "and ANTHROPIC_MODEL when creating a tool."
        ),
    ),
    model_api_key: Optional[str] = typer.Option(
        None,
        "--model-api-key",
        help=(
            "Model API key to inject into OPENCODE_API_KEY, CODEX_API_KEY, "
            "and ANTHROPIC_AUTH_TOKEN when creating a tool."
        ),
    ),
    model_provider: Optional[str] = typer.Option(
        None,
        "--model-provider",
        help="Model provider to use for base URLs, defaults, and model catalog.",
    ),
    model_base_url: Optional[str] = typer.Option(
        None,
        "--model-base-url",
        help=(
            "Custom model base URL to inject into OPENCODE_BASE_URL, "
            "CODEX_BASE_URL, MODEL_BASE_URL, and ANTHROPIC_BASE_URL."
        ),
    ),
    websearch_apikey: Optional[str] = typer.Option(
        None,
        "--websearch-apikey",
        help=(
            "Web search API key to inject as WEB_SEARCH_API_KEY env. "
            f"Mutually exclusive with {SKILL_ROLE_NAME_OPTION}. "
            "Use --disable-websearch-apikey in exec to disable it per session."
        ),
    ),
    image_url: Optional[str] = typer.Option(
        None,
        "--image-url",
        help="Custom image URL. Defaults to sandbox.yaml (from sandbox build). Required for Private tools.",
    ),
    network_config: Optional[str] = typer.Option(
        None,
        "--network-config",
        help=(
            "Network config as inline JSON or a JSON file path. Fields: "
            "private_access=false, public_access=true, vpc_id, subnet_ids, "
            "enable_shared_internet_access. private_access=true requires vpc_id."
        ),
    ),
) -> None:
    """Create an AgentKit Tool with optional TOS mount.

    Extra option:
    - --skill-role-name ROLE_NAME: reuse the role if it exists, otherwise create it
    - --skill-role-name: create a role with an auto-generated name
    """
    result = None
    try:
        skill_role_name, skill_role_name_provided = _resolve_create_extra_args(ctx)
        tool_type, image_url = _resolve_create_tool_image_defaults(
            tool_type=tool_type,
            image_url=image_url,
        )
        if tos_mount is not None and not (tos_bucket or "").strip():
            error("--tos-mount requires --tos-bucket")
        result = create_tool(
            tool_type=tool_type,
            tool_name=tool_name,
            tos_bucket=tos_bucket,
            tos_mount_path=tos_mount or DEFAULT_TOS_LOCAL_PATH,
            cpu=cpu,
            model_name=model_name,
            model_api_key=model_api_key,
            model_provider=model_provider,
            model_base_url=model_base_url,
            skill_role_name=skill_role_name,
            skill_role_name_provided=skill_role_name_provided,
            websearch_apikey=websearch_apikey,
            image_url=image_url,
            network_config=network_config,
        )
        save_tool_result_if_resolvable(str(result["tool_type"]), result)
    except (typer.Abort, typer.Exit):
        raise
    except Exception as exc:
        error(str(exc))

    typer.echo("工具创建成功")
    typer.echo(f"工具ID：{result['tool_id']}")
    typer.echo(f"状态：{result['status']}")
    if result.get("role_name"):
        typer.echo(f"角色名：{result['role_name']}")
    if not result.get("role_name") and not result.get("websearch_apikey_set"):
        typer.echo(
            "提示：未配置 WebSearch（可通过 --skill-role-name 配置 Role 或 "
            "--websearch-apikey 配置 API Key 来启用）"
        )
