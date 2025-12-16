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
    AddMemoryCollectionRequest,
    AddMemoryCollectionResponse,
    CreateMemoryCollectionRequest,
    CreateMemoryCollectionResponse,
    DeleteMemoryCollectionRequest,
    DeleteMemoryCollectionResponse,
    GetMemoryCollectionRequest,
    GetMemoryCollectionResponse,
    GetMemoryConnectionInfoRequest,
    GetMemoryConnectionInfoResponse,
    ListMemoryCollectionsRequest,
    ListMemoryCollectionsResponse,
    UpdateMemoryCollectionRequest,
    UpdateMemoryCollectionResponse,
)


class AgentkitMemoryClient(BaseAgentkitClient):
    """AgentKit Memory Management Service"""

    API_ACTIONS: Dict[str, str] = {
        "AddMemoryCollection": "AddMemoryCollection",
        "CreateMemoryCollection": "CreateMemoryCollection",
        "DeleteMemoryCollection": "DeleteMemoryCollection",
        "GetMemoryCollection": "GetMemoryCollection",
        "GetMemoryConnectionInfo": "GetMemoryConnectionInfo",
        "ListMemoryCollections": "ListMemoryCollections",
        "UpdateMemoryCollection": "UpdateMemoryCollection",
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
            service_name="memory",
        )

    def add_memory_collection(
        self, request: AddMemoryCollectionRequest
    ) -> AddMemoryCollectionResponse:
        return self._invoke_api(
            api_action="AddMemoryCollection",
            request=request,
            response_type=AddMemoryCollectionResponse,
        )

    def create_memory_collection(
        self, request: CreateMemoryCollectionRequest
    ) -> CreateMemoryCollectionResponse:
        return self._invoke_api(
            api_action="CreateMemoryCollection",
            request=request,
            response_type=CreateMemoryCollectionResponse,
        )

    def delete_memory_collection(
        self, request: DeleteMemoryCollectionRequest
    ) -> DeleteMemoryCollectionResponse:
        return self._invoke_api(
            api_action="DeleteMemoryCollection",
            request=request,
            response_type=DeleteMemoryCollectionResponse,
        )

    def get_memory_collection(
        self, request: GetMemoryCollectionRequest
    ) -> GetMemoryCollectionResponse:
        return self._invoke_api(
            api_action="GetMemoryCollection",
            request=request,
            response_type=GetMemoryCollectionResponse,
        )

    def get_memory_connection_info(
        self, request: GetMemoryConnectionInfoRequest
    ) -> GetMemoryConnectionInfoResponse:
        return self._invoke_api(
            api_action="GetMemoryConnectionInfo",
            request=request,
            response_type=GetMemoryConnectionInfoResponse,
        )

    def list_memory_collections(
        self, request: ListMemoryCollectionsRequest
    ) -> ListMemoryCollectionsResponse:
        return self._invoke_api(
            api_action="ListMemoryCollections",
            request=request,
            response_type=ListMemoryCollectionsResponse,
        )

    def update_memory_collection(
        self, request: UpdateMemoryCollectionRequest
    ) -> UpdateMemoryCollectionResponse:
        return self._invoke_api(
            api_action="UpdateMemoryCollection",
            request=request,
            response_type=UpdateMemoryCollectionResponse,
        )
