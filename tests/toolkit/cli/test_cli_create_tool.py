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

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

runner = CliRunner()
_PLACEHOLDER_A = "example-value-a"
_PLACEHOLDER_B = "example-value-b"
_PLACEHOLDER_MODEL_VALUE = "example-model-value"
_DEFAULT_BROWSER_EXTRA_ARGS = (
    "--enable-unsafe-swiftshader --use-gl=angle "
    "--use-angle=swiftshader-webgl --ignore-gpu-blocklist"
)


@pytest.fixture
def tool_store_path(monkeypatch, tmp_path):
    import agentkit.toolkit.cli.sandbox.tool_resolve as tool_resolve

    store_path = tmp_path / ".agentkit" / "sandbox" / "tools.json"
    monkeypatch.setattr(tool_resolve, "_get_tool_store_path", lambda: store_path)
    return store_path


@pytest.fixture(autouse=True)
def _use_tool_store_path(tool_store_path):
    pass


class _FakeCreateToolResponse:
    tool_id = "t-created"


class _FakeGetToolResponse:
    def __init__(self, status="Ready"):
        self.status = status
        self.tool_id = "t-created"
        self.name = "demo-tool"
        self.tool_type = "SkillEnv"
        self.tos_mount_config = None

    def model_dump(self, by_alias=False, exclude_none=False):
        payload = {
            "ToolId": self.tool_id,
            "Name": self.name,
            "Status": self.status,
            "ToolType": self.tool_type,
            "TosMountConfig": self.tos_mount_config,
        }
        if exclude_none:
            payload = {
                key: value for key, value in payload.items() if value is not None
            }
        return payload


class _FakeToolsClient:
    instances = []
    last_request = None
    get_statuses = ["Ready"]
    get_call_count = 0

    def __init__(self, **kwargs):
        self.access_key = kwargs.get("access" + "_key", "")
        self.secret_key = kwargs.get("secret" + "_key", "")
        self.region = kwargs.get("region", "")
        self.session_token = kwargs.get("session_token", "")
        _FakeToolsClient.instances.append(self)

    def create_tool(self, request):
        _FakeToolsClient.last_request = request
        return _FakeCreateToolResponse()

    def get_tool(self, request):
        _FakeToolsClient.get_call_count += 1
        if len(_FakeToolsClient.get_statuses) > 1:
            status = _FakeToolsClient.get_statuses.pop(0)
        else:
            status = _FakeToolsClient.get_statuses[0]
        return _FakeGetToolResponse(status=status)


class _FakeTOSService:
    instances = []
    generated_bucket_name = "agentkit-platform-123"

    def __init__(self, config):
        self.config = config
        self.created_directories = []
        self.bucket_path = ""
        self.local_mount_path = ""
        _FakeTOSService.instances.append(self)

    @staticmethod
    def generate_bucket_name():
        return _FakeTOSService.generated_bucket_name

    def build_mount_config(
        self,
        *,
        bucket_path,
        local_mount_path,
        read_only=False,
    ):
        from agentkit.toolkit.volcengine.services.tos_service import (
            TOSMountConfig,
            TOSMountCredentials,
            TOSMountPoint,
        )

        self.bucket_path = bucket_path
        self.local_mount_path = local_mount_path
        self.created_directories = [
            "sandbox-session/",
            "sandbox-session/default/",
            "sandbox-session/default/default/",
        ]
        return TOSMountConfig(
            credentials=TOSMountCredentials(
                **{
                    "access_key_id": _PLACEHOLDER_A,
                    "secret_" + "access_key": _PLACEHOLDER_B,
                }
            ),
            mount_points=[
                TOSMountPoint(
                    bucket_name=self.config.bucket,
                    bucket_path=bucket_path,
                    endpoint="http://tos-cn-beijing.ivolces.com",
                    local_mount_path=local_mount_path,
                    read_only=read_only,
                )
            ],
        )


class _FakePlatformConfig:
    endpoint_regions = {"agentkit": "cn-beijing", "tos": "cn-beijing"}

    def get_service_endpoint(self, service_key):
        return SimpleNamespace(region=self.endpoint_regions[service_key])


def _reset_fake_tools_client():
    _FakeToolsClient.instances = []
    _FakeToolsClient.last_request = None
    _FakeToolsClient.get_statuses = ["Ready"]
    _FakeToolsClient.get_call_count = 0
    _FakeTOSService.instances = []
    _FakePlatformConfig.endpoint_regions = {
        "agentkit": "cn-beijing",
        "tos": "cn-beijing",
    }


@pytest.fixture(autouse=True)
def _use_platform_config(monkeypatch):
    from agentkit.toolkit.cli.sandbox import cli_create

    _reset_fake_tools_client()
    monkeypatch.setattr(cli_create, "VolcConfiguration", _FakePlatformConfig)


def test_create_command_skips_tos_mount_by_default(
    monkeypatch,
    tool_store_path,
):
    from agentkit.toolkit.cli.cli import app
    from agentkit.toolkit.cli.sandbox import cli_create

    _reset_fake_tools_client()
    monkeypatch.delenv("AGENTKIT_SANDBOX_REGION", raising=False)
    monkeypatch.delenv("AGENTKIT_SANDBOX_TOS_REGION", raising=False)
    monkeypatch.setattr(cli_create, "AgentkitToolsClient", _FakeToolsClient)
    monkeypatch.setattr(cli_create, "TOSService", _FakeTOSService)

    result = runner.invoke(app, ["sandbox", "create", "--tool-name", "demo-tool"])

    assert result.exit_code == 0
    assert "工具创建成功" in result.output
    assert "工具ID：t-created" in result.output
    assert "状态：Ready" in result.output
    assert len(_FakeToolsClient.instances) == 1
    client = _FakeToolsClient.instances[0]
    assert client.access_key == ""
    assert client.secret_key == ""
    assert client.session_token == ""
    assert client.region == "cn-beijing"
    assert _FakeTOSService.instances == []
    assert _FakeToolsClient.last_request.name == "demo-tool"
    assert _FakeToolsClient.last_request.tool_type == "CodeEnv"
    assert _FakeToolsClient.last_request.cpu_milli == 4000
    assert _FakeToolsClient.last_request.memory_mb == 8192
    assert _FakeToolsClient.last_request.tos_mount_config is None
    assert _FakeToolsClient.get_call_count == 1
    assert json.loads(tool_store_path.read_text(encoding="utf-8")) == {
        "SkillEnv": {
            "ToolId": "t-created",
            "Name": "demo-tool",
            "Status": "Ready",
            "ToolType": "SkillEnv",
            "ModelProvider": "model_square",
        }
    }


