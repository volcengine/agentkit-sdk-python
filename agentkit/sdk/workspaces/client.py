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

"""AgentKit Workspaces Management Service client.

Mirrors the AgentKit OpenAPI workspace-lifecycle and workspace-member
actions on the ``agentkit`` signing service (amon workspace service).
GET-declared actions (``ListWorkspaces``, ``GetWorkspace``,
``ListWorkspaceMembers``, ``GetWorkspaceMember``) carry business params in
the query string; every other action is a JSON-body POST. Every request is
scoped to the signed account and validated workspace -> org -> account
server-side.
"""

from __future__ import annotations

from typing import Dict, Union

from agentkit.client import BaseAgentkitClient
from agentkit.client.base_service_client import ApiConfig

from .types import (
    AddWorkspaceMemberRequest,
    AddWorkspaceMemberResponse,
    BatchUpdateWorkspaceMembersRequest,
    BatchUpdateWorkspaceMembersResponse,
    CreateWorkspaceRequest,
    CreateWorkspaceResponse,
    DeleteWorkspaceRequest,
    DeleteWorkspaceResponse,
    GetWorkspaceMemberRequest,
    GetWorkspaceMemberResponse,
    GetWorkspaceRequest,
    GetWorkspaceResponse,
    GrantSystemAdminRequest,
    GrantSystemAdminResponse,
    ListWorkspaceMembersRequest,
    ListWorkspaceMembersResponse,
    ListWorkspacesRequest,
    ListWorkspacesResponse,
    RemoveWorkspaceMemberRequest,
    RemoveWorkspaceMemberResponse,
    UpdateWorkspaceMemberRoleRequest,
    UpdateWorkspaceMemberRoleResponse,
    UpdateWorkspaceRequest,
    UpdateWorkspaceResponse,
)

# The server reads the workspace region from this (unsigned by the TS CLI)
# header on CreateWorkspace; a body Region field is ignored.
_TOP_REGION_HEADER = "X-Top-Region"


