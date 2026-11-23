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

"""AgentKit Organizations Management Service client.

Mirrors the AgentKit OpenAPI organization-lifecycle and organization-member
actions on the ``agentkit`` signing service (amon organization service).
All actions resolve the organization from the signed account.
GET-declared actions (``GetOrganization``, ``ListOrganizationMembers``)
carry business params in the query string; every other action is a
JSON-body POST.
"""

from __future__ import annotations

from typing import Dict, Union

from agentkit.client import BaseAgentkitClient
from agentkit.client.base_service_client import ApiConfig

from .types import (
    AddOrganizationMemberRequest,
    AddOrganizationMemberResponse,
    CreateOrganizationRequest,
    CreateOrganizationResponse,
    DeleteOrganizationRequest,
    DeleteOrganizationResponse,
    GetOrganizationRequest,
    GetOrganizationResponse,
    ListOrganizationMembersRequest,
    ListOrganizationMembersResponse,
    RemoveOrganizationMemberRequest,
    RemoveOrganizationMemberResponse,
    UpdateOrganizationRequest,
    UpdateOrganizationResponse,
)


class AgentkitOrganizationClient(BaseAgentkitClient):
    """AgentKit Organizations Management Service."""

    API_ACTIONS: Dict[str, Union[str, ApiConfig]] = {
        # GET-declared actions: business params are signed in the query
        # string and no JSON body is sent.
        "GetOrganization": ApiConfig(action="GetOrganization", method="GET"),
        "ListOrganizationMembers": ApiConfig(
            action="ListOrganizationMembers", method="GET"
        ),
        # POST-declared actions: business params travel in the JSON body.
        "CreateOrganization": "CreateOrganization",
        "UpdateOrganization": "UpdateOrganization",
        "DeleteOrganization": "DeleteOrganization",
        "AddOrganizationMember": "AddOrganizationMember",
        "RemoveOrganizationMember": "RemoveOrganizationMember",
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
            service_name="organizations",
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

    def create_organization(
        self, request: CreateOrganizationRequest
    ) -> CreateOrganizationResponse:
        """Provision (or idempotently reuse) the account's organization.
        ``created=False`` means an active organization already existed and
        was reused."""
        return self._invoke_api(
            api_action="CreateOrganization",
            request=request,
            response_type=CreateOrganizationResponse,
        )

    def get_organization(
        self, request: GetOrganizationRequest
    ) -> GetOrganizationResponse:
        """Fetch one organization. Without ``org_id`` the server resolves
        the current account's organization; an empty result is a legal
        "account not provisioned yet" answer surfaced as
        ``organization=None``."""
        return self._invoke_get_api(
            api_action="GetOrganization",
            params=self._query_params(request),
            response_type=GetOrganizationResponse,
        )

    def update_organization(
        self, request: UpdateOrganizationRequest
    ) -> UpdateOrganizationResponse:
        """Update one organization. The Endpoint binding is only sent when
        both id and base_url are present (enforced by the request model);
        the server rejects overwriting an existing binding."""
        return self._invoke_api(
            api_action="UpdateOrganization",
            request=request,
            response_type=UpdateOrganizationResponse,
        )

    def delete_organization(
        self, request: DeleteOrganizationRequest
    ) -> DeleteOrganizationResponse:
        """Delete one organization. The deletion is synchronous and
        cascades to all workspaces and member bindings; the response
        reports the final status."""
        return self._invoke_api(
            api_action="DeleteOrganization",
            request=request,
            response_type=DeleteOrganizationResponse,
        )

    def add_organization_member(
        self, request: AddOrganizationMemberRequest
    ) -> AddOrganizationMemberResponse:
        """Grant a role on the account's organization (only
        ``organization_admin`` is supported today). Idempotent."""
        return self._invoke_api(
            api_action="AddOrganizationMember",
            request=request,
            response_type=AddOrganizationMemberResponse,
        )

    def remove_organization_member(
        self, request: RemoveOrganizationMemberRequest
    ) -> RemoveOrganizationMemberResponse:
        """Revoke a role on the account's organization. Idempotent:
        revoking a missing binding still succeeds with ``revoked=True``."""
        return self._invoke_api(
            api_action="RemoveOrganizationMember",
            request=request,
            response_type=RemoveOrganizationMemberResponse,
        )

    def list_organization_members(
        self, request: ListOrganizationMembersRequest
    ) -> ListOrganizationMembersResponse:
        """List members of the account's organization. Filters are exact
        matches; ``max_results=0`` lets the server default (10, max 100)."""
        return self._invoke_get_api(
            api_action="ListOrganizationMembers",
            params=self._query_params(request),
            response_type=ListOrganizationMembersResponse,
        )
