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

"""Session creation helpers for sandbox CLI."""

from __future__ import annotations

import os
import time
import uuid
from typing import Optional

from agentkit.sdk.tools import types as tools_types
from agentkit.toolkit.cli.sandbox.agentkit_client import (
    AgentkitToolsClient,
    is_tip_agentkit_client,
)
from agentkit.toolkit.cli.sandbox.config_store import (
    config_default_int,
    config_default_str,
)
from agentkit.toolkit.cli.sandbox.env_config import (
    WEB_SEARCH_API_KEY_ENV as _WEB_SEARCH_API_KEY_ENV,
    build_exec_session_envs,
)
from agentkit.toolkit.cli.sandbox.session_sync import (
    session_info_to_result,
    sync_remote_sessions,
)
from agentkit.toolkit.cli.sandbox.tos_config import build_session_tos_mount_points
from agentkit.toolkit.cli.sandbox.tool_resolve import (
    DEFAULT_SANDBOX_TOOL_TYPE,
    is_tool_snapshot_enabled,
    resolve_existing_sandbox_tool_id,
    resolve_sandbox_tool_id,
)
from agentkit.toolkit.cli.sandbox.sandbox_client import (
    error,
    find_session_result,
    save_session_result,
)

DEFAULT_SANDBOX_TTL = 28800
SANDBOX_TOOL_ID_ENV = "AGENTKIT_SANDBOX_TOOL_ID"
SANDBOX_TTL_ENV = "AGENTKIT_SANDBOX_TTL"
WEB_SEARCH_API_KEY_ENV = _WEB_SEARCH_API_KEY_ENV
CREATE_SESSION_START_FAIL_CODE = "ErrCreateSessionFail"
CREATE_SESSION_CONFIRM_ATTEMPTS = 6
CREATE_SESSION_CONFIRM_INTERVAL_SECONDS = 5
CREATE_SESSION_READY_STATUS = "ready"


def build_model_envs(**kwargs):
    """Backward-compatible wrapper for the exec session env profile."""
    return build_exec_session_envs(**kwargs)


def _resolve_ttl(ttl: Optional[int]) -> int:
    if ttl is not None:
        return ttl

    configured_ttl = config_default_int("ttl")
    if configured_ttl is not None:
        return configured_ttl

    raw = (os.getenv(SANDBOX_TTL_ENV) or "").strip()
    if not raw:
        return DEFAULT_SANDBOX_TTL

    try:
        return int(raw)
    except ValueError:
        error(f"{SANDBOX_TTL_ENV} must be an integer")


def _is_session_missing_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(
        token in message
        for token in (
            "not found",
            "not exist",
            "notfound",
            "not_found",
            "不存在",
        )
    )


def _is_create_session_start_fail_error(exc: Exception) -> bool:
    return CREATE_SESSION_START_FAIL_CODE in str(exc)


def _is_confirmed_session_ready(
    session: tools_types.SessionInfosForListSessions,
) -> bool:
    status = getattr(session, "status", None)
    endpoint = getattr(session, "endpoint", None)
    if (
        not isinstance(status, str)
        or status.strip().lower() != CREATE_SESSION_READY_STATUS
    ):
        return False
    return isinstance(endpoint, str) and bool(endpoint.strip())


def _build_result(
    *,
    session_id: str,
    tool_id: str,
    instance_id: object,
    endpoint: object,
) -> dict[str, object]:
    return {
        "session_id": session_id,
        "tool_id": tool_id,
        "instance_id": instance_id,
        "endpoint": endpoint,
    }


def _build_create_result(
    response: tools_types.CreateSessionResponse,
    session_id: str,
    tool_id: str,
) -> dict[str, object]:
    return _build_result(
        session_id=response.user_session_id or session_id,
        tool_id=tool_id,
        instance_id=response.session_id,
        endpoint=response.endpoint,
    )


def _build_get_result(
    response: tools_types.GetSessionResponse,
    existing: dict[str, object],
    session_id: str,
    tool_id: str,
) -> dict[str, object]:
    return _build_result(
        session_id=response.user_session_id or session_id,
        tool_id=tool_id,
        instance_id=response.session_id or existing.get("instance_id"),
        endpoint=response.endpoint or existing.get("endpoint"),
    )


def _get_existing_remote_session(
    client: AgentkitToolsClient,
    existing: dict[str, object],
    session_id: str,
    tool_id: str,
) -> dict[str, object] | None:
    instance_id = existing.get("instance_id")
    if not isinstance(instance_id, str) or not instance_id:
        return None

    try:
        response = client.get_session(
            tools_types.GetSessionRequest(
                tool_id=tool_id,
                session_id=instance_id,
            )
        )
    except Exception as exc:
        if _is_session_missing_error(exc):
            return None
        raise

    return _build_get_result(response, existing, session_id, tool_id)


