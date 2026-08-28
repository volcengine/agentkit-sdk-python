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

import pytest
from pydantic import ValidationError

from agentkit.sdk.tools import types as tools_types


@pytest.mark.parametrize(
    "model_type",
    [
        tools_types.TosMountForCreateTool,
        tools_types.TosMountConfigForGetTool,
        tools_types.TosMountForUpdateTool,
    ],
)
@pytest.mark.parametrize("credential_type", list(tools_types.CredentialType))
def test_tos_mount_credential_type_accepts_supported_values(
    model_type,
    credential_type,
) -> None:
    config = model_type(CredentialType=credential_type.value)

    assert config.credential_type is credential_type
    assert config.model_dump(by_alias=True, mode="json", exclude_none=True) == {
        "CredentialType": credential_type.value
    }


@pytest.mark.parametrize(
    "model_type",
    [
        tools_types.TosMountForCreateTool,
        tools_types.TosMountConfigForGetTool,
        tools_types.TosMountForUpdateTool,
    ],
)
def test_tos_mount_credential_type_rejects_unknown_value(model_type) -> None:
    with pytest.raises(ValidationError):
        model_type(CredentialType="UNKNOWN")


def test_update_tool_iam_role_tos_mount_keeps_credential_type_without_ak_sk(
) -> None:
    request = tools_types.UpdateToolRequest(
        ToolId="tool-123",
        TosMountConfig=tools_types.TosMountForUpdateTool(
            EnableTos=True,
            CredentialType=(
                tools_types.CredentialType.TOS_CREDENTIAL_TYPE_IAM_ROLE
            ),
            MountPoints=[
                tools_types.TosMountMountPointsItemForUpdateTool(
                    BucketName="existing-bucket",
                    BucketPath="/sandbox-session/default/default",
                    Endpoint="http://tos-cn-beijing.ivolces.com",
                    LocalMountPath="/home/gem/workspace",
                    ReadOnly=False,
                )
            ],
        ),
    )

    assert request.model_dump(
        by_alias=True,
        mode="json",
        exclude_none=True,
    ) == {
        "ToolId": "tool-123",
        "TosMountConfig": {
            "EnableTos": True,
            "CredentialType": "TOS_CREDENTIAL_TYPE_IAM_ROLE",
            "MountPoints": [
                {
                    "BucketName": "existing-bucket",
                    "BucketPath": "/sandbox-session/default/default",
                    "Endpoint": "http://tos-cn-beijing.ivolces.com",
                    "LocalMountPath": "/home/gem/workspace",
                    "ReadOnly": False,
                }
            ],
        },
    }
