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

"""Mount command for sandbox CLI."""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
from typing import Optional
from urllib.parse import urljoin
from urllib.request import urlopen

import typer

from agentkit.utils.http_defaults import http_timeout
from agentkit.sdk.tools import types as tools_types
from agentkit.toolkit.cli.sandbox.agentkit_client import AgentkitToolsClient
from agentkit.toolkit.cli.sandbox.session_create import SANDBOX_TOOL_ID_ENV
from agentkit.toolkit.cli.sandbox.session_sync import sync_remote_sessions
from agentkit.toolkit.cli.sandbox.sandbox_client import (
    echo_json,
    error,
    find_session_result,
)

SANDBOX_DISCOVERY_PATH = Path(".agentkit") / "sandbox" / "agentkit-cli"
AUTH_SESSION_NAME_PREFIX = "agentkit-cli-"
AUTH_SESSION_NAME_SUFFIX = "volces.com.json"
AUTH_SESSION_JSON_SUFFIX = ".json"
TOS_BROWSER_DOWNLOAD_URL = (
    "https://lf3-cdn-tos.bytegoofy.com/obj/tron-demo/7605960479860594954/"
    "releases/328661904/1.12.7/darwin-arm64/"
    "TOS_Browser_Public-v1.12.7-darwin-arm64.dmg"
)
TOS_BROWSER_INSTALL_HINT = "请安装 TosBrowser 应用"
USER_POOL_PATTERN = re.compile(r"userpool-([^.]+)\.userpool")


class TosBrowserNotFoundError(Exception):
    """Raised when the OS has no handler for the tosbrowser URL scheme."""


def _get_discovery_store_path() -> Path:
    return Path.cwd() / SANDBOX_DISCOVERY_PATH


def _get_auth_sessions_dir() -> Path:
    return Path.home() / ".agentkit" / "auth" / "sessions"


def _resolve_required(value: str, option_name: str) -> str:
    resolved = (value or "").strip()
    if not resolved:
        error(f"{option_name} must not be empty")
    return resolved


def _normalize_oauth_url(oauth_url: str) -> str:
    resolved = oauth_url.strip()
    if "://" not in resolved:
        return f"https://{resolved}"
    return resolved


def _oauth_url_from_session_file_name(file_name: str) -> str:
    if not file_name.startswith(AUTH_SESSION_NAME_PREFIX) or not file_name.endswith(
        AUTH_SESSION_NAME_SUFFIX
    ):
        error(
            "Invalid auth session filename for sandbox mount: "
            f"{file_name}. Expected {AUTH_SESSION_NAME_PREFIX}*"
            f"{AUTH_SESSION_NAME_SUFFIX}"
        )
    return file_name[: -len(AUTH_SESSION_JSON_SUFFIX)]


def _latest_auth_session_file() -> Path:
    sessions_dir = _get_auth_sessions_dir()
    if not sessions_dir.is_dir():
        error(f"Auth session directory not found: {sessions_dir}")

    session_files = [path for path in sessions_dir.iterdir() if path.is_file()]
    if not session_files:
        error(f"Auth session directory is empty: {sessions_dir}")

    return max(session_files, key=lambda path: path.stat().st_mtime)


def _resolve_oauth_url(oauth_url: Optional[str]) -> str:
    if oauth_url is not None:
        return _normalize_oauth_url(_resolve_required(oauth_url, "--oauth-url"))

    session_file = _latest_auth_session_file()
    return _normalize_oauth_url(_oauth_url_from_session_file_name(session_file.name))


def _field_value(source: object, *keys: str) -> object:
    for key in keys:
        if isinstance(source, dict):
            value = source.get(key)
        else:
            value = getattr(source, key, None)
        if value is not None:
            return value
    return None


def _tool_payload(response: object) -> object:
    if isinstance(response, dict) and isinstance(response.get("Result"), dict):
        return response["Result"]
    return response


def _extract_tos_bucket_from_tool(tool: object) -> str | None:
    payload = _tool_payload(tool)
    tos_mount_config = _field_value(
        payload,
        "TosMountConfig",
        "tos_mount_config",
    )
    if not tos_mount_config:
        return None

    mount_points = _field_value(tos_mount_config, "MountPoints", "mount_points")
    if not isinstance(mount_points, list):
        return None

    for mount_point in mount_points:
        bucket_name = _field_value(mount_point, "BucketName", "bucket_name")
        if isinstance(bucket_name, str) and bucket_name.strip():
            return bucket_name.strip()
    return None


def _resolve_tos_bucket(*, tool_id: str) -> str:
    try:
        tool = AgentkitToolsClient().get_tool(
            tools_types.GetToolRequest(tool_id=tool_id)
        )
    except Exception as exc:
        error(f"Failed to get sandbox tool {tool_id}: {exc}")

    resolved_tos_bucket = _extract_tos_bucket_from_tool(tool)
    if not resolved_tos_bucket:
        error(f"当前工具未挂载 Tos: {tool_id}")
    return resolved_tos_bucket


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


def _session_tool_id(session: dict[str, object], session_id: str) -> str:
    tool_id = _field_value(session, "tool_id", "ToolId")
    if not isinstance(tool_id, str) or not tool_id.strip():
        error(f"Sandbox session record missing tool_id: {session_id}")
    return tool_id.strip()


