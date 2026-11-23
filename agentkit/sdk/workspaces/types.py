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

"""Pydantic models for the AgentKit Workspaces OpenAPI (amon workspace
service, signing service ``agentkit``).

Wire-format notes (mirroring the published OpenAPI definition):
- GET-declared actions (``ListWorkspaces``, ``GetWorkspace``,
  ``ListWorkspaceMembers``, ``GetWorkspaceMember``) carry business params
  in the query string with PascalCase keys.
- ``CreateWorkspace`` additionally requires the unsigned ``X-Top-Region``
  request header (the server reads the workspace region from it); handled
  by the client, not the models.
- Single-object responses nest under a ``Workspace``/``Binding`` key.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# Workspace member roles the OpenAPI supports.
WORKSPACE_ROLES = (
    "global_admin",
    "system_admin",
    "workspace_admin",
    "workspace_developer",
    "workspace_user",
)

# Operations accepted by BatchUpdateWorkspaceMembers.
BATCH_MEMBER_OPERATIONS = ("create", "update", "delete")

MAX_LIST_WORKSPACES_RESULTS = 100
MAX_LIST_WORKSPACE_MEMBERS_RESULTS = 100
MAX_BATCH_MEMBER_OPERATIONS = 100


class WorkspacesBaseModel(BaseModel):
    """AgentKit Workspaces base model"""

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


def _normalize_optional(v: Optional[str]) -> Optional[str]:
    """Trim an optional string; blank means "not provided"."""
    if v is None:
        return None
    v = v.strip()
    return v or None


def _validate_workspace_role(role: str) -> str:
    if role not in WORKSPACE_ROLES:
        raise ValueError(
            f"role {role!r} is invalid; supported roles: "
            f"{', '.join(WORKSPACE_ROLES)}."
        )
    return role


# Data Types


class WorkspaceData(WorkspacesBaseModel):
    """One workspace as returned by the workspace lifecycle actions."""

    workspace_id: Optional[str] = Field(default=None, alias="WorkspaceId")
    org_id: Optional[str] = Field(default=None, alias="OrgId")
    name: Optional[str] = Field(default=None, alias="Name")
    description: Optional[str] = Field(default=None, alias="Description")
    workspace_type: Optional[str] = Field(default=None, alias="WorkspaceType")
    status: Optional[str] = Field(default=None, alias="Status")
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    region: Optional[str] = Field(default=None, alias="Region")
    create_time: Optional[str] = Field(default=None, alias="CreateTime")
    update_time: Optional[str] = Field(default=None, alias="UpdateTime")


class WorkspaceMemberBindingData(WorkspacesBaseModel):
    """One workspace member binding as returned by the member actions."""

    binding_id: Optional[str] = Field(default=None, alias="BindingId")
    workspace_id: Optional[str] = Field(default=None, alias="WorkspaceId")
    user_id: Optional[str] = Field(default=None, alias="UserId")
    org_id: Optional[str] = Field(default=None, alias="OrgId")
    account_id: Optional[str] = Field(default=None, alias="AccountId")
    role: Optional[str] = Field(default=None, alias="Role")
    username: Optional[str] = Field(default=None, alias="Username")
    email: Optional[str] = Field(default=None, alias="Email")
    create_time: Optional[str] = Field(default=None, alias="CreateTime")


class GrantSystemAdminBindingData(WorkspacesBaseModel):
    """One binding created by ``GrantSystemAdmin`` (IAM users, no profile
    fields)."""

    binding_id: Optional[str] = Field(default=None, alias="BindingId")
    workspace_id: Optional[str] = Field(default=None, alias="WorkspaceId")
    user_id: Optional[str] = Field(default=None, alias="UserId")
    org_id: Optional[str] = Field(default=None, alias="OrgId")
    account_id: Optional[str] = Field(default=None, alias="AccountId")


class WorkspaceMemberOperationItem(WorkspacesBaseModel):
    """One batched member change. ``role`` is required for create/update
    and must not be set for delete."""

    operation: str = Field(..., alias="Operation")
    user_id: str = Field(..., alias="UserId")
    role: Optional[str] = Field(default=None, alias="Role")

    @field_validator("user_id")
    @classmethod
    def _validate_user_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("userId must not be empty.")
        return v

    @model_validator(mode="after")
    def _validate_role_rules(self) -> "WorkspaceMemberOperationItem":
        if self.operation not in BATCH_MEMBER_OPERATIONS:
            raise ValueError(
                f"operation {self.operation!r} is invalid; supported "
                f"operations: {', '.join(BATCH_MEMBER_OPERATIONS)}."
            )
        if self.operation in ("create", "update"):
            if self.role is None or not self.role.strip():
                raise ValueError(
                    f"role is required for {self.operation} operations."
                )
            _validate_workspace_role(self.role)
        elif self.role is not None and self.role.strip() != "":
            raise ValueError("role must not be set for delete operations.")
        return self


class WorkspaceMemberOperationResultItem(WorkspacesBaseModel):
    """Per-operation outcome from ``BatchUpdateWorkspaceMembers``, keyed by
    the input operation's index."""

    index: Optional[int] = Field(default=None, alias="Index")
    status: Optional[str] = Field(default=None, alias="Status")
    binding_id: Optional[str] = Field(default=None, alias="BindingId")
    error_code: Optional[str] = Field(default=None, alias="ErrorCode")