def test_create_command_uses_region_envs(monkeypatch):
    from agentkit.toolkit.cli.cli import app
    from agentkit.toolkit.cli.sandbox import cli_create

    _reset_fake_tools_client()
    _FakePlatformConfig.endpoint_regions = {
        "agentkit": "platform-agentkit-region",
        "tos": "platform-tos-region",
    }
    monkeypatch.setenv("AGENTKIT_SANDBOX_REGION", " cn-shanghai ")
    monkeypatch.setenv("AGENTKIT_SANDBOX_TOS_REGION", " cn-guangzhou ")
    monkeypatch.setattr(cli_create, "AgentkitToolsClient", _FakeToolsClient)
    monkeypatch.setattr(cli_create, "TOSService", _FakeTOSService)

    result = runner.invoke(
        app,
        [
            "sandbox",
            "create",
            "--tool-name",
            "demo-tool",
            "--tos-bucket",
            "my-bucket",
        ],
    )

    assert result.exit_code == 0
    assert _FakeToolsClient.instances[0].region == "cn-shanghai"
    assert _FakeTOSService.instances[0].config.region == "cn-guangzhou"


def test_create_command_falls_back_to_platform_regions(monkeypatch):
    from agentkit.toolkit.cli.cli import app
    from agentkit.toolkit.cli.sandbox import cli_create

    _reset_fake_tools_client()
    _FakePlatformConfig.endpoint_regions = {
        "agentkit": "cn-shanghai",
        "tos": "cn-guangzhou",
    }
    monkeypatch.delenv("AGENTKIT_SANDBOX_REGION", raising=False)
    monkeypatch.delenv("AGENTKIT_SANDBOX_TOS_REGION", raising=False)
    monkeypatch.setattr(cli_create, "AgentkitToolsClient", _FakeToolsClient)
    monkeypatch.setattr(cli_create, "TOSService", _FakeTOSService)

    result = runner.invoke(
        app,
        [
            "sandbox",
            "create",
            "--tool-name",
            "demo-tool",
            "--tos-bucket",
            "my-bucket",
        ],
    )

    assert result.exit_code == 0
    assert _FakeToolsClient.instances[0].region == "cn-shanghai"
    assert _FakeTOSService.instances[0].config.region == "cn-guangzhou"


def test_create_command_uses_tos_service_when_bucket_is_set(monkeypatch):
    from agentkit.toolkit.cli.cli import app
    from agentkit.toolkit.cli.sandbox import cli_create

    _reset_fake_tools_client()
    monkeypatch.delenv("AGENTKIT_SANDBOX_TOS_REGION", raising=False)
    monkeypatch.setattr(cli_create, "AgentkitToolsClient", _FakeToolsClient)
    monkeypatch.setattr(cli_create, "TOSService", _FakeTOSService)

    result = runner.invoke(
        app,
        [
            "sandbox",
            "create",
            "--tool-name",
            "demo-tool",
            "--tos-bucket",
            "my-bucket",
        ],
    )

    assert result.exit_code == 0
    assert len(_FakeTOSService.instances) == 1
    assert _FakeTOSService.instances[0].config.bucket == "my-bucket"
    assert _FakeTOSService.instances[0].config.region == "cn-beijing"
    assert _FakeTOSService.instances[0].local_mount_path == "/home/gem/workspace"
    tos_config = _FakeToolsClient.last_request.tos_mount_config
    assert tos_config is not None
    assert tos_config.mount_points[0].bucket_name == "my-bucket"
    assert tos_config.mount_points[0].bucket_path == "/sandbox-session/default/default"


def test_create_command_uses_tos_mount_option(monkeypatch):
    from agentkit.toolkit.cli.cli import app
    from agentkit.toolkit.cli.sandbox import cli_create

    _reset_fake_tools_client()
    monkeypatch.setattr(cli_create, "AgentkitToolsClient", _FakeToolsClient)
    monkeypatch.setattr(cli_create, "TOSService", _FakeTOSService)

    result = runner.invoke(
        app,
        [
            "sandbox",
            "create",
            "--tool-name",
            "demo-tool",
            "--tos-bucket",
            "my-bucket",
            "--tos-mount",
            "/mnt/workspace",
        ],
    )

    assert result.exit_code == 0
    assert _FakeTOSService.instances[0].local_mount_path == "/mnt/workspace"
    tos_config = _FakeToolsClient.last_request.tos_mount_config
    assert tos_config is not None
    assert tos_config.mount_points[0].local_mount_path == "/mnt/workspace"


def test_create_command_rejects_tos_mount_without_tos_bucket(monkeypatch):
    from agentkit.toolkit.cli.cli import app
    from agentkit.toolkit.cli.sandbox import cli_create

    _reset_fake_tools_client()
    monkeypatch.setattr(cli_create, "AgentkitToolsClient", _FakeToolsClient)
    monkeypatch.setattr(cli_create, "TOSService", _FakeTOSService)

    result = runner.invoke(
        app,
        [
            "sandbox",
            "create",
            "--tool-name",
            "demo-tool",
            "--tos-mount",
            "/home/gem/tmp",
        ],
    )

    assert result.exit_code == 1
    assert "--tos-mount requires --tos-bucket" in result.output
    assert _FakeToolsClient.instances == []
    assert _FakeTOSService.instances == []