def _create_session(
    client: AgentkitToolsClient,
    session_id: str,
    tool_id: str,
    ttl: int,
    envs: Optional[list[tools_types.EnvsItemForCreateSession]] = None,
    include_tos_mount_points: bool = True,
) -> dict[str, object]:
    tos_mount_points = None
    if include_tos_mount_points and not is_tip_agentkit_client(client):
        tool = client.get_tool(tools_types.GetToolRequest(tool_id=tool_id))
        tos_mount_points = build_session_tos_mount_points(
            tool,
            tool_id=tool_id,
            session_id=session_id,
        )
    request = tools_types.CreateSessionRequest(
        tool_id=tool_id,
        ttl=ttl,
        ttl_unit="second",
        user_session_id=session_id,
        envs=envs,
        tos_mount_points=tos_mount_points,
    )
    try:
        response = client.create_session(request)
    except Exception as exc:
        if not _is_create_session_start_fail_error(exc):
            raise
        result = _confirm_session_after_create_start_fail(
            client,
            session_id=session_id,
            tool_id=tool_id,
        )
        if result:
            return result
        raise
    return _build_create_result(response, session_id, tool_id)


def _confirm_session_after_create_start_fail(
    client: AgentkitToolsClient,
    *,
    session_id: str,
    tool_id: str,
) -> dict[str, object] | None:
    for attempt in range(CREATE_SESSION_CONFIRM_ATTEMPTS):
        response = client.list_sessions(
            tools_types.ListSessionsRequest(
                tool_id=tool_id,
                max_results=10,
                filters=[
                    tools_types.FiltersItemForListSessions(
                        name="UserSessionId",
                        values=[session_id],
                    )
                ],
            )
        )
        for session in response.session_infos or []:
            result = session_info_to_result(session, tool_id)
            if (
                result
                and result.get("session_id") == session_id
                and _is_confirmed_session_ready(session)
            ):
                return result

        if attempt < CREATE_SESSION_CONFIRM_ATTEMPTS - 1:
            time.sleep(CREATE_SESSION_CONFIRM_INTERVAL_SECONDS)

    return None


def _get_remote_session_by_user_session_id(
    client: AgentkitToolsClient,
    *,
    session_id: str,
    tool_id: str,
) -> dict[str, object] | None:
    response = client.list_sessions(
        tools_types.ListSessionsRequest(
            tool_id=tool_id,
            max_results=10,
            filters=[
                tools_types.FiltersItemForListSessions(
                    name="UserSessionId",
                    values=[session_id],
                )
            ],
        )
    )
    for session in response.session_infos or []:
        result = session_info_to_result(session, tool_id)
        if result and result.get("session_id") == session_id:
            return result
    return None


def _get_first_session_snapshot_id(
    client: AgentkitToolsClient,
    *,
    session_id: str,
    tool_id: str,
) -> str | None:
    response = client.list_session_snapshots(
        tools_types.ListSessionSnapshotsRequest(
            tool_id=tool_id,
            user_session_id=session_id,
            max_results=1,
        )
    )
    for snapshot in response.snapshots or []:
        snapshot_id = getattr(snapshot, "snapshot_id", None)
        if isinstance(snapshot_id, str) and snapshot_id.strip():
            return snapshot_id.strip()
    return None


def _resume_session_from_snapshot(
    client: AgentkitToolsClient,
    *,
    session_id: str,
    tool_id: str,
    snapshot_id: str,
    ttl: int,
) -> dict[str, object]:
    response = client.resume_session_from_snapshot(
        tools_types.ResumeSessionFromSnapshotRequest(
            tool_id=tool_id,
            snapshot_id=snapshot_id,
            ttl=ttl,
            create_new_instance=False,
        )
    )
    instance_id = response.session_id
    if not isinstance(instance_id, str) or not instance_id.strip():
        raise RuntimeError("ResumeSessionFromSnapshot response missing SessionId")

    session = client.get_session(
        tools_types.GetSessionRequest(
            tool_id=tool_id,
            session_id=instance_id.strip(),
        )
    )
    return _build_result(
        session_id=session_id,
        tool_id=tool_id,
        instance_id=session.session_id or instance_id.strip(),
        endpoint=session.endpoint,
    )


def _maybe_restore_snapshot_session(
    client: AgentkitToolsClient,
    *,
    session_id: str,
    tool_id: str,
    tool_type: str,
    ttl: int,
) -> tuple[dict[str, object], bool] | None:
    if not is_tool_snapshot_enabled(tool_id=tool_id, tool_type=tool_type):
        return None

    current = _get_remote_session_by_user_session_id(
        client,
        session_id=session_id,
        tool_id=tool_id,
    )
    if current:
        return current, False

    snapshot_id = _get_first_session_snapshot_id(
        client,
        session_id=session_id,
        tool_id=tool_id,
    )
    if not snapshot_id:
        return None

    result = _resume_session_from_snapshot(
        client,
        session_id=session_id,
        tool_id=tool_id,
        snapshot_id=snapshot_id,
        ttl=ttl,
    )
    return result, True