class AgentkitWorkspaceClient(BaseAgentkitClient):
    """AgentKit Workspaces (workspace lifecycle + members) Management
    Service."""

    API_ACTIONS: Dict[str, Union[str, ApiConfig]] = {
        # GET-declared actions: business params are signed in the query
        # string and no JSON body is sent.
        "ListWorkspaces": ApiConfig(action="ListWorkspaces", method="GET"),
        "GetWorkspace": ApiConfig(action="GetWorkspace", method="GET"),
        "ListWorkspaceMembers": ApiConfig(
            action="ListWorkspaceMembers", method="GET"
        ),
        "GetWorkspaceMember": ApiConfig(
            action="GetWorkspaceMember", method="GET"
        ),
        # POST-declared actions: business params travel in the JSON body.
        "CreateWorkspace": "CreateWorkspace",
        "UpdateWorkspace": "UpdateWorkspace",
        "DeleteWorkspace": "DeleteWorkspace",
        "GrantSystemAdmin": "GrantSystemAdmin",
        "AddWorkspaceMember": "AddWorkspaceMember",
        "UpdateWorkspaceMemberRole": "UpdateWorkspaceMemberRole",
        "RemoveWorkspaceMember": "RemoveWorkspaceMember",
        "BatchUpdateWorkspaceMembers": "BatchUpdateWorkspaceMembers",
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
            service_name="workspaces",
        )

    @staticmethod
    def _query_params(request) -> Dict[str, object]:
        """Dump a GET request into query params (PascalCase keys, None
        dropped). Booleans become lowercase ``"true"``; ``False`` flags are
        omitted (matching the CLI's compact semantics)."""
        params = request.model_dump(by_alias=True, exclude_none=True)
        return {
            key: ("true" if value else value) if isinstance(value, bool) else value
            for key, value in params.items()
            if not (isinstance(value, bool) and not value)
        }

    def _invoke_with_region_header(self, request, response_type):
        """POST ``request`` with the ``X-Top-Region`` header set to this
        client's signing region (required by CreateWorkspace). The header
        is installed on the shared ServiceInfo for the duration of the call
        and restored afterwards."""
        region = (self.region or "").strip()
        if not region:
            raise ValueError(
                "region is required to create a workspace (sent as the "
                "X-Top-Region header)."
            )
        header = self.service_info.header
        previous = header.get(_TOP_REGION_HEADER)
        header[_TOP_REGION_HEADER] = region
        try:
            return self._invoke_api(
                api_action="CreateWorkspace",
                request=request,
                response_type=response_type,
            )
        finally:
            if previous is None:
                header.pop(_TOP_REGION_HEADER, None)
            else:
                header[_TOP_REGION_HEADER] = previous

    def create_workspace(self, request: CreateWorkspaceRequest) -> CreateWorkspaceResponse:
        """Create a workspace. The server reads the workspace region from
        the ``X-Top-Region`` header, which this method fills with the
        client's signing region."""
        return self._invoke_with_region_header(
            request, CreateWorkspaceResponse
        )

    def list_workspaces(self, request: ListWorkspacesRequest) -> ListWorkspacesResponse:
        """List workspaces of one organization (``org_id`` mandatory).
        Filters are exact matches; ``max_results=0`` lets the server default
        (10, max 100). ``next_token`` is None on the last page."""
        return self._invoke_get_api(
            api_action="ListWorkspaces",
            params=self._query_params(request),
            response_type=ListWorkspacesResponse,
        )

    def get_workspace(self, request: GetWorkspaceRequest) -> GetWorkspaceResponse:
        """Fetch one workspace. ``workspace_id`` takes precedence over
        ``project_name`` (only the latter is sent when no workspace id is
        given). Member counts are only filled server-side when
        ``count_member`` is set."""
        params = self._query_params(request)
        if "WorkspaceId" in params:
            params.pop("ProjectName", None)
        return self._invoke_get_api(
            api_action="GetWorkspace",
            params=params,
            response_type=GetWorkspaceResponse,
        )

    def update_workspace(self, request: UpdateWorkspaceRequest) -> UpdateWorkspaceResponse:
        """Update one workspace's name/description; the response is the
        updated workspace."""
        return self._invoke_api(
            api_action="UpdateWorkspace",
            request=request,
            response_type=UpdateWorkspaceResponse,
        )

    def delete_workspace(self, request: DeleteWorkspaceRequest) -> DeleteWorkspaceResponse:
        """Delete one workspace; the response reports whether the binding
        was deleted."""
        return self._invoke_api(
            api_action="DeleteWorkspace",
            request=request,
            response_type=DeleteWorkspaceResponse,
        )

    def grant_system_admin(
        self, request: GrantSystemAdminRequest
    ) -> GrantSystemAdminResponse:
        """Grant ``system_admin`` on a workspace to IAM users (not local
        users-mirror users). Re-granting an existing binding is idempotent;
        the response lists the resulting bindings."""
        return self._invoke_api(
            api_action="GrantSystemAdmin",
            request=request,
            response_type=GrantSystemAdminResponse,
        )

    def add_workspace_member(
        self, request: AddWorkspaceMemberRequest
    ) -> AddWorkspaceMemberResponse:
        """Add one member with a role to a workspace; the response is the
        created binding."""
        return self._invoke_api(
            api_action="AddWorkspaceMember",
            request=request,
            response_type=AddWorkspaceMemberResponse,
        )

    def list_workspace_members(
        self, request: ListWorkspaceMembersRequest
    ) -> ListWorkspaceMembersResponse:
        """List members of one workspace. Filters are exact matches;
        ``max_results=0`` lets the server default (10, max 100)."""
        return self._invoke_get_api(
            api_action="ListWorkspaceMembers",
            params=self._query_params(request),
            response_type=ListWorkspaceMembersResponse,
        )

    def get_workspace_member(
        self, request: GetWorkspaceMemberRequest
    ) -> GetWorkspaceMemberResponse:
        """Fetch one workspace member. A missing ``binding`` in the
        response is a legal "not a member" answer (no error)."""
        return self._invoke_get_api(
            api_action="GetWorkspaceMember",
            params=self._query_params(request),
            response_type=GetWorkspaceMemberResponse,
        )

    def update_workspace_member_role(
        self, request: UpdateWorkspaceMemberRoleRequest
    ) -> UpdateWorkspaceMemberRoleResponse:
        """Change one member's role; the response carries the updated
        binding and the member's effective roles."""
        return self._invoke_api(
            api_action="UpdateWorkspaceMemberRole",
            request=request,
            response_type=UpdateWorkspaceMemberRoleResponse,
        )

    def remove_workspace_member(
        self, request: RemoveWorkspaceMemberRequest
    ) -> RemoveWorkspaceMemberResponse:
        """Remove one member from a workspace; the response reports the
        deleted binding's id."""
        return self._invoke_api(
            api_action="RemoveWorkspaceMember",
            request=request,
            response_type=RemoveWorkspaceMemberResponse,
        )

    def batch_update_workspace_members(
        self, request: BatchUpdateWorkspaceMembersRequest
    ) -> BatchUpdateWorkspaceMembersResponse:
        """Batch create/update/delete workspace members (1-100 operations).
        The server is all-or-nothing: any failed pre-check rejects the whole
        batch. The response reports success/failure counts and per-item
        outcomes aligned with the request's operation order."""
        return self._invoke_api(
            api_action="BatchUpdateWorkspaceMembers",
            request=request,
            response_type=BatchUpdateWorkspaceMembersResponse,
        )