def test_create_command_uses_cpu_option_for_resource_shape(monkeypatch):
    from agentkit.toolkit.cli.cli import app
    from agentkit.toolkit.cli.sandbox import cli_create

    _reset_fake_tools_client()
    monkeypatch.setattr(cli_create, "AgentkitToolsClient", _FakeToolsClient)
    monkeypatch.setattr(cli_create, "TOSService", _FakeTOSService)

    result = runner.invoke(
        app,
        [
            "sandbox",
            "create",
            "--tool-name",
            "demo-tool",
            "--cpu",
            "2",
        ],
    )

    assert result.exit_code == 0
    assert _FakeToolsClient.last_request.cpu_milli == 2000
    assert _FakeToolsClient.last_request.memory_mb == 4096


def test_create_command_rejects_invalid_cpu(monkeypatch):
    from agentkit.toolkit.cli.cli import app
    from agentkit.toolkit.cli.sandbox import cli_create

    _reset_fake_tools_client()
    monkeypatch.setattr(cli_create, "AgentkitToolsClient", _FakeToolsClient)
    monkeypatch.setattr(cli_create, "TOSService", _FakeTOSService)

    result = runner.invoke(
        app,
        [
            "sandbox",
            "create",
            "--tool-name",
            "demo-tool",
            "--cpu",
            "3",
        ],
    )

    assert result.exit_code != 0
    assert "--cpu must be one of: 2, 4, 8" in result.output
    assert "16" in result.output
    assert _FakeToolsClient.instances == []
    assert _FakeTOSService.instances == []


def test_create_command_rejects_region_option(monkeypatch):
    from agentkit.toolkit.cli.cli import app
    from agentkit.toolkit.cli.sandbox import cli_create

    _reset_fake_tools_client()
    monkeypatch.setattr(cli_create, "AgentkitToolsClient", _FakeToolsClient)
    monkeypatch.setattr(cli_create, "TOSService", _FakeTOSService)

    result = runner.invoke(
        app,
        ["sandbox", "create", "--tool-name", "demo-tool", "--region", "cn-shanghai"],
    )

    assert result.exit_code != 0
    assert "Unknown arguments: --region cn-shanghai" in result.output
    assert _FakeToolsClient.instances == []
    assert _FakeTOSService.instances == []


def test_create_command_help_includes_model_base_url_option():
    from agentkit.toolkit.cli.cli import app

    result = runner.invoke(app, ["sandbox", "create", "--help"])

    assert result.exit_code == 0
    assert "--tos-mount" in result.output
    assert "/home/gem/workspace" in result.output
    assert "--model-provider" in result.output
    assert "--model-base-url" in result.output


def test_create_command_waits_until_tool_ready(monkeypatch):
    from agentkit.toolkit.cli.cli import app
    from agentkit.toolkit.cli.sandbox import cli_create

    _reset_fake_tools_client()
    _FakeToolsClient.get_statuses = ["Creating", "Ready"]
    monkeypatch.setattr(cli_create, "AgentkitToolsClient", _FakeToolsClient)
    monkeypatch.setattr(cli_create, "TOSService", _FakeTOSService)
    monkeypatch.setattr(cli_create.time, "sleep", lambda _seconds: None)

    result = runner.invoke(app, ["sandbox", "create", "--tool-name", "demo-tool"])

    assert result.exit_code == 0
    assert "工具状态：Creating" in result.output
    assert "工具状态：Ready" in result.output
    assert "工具创建成功" in result.output
    assert _FakeToolsClient.get_call_count == 2


def test_create_command_prints_sanitized_details_on_error(monkeypatch):
    from agentkit.toolkit.cli.cli import app
    from agentkit.toolkit.cli.sandbox import cli_create

    _reset_fake_tools_client()
    _FakeToolsClient.get_statuses = ["Error"]
    monkeypatch.setattr(cli_create, "AgentkitToolsClient", _FakeToolsClient)
    monkeypatch.setattr(cli_create, "TOSService", _FakeTOSService)

    result = runner.invoke(app, ["sandbox", "create", "--tool-name", "demo-tool"])

    assert result.exit_code == 1
    assert "entered terminal status: Error" in result.output
    assert "Summary:" in result.output
    assert "Name: demo-tool" in result.output
    assert _PLACEHOLDER_A not in result.output
    assert _PLACEHOLDER_B not in result.output


def test_build_create_tool_request_adds_tos_mount(monkeypatch):
    from agentkit.toolkit.cli.sandbox import cli_create

    _reset_fake_tools_client()
    monkeypatch.setattr(cli_create, "TOSService", _FakeTOSService)

    request = cli_create._build_create_tool_request(
        tool_type="CodeEnv",
        name="demo-tool",
        tos_bucket="my-bucket",
        tos_region="cn-beijing",
    )

    fake_service = _FakeTOSService.instances[0]
    assert fake_service.config.bucket == "my-bucket"
    assert fake_service.config.region == "cn-beijing"
    tos_config = request.tos_mount_config
    assert tos_config is not None
    assert tos_config.enable_tos is True
    assert tos_config.credentials.access_key_id == _PLACEHOLDER_A
    assert tos_config.credentials.secret_access_key == _PLACEHOLDER_B
    assert len(tos_config.mount_points) == 1
    mount_point = tos_config.mount_points[0]
    assert mount_point.bucket_name == "my-bucket"
    assert mount_point.bucket_path == "/sandbox-session/default/default"
    assert mount_point.endpoint == "http://tos-cn-beijing.ivolces.com"
    assert mount_point.local_mount_path == "/home/gem/workspace"
    assert mount_point.read_only is False
    assert fake_service.created_directories == [
        "sandbox-session/",
        "sandbox-session/default/",
        "sandbox-session/default/default/",
    ]
    assert request.authorizer_configuration is not None
    assert request.authorizer_configuration.key_auth is not None
    assert request.authorizer_configuration.key_auth.api_key_name
    assert request.authorizer_configuration.key_auth.api_key_location == "Header"
    assert request.network_configuration is not None
    assert request.network_configuration.enable_public_network is True
    assert request.network_configuration.enable_private_network is False
    assert request.cpu_milli == 4000
    assert request.memory_mb == 8192


