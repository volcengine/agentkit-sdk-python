# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
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

# Includes generated management APIs and maintained async command APIs.

from __future__ import annotations

from typing import Dict
from agentkit.client import BaseAgentkitClient
from ._data_plane import ToolsDataPlaneMixin
from .types import (
    DeleteAsyncCommandResponse,
    DeleteAsyncCommandRequest,
    ViewAsyncCommandResponse,
    ViewAsyncCommandRequest,
    AsyncExecCommandResponse,
    AsyncExecCommandRequest,
    CreateSessionRequest,
    CreateSessionResponse,
    CreateSessionSnapshotRequest,
    CreateSessionSnapshotResponse,
    CreateToolRequest,
    CreateToolResponse,
    DeleteSessionRequest,
    DeleteSessionResponse,
    DeleteSessionSnapshotRequest,
    DeleteSessionSnapshotResponse,
    DeleteToolRequest,
    DeleteToolResponse,
    GetSessionLogsRequest,
    GetSessionLogsResponse,
    GetSessionRequest,
    GetSessionResponse,
    GetSessionSnapshotRequest,
    GetSessionSnapshotResponse,
    GetToolRequest,
    GetToolResponse,
    ListSessionSnapshotsRequest,
    ListSessionSnapshotsResponse,
    ListSessionsRequest,
    ListSessionsResponse,
    ListToolsRequest,
    ListToolsResponse,
    PauseSessionRequest,
    PauseSessionResponse,
    ResumeSessionRequest,
    ResumeSessionResponse,
    ResumeSessionFromSnapshotRequest,
    ResumeSessionFromSnapshotResponse,
    SetSessionTtlRequest,
    SetSessionTtlResponse,
    UpdateToolRequest,
    UpdateToolResponse,
)