def _resolve_session_tool_id(session_id: str) -> str:
    session = find_session_result(session_id)
    resolved_tool_id: str | None = None
    if session is None:
        resolved_tool_id = sync_remote_sessions(
            session_id=session_id,
            tool_id=None,
            tool_type=None,
            client=AgentkitToolsClient(),
            env_var_name=SANDBOX_TOOL_ID_ENV,
        )
        session = find_session_result(session_id)

    if session is None:
        echo_json(
            _session_not_found_result(
                session_id=session_id,
                tool_id=resolved_tool_id,
            )
        )
        raise typer.Exit(1)

    return _session_tool_id(session, session_id)


def _build_discovery_url(oauth_url: str) -> str:
    return urljoin(f"{oauth_url.rstrip('/')}/", ".well-known/agentkit-cli")


def _download_discovery(oauth_url: str) -> dict[str, object]:
    discovery_url = _build_discovery_url(oauth_url)
    path = _get_discovery_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    with urlopen(discovery_url, timeout=http_timeout()) as response:
        content = response.read()
    path.write_bytes(content)

    try:
        data = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        error(f"Invalid sandbox mount discovery file {path}: {exc}")

    if not isinstance(data, dict):
        error(f"Invalid sandbox mount discovery file {path}: expected JSON object")
    return data


def _required_discovery_field(
    discovery: dict[str, object],
    field_name: str,
) -> str:
    value = discovery.get(field_name)
    if not isinstance(value, str) or not value.strip():
        error(f"Sandbox mount discovery missing {field_name}")
    return value.strip()


def _extract_user_pool_id(issuer: str) -> str:
    match = USER_POOL_PATTERN.search(issuer)
    if not match:
        error("Sandbox mount discovery issuer missing user pool ID")
    return match.group(1)


def _build_tosbrowser_command(
    *,
    tos_bucket: str,
    tool_id: str,
    session_id: str,
    role_trn: str,
    user_pool_id: str,
    client_id: str,
) -> str:
    return (
        "tosbrowser://open?"
        f"path=tos://{tos_bucket}/sandbox-session/tool-{tool_id}/"
        f"session-{session_id}/"
        f"&type=oAuthLogin"
        f"&role={role_trn}"
        f"&userPool={user_pool_id}"
        f"&clientId={client_id}"
    )


def _called_process_error_output(exc: subprocess.CalledProcessError) -> str:
    parts = [
        str(item).strip()
        for item in (exc.stderr, exc.stdout)
        if isinstance(item, str) and item.strip()
    ]
    if parts:
        return "\n".join(parts)
    return str(exc)


def _is_tosbrowser_not_found_error(message: str) -> bool:
    return (
        "No application knows how to open URL" in message
        or "kLSApplicationNotFoundErr" in message
        or "Code=-10814" in message
    )


def _open_tosbrowser(command: str) -> None:
    try:
        subprocess.run(
            ["open", command],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        output = _called_process_error_output(exc)
        if _is_tosbrowser_not_found_error(output):
            raise TosBrowserNotFoundError(output) from exc
        raise


def mount_command(
    session_id: str = typer.Option(
        ...,
        "--session-id",
        "--sid",
        "-s",
        help="Sandbox session ID to mount.",
    ),
    oauth_url: Optional[str] = typer.Option(
        None,
        "--oauth-url",
        help=(
            "OAuth discovery base URL. Defaults to the latest "
            "~/.agentkit/auth/sessions/ agentkit-cli session."
        ),
    ),
) -> None:
    """Open the sandbox session TOS path in TOS Browser."""
    try:
        resolved_session_id = _resolve_required(session_id, "--session-id")
        resolved_oauth_url = _resolve_oauth_url(oauth_url)
        resolved_tool_id = _resolve_session_tool_id(resolved_session_id)
        resolved_tos_bucket = _resolve_tos_bucket(tool_id=resolved_tool_id)
        discovery = _download_discovery(resolved_oauth_url)
        issuer = _required_discovery_field(discovery, "issuer")
        role_trn = _required_discovery_field(discovery, "role_trn")
        client_id = _required_discovery_field(discovery, "client_id")
        user_pool_id = _extract_user_pool_id(issuer)
        command = _build_tosbrowser_command(
            tos_bucket=resolved_tos_bucket,
            tool_id=resolved_tool_id,
            session_id=resolved_session_id,
            role_trn=role_trn,
            user_pool_id=user_pool_id,
            client_id=client_id,
        )
        _open_tosbrowser(command)
    except TosBrowserNotFoundError as exc:
        echo_json(
            {
                "tool_id": resolved_tool_id,
                "session_id": resolved_session_id,
                "command": command,
                "error_msg": "Failed to open TosBrowser",
                "original_error": str(exc),
                "install_hint": TOS_BROWSER_INSTALL_HINT,
                "download_url": TOS_BROWSER_DOWNLOAD_URL,
            }
        )
        raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as exc:
        error(str(exc))

    echo_json(
        {
            "tool_id": resolved_tool_id,
            "session_id": resolved_session_id,
            "command": command,
        }
    )