def test_build_create_tool_request_uses_custom_tos_mount(monkeypatch):
    from agentkit.toolkit.cli.sandbox import cli_create

    _reset_fake_tools_client()
    monkeypatch.setattr(cli_create, "TOSService", _FakeTOSService)

    request = cli_create._build_create_tool_request(
        tool_type="CodeEnv",
        name="demo-tool",
        tos_bucket="my-bucket",
        tos_region="cn-beijing",
        tos_mount_path="/mnt/workspace",
    )

    assert _FakeTOSService.instances[0].local_mount_path == "/mnt/workspace"
    tos_config = request.tos_mount_config
    assert tos_config is not None
    assert tos_config.mount_points[0].local_mount_path == "/mnt/workspace"


def test_build_create_tool_request_skips_tos_mount_without_bucket(monkeypatch):
    from agentkit.toolkit.cli.sandbox import cli_create

    _reset_fake_tools_client()
    monkeypatch.setattr(cli_create, "TOSService", _FakeTOSService)

    request = cli_create._build_create_tool_request(
        tool_type="CodeEnv",
        name="demo-tool",
        tos_bucket=None,
        tos_region="cn-beijing",
    )

    assert _FakeTOSService.instances == []
    assert request.tos_mount_config is None


def test_build_create_tool_request_translates_custom_tool_env_to_private(monkeypatch):
    from agentkit.toolkit.cli.sandbox import cli_create
    from agentkit.toolkit.cli.sandbox.env_config import (
        CUSTOM_TOOL_ENV_COMMAND,
        CUSTOM_TOOL_ENV_VARS,
    )

    _reset_fake_tools_client()
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.setattr(cli_create, "TOSService", _FakeTOSService)

    request = cli_create._build_create_tool_request(
        tool_type="CustomToolEnv",
        name="demo-tool",
        tos_bucket=None,
        tos_region="cn-beijing",
        image_url="registry.example.com/custom-image:latest",
        model_name="ignored-model",
        **{"model_" + "api_key": _PLACEHOLDER_MODEL_VALUE},
    )

    assert request.tool_type == "Private"
    assert request.image_url == "registry.example.com/custom-image:latest"
    assert request.command == CUSTOM_TOOL_ENV_COMMAND
    assert request.port == 8080
    assert request.tos_mount_config is None
    env_map = {item.key: item.value for item in request.envs}
    assert [
        (item.key, item.value)
        for item in request.envs[: len(CUSTOM_TOOL_ENV_VARS)]
    ] == list(CUSTOM_TOOL_ENV_VARS)
    env_keys = set(env_map)
    assert "ABC" not in env_keys
    assert env_map["OPENCODE_MODEL"] == "ignored-model"
    assert env_map["CODEX_MODEL"] == "ignored-model"
    assert env_map["ANTHROPIC_MODEL"] == "ignored-model"
    assert env_map["CODEX_API_KEY"] == _PLACEHOLDER_MODEL_VALUE
    assert env_map["CODEX_BASE_URL"] == "https://ark.cn-beijing.volces.com/api/v3"
    assert "CODEX_CONFIG_TOML" in env_map
    assert "CODEX_MODEL_CATALOG_JSON" in env_map
    assert env_map["DISABLE_JUPYTER"] == "false"
    assert env_map["DISABLE_CODE_SERVER"] == "false"
    assert env_map["BROWSER_EXTRA_ARGS"] == ""


def test_build_create_tool_request_requires_image_url_for_custom_tool_env(monkeypatch):
    from agentkit.toolkit.cli.sandbox import cli_create

    _reset_fake_tools_client()
    monkeypatch.setattr(cli_create, "TOSService", _FakeTOSService)

    with pytest.raises(cli_create.typer.Exit):
        cli_create._build_create_tool_request(
            tool_type="CustomToolEnv",
            name="demo-tool",
            tos_bucket=None,
            tos_region="cn-beijing",
        )


def test_build_create_tool_request_derives_memory_from_cpu(monkeypatch):
    from agentkit.toolkit.cli.sandbox import cli_create

    _reset_fake_tools_client()
    monkeypatch.setattr(cli_create, "TOSService", _FakeTOSService)

    request = cli_create._build_create_tool_request(
        tool_type="CodeEnv",
        name="demo-tool",
        tos_bucket=None,
        tos_region="cn-beijing",
        cpu=8,
    )

    assert request.cpu_milli == 8000
    assert request.memory_mb == 16384


def test_create_command_translates_custom_tool_env_and_caches_cli_type(
    monkeypatch,
    tool_store_path,
):
    from agentkit.toolkit.cli.cli import app
    from agentkit.toolkit.cli.sandbox import cli_create

    _reset_fake_tools_client()
    monkeypatch.setattr(cli_create, "AgentkitToolsClient", _FakeToolsClient)
    monkeypatch.setattr(cli_create, "TOSService", _FakeTOSService)

    result = runner.invoke(
        app,
        [
            "sandbox",
            "create",
            "--tool-type",
            "CustomToolEnv",
            "--tool-name",
            "demo-aio",
            "--image-url",
            "registry.example.com/custom-image:latest",
        ],
    )

    assert result.exit_code == 0
    request = _FakeToolsClient.last_request
    assert request.tool_type == "Private"
    assert request.command == "/opt/gem/run.sh"
    assert request.image_url == "registry.example.com/custom-image:latest"
    assert request.port == 8080
    tool_store = json.loads(tool_store_path.read_text(encoding="utf-8"))
    assert tool_store["CustomToolEnv"] == {
        "ToolId": "t-created",
        "Name": "demo-tool",
        "Status": "Ready",
        "ToolType": "CustomToolEnv",
    }