class AgentkitToolsClient(ToolsDataPlaneMixin, BaseAgentkitClient):
    """AgentKit Tools Management Service"""

    API_ACTIONS: Dict[str, str] = {
        "DeleteAsyncCommand": "DeleteAsyncCommand",
        "ViewAsyncCommand": "ViewAsyncCommand",
        "AsyncExecCommand": "AsyncExecCommand",
        "CreateSession": "CreateSession",
        "CreateSessionSnapshot": "CreateSessionSnapshot",
        "CreateTool": "CreateTool",
        "DeleteSession": "DeleteSession",
        "DeleteSessionSnapshot": "DeleteSessionSnapshot",
        "DeleteTool": "DeleteTool",
        "GetSession": "GetSession",
        "GetSessionLogs": "GetSessionLogs",
        "GetSessionSnapshot": "GetSessionSnapshot",
        "GetTool": "GetTool",
        "ListSessionSnapshots": "ListSessionSnapshots",
        "ListSessions": "ListSessions",
        "ListTools": "ListTools",
        "PauseSession": "PauseSession",
        "ResumeSession": "ResumeSession",
        "ResumeSessionFromSnapshot": "ResumeSessionFromSnapshot",
        "SetSessionTtl": "SetSessionTtl",
        "UpdateTool": "UpdateTool",
    }

    def __init__(
        self,
        access_key: str = "",
        secret_key: str = "",
        region: str = "",
        session_token: str = "",
        *,
        data_plane_host: str = "",
    ) -> None:
        super().__init__(
            access_key=access_key,
            secret_key=secret_key,
            region=region,
            session_token=session_token,
            service_name="tools",
            data_plane_host=data_plane_host,
        )

    def create_session(self, request: CreateSessionRequest) -> CreateSessionResponse:
        return self._invoke_api(
            api_action="CreateSession",
            request=request,
            response_type=CreateSessionResponse,
        )

    def create_session_snapshot(
        self, request: CreateSessionSnapshotRequest
    ) -> CreateSessionSnapshotResponse:
        return self._invoke_api(
            api_action="CreateSessionSnapshot",
            request=request,
            response_type=CreateSessionSnapshotResponse,
        )

    def create_tool(self, request: CreateToolRequest) -> CreateToolResponse:
        return self._invoke_api(
            api_action="CreateTool",
            request=request,
            response_type=CreateToolResponse,
        )

    def delete_session(self, request: DeleteSessionRequest) -> DeleteSessionResponse:
        return self._invoke_api(
            api_action="DeleteSession",
            request=request,
            response_type=DeleteSessionResponse,
        )

    def delete_session_snapshot(
        self, request: DeleteSessionSnapshotRequest
    ) -> DeleteSessionSnapshotResponse:
        return self._invoke_api(
            api_action="DeleteSessionSnapshot",
            request=request,
            response_type=DeleteSessionSnapshotResponse,
        )

    def delete_tool(self, request: DeleteToolRequest) -> DeleteToolResponse:
        return self._invoke_api(
            api_action="DeleteTool",
            request=request,
            response_type=DeleteToolResponse,
        )

    def get_session(self, request: GetSessionRequest) -> GetSessionResponse:
        return self._invoke_api(
            api_action="GetSession",
            request=request,
            response_type=GetSessionResponse,
        )

    def get_session_logs(
        self, request: GetSessionLogsRequest
    ) -> GetSessionLogsResponse:
        return self._invoke_api(
            api_action="GetSessionLogs",
            request=request,
            response_type=GetSessionLogsResponse,
        )

    def get_session_snapshot(
        self, request: GetSessionSnapshotRequest
    ) -> GetSessionSnapshotResponse:
        return self._invoke_api(
            api_action="GetSessionSnapshot",
            request=request,
            response_type=GetSessionSnapshotResponse,
        )

    def get_tool(self, request: GetToolRequest) -> GetToolResponse:
        return self._invoke_api(
            api_action="GetTool",
            request=request,
            response_type=GetToolResponse,
        )

    def list_session_snapshots(
        self, request: ListSessionSnapshotsRequest
    ) -> ListSessionSnapshotsResponse:
        return self._invoke_api(
            api_action="ListSessionSnapshots",
            request=request,
            response_type=ListSessionSnapshotsResponse,
        )

    def list_sessions(self, request: ListSessionsRequest) -> ListSessionsResponse:
        return self._invoke_api(
            api_action="ListSessions",
            request=request,
            response_type=ListSessionsResponse,
        )

    def list_tools(self, request: ListToolsRequest) -> ListToolsResponse:
        return self._invoke_api(
            api_action="ListTools",
            request=request,
            response_type=ListToolsResponse,
        )

    def pause_session(self, request: PauseSessionRequest) -> PauseSessionResponse:
        return self._invoke_api(
            api_action="PauseSession",
            request=request,
            response_type=PauseSessionResponse,
        )

    def resume_session(self, request: ResumeSessionRequest) -> ResumeSessionResponse:
        return self._invoke_api(
            api_action="ResumeSession",
            request=request,
            response_type=ResumeSessionResponse,
        )

    def resume_session_from_snapshot(
        self, request: ResumeSessionFromSnapshotRequest
    ) -> ResumeSessionFromSnapshotResponse:
        return self._invoke_api(
            api_action="ResumeSessionFromSnapshot",
            request=request,
            response_type=ResumeSessionFromSnapshotResponse,
        )

    def set_session_ttl(self, request: SetSessionTtlRequest) -> SetSessionTtlResponse:
        return self._invoke_api(
            api_action="SetSessionTtl",
            request=request,
            response_type=SetSessionTtlResponse,
        )

    def update_tool(self, request: UpdateToolRequest) -> UpdateToolResponse:
        return self._invoke_api(
            api_action="UpdateTool",
            request=request,
            response_type=UpdateToolResponse,
        )

    def async_exec_command(
        self, request: AsyncExecCommandRequest
    ) -> AsyncExecCommandResponse:
        return self._invoke_api(
            api_action="AsyncExecCommand",
            request=request,
            response_type=AsyncExecCommandResponse,
        )

    def view_async_command(
        self, request: ViewAsyncCommandRequest
    ) -> ViewAsyncCommandResponse:
        return self._invoke_api(
            api_action="ViewAsyncCommand",
            request=request,
            response_type=ViewAsyncCommandResponse,
        )

    def delete_async_command(
        self, request: DeleteAsyncCommandRequest
    ) -> DeleteAsyncCommandResponse:
        return self._invoke_api(
            api_action="DeleteAsyncCommand",
            request=request,
            response_type=DeleteAsyncCommandResponse,
        )
