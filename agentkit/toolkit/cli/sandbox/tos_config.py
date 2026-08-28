# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
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

"""TOS mount configuration helpers for sandbox CLI commands."""

from __future__ import annotations

from typing import Optional

from agentkit.sdk.tools import types as tools_types
from agentkit.toolkit.cli.sandbox.sandbox_client import error
from agentkit.toolkit.volcengine.services.tos_service import (
    TOSMountConfig,
    TOSService,
    TOSServiceConfig,
)

DEFAULT_TOS_BUCKET_PATH = "/sandbox-session/default/default"
DEFAULT_TOS_LOCAL_PATH = "/home/gem/workspace"
DEFAULT_SANDBOX_WORKSPACE = "/home/gem"
DEFAULT_TOS_CREDENTIAL_TYPE = (
    tools_types.CredentialType.TOS_CREDENTIAL_TYPE_ACCESS_KEY
)


def normalize_tos_credential_type(
    value: str | tools_types.CredentialType | None,
) -> tools_types.CredentialType:
    if isinstance(value, tools_types.CredentialType):
        return value

    normalized = (value or "").strip().upper().replace("-", "_")
    aliases = {
        "": DEFAULT_TOS_CREDENTIAL_TYPE,
        "ACCESS_KEY": tools_types.CredentialType.TOS_CREDENTIAL_TYPE_ACCESS_KEY,
        "TOS_CREDENTIAL_TYPE_ACCESS_KEY": (
            tools_types.CredentialType.TOS_CREDENTIAL_TYPE_ACCESS_KEY
        ),
        "IAM_ROLE": tools_types.CredentialType.TOS_CREDENTIAL_TYPE_IAM_ROLE,
        "TOS_CREDENTIAL_TYPE_IAM_ROLE": (
            tools_types.CredentialType.TOS_CREDENTIAL_TYPE_IAM_ROLE
        ),
    }
    credential_type = aliases.get(normalized)
    if credential_type is None:
        error(
            "--tos-credential-type must be one of: access-key, iam-role"
        )
    return credential_type


def resolve_tos_bucket(tos_bucket: Optional[str]) -> str:
    resolved_bucket = (tos_bucket or "").strip()
    if not resolved_bucket:
        error("--tos-bucket must not be empty")
    return resolved_bucket


def resolve_tos_mount_path(value: str | None) -> str:
    resolved = (value or "").strip()
    if not resolved:
        error("--tos-mount must not be empty")
    return resolved


def build_create_tool_tos_mount_config(
    tos_bucket: Optional[str],
    region: str,
    *,
    local_mount_path: str = DEFAULT_TOS_LOCAL_PATH,
    credential_type: str | tools_types.CredentialType | None = None,
    tos_service_cls=TOSService,
    tos_service_config_cls=TOSServiceConfig,
) -> tools_types.TosMountForCreateTool | None:
    if not (tos_bucket or "").strip():
        return None

    resolved_bucket = resolve_tos_bucket(tos_bucket)
    resolved_local_mount_path = resolve_tos_mount_path(local_mount_path)
    resolved_credential_type = normalize_tos_credential_type(credential_type)
    if (
        resolved_credential_type
        == tools_types.CredentialType.TOS_CREDENTIAL_TYPE_IAM_ROLE
    ):
        return tools_types.TosMountForCreateTool(
            EnableTos=True,
            CredentialType=resolved_credential_type,
            MountPoints=[
                tools_types.TosMountMountPointsItemForCreateTool(
                    BucketName=resolved_bucket,
                    BucketPath=DEFAULT_TOS_BUCKET_PATH,
                    Endpoint=TOSService.build_mount_endpoint(region),
                    LocalMountPath=resolved_local_mount_path,
                    ReadOnly=False,
                )
            ],
        )

    service = tos_service_cls(
        tos_service_config_cls(
            bucket=resolved_bucket,
            region=region,
        )
    )
    mount_config = service.build_mount_config(
        bucket_path=DEFAULT_TOS_BUCKET_PATH,
        local_mount_path=resolved_local_mount_path,
    )
    return to_create_tool_tos_mount_config(mount_config)


def to_create_tool_tos_mount_config(
    mount_config: TOSMountConfig,
) -> tools_types.TosMountForCreateTool:
    return tools_types.TosMountForCreateTool(
        EnableTos=True,
        CredentialType=(
            tools_types.CredentialType.TOS_CREDENTIAL_TYPE_ACCESS_KEY
        ),
        Credentials=tools_types.TosMountCredentialsForCreateTool(
            AccessKeyId=mount_config.credentials.access_key_id,
            SecretAccessKey=mount_config.credentials.secret_access_key,
        ),
        MountPoints=[
            tools_types.TosMountMountPointsItemForCreateTool(
                BucketName=mount.bucket_name,
                BucketPath=mount.bucket_path,
                Endpoint=mount.endpoint,
                LocalMountPath=mount.local_mount_path,
                ReadOnly=mount.read_only,
            )
            for mount in mount_config.mount_points
        ],
    )


def build_session_bucket_path(
    bucket_path: object,
    *,
    tool_id: str,
    session_id: str,
) -> str:
    base_path = bucket_path if isinstance(bucket_path, str) else ""
    base_path = base_path.strip().rstrip("/")
    if base_path.endswith("/default/default"):
        base_path = base_path[: -len("/default/default")]
    if not base_path:
        base_path = "/sandbox-session"
    if not base_path.startswith("/"):
        base_path = f"/{base_path}"
    return f"{base_path}/tool-{tool_id}/session-{session_id}/"


def build_session_tos_mount_points(
    tool: tools_types.GetToolResponse,
    *,
    tool_id: str,
    session_id: str,
) -> list[tools_types.TosMountPointsItemForCreateSession] | None:
    tos_mount_config = getattr(tool, "tos_mount_config", None)
    if not tos_mount_config:
        return None

    mount_points = getattr(tos_mount_config, "mount_points", None) or []
    result: list[tools_types.TosMountPointsItemForCreateSession] = []
    for mount in mount_points:
        bucket_name = getattr(mount, "bucket_name", None)
        local_mount_path = getattr(mount, "local_mount_path", None)
        if not bucket_name or not local_mount_path:
            continue
        result.append(
            tools_types.TosMountPointsItemForCreateSession(
                bucket_name=bucket_name,
                bucket_path=build_session_bucket_path(
                    getattr(mount, "bucket_path", None),
                    tool_id=tool_id,
                    session_id=session_id,
                ),
                local_mount_path=local_mount_path,
            )
        )

    return result or None