def test_build_create_tool_request_adds_model_envs(monkeypatch):
    from agentkit.toolkit.cli.sandbox import cli_create

    _reset_fake_tools_client()
    monkeypatch.setattr(cli_create, "TOSService", _FakeTOSService)

    request = cli_create._build_create_tool_request(
        tool_type="SkillEnv",
        name="demo-tool",
        tos_bucket="my-bucket",
        tos_region="cn-beijing",
        model_name="deepseek-v4-pro-260425",
        **{"model_" + "api_key": _PLACEHOLDER_MODEL_VALUE},
    )

    assert [(item.key, item.value) for item in request.envs] == [
        ("AGENTKIT_SANDBOX_MODEL_PROVIDER", "model_square"),
        ("OPENCODE_MODEL", "deepseek-v4-pro-260425"),
        ("CODEX_MODEL", "deepseek-v4-pro-260425"),
        ("ANTHROPIC_MODEL", "deepseek-v4-pro-260425"),
        ("OPENCODE_API_KEY", _PLACEHOLDER_MODEL_VALUE),
        ("CODEX_API_KEY", _PLACEHOLDER_MODEL_VALUE),
        ("ANTHROPIC_AUTH_TOKEN", _PLACEHOLDER_MODEL_VALUE),
        ("OPENCODE_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"),
        ("CODEX_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"),
        ("MODEL_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"),
        (
            "ANTHROPIC_BASE_URL",
            "https://ark.cn-beijing.volces.com/api/compatible",
        ),
        ("DISABLE_JUPYTER", "true"),
        ("DISABLE_CODE_SERVER", "true"),
        ("DISABLE_NODEJS_REPL", "true"),
        ("BROWSER_EXTRA_ARGS", _DEFAULT_BROWSER_EXTRA_ARGS),
    ]


def test_build_create_tool_request_adds_code_env_config_envs(monkeypatch):
    from agentkit.toolkit.cli.sandbox import cli_create

    _reset_fake_tools_client()
    monkeypatch.setattr(cli_create, "TOSService", _FakeTOSService)

    request = cli_create._build_create_tool_request(
        tool_type="CodeEnv",
        name="demo-tool",
        tos_bucket="my-bucket",
        tos_region="cn-beijing",
        model_name="deepseek-v4-pro-260425",
    )

    envs = {item.key: item.value for item in request.envs}
    assert envs["BROWSER_EXTRA_ARGS"] == _DEFAULT_BROWSER_EXTRA_ARGS
    assert envs["OPENCODE_DISABLE_AUTOUPDATE"] == "1"
    assert envs["HOME"] == "/home/gem"
    assert envs["CODEX_HOME"] == "/home/gem/.codex"
    config_toml = envs["CODEX_CONFIG_TOML"]
    assert 'model = "deepseek-v4-pro-260425"' in config_toml
    assert 'review_model = "deepseek-v4-pro-260425"' in config_toml
    assert 'model = "deepseek-v4-flash-260425"' not in config_toml
    assert 'model_catalog_json = "/home/gem/.codex/model-catalog.json"' in config_toml
    assert "model_availability_nux" not in config_toml
    assert "gpt-5.5" not in config_toml
    assert 'web_search = "disabled"' in config_toml
    assert "model_context_window" not in config_toml
    assert "model_auto_compact_token_limit" not in config_toml
    assert "model_supports_reasoning_summaries" not in config_toml
    assert "model_reasoning_summary" not in config_toml
    assert (
        'model_catalog_json = "/home/gem/.codex/model-catalog.json"\n'
        'developer_instructions = """\n'
        "When the user asks for simple browser operation tasks, "
        "you can use xdg-open to complete them.\n"
        '"""'
    ) in config_toml
    assert "[tui]" in config_toml
    assert "show_tooltips = false" in config_toml
    assert '[projects."/home/gem"]' in config_toml
    assert 'trust_level = "trusted"' in config_toml
    assert "check_for_update_on_startup = false" in config_toml
    assert config_toml.rstrip().endswith(
        '[mcp_servers.browser-use]\nurl = "http://localhost:8100/mcp"'
    )

    catalog_json = envs["CODEX_MODEL_CATALOG_JSON"]
    assert "\n  " in catalog_json
    catalog = json.loads(catalog_json)
    models = catalog["models"]
    assert models[0]["slug"] == "deepseek-v4-pro-260425"
    assert models[0]["display_name"] == "deepseek-v4-pro-260425"
    assert "deepseek-v4-flash-260425" in [model["slug"] for model in models]
    models_by_slug = {model["slug"]: model for model in models}
    assert "doubao-seed-2-0-pro-260215" in models_by_slug
    assert models_by_slug["doubao-seed-2-0-pro-260215"]["max_context_window"] == 200000
    assert models[0]["truncation_policy"] == {"mode": "tokens", "limit": 10000}


def test_build_create_tool_request_uses_model_provider(monkeypatch):
    from agentkit.toolkit.cli.sandbox import cli_create

    _reset_fake_tools_client()
    monkeypatch.setattr(cli_create, "TOSService", _FakeTOSService)

    request = cli_create._build_create_tool_request(
        tool_type="CodeEnv",
        name="demo-tool",
        tos_bucket="my-bucket",
        tos_region="cn-beijing",
        model_provider="coding_plan",
    )

    envs = {item.key: item.value for item in request.envs}
    assert envs["OPENCODE_MODEL"] == "deepseek-v4-flash"
    assert envs["CODEX_MODEL"] == "deepseek-v4-flash"
    assert envs["ANTHROPIC_MODEL"] == "deepseek-v4-flash"
    assert envs["OPENCODE_BASE_URL"] == (
        "https://ark.cn-beijing.volces.com/api/coding/v3"
    )
    assert envs["CODEX_BASE_URL"] == ("https://ark.cn-beijing.volces.com/api/coding/v3")
    assert envs["MODEL_BASE_URL"] == ("https://ark.cn-beijing.volces.com/api/coding/v3")
    assert envs["ANTHROPIC_BASE_URL"] == (
        "https://ark.cn-beijing.volces.com/api/coding"
    )
    assert (
        'base_url = "https://ark.cn-beijing.volces.com/api/coding/v3"'
        in envs["CODEX_CONFIG_TOML"]
    )

    catalog = json.loads(envs["CODEX_MODEL_CATALOG_JSON"])
    models = {model["slug"]: model for model in catalog["models"]}
    assert "deepseek-v4-flash" in models
    assert "deepseek-v4-flash-260425" not in models
    assert "glm-5.2" not in models


