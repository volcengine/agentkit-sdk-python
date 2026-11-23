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

"""AgentKit Users (user pool) Management Service client.

Mirrors the AgentKit OpenAPI ``ListUsers``/``GetUser``/``CreateUsers``/
``UpdateUser``/``DeleteUser``/``ImportUsers``/group-membership actions on
the ``agentkit`` signing service. ``ListUsers`` and ``GetUser`` are
declared as HTTP GET in the OpenAPI definition, so their business params
travel in the query string (see ``_invoke_get_api``); every other action
is a JSON-body POST.
"""

from __future__ import annotations

from typing import Dict, Union

from agentkit.client import BaseAgentkitClient
from agentkit.client.base_service_client import ApiConfig

from .types import (
    AddUsersToGroupRequest,
    AddUsersToGroupResponse,
    ChangeUsersGroupRequest,
    ChangeUsersGroupResponse,
    CreateUsersRequest,
    CreateUsersResponse,
    DeleteUserRequest,
    DeleteUserResponse,
    GetUserRequest,
    GetUserResponse,
    ImportUsersRequest,
    ImportUsersResponse,
    ListUsersRequest,
    ListUsersResponse,
    RemoveUsersFromGroupRequest,
    RemoveUsersFromGroupResponse,
    UpdateUserRequest,
    UpdateUserResponse,
)


class AgentkitUsersClient(BaseAgentkitClient):
    """AgentKit Users (user pool) Management Service.

    ``user_pool_id`` is optional on every action: when omitted the server
    falls back to the current account's default user pool.
    """

    API_ACTIONS: Dict[str, Union[str, ApiConfig]] = {
        # GET-declared actions: business params are signed in the query
        # string and no JSON body is sent.
        "ListUsers": ApiConfig(action="ListUsers", method="GET"),
        "GetUser": ApiConfig(action="GetUser", method="GET"),
        # POST-declared actions: business params travel in the JSON body.
        "CreateUsers": "CreateUsers",
        "UpdateUser": "UpdateUser",
        "DeleteUser": "DeleteUser",
        "AddUsersToGroup": "AddUsersToGroup",
        "RemoveUsersFromGroup": "RemoveUsersFromGroup",
        "ChangeUsersGroup": "ChangeUsersGroup",
        "ImportUsers": "ImportUsers",
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
            service_name="users",
        )

    @staticmethod
    def _query_params(request) -> Dict[str, object]:
        """Dump a GET request into query params (PascalCase keys, None
        dropped). Int/bool values are stringified by
        ``Service.prepare_request`` before signing."""
        return request.model_dump(by_alias=True, exclude_none=True)

    def create_users(self, request: CreateUsersRequest) -> CreateUsersResponse:
        """Create 1-1000 users in a user pool. ``results[i]`` keeps request
        order; a present ``error`` marks that user as failed without
        affecting the others."""
        return self._invoke_api(
            api_action="CreateUsers",
            request=request,
            response_type=CreateUsersResponse,
        )

    def update_user(self, request: UpdateUserRequest) -> UpdateUserResponse:
        """Update one user; omitted fields are kept, empty strings clear
        them server-side."""
        return self._invoke_api(
            api_action="UpdateUser",
            request=request,
            response_type=UpdateUserResponse,
        )

    def delete_user(self, request: DeleteUserRequest) -> DeleteUserResponse:
        """Delete one user from a user pool (irreversible)."""
        return self._invoke_api(
            api_action="DeleteUser",
            request=request,
            response_type=DeleteUserResponse,
        )

    def list_users(self, request: ListUsersRequest) -> ListUsersResponse:
        """List users in a user pool. Filters are exact matches;
        ``max_results=0`` means "unspecified" and lets the server default
        (10, max 100). ``next_token`` is None on the last page."""
        return self._invoke_get_api(
            api_action="ListUsers",
            params=self._query_params(request),
            response_type=ListUsersResponse,
        )

    def get_user(self, request: GetUserRequest) -> GetUserResponse:
        """Fetch one user (carries WorkspaceIds, no phone/updatedAt)."""
        return self._invoke_get_api(
            api_action="GetUser",
            params=self._query_params(request),
            response_type=GetUserResponse,
        )

    def add_users_to_group(
        self, request: AddUsersToGroupRequest
    ) -> AddUsersToGroupResponse:
        """Add 1-100 users to a group; results keep request order."""
        return self._invoke_api(
            api_action="AddUsersToGroup",
            request=request,
            response_type=AddUsersToGroupResponse,
        )

    def remove_users_from_group(
        self, request: RemoveUsersFromGroupRequest
    ) -> RemoveUsersFromGroupResponse:
        """Remove 1-100 users from a group; results keep request order."""
        return self._invoke_api(
            api_action="RemoveUsersFromGroup",
            request=request,
            response_type=RemoveUsersFromGroupResponse,
        )

    def change_users_group(
        self, request: ChangeUsersGroupRequest
    ) -> ChangeUsersGroupResponse:
        """Move 1-100 users from one group to another; results keep
        request order."""
        return self._invoke_api(
            api_action="ChangeUsersGroup",
            request=request,
            response_type=ChangeUsersGroupResponse,
        )

    def import_users(self, request: ImportUsersRequest) -> ImportUsersResponse:
        """Bulk-import users from a base64-encoded CSV (header row + one
        user per row; only CSV is supported)."""
        return self._invoke_api(
            api_action="ImportUsers",
            request=request,
            response_type=ImportUsersResponse,
        )