# CreateWorkspace - Request / Response
class CreateWorkspaceRequest(WorkspacesBaseModel):
    name: str = Field(..., alias="Name")
    org_id: str = Field(..., alias="OrgId")
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    description: Optional[str] = Field(default=None, alias="Description")

    @field_validator("name", "org_id")
    @classmethod
    def _validate_required_ids(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name and org_id are required to create a workspace.")
        return v

    @field_validator("project_name")
    @classmethod
    def _validate_project_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("project_name must not be empty when provided.")
        return v


class CreateWorkspaceResponse(WorkspacesBaseModel):
    workspace: Optional[WorkspaceData] = Field(default=None, alias="Workspace")


# ListWorkspaces - Request / Response
class ListWorkspacesRequest(WorkspacesBaseModel):
    org_id: str = Field(..., alias="OrgId")
    workspace_type: Optional[str] = Field(default=None, alias="WorkspaceType")
    status: Optional[str] = Field(default=None, alias="Status")
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    # 0 means "unspecified" and lets the server default (10, max 100).
    max_results: Optional[int] = Field(
        default=None, alias="MaxResults", ge=0, le=MAX_LIST_WORKSPACES_RESULTS
    )
    next_token: Optional[str] = Field(default=None, alias="NextToken")

    @field_validator("org_id")
    @classmethod
    def _validate_org_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("org_id is required to list workspaces.")
        return v

    @field_validator("workspace_type", "status", "project_name", "next_token")
    @classmethod
    def _validate_non_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("filter fields must not be empty when provided.")
        return v


class ListWorkspacesResponse(WorkspacesBaseModel):
    workspaces: Optional[List[WorkspaceData]] = Field(
        default=None, alias="Workspaces"
    )
    next_token: Optional[str] = Field(default=None, alias="NextToken")

    @field_validator("next_token")
    @classmethod
    def _empty_token_is_none(cls, v: Optional[str]) -> Optional[str]:
        # The server returns an empty NextToken on the last page.
        return v or None


# GetWorkspace - Request / Response
class GetWorkspaceRequest(WorkspacesBaseModel):
    """Lookup by workspace ID (takes precedence) or by project name (the
    org's default workspace in that project); one of them is required."""

    workspace_id: Optional[str] = Field(default=None, alias="WorkspaceId")
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    # Also fetch per-role member counts (sent as "true" in the query).
    count_member: Optional[bool] = Field(default=None, alias="CountMember")

    @field_validator("workspace_id", "project_name")
    @classmethod
    def _normalize_ids(cls, v: Optional[str]) -> Optional[str]:
        return _normalize_optional(v)

    @model_validator(mode="after")
    def _validate_lookup_key(self) -> "GetWorkspaceRequest":
        if not (self.workspace_id or self.project_name):
            raise ValueError(
                "Either workspace_id or project_name is required to fetch "
                "a workspace."
            )
        return self


class GetWorkspaceResponse(WorkspacesBaseModel):
    workspace: Optional[WorkspaceData] = Field(default=None, alias="Workspace")


# UpdateWorkspace - Request / Response
class UpdateWorkspaceRequest(WorkspacesBaseModel):
    workspace_id: str = Field(..., alias="WorkspaceId")
    name: Optional[str] = Field(default=None, alias="Name")
    description: Optional[str] = Field(default=None, alias="Description")

    @field_validator("workspace_id")
    @classmethod
    def _validate_workspace_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("workspace_id is required to update a workspace.")
        return v

    @field_validator("name", "description")
    @classmethod
    def _validate_non_empty(cls, v: Optional[str]) -> Optional[str]:
        # Empty strings do not update server-side -- there is no
        # clear-by-empty-string semantics.
        if v is not None and not v.strip():
            raise ValueError(
                "name/description must not be empty; omit them to keep the "
                "current values."
            )
        return v

    @model_validator(mode="after")
    def _validate_has_change(self) -> "UpdateWorkspaceRequest":
        if self.name is None and self.description is None:
            raise ValueError(
                "Nothing to update. Pass at least one of name/description."
            )
        return self


class UpdateWorkspaceResponse(WorkspacesBaseModel):
    workspace: Optional[WorkspaceData] = Field(default=None, alias="Workspace")


# DeleteWorkspace - Request / Response
class DeleteWorkspaceRequest(WorkspacesBaseModel):
    workspace_id: str = Field(..., alias="WorkspaceId")

    @field_validator("workspace_id")
    @classmethod
    def _validate_workspace_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("workspace_id is required to delete a workspace.")
        return v


class DeleteWorkspaceResponse(WorkspacesBaseModel):
    deleted: Optional[bool] = Field(default=None, alias="Deleted")


# GrantSystemAdmin - Request / Response
class GrantSystemAdminRequest(WorkspacesBaseModel):
    workspace_id: str = Field(..., alias="WorkspaceId")
    # IAM user ids; the server requires a non-empty list without blanks.
    iam_user_ids: List[str] = Field(..., alias="IamUserIdList")

    @field_validator("workspace_id")
    @classmethod
    def _validate_workspace_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("workspace_id is required to grant system admin.")
        return v

    @model_validator(mode="after")
    def _validate_user_ids(self) -> "GrantSystemAdminRequest":
        if not self.iam_user_ids:
            raise ValueError("iam_user_ids must contain at least one user id.")
        for i, user_id in enumerate(self.iam_user_ids):
            if not user_id.strip():
                raise ValueError(f"iam_user_ids[{i}] must not be empty.")
        return self


class GrantSystemAdminResponse(WorkspacesBaseModel):
    bindings: Optional[List[GrantSystemAdminBindingData]] = Field(
        default=None, alias="Bindings"
    )


# AddWorkspaceMember - Request / Response
class AddWorkspaceMemberRequest(WorkspacesBaseModel):
    workspace_id: str = Field(..., alias="WorkspaceId")
    user_id: str = Field(..., alias="UserId")
    role: str = Field(..., alias="Role")

    @field_validator("workspace_id", "user_id")
    @classmethod
    def _validate_required_ids(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(
                "workspace_id and user_id are required to add a workspace "
                "member."
            )
        return v

    @field_validator("role")
    @classmethod
    def _validate_role(cls, v: str) -> str:
        return _validate_workspace_role(v)


class AddWorkspaceMemberResponse(WorkspacesBaseModel):
    binding: Optional[WorkspaceMemberBindingData] = Field(
        default=None, alias="Binding"
    )


# ListWorkspaceMembers - Request / Response
class ListWorkspaceMembersRequest(WorkspacesBaseModel):
    workspace_id: str = Field(..., alias="WorkspaceId")
    role: Optional[str] = Field(default=None, alias="Role")
    username: Optional[str] = Field(default=None, alias="Username")
    email: Optional[str] = Field(default=None, alias="Email")
    user_id: Optional[str] = Field(default=None, alias="UserId")
    # 0 means "unspecified" and lets the server default (10, max 100).
    max_results: Optional[int] = Field(
        default=None,
        alias="MaxResults",
        ge=0,
        le=MAX_LIST_WORKSPACE_MEMBERS_RESULTS,
    )
    next_token: Optional[str] = Field(default=None, alias="NextToken")

    @field_validator("workspace_id")
    @classmethod
    def _validate_workspace_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(
                "workspace_id is required to list workspace members."
            )
        return v

    @field_validator("role")
    @classmethod
    def _validate_role(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v.strip():
                raise ValueError("role must not be empty when provided.")
            return _validate_workspace_role(v)
        return v

    @field_validator("username", "email", "user_id", "next_token")
    @classmethod
    def _validate_non_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("filter fields must not be empty when provided.")
        return v


class ListWorkspaceMembersResponse(WorkspacesBaseModel):
    bindings: Optional[List[WorkspaceMemberBindingData]] = Field(
        default=None, alias="Bindings"
    )
    next_token: Optional[str] = Field(default=None, alias="NextToken")

    @field_validator("next_token")
    @classmethod
    def _empty_token_is_none(cls, v: Optional[str]) -> Optional[str]:
        return v or None


# GetWorkspaceMember - Request / Response
class GetWorkspaceMemberRequest(WorkspacesBaseModel):
    workspace_id: str = Field(..., alias="WorkspaceId")
    user_id: str = Field(..., alias="UserId")

    @field_validator("workspace_id", "user_id")
    @classmethod
    def _validate_required_ids(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(
                "workspace_id and user_id are required to fetch a workspace "
                "member."
            )
        return v


class GetWorkspaceMemberResponse(WorkspacesBaseModel):
    """A missing ``binding`` is a legal "not a member" answer (no error):
    the ids are still present and ``effective_roles`` is empty."""

    workspace_id: Optional[str] = Field(default=None, alias="WorkspaceId")
    user_id: Optional[str] = Field(default=None, alias="UserId")
    binding: Optional[WorkspaceMemberBindingData] = Field(
        default=None, alias="Binding"
    )
    effective_roles: Optional[List[str]] = Field(
        default=None, alias="EffectiveRoles"
    )


# UpdateWorkspaceMemberRole - Request / Response
class UpdateWorkspaceMemberRoleRequest(WorkspacesBaseModel):
    workspace_id: str = Field(..., alias="WorkspaceId")
    user_id: str = Field(..., alias="UserId")
    role: str = Field(..., alias="Role")

    @field_validator("workspace_id", "user_id")
    @classmethod
    def _validate_required_ids(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(
                "workspace_id and user_id are required to update a workspace "
                "member role."
            )
        return v

    @field_validator("role")
    @classmethod
    def _validate_role(cls, v: str) -> str:
        return _validate_workspace_role(v)


class UpdateWorkspaceMemberRoleResponse(WorkspacesBaseModel):
    binding: Optional[WorkspaceMemberBindingData] = Field(
        default=None, alias="Binding"
    )
    effective_roles: Optional[List[str]] = Field(
        default=None, alias="EffectiveRoles"
    )


# RemoveWorkspaceMember - Request / Response
class RemoveWorkspaceMemberRequest(WorkspacesBaseModel):
    workspace_id: str = Field(..., alias="WorkspaceId")
    user_id: str = Field(..., alias="UserId")

    @field_validator("workspace_id", "user_id")
    @classmethod
    def _validate_required_ids(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(
                "workspace_id and user_id are required to remove a workspace "
                "member."
            )
        return v


class RemoveWorkspaceMemberResponse(WorkspacesBaseModel):
    deleted_binding_id: Optional[str] = Field(
        default=None, alias="DeletedBindingId"
    )


# BatchUpdateWorkspaceMembers - Request / Response
class BatchUpdateWorkspaceMembersRequest(WorkspacesBaseModel):
    workspace_id: str = Field(..., alias="WorkspaceId")
    operations: List[WorkspaceMemberOperationItem] = Field(
        ..., alias="Operations"
    )

    @field_validator("workspace_id")
    @classmethod
    def _validate_workspace_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(
                "workspace_id is required to batch update workspace members."
            )
        return v

    @model_validator(mode="after")
    def _validate_batch(self) -> "BatchUpdateWorkspaceMembersRequest":
        if not 1 <= len(self.operations) <= MAX_BATCH_MEMBER_OPERATIONS:
            raise ValueError(
                f"operations must contain 1-{MAX_BATCH_MEMBER_OPERATIONS} "
                f"entries, got {len(self.operations)}."
            )
        return self


class BatchUpdateWorkspaceMembersResponse(WorkspacesBaseModel):
    """The server is all-or-nothing: any failed pre-check rejects the whole
    batch, so a success response carries no per-item errors."""

    succeeded_count: Optional[int] = Field(
        default=None, alias="SucceededCount"
    )
    failed_count: Optional[int] = Field(default=None, alias="FailedCount")
    results: Optional[List[WorkspaceMemberOperationResultItem]] = Field(
        default=None, alias="Results"
    )