def test_build_create_tool_request_uses_model_base_url_over_provider(monkeypatch):
    from agentkit.toolkit.cli.sandbox import cli_create

    _reset_fake_tools_client()
    monkeypatch.setattr(cli_create, "TOSService", _FakeTOSService)

    request = cli_create._build_create_tool_request(
        tool_type="CodeEnv",
        name="demo-tool",
        tos_bucket="my-bucket",
        tos_region="cn-beijing",
        model_provider="agent_plan",
        model_name="custom-model",
        model_base_url="https://models.example.com/v1",
    )

    envs = {item.key: item.value for item in request.envs}
    assert envs["AGENTKIT_SANDBOX_MODEL_PROVIDER"] == "agent_plan"
    assert envs["OPENCODE_MODEL"] == "custom-model"
    assert envs["CODEX_MODEL"] == "custom-model"
    assert envs["ANTHROPIC_MODEL"] == "custom-model"
    assert envs["OPENCODE_BASE_URL"] == "https://models.example.com/v1"
    assert envs["CODEX_BASE_URL"] == "https://models.example.com/v1"
    assert envs["MODEL_BASE_URL"] == "https://models.example.com/v1"
    assert envs["ANTHROPIC_BASE_URL"] == "https://models.example.com/v1"
    assert envs["OPENCODE_DISABLE_AUTOUPDATE"] == "1"
    assert envs["HOME"] == "/home/gem"
    assert envs["CODEX_HOME"] == "/home/gem/.codex"
    assert 'model_provider = "agent_plan"' in envs["CODEX_CONFIG_TOML"]
    assert 'model = "custom-model"' in envs["CODEX_CONFIG_TOML"]
    assert 'base_url = "https://models.example.com/v1"' in envs["CODEX_CONFIG_TOML"]
    assert (
        'model_catalog_json = "/home/gem/.codex/model-catalog.json"'
        in envs["CODEX_CONFIG_TOML"]
    )
    assert "CODEX_MODEL_CATALOG_JSON" in envs


def test_build_create_tool_request_allows_arbitrary_model_provider_with_base_url(
    monkeypatch,
):
    from agentkit.toolkit.cli.sandbox import cli_create

    _reset_fake_tools_client()
    monkeypatch.setattr(cli_create, "TOSService", _FakeTOSService)

    request = cli_create._build_create_tool_request(
        tool_type="CodeEnv",
        name="demo-tool",
        tos_bucket="my-bucket",
        tos_region="cn-beijing",
        model_provider="model-square-experimental",
        model_name="custom-model",
        model_base_url="https://models.example.com/v1",
    )

    envs = {item.key: item.value for item in request.envs}
    assert envs["AGENTKIT_SANDBOX_MODEL_PROVIDER"] == "model-square-experimental"
    assert envs["CODEX_MODEL"] == "custom-model"
    assert envs["CODEX_BASE_URL"] == "https://models.example.com/v1"
    assert envs["ANTHROPIC_BASE_URL"] == "https://models.example.com/v1"
    assert 'model_provider = "model-square-experimental"' in envs["CODEX_CONFIG_TOML"]
    assert 'model = "custom-model"' in envs["CODEX_CONFIG_TOML"]
    assert 'base_url = "https://models.example.com/v1"' in envs["CODEX_CONFIG_TOML"]
    assert "model_catalog_json" not in envs["CODEX_CONFIG_TOML"]
    assert "CODEX_MODEL_CATALOG_JSON" not in envs


def test_build_create_tool_request_renames_reserved_codex_provider(monkeypatch):
    from agentkit.toolkit.cli.sandbox import cli_create

    _reset_fake_tools_client()
    monkeypatch.setattr(cli_create, "TOSService", _FakeTOSService)

    request = cli_create._build_create_tool_request(
        tool_type="CodeEnv",
        name="demo-tool",
        tos_bucket="my-bucket",
        tos_region="cn-beijing",
        model_provider="openai",
        model_name="custom-model",
        model_base_url="https://models.example.com/v1",
    )

    envs = {item.key: item.value for item in request.envs}
    assert envs["AGENTKIT_SANDBOX_MODEL_PROVIDER"] == "openai"
    assert 'model_provider = "openai-custom"' in envs["CODEX_CONFIG_TOML"]
    assert "[model_providers.openai-custom]" in envs["CODEX_CONFIG_TOML"]
    assert 'name = "openai-custom"' in envs["CODEX_CONFIG_TOML"]
    assert "[model_providers.openai]" not in envs["CODEX_CONFIG_TOML"]
    assert "model_catalog_json" not in envs["CODEX_CONFIG_TOML"]
    assert "CODEX_MODEL_CATALOG_JSON" not in envs


def test_build_create_tool_request_allows_arbitrary_model_provider_without_base_url(
    monkeypatch,
):
    from agentkit.toolkit.cli.sandbox import cli_create

    _reset_fake_tools_client()
    monkeypatch.setattr(cli_create, "TOSService", _FakeTOSService)

    request = cli_create._build_create_tool_request(
        tool_type="CodeEnv",
        name="demo-tool",
        tos_bucket="my-bucket",
        tos_region="cn-beijing",
        model_provider="model-square-experimental",
        model_name="custom-model",
    )

    envs = {item.key: item.value for item in request.envs}
    assert envs["AGENTKIT_SANDBOX_MODEL_PROVIDER"] == "model-square-experimental"
    assert envs["CODEX_MODEL"] == "custom-model"
    assert "CODEX_BASE_URL" not in envs
    assert "ANTHROPIC_BASE_URL" not in envs
    assert 'model_provider = "model-square-experimental"' in envs["CODEX_CONFIG_TOML"]
    assert 'model = "custom-model"' in envs["CODEX_CONFIG_TOML"]
    assert (
        'base_url = "https://ark.cn-beijing.volces.com/api/v3"'
        in envs["CODEX_CONFIG_TOML"]
    )
    assert "model_catalog_json" not in envs["CODEX_CONFIG_TOML"]
    assert "CODEX_MODEL_CATALOG_JSON" not in envs


