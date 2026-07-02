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
from agentkit.toolkit.cli.sandbox.model_config import (
    ANTHROPIC_BASE_URL_ENV_KEYS,
    CODEX_CONFIG_TOML_ENV,
    CODEX_MODEL_CATALOG_JSON_ENV,
    MODEL_API_KEY_ENV,
    MODEL_API_KEY_ENV_KEYS,
    MODEL_BASE_URL_ENV_KEYS,
    MODEL_NAME_ENV_KEYS,
    MODEL_PROVIDER_ENV,
    ModelProviderType,
    build_codex_config_toml,
    build_codex_model_catalog_json,
    infer_model_provider_from_base_url,
    normalize_model_base_url,
    normalize_optional_model_provider,
    resolve_model_base_urls,
    resolve_model_name,
    should_emit_codex_model_catalog,
    should_emit_codex_model_config,
    validate_model_provider_base_url,
)
from agentkit.toolkit.cli.sandbox.session_sync import (
    session_info_to_result,
    sync_remote_sessions,
)
from agentkit.toolkit.cli.sandbox.tos_config import build_session_tos_mount_points
from agentkit.toolkit.cli.sandbox.tool_resolve import (
    DEFAULT_SANDBOX_TOOL_TYPE,
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
WEB_SEARCH_API_KEY_ENV = "WEB_SEARCH_API_KEY"
CREATE_SESSION_START_FAIL_CODE = "ErrCreateSessionFail"
CREATE_SESSION_CONFIRM_ATTEMPTS = 6
CREATE_SESSION_CONFIRM_INTERVAL_SECONDS = 5
CREATE_SESSION_READY_STATUS = "ready"


def _append_envs(
    envs: list[tools_types.EnvsItemForCreateSession],
    keys: tuple[str, ...],
    value: Optional[str],
) -> None:
    resolved = (value or "").strip()
    if not resolved:
        return

    envs.extend(
        tools_types.EnvsItemForCreateSession(key=key, value=resolved) for key in keys
    )


def _append_codex_config_envs(
    envs: list[tools_types.EnvsItemForCreateSession],
    model_name: Optional[str],
    model_provider: str | ModelProviderType | None,
    model_base_url: Optional[str],
) -> None:
    resolved_model_name = (model_name or "").strip()
    if not resolved_model_name:
        return

    envs.append(
        tools_types.EnvsItemForCreateSession(
            key=CODEX_CONFIG_TOML_ENV,
            value=build_codex_config_toml(
                resolved_model_name,
                model_provider,
                model_base_url,
            ),
        )
    )
    if should_emit_codex_model_catalog(model_provider):
        envs.append(
            tools_types.EnvsItemForCreateSession(
                key=CODEX_MODEL_CATALOG_JSON_ENV,
                value=build_codex_model_catalog_json(
                    resolved_model_name,
                    model_provider,
                ),
            )
        )


def build_model_envs(
    *,
    model_name: Optional[str] = None,
    model_api_key: Optional[str] = None,
    model_provider: str | ModelProviderType | None = None,
    model_base_url: Optional[str] = None,
    model_provider_was_provided: Optional[bool] = None,
    model_base_url_was_provided: Optional[bool] = None,
    include_codex_config: bool = False,
    disable_websearch_apikey: bool = False,
) -> list[tools_types.EnvsItemForCreateSession] | None:
    envs: list[tools_types.EnvsItemForCreateSession] = []
    validate_model_provider_base_url(
        model_provider=model_provider,
        model_base_url=model_base_url,
        model_provider_was_provided=model_provider_was_provided,
        model_base_url_was_provided=model_base_url_was_provided,
    )
    resolved_model_base_url = normalize_model_base_url(model_base_url)
    effective_model_provider = model_provider or infer_model_provider_from_base_url(
        resolved_model_base_url
    )
    resolved_model_provider = normalize_optional_model_provider(
        effective_model_provider
    )
    resolved_model_name = (
        resolve_model_name(model_name, resolved_model_provider)
        if resolved_model_provider
        else (model_name or "").strip()
    )
    resolved_base_url, resolved_anthropic_base_url = (
        resolve_model_base_urls(
            model_provider=resolved_model_provider,
            model_base_url=resolved_model_base_url,
        )
        if resolved_model_provider or resolved_model_base_url
        else (None, None)
    )
    resolved_model_api_key = model_api_key or os.getenv(MODEL_API_KEY_ENV)
    _append_envs(envs, (MODEL_PROVIDER_ENV,), resolved_model_provider)
    _append_envs(envs, MODEL_NAME_ENV_KEYS, resolved_model_name)
    if resolved_base_url:
        _append_envs(envs, MODEL_BASE_URL_ENV_KEYS, resolved_base_url)
    if resolved_anthropic_base_url:
        _append_envs(
            envs,
            ANTHROPIC_BASE_URL_ENV_KEYS,
            resolved_anthropic_base_url,
        )
    if (
        include_codex_config
        and resolved_model_name
        and should_emit_codex_model_config(
            model_provider=resolved_model_provider,
            model_base_url=resolved_model_base_url,
        )
    ):
        _append_codex_config_envs(
            envs,
            resolved_model_name,
            resolved_model_provider,
            resolved_model_base_url,
        )
    _append_envs(envs, MODEL_API_KEY_ENV_KEYS, resolved_model_api_key)
    if disable_websearch_apikey:
        envs.append(
            tools_types.EnvsItemForCreateSession(key=WEB_SEARCH_API_KEY_ENV, value="")
        )
    return envs or None


def _resolve_ttl(ttl: Optional[int]) -> int:
    if ttl is not None:
        return ttl

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


def ensure_sandbox_session_with_status(
    session_id: Optional[str] = None,
    tool_id: Optional[str] = None,
    tool_type: str = DEFAULT_SANDBOX_TOOL_TYPE,
    ttl: Optional[int] = None,
    envs: Optional[list[tools_types.EnvsItemForCreateSession]] = None,
    resolve_tool: bool = True,
    include_tos_mount_points: bool = True,
) -> tuple[dict[str, object], bool]:
    resolved_session_id = session_id or str(uuid.uuid4())
    existing = find_session_result(resolved_session_id) if session_id else None
    client = AgentkitToolsClient()
    synced_tool_id = None
    if resolve_tool and session_id and not existing:
        synced_tool_id = sync_remote_sessions(
            session_id=resolved_session_id,
            tool_id=tool_id,
            tool_type=tool_type,
            client=client,
            env_var_name=SANDBOX_TOOL_ID_ENV,
        )
        existing = find_session_result(resolved_session_id)

    resolved_tool_id = synced_tool_id
    if not resolved_tool_id:
        if resolve_tool:
            resolved_tool_id = resolve_sandbox_tool_id(
                tool_id=tool_id,
                tool_type=tool_type,
                default_tool_id=existing.get("tool_id") if existing else None,
                client=client,
                env_var_name=SANDBOX_TOOL_ID_ENV,
            )
        else:
            resolved_tool_id = (tool_id or "").strip()
            if not resolved_tool_id:
                error("Sandbox tool ID is required")

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
                tool_type=tool_type,
                client=client,
                env_var_name=SANDBOX_TOOL_ID_ENV,
            )
            if synced_tool_id:
                resolved_tool_id = synced_tool_id
            existing = find_session_result(resolved_session_id)
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
        _resolve_ttl(ttl),
        envs=session_envs,
        include_tos_mount_points=include_tos_mount_points,
    )
    save_session_result(result)
    return result, True


def ensure_sandbox_session(
    session_id: Optional[str] = None,
    tool_id: Optional[str] = None,
    tool_type: str = DEFAULT_SANDBOX_TOOL_TYPE,
    ttl: Optional[int] = None,
    envs: Optional[list[tools_types.EnvsItemForCreateSession]] = None,
    resolve_tool: bool = True,
    include_tos_mount_points: bool = True,
) -> dict[str, object]:
    result, _is_new = ensure_sandbox_session_with_status(
        session_id=session_id,
        tool_id=tool_id,
        tool_type=tool_type,
        ttl=ttl,
        envs=envs,
        resolve_tool=resolve_tool,
        include_tos_mount_points=include_tos_mount_points,
    )
    return result
