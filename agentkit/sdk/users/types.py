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

"""Pydantic models for the AgentKit Users (user pool) OpenAPI.

Wire-format notes (mirroring the AgentKit OpenAPI definition):
- ``CreateUsers`` carries a mixed-casing body: PascalCase top-level keys
  (``UserPoolId``) but a lowercase ``users`` array whose items use
  snake_case keys (``preferred_username``, ``name``, ...).
- GET-declared actions (``ListUsers``, ``GetUser``) carry business params
  in the query string with PascalCase keys.
- ``UpdateUser``/``DeleteUser`` return an empty ``Result`` on success.
"""

from __future__ import annotations

import base64
import binascii
import re
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# Client-side mirrors of the server's field rules so invalid input fails
# fast with readable errors instead of one failed round-trip per mistake.
USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{2,64}$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_E164_RE = re.compile(r"^\+[1-9]\d{1,14}$")

MAX_CREATE_USERS_BATCH_SIZE = 1000
MAX_GROUP_MEMBER_BATCH_SIZE = 100

# The only content type ImportUsers accepts (case-insensitive).
IMPORT_USERS_CONTENT_TYPE_CSV = "CSV"


class UsersBaseModel(BaseModel):
    """AgentKit Users base model"""

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


def _normalize_user_pool_id(v: Optional[str]) -> Optional[str]:
    """Trim an optional UserPoolId; empty means "use the account's default
    user pool", which the server resolves itself."""
    if v is None:
        return None
    v = v.strip()
    return v or None


def _validate_username_field(cls, v: str) -> str:
    if not USERNAME_RE.match(v):
        raise ValueError(
            f"{v!r} must be 2-64 characters of letters, digits, '.', '_' or '-'."
        )
    if v[0].isdigit():
        raise ValueError(f"{v!r} must not start with a digit.")
    if ".." in v:
        raise ValueError(f"{v!r} must not contain consecutive dots.")
    return v


# Data Types