def test_build_create_tool_request_allows_custom_model_name(monkeypatch):
    from agentkit.toolkit.cli.sandbox import cli_create

    _reset_fake_tools_client()
    monkeypatch.setattr(cli_create, "TOSService", _FakeTOSService)

    request = cli_create._build_create_tool_request(
        tool_type="CodeEnv",
        name="demo-tool",
        tos_bucket="my-bucket",
        tos_region="cn-beijing",
        model_provider="agent_plan",
        model_name="deepseek-v4-flash-260428",
    )

    envs = {item.key: item.value for item in request.envs}
    assert envs["OPENCODE_MODEL"] == "deepseek-v4-flash-260428"
    assert envs["CODEX_MODEL"] == "deepseek-v4-flash-260428"
    assert envs["ANTHROPIC_MODEL"] == "deepseek-v4-flash-260428"
    assert (
        'base_url = "https://ark.cn-beijing.volces.com/api/plan/v3"'
        in envs["CODEX_CONFIG_TOML"]
    )
    catalog = json.loads(envs["CODEX_MODEL_CATALOG_JSON"])
    assert catalog["models"][0]["slug"] == "deepseek-v4-flash-260428"
    assert catalog["models"][0]["supports_reasoning_summaries"] is True
    assert catalog["models"][0]["max_context_window"] == 1000000


def test_build_codex_model_catalog_infers_custom_model_context_window():
    from agentkit.toolkit.cli.sandbox.model_config import (
        build_codex_model_catalog_json,
    )

    expected_context_windows = {
        "deepseek-v4-flash-260428": 1000000,
        "glm-5.2": 1000000,
        "doubao-seed-2-0-code-preview-260215": 200000,
        "glm-4-7-251222": 200000,
        "some-other-model": 200000,
    }

    for model_name, expected_context_window in expected_context_windows.items():
        catalog = json.loads(build_codex_model_catalog_json(model_name, "model_square"))
        assert catalog["models"][0]["slug"] == model_name
        assert catalog["models"][0]["max_context_window"] == expected_context_window


def test_build_create_tool_request_uses_model_api_key_env(monkeypatch):
    from agentkit.toolkit.cli.sandbox import cli_create

    _reset_fake_tools_client()
    monkeypatch.setenv("MODEL_API_KEY", _PLACEHOLDER_MODEL_VALUE)
    monkeypatch.setattr(cli_create, "TOSService", _FakeTOSService)

    request = cli_create._build_create_tool_request(
        tool_type="SkillEnv",
        name="demo-tool",
        tos_bucket="my-bucket",
        tos_region="cn-beijing",
    )

    assert ("OPENCODE_API_KEY", _PLACEHOLDER_MODEL_VALUE) in [
        (item.key, item.value) for item in request.envs
    ]
    assert ("CODEX_API_KEY", _PLACEHOLDER_MODEL_VALUE) in [
        (item.key, item.value) for item in request.envs
    ]
    assert ("ANTHROPIC_AUTH_TOKEN", _PLACEHOLDER_MODEL_VALUE) in [
        (item.key, item.value) for item in request.envs
    ]


def test_build_create_tool_request_model_api_key_option_overrides_env(
    monkeypatch,
):
    from agentkit.toolkit.cli.sandbox import cli_create

    _reset_fake_tools_client()
    monkeypatch.setenv("MODEL_API_KEY", "env-model-value")
    monkeypatch.setattr(cli_create, "TOSService", _FakeTOSService)

    request = cli_create._build_create_tool_request(
        tool_type="SkillEnv",
        name="demo-tool",
        tos_bucket="my-bucket",
        tos_region="cn-beijing",
        **{"model_" + "api_key": _PLACEHOLDER_MODEL_VALUE},
    )

    assert ("OPENCODE_API_KEY", _PLACEHOLDER_MODEL_VALUE) in [
        (item.key, item.value) for item in request.envs
    ]
    assert ("OPENCODE_API_KEY", "env-model-value") not in [
        (item.key, item.value) for item in request.envs
    ]


def test_create_command_accepts_model_base_url_without_model_name(monkeypatch):
    from agentkit.toolkit.cli.cli import app
    from agentkit.toolkit.cli.sandbox import cli_create

    _reset_fake_tools_client()
    monkeypatch.setattr(cli_create, "AgentkitToolsClient", _FakeToolsClient)
    monkeypatch.setattr(cli_create, "TOSService", _FakeTOSService)

    result = runner.invoke(
        app,
        [
            "sandbox",
            "create",
            "--model-provider",
            "custom_provider",
            "--model-base-url",
            "https://models.example.com",
        ],
    )

    assert result.exit_code == 0
    envs = {item.key: item.value for item in _FakeToolsClient.last_request.envs}
    assert envs["AGENTKIT_SANDBOX_MODEL_PROVIDER"] == "custom_provider"
    assert envs["CODEX_BASE_URL"] == "https://models.example.com"
    assert envs["CODEX_MODEL"] == "deepseek-v4-flash-260425"
    assert 'model_provider = "custom_provider"' in envs["CODEX_CONFIG_TOML"]
    assert 'model = "deepseek-v4-flash-260425"' in envs["CODEX_CONFIG_TOML"]
    assert 'base_url = "https://models.example.com"' in envs["CODEX_CONFIG_TOML"]
    assert "model_catalog_json" not in envs["CODEX_CONFIG_TOML"]
    assert "CODEX_MODEL_CATALOG_JSON" not in envs


def test_build_create_tool_request_infers_provider_from_builtin_model_base_url(
    monkeypatch,
):
    from agentkit.toolkit.cli.sandbox import cli_create

    _reset_fake_tools_client()
    monkeypatch.setattr(cli_create, "TOSService", _FakeTOSService)

    request = cli_create._build_create_tool_request(
        tool_type="CodeEnv",
        name="demo-tool",
        tos_bucket="my-bucket",
        tos_region="cn-beijing",
        model_base_url="https://ark.cn-beijing.volces.com/api/plan/v3",
    )

    envs = {item.key: item.value for item in request.envs}
    assert envs["AGENTKIT_SANDBOX_MODEL_PROVIDER"] == "agent_plan"
    assert envs["CODEX_MODEL"] == "deepseek-v4-flash"
    assert envs["CODEX_BASE_URL"] == "https://ark.cn-beijing.volces.com/api/plan/v3"
    assert 'model_provider = "agent_plan"' in envs["CODEX_CONFIG_TOML"]
    assert (
        'base_url = "https://ark.cn-beijing.volces.com/api/plan/v3"'
        in envs["CODEX_CONFIG_TOML"]
    )
    assert "CODEX_MODEL_CATALOG_JSON" in envs


