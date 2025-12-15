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

# Auto-generated from API JSON definition
# Do not edit manually

from __future__ import annotations

from typing import Dict
from agentkit.client import BaseAgentkitClient
from .types import (
    CreateSessionRequest,
    CreateSessionResponse,
    CreateToolRequest,
    CreateToolResponse,
    DeleteSessionRequest,
    DeleteSessionResponse,
    DeleteToolRequest,
    DeleteToolResponse,
    GetSessionLogsRequest,
    GetSessionLogsResponse,
    GetSessionRequest,
    GetSessionResponse,
    GetToolRequest,
    GetToolResponse,
    ListSessionsRequest,
    ListSessionsResponse,
    ListToolsRequest,
    ListToolsResponse,
    SetSessionTtlRequest,
    SetSessionTtlResponse,
    UpdateToolRequest,
    UpdateToolResponse,
)


class AgentkitToolsClient(BaseAgentkitClient):
    """AgentKit Tools Management Service"""

    API_ACTIONS: Dict[str, str] = {
        "CreateSession": "CreateSession",
        "CreateTool": "CreateTool",
        "DeleteSession": "DeleteSession",
        "DeleteTool": "DeleteTool",
        "GetSession": "GetSession",
        "GetSessionLogs": "GetSessionLogs",
        "GetTool": "GetTool",
        "ListSessions": "ListSessions",
        "ListTools": "ListTools",
        "SetSessionTtl": "SetSessionTtl",
        "UpdateTool": "UpdateTool",
    }

    def __init__(
        self,
        access_key: str = "",
        secret_key: str = "",
        region: str = "",
        session_token: str = "",
    ) -> None:
        super().__init__(
            access_key=access_key,
            secret_key=secret_key,
            region=region,
            session_token=session_token,
            service_name="tools",
        )

    def create_session(self, request: CreateSessionRequest) -> CreateSessionResponse:
        return self._invoke_api(
            api_action="CreateSession",
            request=request,
            response_type=CreateSessionResponse,
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

    def get_tool(self, request: GetToolRequest) -> GetToolResponse:
        return self._invoke_api(
            api_action="GetTool",
            request=request,
            response_type=GetToolResponse,
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