class UserForCreateUsers(UsersBaseModel):
    """One user to create, as the ``CreateUsers`` body's ``users`` items
    expect it. Wire keys are snake_case (unlike the PascalCase envelope)."""

    preferred_username: str = Field(..., alias="preferred_username")
    name: str = Field(..., alias="name")
    email: Optional[str] = Field(default=None, alias="email")
    phone: Optional[str] = Field(default=None, alias="phone")
    external_provider_id: Optional[str] = Field(
        default=None, alias="external_provider_id"
    )

    @field_validator("preferred_username")
    @classmethod
    def _validate_preferred_username(cls, v: str) -> str:
        return _validate_username_field(cls, v)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        if not v:
            raise ValueError("name is required and must not be empty.")
        if len(v) > 255:
            raise ValueError("name must be at most 255 characters.")
        return v

    @field_validator("email")
    @classmethod
    def _validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if len(v) > 255:
            raise ValueError("email must be at most 255 characters.")
        if not EMAIL_RE.match(v):
            raise ValueError(f"{v!r} is not a valid email address.")
        return v

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not PHONE_E164_RE.match(v):
            raise ValueError(
                f"{v!r} must be an E.164 number, e.g. '+8613800138000'."
            )
        return v

    @field_validator("external_provider_id")
    @classmethod
    def _validate_external_provider_id(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 255:
            raise ValueError("external_provider_id must be at most 255 characters.")
        return v


class ErrorForCreateUserResultItem(UsersBaseModel):
    code: Optional[str] = Field(default=None, alias="Code")
    message: Optional[str] = Field(default=None, alias="Message")


class CreateUserResultItem(UsersBaseModel):
    """Per-user outcome from ``CreateUsers``. ``Results[i]`` corresponds to
    ``users[i]``; a present ``error`` marks that user as failed without
    affecting the others."""

    user_id: Optional[str] = Field(default=None, alias="UserId")
    create_time: Optional[str] = Field(default=None, alias="CreateTime")
    update_time: Optional[str] = Field(default=None, alias="UpdateTime")
    error: Optional[ErrorForCreateUserResultItem] = Field(
        default=None, alias="Error"
    )


class ErrorForGroupUserResultItem(UsersBaseModel):
    code: Optional[str] = Field(default=None, alias="Code")
    message: Optional[str] = Field(default=None, alias="Message")


class GroupUserResultItem(UsersBaseModel):
    """Per-user outcome from a group membership action. ``Results[i]``
    corresponds to ``userIds[i]``, so a single batch can partly succeed."""

    user_id: Optional[str] = Field(default=None, alias="UserId")
    # Only reported by AddUsersToGroup; absence of error means success
    # for RemoveUsersFromGroup/ChangeUsersGroup.
    success: Optional[bool] = Field(default=None, alias="Success")
    error: Optional[ErrorForGroupUserResultItem] = Field(
        default=None, alias="Error"
    )


class ImportUserErrorItem(UsersBaseModel):
    """One structured import failure, keyed by CSV row."""

    index: Optional[int] = Field(default=None, alias="Index")
    field: Optional[str] = Field(default=None, alias="Field")
    error_type: Optional[str] = Field(default=None, alias="ErrorType")
    error_message: Optional[str] = Field(default=None, alias="ErrorMessage")
    duplicated_user_id: Optional[str] = Field(
        default=None, alias="DuplicatedUserId"
    )


class UsersItemForListUsers(UsersBaseModel):
    """One user as returned by ``ListUsers``."""

    user_id: Optional[str] = Field(default=None, alias="UserId")
    preferred_username: Optional[str] = Field(
        default=None, alias="PreferredUsername"
    )
    name: Optional[str] = Field(default=None, alias="Name")
    email: Optional[str] = Field(default=None, alias="Email")
    phone: Optional[str] = Field(default=None, alias="Phone")
    created_at: Optional[str] = Field(default=None, alias="CreatedAt")
    updated_at: Optional[str] = Field(default=None, alias="UpdatedAt")


# CreateUsers - Request / Response
class CreateUsersRequest(UsersBaseModel):
    user_pool_id: Optional[str] = Field(default=None, alias="UserPoolId")
    # Wire quirk: the array key is lowercase "users" while the envelope is
    # PascalCase; item keys are snake_case (see UserForCreateUsers).
    users: List[UserForCreateUsers] = Field(..., alias="users")

    @field_validator("user_pool_id")
    @classmethod
    def _normalize_pool(cls, v: Optional[str]) -> Optional[str]:
        return _normalize_user_pool_id(v)

    @model_validator(mode="after")
    def _validate_batch(self) -> "CreateUsersRequest":
        if not 1 <= len(self.users) <= MAX_CREATE_USERS_BATCH_SIZE:
            raise ValueError(
                f"users must contain 1-{MAX_CREATE_USERS_BATCH_SIZE} users, "
                f"got {len(self.users)}."
            )
        return self


class CreateUsersResponse(UsersBaseModel):
    results: Optional[List[CreateUserResultItem]] = Field(
        default=None, alias="Results"
    )


# UpdateUser - Request / Response
class UpdateUserRequest(UsersBaseModel):
    """Fields to change on one user. Omitted (None) leaves the field
    untouched; an empty string clears it server-side (the username cannot
    be cleared)."""

    user_pool_id: Optional[str] = Field(default=None, alias="UserPoolId")
    user_id: str = Field(..., alias="UserId")
    preferred_username: Optional[str] = Field(
        default=None, alias="PreferredUsername"
    )
    name: Optional[str] = Field(default=None, alias="Name")
    email: Optional[str] = Field(default=None, alias="Email")
    phone: Optional[str] = Field(default=None, alias="Phone")

    @field_validator("user_pool_id")
    @classmethod
    def _normalize_pool(cls, v: Optional[str]) -> Optional[str]:
        return _normalize_user_pool_id(v)

    @field_validator("user_id")
    @classmethod
    def _validate_user_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("user_id is required to identify the user to update.")
        return v

    @field_validator("preferred_username")
    @classmethod
    def _validate_preferred_username(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if v == "":
            raise ValueError(
                "preferred_username must not be empty; omit it to keep the "
                "current username."
            )
        return _validate_username_field(cls, v)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: Optional[str]) -> Optional[str]:
        # Empty string clears the field and is valid; otherwise cap at 255.
        if v is not None and len(v) > 255:
            raise ValueError("name must be at most 255 characters.")
        return v

    @field_validator("email")
    @classmethod
    def _validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return v
        if len(v) > 255:
            raise ValueError("email must be at most 255 characters.")
        if not EMAIL_RE.match(v):
            raise ValueError(f"{v!r} is not a valid email address.")
        return v

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v != "" and not PHONE_E164_RE.match(v):
            raise ValueError(
                f"{v!r} must be an E.164 number, e.g. '+8613800138000'."
            )
        return v


class UpdateUserResponse(UsersBaseModel):
    """Empty on success."""


# DeleteUser - Request / Response
class DeleteUserRequest(UsersBaseModel):
    user_pool_id: Optional[str] = Field(default=None, alias="UserPoolId")
    user_id: str = Field(..., alias="UserId")

    @field_validator("user_pool_id")
    @classmethod
    def _normalize_pool(cls, v: Optional[str]) -> Optional[str]:
        return _normalize_user_pool_id(v)

    @field_validator("user_id")
    @classmethod
    def _validate_user_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("user_id is required to delete a user.")
        return v


class DeleteUserResponse(UsersBaseModel):
    """Empty on success."""


# ListUsers - Request / Response
class ListUsersRequest(UsersBaseModel):
    user_pool_id: Optional[str] = Field(default=None, alias="UserPoolId")
    email: Optional[str] = Field(default=None, alias="Email")
    preferred_username: Optional[str] = Field(
        default=None, alias="PreferredUsername"
    )
    name: Optional[str] = Field(default=None, alias="Name")
    # 0 means "unspecified" and lets the server default (10, max 100).
    max_results: Optional[int] = Field(
        default=None, alias="MaxResults", ge=0, le=100
    )
    next_token: Optional[str] = Field(default=None, alias="NextToken")

    @field_validator("user_pool_id")
    @classmethod
    def _normalize_pool(cls, v: Optional[str]) -> Optional[str]:
        return _normalize_user_pool_id(v)

    @field_validator("email", "preferred_username", "name", "next_token")
    @classmethod
    def _validate_non_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("filter fields must not be empty when provided.")
        return v


class ListUsersResponse(UsersBaseModel):
    users: Optional[List[UsersItemForListUsers]] = Field(
        default=None, alias="Users"
    )
    next_token: Optional[str] = Field(default=None, alias="NextToken")

    @field_validator("next_token")
    @classmethod
    def _empty_token_is_none(cls, v: Optional[str]) -> Optional[str]:
        # The server returns an empty NextToken on the last page.
        return v or None


# GetUser - Request / Response
class GetUserRequest(UsersBaseModel):
    user_pool_id: Optional[str] = Field(default=None, alias="UserPoolId")
    user_id: str = Field(..., alias="UserId")

    @field_validator("user_pool_id")
    @classmethod
    def _normalize_pool(cls, v: Optional[str]) -> Optional[str]:
        return _normalize_user_pool_id(v)

    @field_validator("user_id")
    @classmethod
    def _validate_user_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("user_id is required to fetch a user.")
        return v


class GetUserResponse(UsersBaseModel):
    """Unlike ``ListUsers`` items, ``GetUser`` carries ``WorkspaceIds`` and
    no ``Phone``/``UpdatedAt``."""

    user_id: Optional[str] = Field(default=None, alias="UserId")
    preferred_username: Optional[str] = Field(
        default=None, alias="PreferredUsername"
    )
    name: Optional[str] = Field(default=None, alias="Name")
    email: Optional[str] = Field(default=None, alias="Email")
    created_at: Optional[str] = Field(default=None, alias="CreatedAt")
    workspace_ids: Optional[List[str]] = Field(
        default=None, alias="WorkspaceIds"
    )


# AddUsersToGroup - Request / Response
class AddUsersToGroupRequest(UsersBaseModel):
    user_pool_id: Optional[str] = Field(default=None, alias="UserPoolId")
    group_id: str = Field(..., alias="GroupId")
    user_ids: List[str] = Field(..., alias="UserIds")

    @field_validator("user_pool_id")
    @classmethod
    def _normalize_pool(cls, v: Optional[str]) -> Optional[str]:
        return _normalize_user_pool_id(v)

    @field_validator("group_id")
    @classmethod
    def _validate_group_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("group_id is required.")
        return v

    @model_validator(mode="after")
    def _validate_batch(self) -> "AddUsersToGroupRequest":
        _validate_user_ids(self.user_ids)
        return self


class AddUsersToGroupResponse(UsersBaseModel):
    results: Optional[List[GroupUserResultItem]] = Field(
        default=None, alias="Results"
    )


# RemoveUsersFromGroup - Request / Response
class RemoveUsersFromGroupRequest(UsersBaseModel):
    user_pool_id: Optional[str] = Field(default=None, alias="UserPoolId")
    group_id: str = Field(..., alias="GroupId")
    user_ids: List[str] = Field(..., alias="UserIds")

    @field_validator("user_pool_id")
    @classmethod
    def _normalize_pool(cls, v: Optional[str]) -> Optional[str]:
        return _normalize_user_pool_id(v)

    @field_validator("group_id")
    @classmethod
    def _validate_group_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("group_id is required.")
        return v

    @model_validator(mode="after")
    def _validate_batch(self) -> "RemoveUsersFromGroupRequest":
        _validate_user_ids(self.user_ids)
        return self


class RemoveUsersFromGroupResponse(UsersBaseModel):
    results: Optional[List[GroupUserResultItem]] = Field(
        default=None, alias="Results"
    )


# ChangeUsersGroup - Request / Response
class ChangeUsersGroupRequest(UsersBaseModel):
    user_pool_id: Optional[str] = Field(default=None, alias="UserPoolId")
    origin_group_id: str = Field(..., alias="OriginGroupId")
    target_group_id: str = Field(..., alias="TargetGroupId")
    user_ids: List[str] = Field(..., alias="UserIds")

    @field_validator("user_pool_id")
    @classmethod
    def _normalize_pool(cls, v: Optional[str]) -> Optional[str]:
        return _normalize_user_pool_id(v)

    @field_validator("origin_group_id", "target_group_id")
    @classmethod
    def _validate_group_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("group ids are required.")
        return v

    @model_validator(mode="after")
    def _validate_batch(self) -> "ChangeUsersGroupRequest":
        _validate_user_ids(self.user_ids)
        return self


class ChangeUsersGroupResponse(UsersBaseModel):
    results: Optional[List[GroupUserResultItem]] = Field(
        default=None, alias="Results"
    )


# ImportUsers - Request / Response
class ImportUsersRequest(UsersBaseModel):
    user_pool_id: Optional[str] = Field(default=None, alias="UserPoolId")
    # Base64-encoded CSV content (header row + one user per row).
    users_base64: str = Field(..., alias="UsersBase64")
    # Import data format; only "CSV" is supported.
    content_type: str = Field(..., alias="ContentType")

    @field_validator("user_pool_id")
    @classmethod
    def _normalize_pool(cls, v: Optional[str]) -> Optional[str]:
        return _normalize_user_pool_id(v)

    @field_validator("users_base64")
    @classmethod
    def _validate_users_base64(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("users_base64 is required.")
        try:
            raw = base64.b64decode(v, validate=True)
            text = raw.decode("utf-8")
        except (binascii.Error, UnicodeDecodeError) as e:
            raise ValueError(
                "users_base64 must be valid standard base64 decoding to "
                "UTF-8 text."
            ) from e
        rows = [
            row
            for row in re.split(r"\r\n|\r|\n", text)
            if row.strip() != ""
        ]
        if len(rows) < 2:
            raise ValueError(
                "users_base64 must decode to CSV with a header row and at "
                "least one user row."
            )
        return v

    @field_validator("content_type")
    @classmethod
    def _validate_content_type(cls, v: str) -> str:
        if v.strip().upper() != IMPORT_USERS_CONTENT_TYPE_CSV:
            raise ValueError(
                f"content_type {v!r} is invalid; only CSV is supported."
            )
        return v


class ImportUsersResponse(UsersBaseModel):
    success_count: Optional[int] = Field(default=None, alias="SuccessCount")
    failure_count: Optional[int] = Field(default=None, alias="FailureCount")
    successful_user_ids: Optional[List[str]] = Field(
        default=None, alias="SuccessfulUserIds"
    )
    errors: Optional[List[ImportUserErrorItem]] = Field(
        default=None, alias="Errors"
    )


def _validate_user_ids(user_ids: List[str]) -> None:
    if not 1 <= len(user_ids) <= MAX_GROUP_MEMBER_BATCH_SIZE:
        raise ValueError(
            f"user_ids must contain 1-{MAX_GROUP_MEMBER_BATCH_SIZE} users, "
            f"got {len(user_ids)}."
        )
    for i, user_id in enumerate(user_ids):
        if not user_id.strip():
            raise ValueError(f"user_ids[{i}] must not be empty.")