def test_create_command_rejects_non_ark_model_base_url_without_model_provider(
    monkeypatch,
):
    from agentkit.toolkit.cli.cli import app
    from agentkit.toolkit.cli.sandbox import cli_create

    _reset_fake_tools_client()
    monkeypatch.setattr(cli_create, "AgentkitToolsClient", _FakeToolsClient)
    monkeypatch.setattr(cli_create, "TOSService", _FakeTOSService)

    result = runner.invoke(
        app,
        [
            "sandbox",
            "create",
            "--tool-name",
            "demo-tool",
            "--model-name",
            "custom-model",
            "--model-base-url",
            "https://models.example.com/v1",
        ],
    )

    assert result.exit_code != 0
    assert (
        "--model-base-url requires --model-provider for non-Ark base URLs"
        in result.output
    )
    assert _FakeToolsClient.instances == []


def test_create_command_accepts_model_base_url_with_model_name_and_provider(
    monkeypatch,
):
    from agentkit.toolkit.cli.cli import app
    from agentkit.toolkit.cli.sandbox import cli_create

    _reset_fake_tools_client()
    monkeypatch.setattr(cli_create, "AgentkitToolsClient", _FakeToolsClient)
    monkeypatch.setattr(cli_create, "TOSService", _FakeTOSService)

    result = runner.invoke(
        app,
        [
            "sandbox",
            "create",
            "--tool-name",
            "demo-tool",
            "--model-name",
            "custom-model",
            "--model-provider",
            "custom_provider",
            "--model-base-url",
            "https://models.example.com/v1",
        ],
    )

    assert result.exit_code == 0
    envs = {item.key: item.value for item in _FakeToolsClient.last_request.envs}
    assert envs["CODEX_BASE_URL"] == "https://models.example.com/v1"
    assert 'model_provider = "custom_provider"' in envs["CODEX_CONFIG_TOML"]
    assert 'model = "custom-model"' in envs["CODEX_CONFIG_TOML"]
    assert 'base_url = "https://models.example.com/v1"' in envs["CODEX_CONFIG_TOML"]
    assert "model_catalog_json" not in envs["CODEX_CONFIG_TOML"]
    assert "CODEX_MODEL_CATALOG_JSON" not in envs


def test_build_create_tool_request_adds_default_model_base_url(monkeypatch):
    from agentkit.toolkit.cli.sandbox import cli_create

    _reset_fake_tools_client()
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.setattr(cli_create, "TOSService", _FakeTOSService)

    request = cli_create._build_create_tool_request(
        tool_type="SkillEnv",
        name="demo-tool",
        tos_bucket="my-bucket",
        tos_region="cn-beijing",
    )

    assert [(item.key, item.value) for item in request.envs] == [
        ("AGENTKIT_SANDBOX_MODEL_PROVIDER", "model_square"),
        ("OPENCODE_MODEL", "deepseek-v4-flash-260425"),
        ("CODEX_MODEL", "deepseek-v4-flash-260425"),
        ("ANTHROPIC_MODEL", "deepseek-v4-flash-260425"),
        ("OPENCODE_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"),
        ("CODEX_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"),
        ("MODEL_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"),
        (
            "ANTHROPIC_BASE_URL",
            "https://ark.cn-beijing.volces.com/api/compatible",
        ),
        ("DISABLE_JUPYTER", "true"),
        ("DISABLE_CODE_SERVER", "true"),
        ("DISABLE_NODEJS_REPL", "true"),
        ("BROWSER_EXTRA_ARGS", _DEFAULT_BROWSER_EXTRA_ARGS),
    ]


def test_tos_service_build_directory_keys():
    from agentkit.toolkit.volcengine.services.tos_service import TOSService

    assert TOSService.build_directory_keys("/sandbox-session/default/default") == [
        "sandbox-session/",
        "sandbox-session/default/",
        "sandbox-session/default/default/",
    ]


def test_tos_service_build_mount_endpoint_uses_default_private_endpoint():
    from agentkit.toolkit.volcengine.services.tos_service import TOSService

    assert (
        TOSService.build_mount_endpoint("cn-beijing")
        == "http://tos-cn-beijing.ivolces.com"
    )


def test_tos_service_build_mount_config_prepares_bucket_path():
    from types import SimpleNamespace

    from agentkit.toolkit.volcengine.services.tos_service import (
        TOSService,
        TOSServiceConfig,
    )

    service = object.__new__(TOSService)
    service.config = TOSServiceConfig(bucket="my-bucket", region="cn-beijing")
    service.credentials = SimpleNamespace(
        **{
            "access_key": _PLACEHOLDER_A,
            "secret_" + "key": _PLACEHOLDER_B,
        }
    )
    service.actual_region = "cn-beijing"
    created_buckets = []
    created_directories = []
    existing_keys = {"sandbox-session/"}
    service.bucket_exists = lambda: False
    service.create_bucket = lambda: created_buckets.append(service.config.bucket)
    service.object_exists = lambda key: key in existing_keys
    service.create_directory_marker = lambda key: created_directories.append(key)

    mount_config = service.build_mount_config(
        bucket_path="/sandbox-session/default/default",
        local_mount_path="/home/gem",
    )

    assert created_buckets == ["my-bucket"]
    assert created_directories == [
        "sandbox-session/default/",
        "sandbox-session/default/default/",
    ]
    assert mount_config.credentials.access_key_id == _PLACEHOLDER_A
    assert mount_config.credentials.secret_access_key == _PLACEHOLDER_B
    assert mount_config.mount_points[0].bucket_name == "my-bucket"
    assert mount_config.mount_points[0].endpoint == "http://tos-cn-beijing.ivolces.com"
