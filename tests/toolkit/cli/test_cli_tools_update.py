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

from types import SimpleNamespace

from typer.testing import CliRunner

from agentkit.sdk.tools import types as tools_types


runner = CliRunner()


class _FakeToolsClient:
    last_request = None

    def __init__(self, **_kwargs):
        pass

    def update_tool(self, request):
        _FakeToolsClient.last_request = request
        return SimpleNamespace(tool_id=request.tool_id)


def test_tools_update_sends_iam_role_tos_mount_without_credentials(
    monkeypatch,
) -> None:
    from agentkit.toolkit.cli import cli_tools
    from agentkit.toolkit.cli.cli import app

    _FakeToolsClient.last_request = None
    monkeypatch.setattr(cli_tools, "AgentkitToolsClient", _FakeToolsClient)

    result = runner.invoke(
        app,
        [
            "tools",
            "update",
            "--tool-id",
            "tool-123",
            "--json",
            """{
                "ToolId": "tool-123",
                "TosMountConfig": {
                    "EnableTos": true,
                    "CredentialType": "TOS_CREDENTIAL_TYPE_IAM_ROLE",
                    "MountPoints": [
                        {
                            "BucketName": "bucket-1",
                            "BucketPath": "/",
                            "Endpoint": "http://tos-cn-beijing.ivolces.com",
                            "LocalMountPath": "/mnt/tos1",
                            "ReadOnly": false
                        },
                        {
                            "BucketName": "bucket-2",
                            "BucketPath": "/",
                            "Endpoint": "http://tos-cn-beijing.ivolces.com",
                            "LocalMountPath": "/mnt/tos2",
                            "ReadOnly": false
                        }
                    ]
                }
            }""",
        ],
    )

    assert result.exit_code == 0
    request = _FakeToolsClient.last_request
    assert isinstance(request, tools_types.UpdateToolRequest)
    assert request.tool_id == "tool-123"
    tos_config = request.tos_mount_config
    assert (
        tos_config.credential_type
        == tools_types.CredentialType.TOS_CREDENTIAL_TYPE_IAM_ROLE
    )
    assert tos_config.credentials is None
    assert [item.local_mount_path for item in tos_config.mount_points] == [
        "/mnt/tos1",
        "/mnt/tos2",
    ]


def test_tools_update_uses_cli_tool_id_when_json_id_has_whitespace(
    monkeypatch,
) -> None:
    from agentkit.toolkit.cli import cli_tools
    from agentkit.toolkit.cli.cli import app

    _FakeToolsClient.last_request = None
    monkeypatch.setattr(cli_tools, "AgentkitToolsClient", _FakeToolsClient)

    result = runner.invoke(
        app,
        [
            "tools",
            "update",
            "--tool-id",
            "tool-123",
            "--json",
            '{"ToolId": "tool-123 ", "Description": "updated"}',
        ],
    )

    assert result.exit_code == 0
    assert _FakeToolsClient.last_request.tool_id == "tool-123"
