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
    CreateSkillRequest,
    CreateSkillResponse,
    CreateSkillSpaceRequest,
    CreateSkillSpaceResponse,
    DeleteSkillRequest,
    DeleteSkillResponse,
    DeleteSkillSpaceRequest,
    DeleteSkillSpaceResponse,
    GetSkillInfoRequest,
    GetSkillInfoResponse,
    GetSkillRequest,
    GetSkillResponse,
    GetSkillSpaceRequest,
    GetSkillSpaceResponse,
    GetSkillVersionRequest,
    GetSkillVersionResponse,
    ListSkillSpacesBySkillRequest,
    ListSkillSpacesBySkillResponse,
    ListSkillSpacesRequest,
    ListSkillSpacesResponse,
    ListSkillVersionsRequest,
    ListSkillVersionsResponse,
    ListSkillsBySkillSpaceRequest,
    ListSkillsBySkillSpaceResponse,
    ListSkillsBySpaceIdRequest,
    ListSkillsBySpaceIdResponse,
    ListSkillsBySpaceNameRequest,
    ListSkillsBySpaceNameResponse,
    ListSkillsRequest,
    ListSkillsResponse,
    PublishSkillToSkillSpaceRequest,
    PublishSkillToSkillSpaceResponse,
    RemoveSkillFromSkillSpaceRequest,
    RemoveSkillFromSkillSpaceResponse,
    UpdateSkillRequest,
    UpdateSkillResponse,
    UpdateSkillSpaceRequest,
    UpdateSkillSpaceResponse,
)


