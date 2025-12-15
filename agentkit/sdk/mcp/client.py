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
    CreateMCPServiceRequest,
    CreateMCPServiceResponse,
    CreateMCPToolsetRequest,
    CreateMCPToolsetResponse,
    DeleteMCPServiceRequest,
    DeleteMCPServiceResponse,
    DeleteMCPToolsetRequest,
    DeleteMCPToolsetResponse,
    GetMCPServiceRequest,
    GetMCPServiceResponse,
    GetMCPToolsRequest,
    GetMCPToolsResponse,
    GetMCPToolsetRequest,
    GetMCPToolsetResponse,
    ListMCPServicesRequest,
    ListMCPServicesResponse,
    ListMCPToolsRequest,
    ListMCPToolsResponse,
    ListMCPToolsetsRequest,
    ListMCPToolsetsResponse,
    UpdateMCPServiceRequest,
    UpdateMCPServiceResponse,
    UpdateMCPToolsRequest,
    UpdateMCPToolsResponse,
    UpdateMCPToolsetRequest,
    UpdateMCPToolsetResponse,
)


class AgentkitMCPClient(BaseAgentkitClient):
    """AgentKit MCP (Model Context Protocol) Management Service"""

    API_ACTIONS: Dict[str, str] = {
        "CreateMCPService": "CreateMCPService",
        "CreateMCPToolset": "CreateMCPToolset",
        "DeleteMCPService": "DeleteMCPService",
        "DeleteMCPToolset": "DeleteMCPToolset",
        "GetMCPService": "GetMCPService",
        "GetMCPTools": "GetMCPTools",
        "GetMCPToolset": "GetMCPToolset",
        "ListMCPServices": "ListMCPServices",
        "ListMCPTools": "ListMCPTools",
        "ListMCPToolsets": "ListMCPToolsets",
        "UpdateMCPService": "UpdateMCPService",
        "UpdateMCPTools": "UpdateMCPTools",
        "UpdateMCPToolset": "UpdateMCPToolset",
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
            service_name="mcp",
        )

    def create_mcp_service(
        self, request: CreateMCPServiceRequest
    ) -> CreateMCPServiceResponse:
        return self._invoke_api(
            api_action="CreateMCPService",
            request=request,
            response_type=CreateMCPServiceResponse,
        )

    def create_mcp_toolset(
        self, request: CreateMCPToolsetRequest
    ) -> CreateMCPToolsetResponse:
        return self._invoke_api(
            api_action="CreateMCPToolset",
            request=request,
            response_type=CreateMCPToolsetResponse,
        )

    def delete_mcp_service(
        self, request: DeleteMCPServiceRequest
    ) -> DeleteMCPServiceResponse:
        return self._invoke_api(
            api_action="DeleteMCPService",
            request=request,
            response_type=DeleteMCPServiceResponse,
        )

    def delete_mcp_toolset(
        self, request: DeleteMCPToolsetRequest
    ) -> DeleteMCPToolsetResponse:
        return self._invoke_api(
            api_action="DeleteMCPToolset",
            request=request,
            response_type=DeleteMCPToolsetResponse,
        )

    def get_mcp_service(self, request: GetMCPServiceRequest) -> GetMCPServiceResponse:
        return self._invoke_api(
            api_action="GetMCPService",
            request=request,
            response_type=GetMCPServiceResponse,
        )

    def get_mcp_tools(self, request: GetMCPToolsRequest) -> GetMCPToolsResponse:
        return self._invoke_api(
            api_action="GetMCPTools",
            request=request,
            response_type=GetMCPToolsResponse,
        )

    def get_mcp_toolset(self, request: GetMCPToolsetRequest) -> GetMCPToolsetResponse:
        return self._invoke_api(
            api_action="GetMCPToolset",
            request=request,
            response_type=GetMCPToolsetResponse,
        )

    def list_mcp_services(
        self, request: ListMCPServicesRequest
    ) -> ListMCPServicesResponse:
        return self._invoke_api(
            api_action="ListMCPServices",
            request=request,
            response_type=ListMCPServicesResponse,
        )

    def list_mcp_tools(self, request: ListMCPToolsRequest) -> ListMCPToolsResponse:
        return self._invoke_api(
            api_action="ListMCPTools",
            request=request,
            response_type=ListMCPToolsResponse,
        )

    def list_mcp_toolsets(
        self, request: ListMCPToolsetsRequest
    ) -> ListMCPToolsetsResponse:
        return self._invoke_api(
            api_action="ListMCPToolsets",
            request=request,
            response_type=ListMCPToolsetsResponse,
        )

    def update_mcp_service(
        self, request: UpdateMCPServiceRequest
    ) -> UpdateMCPServiceResponse:
        return self._invoke_api(
            api_action="UpdateMCPService",
            request=request,
            response_type=UpdateMCPServiceResponse,
        )

    def update_mcp_tools(
        self, request: UpdateMCPToolsRequest
    ) -> UpdateMCPToolsResponse:
        return self._invoke_api(
            api_action="UpdateMCPTools",
            request=request,
            response_type=UpdateMCPToolsResponse,
        )

    def update_mcp_toolset(
        self, request: UpdateMCPToolsetRequest
    ) -> UpdateMCPToolsetResponse:
        return self._invoke_api(
            api_action="UpdateMCPToolset",
            request=request,
            response_type=UpdateMCPToolsetResponse,
        )
