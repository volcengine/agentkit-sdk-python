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

"""Pydantic models for the AgentKit Organizations OpenAPI (amon
organization service, signing service ``agentkit``).

All actions resolve the organization from the signed account, so request
bodies only carry the business identifiers below. GET-declared actions
(``GetOrganization``, ``ListOrganizationMembers``) carry business params in
the query string with PascalCase keys; POST-style actions carry them in a
JSON body.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# The only organization role the OpenAPI supports today.
ORGANIZATION_ADMIN_ROLE = "organization_admin"

MAX_LIST_ORGANIZATION_MEMBERS_RESULTS = 100


class OrganizationsBaseModel(BaseModel):
    """AgentKit Organizations base model"""

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


# Data Types


class OrganizationEndpointData(OrganizationsBaseModel):
    """An Endpoint bound to an organization (``UpdateOrganization``, read-
    only elsewhere)."""

    id: Optional[str] = Field(default=None, alias="Id")
    base_url: Optional[str] = Field(default=None, alias="BaseUrl")


class OrganizationData(OrganizationsBaseModel):
    """One organization as returned by ``CreateOrganization`` /
    ``GetOrganization``."""

    org_id: Optional[str] = Field(default=None, alias="OrgId")
    name: Optional[str] = Field(default=None, alias="Name")
    status: Optional[str] = Field(default=None, alias="Status")
    user_pool_id: Optional[str] = Field(default=None, alias="UserPoolId")
    workload_pool_id: Optional[str] = Field(default=None, alias="WorkloadPoolId")
    idp_id: Optional[str] = Field(default=None, alias="IdpId")
    default_user_pool_client_id: Optional[str] = Field(
        default=None, alias="DefaultUserPoolClientId"
    )
    default_user_pool_cli_client_id: Optional[str] = Field(
        default=None, alias="DefaultUserPoolCliClientId"
    )
    endpoint: Optional[OrganizationEndpointData] = Field(
        default=None, alias="Endpoint"
    )
    default_workspace_id: Optional[str] = Field(
        default=None, alias="DefaultWorkspaceId"
    )
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    create_time: Optional[str] = Field(default=None, alias="CreateTime")
    update_time: Optional[str] = Field(default=None, alias="UpdateTime")


class OrganizationMemberData(OrganizationsBaseModel):
    """One organization member as returned by the member actions."""

    binding_id: Optional[str] = Field(default=None, alias="BindingId")
    user_id: Optional[str] = Field(default=None, alias="UserId")
    role: Optional[str] = Field(default=None, alias="Role")
    preferred_username: Optional[str] = Field(
        default=None, alias="PreferredUsername"
    )
    name: Optional[str] = Field(default=None, alias="Name")
    email: Optional[str] = Field(default=None, alias="Email")
    phone: Optional[str] = Field(default=None, alias="Phone")
    create_time: Optional[str] = Field(default=None, alias="CreateTime")


class UpdateOrganizationEndpointData(OrganizationsBaseModel):
    """The Endpoint binding accepted by ``UpdateOrganization``; ``Id`` and
    ``BaseUrl`` must be provided together."""

    id: str = Field(..., alias="Id")
    base_url: str = Field(..., alias="BaseUrl")


# CreateOrganization - Request / Response
class CreateOrganizationRequest(OrganizationsBaseModel):
    # Project name for the default workspace (also used as its name).
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    # Skip auto-creating the default user pool and its clients.
    skip_create_user_pool: Optional[bool] = Field(
        default=None, alias="SkipCreateUserPool"
    )

    @field_validator("project_name")
    @classmethod
    def _validate_project_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("project_name must not be empty when provided.")
        return v


class CreateOrganizationResponse(OrganizationsBaseModel):
    """``created=False`` means an active organization already existed and
    was reused (provisioning is idempotent)."""

    organization: Optional[OrganizationData] = Field(
        default=None, alias="Organization"
    )
    created: Optional[bool] = Field(default=None, alias="Created")


# GetOrganization - Request / Response
class GetOrganizationRequest(OrganizationsBaseModel):
    # Optional: when omitted the server looks up the current account's
    # organization.
    org_id: Optional[str] = Field(default=None, alias="OrgId")

    @field_validator("org_id")
    @classmethod
    def _validate_org_id(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError(
                "org_id must not be empty when provided; omit it to probe "
                "the current account."
            )
        return v


class GetOrganizationResponse(OrganizationsBaseModel):
    """An empty result is a legal "account not provisioned yet" answer (no
    error), surfaced as ``organization=None``."""

    organization: Optional[OrganizationData] = Field(
        default=None, alias="Organization"
    )


# UpdateOrganization - Request / Response
class UpdateOrganizationRequest(OrganizationsBaseModel):
    org_id: str = Field(..., alias="OrgId")
    name: Optional[str] = Field(default=None, alias="Name")
    idp_id: Optional[str] = Field(default=None, alias="IdpId")
    user_pool_id: Optional[str] = Field(default=None, alias="UserPoolId")
    user_pool_client_id: Optional[str] = Field(
        default=None, alias="UserPoolClientId"
    )
    user_pool_client_secret: Optional[str] = Field(
        default=None, alias="UserPoolClientSecret"
    )
    user_pool_cli_client_id: Optional[str] = Field(
        default=None, alias="UserPoolCliClientId"
    )
    endpoint: Optional[UpdateOrganizationEndpointData] = Field(
        default=None, alias="Endpoint"
    )

    @field_validator("org_id")
    @classmethod
    def _validate_org_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("org_id is required to update an organization.")
        return v

    @field_validator(
        "name",
        "idp_id",
        "user_pool_id",
        "user_pool_client_id",
        "user_pool_client_secret",
        "user_pool_cli_client_id",
    )
    @classmethod
    def _validate_non_empty(cls, v: Optional[str]) -> Optional[str]:
        # Empty values do not update server-side.
        if v is not None and not v.strip():
            raise ValueError(
                "update fields must not be empty; omit them to keep the "
                "current values."
            )
        return v

    @model_validator(mode="after")
    def _validate_has_change(self) -> "UpdateOrganizationRequest":
        fields = (
            self.name,
            self.idp_id,
            self.user_pool_id,
            self.user_pool_client_id,
            self.user_pool_client_secret,
            self.user_pool_cli_client_id,
        )
        if all(value is None for value in fields) and self.endpoint is None:
            raise ValueError(
                "Nothing to update. Pass at least one of name/idp_id/"
                "user_pool_id/user_pool_client_id/user_pool_client_secret/"
                "user_pool_cli_client_id/endpoint."
            )
        return self


class UpdateOrganizationResponse(OrganizationsBaseModel):
    org_id: Optional[str] = Field(default=None, alias="OrgId")


# DeleteOrganization - Request / Response
class DeleteOrganizationRequest(OrganizationsBaseModel):
    org_id: str = Field(..., alias="OrgId")
    # Also delete the organization's default user pool (default server
    # behavior).
    delete_user_pool: Optional[bool] = Field(
        default=None, alias="DeleteUserPool"
    )

    @field_validator("org_id")
    @classmethod
    def _validate_org_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("org_id is required to delete an organization.")
        return v


class DeleteOrganizationResponse(OrganizationsBaseModel):
    """The deletion is synchronous and cascades to all workspaces and
    member bindings; the response reports the final status (``DELETED``)."""

    status: Optional[str] = Field(default=None, alias="Status")


# AddOrganizationMember - Request / Response
class AddOrganizationMemberRequest(OrganizationsBaseModel):
    # Both resolve the organization from the signed account -- there is no
    # OrgId param.
    user_id: str = Field(..., alias="UserId")
    role: str = Field(..., alias="Role")

    @field_validator("user_id", "role")
    @classmethod
    def _validate_required(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(
                "userId and role are required for organization member "
                "operations."
            )
        return v

    @field_validator("role")
    @classmethod
    def _validate_role(cls, v: str) -> str:
        if v != ORGANIZATION_ADMIN_ROLE:
            raise ValueError(
                f"role {v!r} is invalid; only "
                f"{ORGANIZATION_ADMIN_ROLE!r} is supported."
            )
        return v


class AddOrganizationMemberResponse(OrganizationsBaseModel):
    """Idempotent server-side: re-granting the same UserId+Role
    restores/reuses the existing binding."""

    member: Optional[OrganizationMemberData] = Field(
        default=None, alias="Member"
    )


# RemoveOrganizationMember - Request / Response
class RemoveOrganizationMemberRequest(OrganizationsBaseModel):
    user_id: str = Field(..., alias="UserId")
    role: str = Field(..., alias="Role")

    @field_validator("user_id", "role")
    @classmethod
    def _validate_required(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(
                "userId and role are required for organization member "
                "operations."
            )
        return v

    @field_validator("role")
    @classmethod
    def _validate_role(cls, v: str) -> str:
        if v != ORGANIZATION_ADMIN_ROLE:
            raise ValueError(
                f"role {v!r} is invalid; only "
                f"{ORGANIZATION_ADMIN_ROLE!r} is supported."
            )
        return v


class RemoveOrganizationMemberResponse(OrganizationsBaseModel):
    """Idempotent: revoking a missing binding still succeeds with
    ``revoked=True``."""

    revoked: Optional[bool] = Field(default=None, alias="Revoked")


# ListOrganizationMembers - Request / Response
class ListOrganizationMembersRequest(OrganizationsBaseModel):
    user_id: Optional[str] = Field(default=None, alias="UserId")
    role: Optional[str] = Field(default=None, alias="Role")
    # 0 means "unspecified" and lets the server default (10, max 100).
    max_results: Optional[int] = Field(
        default=None,
        alias="MaxResults",
        ge=0,
        le=MAX_LIST_ORGANIZATION_MEMBERS_RESULTS,
    )
    next_token: Optional[str] = Field(default=None, alias="NextToken")

    @field_validator("user_id")
    @classmethod
    def _validate_user_id(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("user_id must not be empty when provided.")
        return v

    @field_validator("role")
    @classmethod
    def _validate_role(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v.strip():
                raise ValueError("role must not be empty when provided.")
            if v != ORGANIZATION_ADMIN_ROLE:
                raise ValueError(
                    f"role {v!r} is invalid; only "
                    f"{ORGANIZATION_ADMIN_ROLE!r} is supported."
                )
        return v

    @field_validator("next_token")
    @classmethod
    def _validate_next_token(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("next_token must not be empty when provided.")
        return v


class ListOrganizationMembersResponse(OrganizationsBaseModel):
    members: Optional[List[OrganizationMemberData]] = Field(
        default=None, alias="Members"
    )
    next_token: Optional[str] = Field(default=None, alias="NextToken")

    @field_validator("next_token")
    @classmethod
    def _empty_token_is_none(cls, v: Optional[str]) -> Optional[str]:
        return v or None