class AgentkitSkillsClient(BaseAgentkitClient):
    """AgentKit Skills Management Service"""

    API_ACTIONS: Dict[str, str] = {
        "CreateSkill": "CreateSkill",
        "CreateSkillSpace": "CreateSkillSpace",
        "DeleteSkill": "DeleteSkill",
        "DeleteSkillSpace": "DeleteSkillSpace",
        "GetSkill": "GetSkill",
        "GetSkillInfo": "GetSkillInfo",
        "GetSkillSpace": "GetSkillSpace",
        "GetSkillVersion": "GetSkillVersion",
        "ListSkillSpaces": "ListSkillSpaces",
        "ListSkillSpacesBySkill": "ListSkillSpacesBySkill",
        "ListSkillVersions": "ListSkillVersions",
        "ListSkills": "ListSkills",
        "ListSkillsBySkillSpace": "ListSkillsBySkillSpace",
        "ListSkillsBySpaceId": "ListSkillsBySpaceId",
        "ListSkillsBySpaceName": "ListSkillsBySpaceName",
        "PublishSkillToSkillSpace": "PublishSkillToSkillSpace",
        "RemoveSkillFromSkillSpace": "RemoveSkillFromSkillSpace",
        "UpdateSkill": "UpdateSkill",
        "UpdateSkillSpace": "UpdateSkillSpace",
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
            service_name="skills",
        )

    def create_skill(self, request: CreateSkillRequest) -> CreateSkillResponse:
        return self._invoke_api(
            api_action="CreateSkill",
            request=request,
            response_type=CreateSkillResponse,
        )

    def create_skill_space(
        self, request: CreateSkillSpaceRequest
    ) -> CreateSkillSpaceResponse:
        return self._invoke_api(
            api_action="CreateSkillSpace",
            request=request,
            response_type=CreateSkillSpaceResponse,
        )

    def delete_skill(self, request: DeleteSkillRequest) -> DeleteSkillResponse:
        return self._invoke_api(
            api_action="DeleteSkill",
            request=request,
            response_type=DeleteSkillResponse,
        )

    def delete_skill_space(
        self, request: DeleteSkillSpaceRequest
    ) -> DeleteSkillSpaceResponse:
        return self._invoke_api(
            api_action="DeleteSkillSpace",
            request=request,
            response_type=DeleteSkillSpaceResponse,
        )

    def get_skill(self, request: GetSkillRequest) -> GetSkillResponse:
        return self._invoke_api(
            api_action="GetSkill",
            request=request,
            response_type=GetSkillResponse,
        )

    def get_skill_info(self, request: GetSkillInfoRequest) -> GetSkillInfoResponse:
        return self._invoke_api(
            api_action="GetSkillInfo",
            request=request,
            response_type=GetSkillInfoResponse,
        )

    def get_skill_space(self, request: GetSkillSpaceRequest) -> GetSkillSpaceResponse:
        return self._invoke_api(
            api_action="GetSkillSpace",
            request=request,
            response_type=GetSkillSpaceResponse,
        )

    def get_skill_version(
        self, request: GetSkillVersionRequest
    ) -> GetSkillVersionResponse:
        return self._invoke_api(
            api_action="GetSkillVersion",
            request=request,
            response_type=GetSkillVersionResponse,
        )

    def list_skill_spaces(
        self, request: ListSkillSpacesRequest
    ) -> ListSkillSpacesResponse:
        return self._invoke_api(
            api_action="ListSkillSpaces",
            request=request,
            response_type=ListSkillSpacesResponse,
        )

    def list_skill_spaces_by_skill(
        self, request: ListSkillSpacesBySkillRequest
    ) -> ListSkillSpacesBySkillResponse:
        return self._invoke_api(
            api_action="ListSkillSpacesBySkill",
            request=request,
            response_type=ListSkillSpacesBySkillResponse,
        )

    def list_skill_versions(
        self, request: ListSkillVersionsRequest
    ) -> ListSkillVersionsResponse:
        return self._invoke_api(
            api_action="ListSkillVersions",
            request=request,
            response_type=ListSkillVersionsResponse,
        )

    def list_skills(self, request: ListSkillsRequest) -> ListSkillsResponse:
        return self._invoke_api(
            api_action="ListSkills",
            request=request,
            response_type=ListSkillsResponse,
        )

    def list_skills_by_skill_space(
        self, request: ListSkillsBySkillSpaceRequest
    ) -> ListSkillsBySkillSpaceResponse:
        return self._invoke_api(
            api_action="ListSkillsBySkillSpace",
            request=request,
            response_type=ListSkillsBySkillSpaceResponse,
        )

    def list_skills_by_space_id(
        self, request: ListSkillsBySpaceIdRequest
    ) -> ListSkillsBySpaceIdResponse:
        return self._invoke_api(
            api_action="ListSkillsBySpaceId",
            request=request,
            response_type=ListSkillsBySpaceIdResponse,
        )

    def list_skills_by_space_name(
        self, request: ListSkillsBySpaceNameRequest
    ) -> ListSkillsBySpaceNameResponse:
        return self._invoke_api(
            api_action="ListSkillsBySpaceName",
            request=request,
            response_type=ListSkillsBySpaceNameResponse,
        )

    def publish_skill_to_skill_space(
        self, request: PublishSkillToSkillSpaceRequest
    ) -> PublishSkillToSkillSpaceResponse:
        return self._invoke_api(
            api_action="PublishSkillToSkillSpace",
            request=request,
            response_type=PublishSkillToSkillSpaceResponse,
        )

    def remove_skill_from_skill_space(
        self, request: RemoveSkillFromSkillSpaceRequest
    ) -> RemoveSkillFromSkillSpaceResponse:
        return self._invoke_api(
            api_action="RemoveSkillFromSkillSpace",
            request=request,
            response_type=RemoveSkillFromSkillSpaceResponse,
        )

    def update_skill(self, request: UpdateSkillRequest) -> UpdateSkillResponse:
        return self._invoke_api(
            api_action="UpdateSkill",
            request=request,
            response_type=UpdateSkillResponse,
        )

    def update_skill_space(
        self, request: UpdateSkillSpaceRequest
    ) -> UpdateSkillSpaceResponse:
        return self._invoke_api(
            api_action="UpdateSkillSpace",
            request=request,
            response_type=UpdateSkillSpaceResponse,
        )
