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

"""Remote session sync helpers for sandbox CLI commands."""

from __future__ import annotations

from typing import Optional

from agentkit.sdk.tools import types as tools_types
from agentkit.toolkit.cli.sandbox.agentkit_client import AgentkitToolsClient
from agentkit.toolkit.cli.sandbox.tool_resolve import (
    SandboxToolType,
    resolve_existing_sandbox_tool_id,
)
from agentkit.toolkit.cli.sandbox.sandbox_client import (
    replace_tool_session_results,
)

LIST_SESSIONS_PAGE_SIZE = 100


def session_info_to_result(
    session: tools_types.SessionInfosForListSessions,
    tool_id: str,
) -> dict[str, object] | None:
    session_id = session.user_session_id
    if not isinstance(session_id, str) or not session_id.strip():
        return None

    return {
        "session_id": session_id.strip(),
        "tool_id": tool_id,
        "instance_id": session.session_id,
        "endpoint": session.endpoint,
    }


def list_all_session_results(
    client: AgentkitToolsClient,
    tool_id: str,
) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    next_token: Optional[str] = None
    seen_tokens: set[str] = set()

    while True:
        response = client.list_sessions(
            tools_types.ListSessionsRequest(
                tool_id=tool_id,
                max_results=LIST_SESSIONS_PAGE_SIZE,
                next_token=next_token,
            )
        )
        for session in response.session_infos or []:
            result = session_info_to_result(session, tool_id)
            if result:
                results.append(result)

        next_token = response.next_token or None
        if not next_token or next_token in seen_tokens:
            break
        seen_tokens.add(next_token)

    return results


def sync_remote_sessions(
    *,
    session_id: str | None,
    tool_id: Optional[str],
    tool_name: Optional[str] = None,
    tool_type: str | SandboxToolType | None,
    client: AgentkitToolsClient,
    env_var_name: str,
) -> str | None:
    resolved_tool_id = resolve_existing_sandbox_tool_id(
        tool_id=tool_id,
        tool_name=tool_name,
        tool_type=tool_type,
        client=client,
        env_var_name=env_var_name,
    )
    if not resolved_tool_id:
        return None

    results = list_all_session_results(client, resolved_tool_id)
    replace_tool_session_results(resolved_tool_id, results)
    return resolved_tool_id