def ensure_sandbox_session_with_status(
    session_id: Optional[str] = None,
    tool_id: Optional[str] = None,
    tool_name: Optional[str] = None,
    tool_type: str = DEFAULT_SANDBOX_TOOL_TYPE,
    ttl: Optional[int] = None,
    envs: Optional[list[tools_types.EnvsItemForCreateSession]] = None,
    resolve_tool: bool = True,
    include_tos_mount_points: bool = True,
) -> tuple[dict[str, object], bool]:
    resolved_session_id = (
        session_id or config_default_str("session-id") or str(uuid.uuid4())
    )
    client = AgentkitToolsClient()
    ttl_seconds = _resolve_ttl(ttl)

    if resolve_tool:
        resolved_tool_arg = (
            tool_id
            if tool_name is not None
            else tool_id or config_default_str("tool-id")
        )
        resolved_tool_id = resolve_sandbox_tool_id(
            tool_id=resolved_tool_arg,
            tool_name=tool_name,
            tool_type=tool_type,
            client=client,
            env_var_name=SANDBOX_TOOL_ID_ENV,
        )
    else:
        if tool_name:
            resolved_tool_id = resolve_existing_sandbox_tool_id(
                tool_id=tool_id,
                tool_name=tool_name,
                tool_type=tool_type,
                client=client,
                env_var_name=SANDBOX_TOOL_ID_ENV,
            )
        else:
            resolved_tool_id = (tool_id or "").strip()
        if not resolved_tool_id:
            error("Sandbox tool ID is required")

    existing = (
        find_session_result(resolved_tool_id, resolved_session_id)
        if session_id
        else None
    )
    synced_sessions = False

    snapshot_enabled = bool(session_id) and is_tool_snapshot_enabled(
        tool_id=resolved_tool_id,
        tool_type=tool_type,
    )
    if snapshot_enabled:
        restored = _maybe_restore_snapshot_session(
            client,
            session_id=resolved_session_id,
            tool_id=resolved_tool_id,
            tool_type=tool_type,
            ttl=ttl_seconds,
        )
        if restored:
            result, is_new = restored
            save_session_result(result)
            return result, is_new

        result = _create_session(
            client,
            resolved_session_id,
            resolved_tool_id,
            ttl_seconds,
            envs=envs,
            include_tos_mount_points=include_tos_mount_points,
        )
        save_session_result(result)
        return result, True

    if existing:
        result = _get_existing_remote_session(
            client,
            existing,
            resolved_session_id,
            resolved_tool_id,
        )
        if result:
            save_session_result(result)
            return result, False

        if resolve_tool:
            synced_tool_id = sync_remote_sessions(
                session_id=resolved_session_id,
                tool_id=resolved_tool_id,
                tool_name=None,
                tool_type=tool_type,
                client=client,
                env_var_name=SANDBOX_TOOL_ID_ENV,
            )
            if synced_tool_id:
                synced_sessions = True
                resolved_tool_id = synced_tool_id
            existing = find_session_result(resolved_tool_id, resolved_session_id)
            if existing:
                result = _get_existing_remote_session(
                    client,
                    existing,
                    resolved_session_id,
                    resolved_tool_id,
                )
                if result:
                    save_session_result(result)
                    return result, False

    if resolve_tool and session_id and not existing and not synced_sessions:
        existing = _get_remote_session_by_user_session_id(
            client,
            session_id=resolved_session_id,
            tool_id=resolved_tool_id,
        )
        if existing:
            result = _get_existing_remote_session(
                client,
                existing,
                resolved_session_id,
                resolved_tool_id,
            )
            if result:
                save_session_result(result)
                return result, False

    if session_id and not resolve_tool:
        result = _get_remote_session_by_user_session_id(
            client,
            session_id=resolved_session_id,
            tool_id=resolved_tool_id,
        )
        if result:
            save_session_result(result)
            return result, False

    session_envs = envs
    result = _create_session(
        client,
        resolved_session_id,
        resolved_tool_id,
        ttl_seconds,
        envs=session_envs,
        include_tos_mount_points=include_tos_mount_points,
    )
    save_session_result(result)
    return result, True


def ensure_sandbox_session(
    session_id: Optional[str] = None,
    tool_id: Optional[str] = None,
    tool_name: Optional[str] = None,
    tool_type: str = DEFAULT_SANDBOX_TOOL_TYPE,
    ttl: Optional[int] = None,
    envs: Optional[list[tools_types.EnvsItemForCreateSession]] = None,
    resolve_tool: bool = True,
    include_tos_mount_points: bool = True,
) -> dict[str, object]:
    result, _is_new = ensure_sandbox_session_with_status(
        session_id=session_id,
        tool_id=tool_id,
        tool_name=tool_name,
        tool_type=tool_type,
        ttl=ttl,
        envs=envs,
        resolve_tool=resolve_tool,
        include_tos_mount_points=include_tos_mount_points,
    )
    return result
