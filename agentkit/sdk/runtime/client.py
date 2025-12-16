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
    CreateRuntimeRequest,
    CreateRuntimeResponse,
    DeleteRuntimeRequest,
    DeleteRuntimeResponse,
    GetRuntimeCozeTokenRequest,
    GetRuntimeCozeTokenResponse,
    GetRuntimeInstanceLogsRequest,
    GetRuntimeInstanceLogsResponse,
    GetRuntimeRequest,
    GetRuntimeResponse,
    GetRuntimeVersionRequest,
    GetRuntimeVersionResponse,
    ListRuntimeCrRegistriesRequest,
    ListRuntimeCrRegistriesResponse,
    ListRuntimeInstancesRequest,
    ListRuntimeInstancesResponse,
    ListRuntimeVersionsRequest,
    ListRuntimeVersionsResponse,
    ListRuntimesRequest,
    ListRuntimesResponse,
    ReleaseRuntimeRequest,
    ReleaseRuntimeResponse,
    UpdateRuntimeRequest,
    UpdateRuntimeResponse,
)


class AgentkitRuntimeClient(BaseAgentkitClient):
    """AgentKit Runtime Management Service"""

    API_ACTIONS: Dict[str, str] = {
        "CreateRuntime": "CreateRuntime",
        "DeleteRuntime": "DeleteRuntime",
        "GetRuntime": "GetRuntime",
        "GetRuntimeCozeToken": "GetRuntimeCozeToken",
        "GetRuntimeInstanceLogs": "GetRuntimeInstanceLogs",
        "GetRuntimeVersion": "GetRuntimeVersion",
        "ListRuntimeCrRegistries": "ListRuntimeCrRegistries",
        "ListRuntimeInstances": "ListRuntimeInstances",
        "ListRuntimeVersions": "ListRuntimeVersions",
        "ListRuntimes": "ListRuntimes",
        "ReleaseRuntime": "ReleaseRuntime",
        "UpdateRuntime": "UpdateRuntime",
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
            service_name="runtime",
        )

    def create_runtime(self, request: CreateRuntimeRequest) -> CreateRuntimeResponse:
        return self._invoke_api(
            api_action="CreateRuntime",
            request=request,
            response_type=CreateRuntimeResponse,
        )

    def delete_runtime(self, request: DeleteRuntimeRequest) -> DeleteRuntimeResponse:
        return self._invoke_api(
            api_action="DeleteRuntime",
            request=request,
            response_type=DeleteRuntimeResponse,
        )

    def get_runtime(self, request: GetRuntimeRequest) -> GetRuntimeResponse:
        return self._invoke_api(
            api_action="GetRuntime",
            request=request,
            response_type=GetRuntimeResponse,
        )

    def get_runtime_coze_token(
        self, request: GetRuntimeCozeTokenRequest
    ) -> GetRuntimeCozeTokenResponse:
        return self._invoke_api(
            api_action="GetRuntimeCozeToken",
            request=request,
            response_type=GetRuntimeCozeTokenResponse,
        )

    def get_runtime_instance_logs(
        self, request: GetRuntimeInstanceLogsRequest
    ) -> GetRuntimeInstanceLogsResponse:
        return self._invoke_api(
            api_action="GetRuntimeInstanceLogs",
            request=request,
            response_type=GetRuntimeInstanceLogsResponse,
        )

    def get_runtime_version(
        self, request: GetRuntimeVersionRequest
    ) -> GetRuntimeVersionResponse:
        return self._invoke_api(
            api_action="GetRuntimeVersion",
            request=request,
            response_type=GetRuntimeVersionResponse,
        )

    def list_runtime_cr_registries(
        self, request: ListRuntimeCrRegistriesRequest
    ) -> ListRuntimeCrRegistriesResponse:
        return self._invoke_api(
            api_action="ListRuntimeCrRegistries",
            request=request,
            response_type=ListRuntimeCrRegistriesResponse,
        )

    def list_runtime_instances(
        self, request: ListRuntimeInstancesRequest
    ) -> ListRuntimeInstancesResponse:
        return self._invoke_api(
            api_action="ListRuntimeInstances",
            request=request,
            response_type=ListRuntimeInstancesResponse,
        )

    def list_runtime_versions(
        self, request: ListRuntimeVersionsRequest
    ) -> ListRuntimeVersionsResponse:
        return self._invoke_api(
            api_action="ListRuntimeVersions",
            request=request,
            response_type=ListRuntimeVersionsResponse,
        )

    def list_runtimes(self, request: ListRuntimesRequest) -> ListRuntimesResponse:
        return self._invoke_api(
            api_action="ListRuntimes",
            request=request,
            response_type=ListRuntimesResponse,
        )

    def release_runtime(self, request: ReleaseRuntimeRequest) -> ReleaseRuntimeResponse:
        return self._invoke_api(
            api_action="ReleaseRuntime",
            request=request,
            response_type=ReleaseRuntimeResponse,
        )

    def update_runtime(self, request: UpdateRuntimeRequest) -> UpdateRuntimeResponse:
        return self._invoke_api(
            api_action="UpdateRuntime",
            request=request,
            response_type=UpdateRuntimeResponse,
        )
