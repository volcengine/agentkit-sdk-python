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

from concurrent.futures import ThreadPoolExecutor
import json
import os
import tarfile

import pytest
from typer.testing import CliRunner

runner = CliRunner()


class _FakeCreateSessionResponse:
    user_session_id = "user-session-from-api"
    session_id = "session-from-api"
    endpoint = "https://sandbox.example.com"


class _FakeGetSessionResponse:
    user_session_id = None
    session_id = None
    endpoint = None


class _FakeToolMountPoint:
    def __init__(
        self,
        bucket_name="agentkit-platform-123",
        bucket_path="/sandbox-session/default/default",
        local_mount_path="/home/gem",
    ):
        self.bucket_name = bucket_name
        self.bucket_path = bucket_path
        self.local_mount_path = local_mount_path


class _FakeToolTosMountConfig:
    def __init__(self, mount_points=None):
        self.mount_points = [] if mount_points is None else mount_points


class _FakeGetToolResponse:
    def __init__(
        self,
        tool_id=None,
        tool_type=None,
        name="fake-tool",
        status="Ready",
        tos_mount_config=None,
    ):
        self.tool_id = tool_id
        self.tool_type = tool_type
        self.name = name
        self.status = status
        self.tos_mount_config = tos_mount_config


class _FakeSessionInfo:
    def __init__(
        self,
        user_session_id="user-1",
        session_id="instance-1",
        endpoint="https://sandbox.example.com",
        status="Ready",
    ):
        self.user_session_id = user_session_id
        self.session_id = session_id
        self.endpoint = endpoint
        self.status = status


class _FakeListSessionsResponse:
    def __init__(self, session_infos=None, next_token=None):
        self.session_infos = [] if session_infos is None else session_infos
        self.next_token = next_token


class _FakeListTool:
    def __init__(
        self,
        tool_id="tool-from-list",
        tool_type="CodeEnv",
        name="listed-tool",
        status="Ready",
    ):
        self.tool_id = tool_id
        self.tool_type = tool_type
        self.name = name
        self.status = status


class _FakeListToolsResponse:
    def __init__(self, tools=None):
        self.tools = [] if tools is None else tools


class _FakeToolsClient:
    last_request = None
    last_get_request = None
    last_get_tool_request = None
    last_list_request = None
    last_list_sessions_request = None
    list_sessions_requests = []
    response = _FakeCreateSessionResponse()
    get_response = _FakeGetSessionResponse()
    get_tool_response = _FakeGetToolResponse()
    list_response = _FakeListToolsResponse()
    list_sessions_responses = [_FakeListSessionsResponse()]
    create_error = None
    get_error = None
    get_tool_error = None
    create_call_count = 0
    get_call_count = 0
    get_tool_call_count = 0
    list_call_count = 0
    list_sessions_call_count = 0

    def create_session(self, request):
        _FakeToolsClient.last_request = request
        _FakeToolsClient.create_call_count += 1
        if _FakeToolsClient.create_error:
            raise _FakeToolsClient.create_error
        return _FakeToolsClient.response

    def get_session(self, request):
        _FakeToolsClient.last_get_request = request
        _FakeToolsClient.get_call_count += 1
        if _FakeToolsClient.get_error:
            raise _FakeToolsClient.get_error
        return _FakeToolsClient.get_response

    def get_tool(self, request):
        _FakeToolsClient.last_get_tool_request = request
        _FakeToolsClient.get_tool_call_count += 1
        if _FakeToolsClient.get_tool_error:
            raise _FakeToolsClient.get_tool_error
        if isinstance(_FakeToolsClient.get_tool_response, dict):
            return _FakeToolsClient.get_tool_response
        if _FakeToolsClient.get_tool_response.tool_id is None:
            _FakeToolsClient.get_tool_response.tool_id = request.tool_id
        return _FakeToolsClient.get_tool_response

    def list_tools(self, request):
        _FakeToolsClient.last_list_request = request
        _FakeToolsClient.list_call_count += 1
        return _FakeToolsClient.list_response

    def list_sessions(self, request):
        _FakeToolsClient.last_list_sessions_request = request
        _FakeToolsClient.list_sessions_requests.append(request)
        index = _FakeToolsClient.list_sessions_call_count
        _FakeToolsClient.list_sessions_call_count += 1
        responses = _FakeToolsClient.list_sessions_responses
        if index < len(responses):
            return responses[index]
        return responses[-1]


@pytest.fixture(autouse=True)
def _reset_fake_client():
    _FakeToolsClient.last_request = None
    _FakeToolsClient.last_get_request = None
    _FakeToolsClient.last_get_tool_request = None
    _FakeToolsClient.last_list_request = None
    _FakeToolsClient.last_list_sessions_request = None
    _FakeToolsClient.list_sessions_requests = []
    _FakeToolsClient.response = _FakeCreateSessionResponse()
    _FakeToolsClient.get_response = _FakeGetSessionResponse()
    _FakeToolsClient.get_tool_response = _FakeGetToolResponse()
    _FakeToolsClient.list_response = _FakeListToolsResponse()
    _FakeToolsClient.list_sessions_responses = [_FakeListSessionsResponse()]
    _FakeToolsClient.create_error = None
    _FakeToolsClient.get_error = None
    _FakeToolsClient.get_tool_error = None
    _FakeToolsClient.create_call_count = 0
    _FakeToolsClient.get_call_count = 0
    _FakeToolsClient.get_tool_call_count = 0
    _FakeToolsClient.list_call_count = 0
    _FakeToolsClient.list_sessions_call_count = 0


def _patch_store_path(monkeypatch, tmp_path):
    import agentkit.toolkit.cli.sandbox.sandbox_client as sandbox_client

    store_path = tmp_path / "sessions.json"
    monkeypatch.setattr(sandbox_client, "_get_session_store_path", lambda: store_path)
    return store_path


def _patch_tool_store_path(monkeypatch, tmp_path):
    import agentkit.toolkit.cli.sandbox.tool_resolve as tool_resolve

    store_path = tmp_path / ".agentkit" / "sandbox" / "tools.json"
    monkeypatch.setattr(tool_resolve, "_get_tool_store_path", lambda: store_path)
    return store_path


def _write_session_store(store_path, records):
    store_path.parent.mkdir(parents=True, exist_ok=True)
    store_path.write_text(
        json.dumps(records, indent=2),
        encoding="utf-8",
    )


def _patch_exec_session(monkeypatch, cli_exec, session, capture=None):
    def fake_ensure_sandbox_session(session_id=None, tool_id=None, **kwargs):
        if capture is not None:
            capture["session_id"] = session_id
            capture["tool_id"] = tool_id
            capture.update(kwargs)
        return session

    monkeypatch.setattr(
        cli_exec,
        "ensure_sandbox_session",
        fake_ensure_sandbox_session,
    )


def _patch_shell_session(monkeypatch, cli_shell, session, capture=None):
    def fake_ensure_sandbox_session(session_id=None, tool_id=None, **_kwargs):
        if capture is not None:
            capture["session_id"] = session_id
            capture["tool_id"] = tool_id
            capture.update(_kwargs)
        return session

    monkeypatch.setattr(
        cli_shell,
        "ensure_sandbox_session",
        fake_ensure_sandbox_session,
    )


class _FakeA2AResponse:
    def __init__(self, payload, status_code=200, text=None):
        self._payload = payload
        self.status_code = status_code
        self.text = text if text is not None else json.dumps(payload)

    def json(self):
        return self._payload


def _patch_invoke_session(monkeypatch, cli_invoke, session, capture=None):
    def fake_ensure_sandbox_session(session_id=None, tool_id=None, **kwargs):
        if capture is not None:
            capture["session_id"] = session_id
            capture["tool_id"] = tool_id
            capture.update(kwargs)
        result = dict(session)
        result.setdefault("tool_id", tool_id)
        return result

    monkeypatch.setattr(
        cli_invoke,
        "ensure_sandbox_session",
        fake_ensure_sandbox_session,
    )


def _clear_model_agent_envs(monkeypatch, cli_invoke):
    for key in cli_invoke.MODEL_AGENT_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_ensure_sandbox_session_uses_env_defaults(monkeypatch, tmp_path) -> None:
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    monkeypatch.setenv("AGENTKIT_SANDBOX_TOOL_ID", "tool-env")
    monkeypatch.setenv("AGENTKIT_SANDBOX_TTL", "60")
    monkeypatch.setattr(
        session_create,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    store_path = _patch_store_path(monkeypatch, tmp_path)

    result = session_create.ensure_sandbox_session()

    assert result == {
        "session_id": "user-session-from-api",
        "tool_id": "tool-env",
        "instance_id": "session-from-api",
        "endpoint": "https://sandbox.example.com",
    }
    assert json.loads(store_path.read_text(encoding="utf-8")) == {
        "user-session-from-api": result
    }

    request = _FakeToolsClient.last_request
    assert request.tool_id == "tool-env"
    assert request.ttl == 60
    assert request.ttl_unit == "second"
    assert request.user_session_id


def test_ensure_sandbox_session_uses_cached_tool_by_type(
    monkeypatch,
    tmp_path,
) -> None:
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    monkeypatch.delenv("AGENTKIT_SANDBOX_TOOL_ID", raising=False)
    monkeypatch.setattr(
        session_create,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    _patch_store_path(monkeypatch, tmp_path)
    tool_store_path = _patch_tool_store_path(monkeypatch, tmp_path)
    tool_store_path.parent.mkdir(parents=True, exist_ok=True)
    tool_store_path.write_text(
        json.dumps(
            {
                "SkillEnv": {
                    "ToolId": "tool-from-cache",
                    "ToolType": "SkillEnv",
                    "Name": "cached-tool",
                    "Status": "Ready",
                }
            }
        ),
        encoding="utf-8",
    )

    session_create.ensure_sandbox_session(tool_type="SkillEnv")

    assert _FakeToolsClient.list_call_count == 0
    assert _FakeToolsClient.last_request.tool_id == "tool-from-cache"
    assert _FakeToolsClient.get_tool_call_count == 2
    assert _FakeToolsClient.last_get_tool_request.tool_id == "tool-from-cache"


def test_ensure_sandbox_session_can_skip_tool_lookup_for_resolved_tool_id(
    monkeypatch,
    tmp_path,
) -> None:
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    monkeypatch.setattr(
        session_create,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    _patch_store_path(monkeypatch, tmp_path)

    session_create.ensure_sandbox_session(
        tool_id="SkillEnv",
        tool_type="SkillEnv",
        resolve_tool=False,
        include_tos_mount_points=False,
    )

    assert _FakeToolsClient.get_tool_call_count == 0
    assert _FakeToolsClient.last_request.tool_id == "SkillEnv"


def test_ensure_sandbox_session_skip_tool_lookup_syncs_named_remote_session(
    monkeypatch,
    tmp_path,
) -> None:
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    monkeypatch.setattr(
        session_create,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    _patch_store_path(monkeypatch, tmp_path)
    _FakeToolsClient.list_sessions_responses = [
        _FakeListSessionsResponse(
            [
                _FakeSessionInfo(
                    user_session_id="user-1",
                    session_id="instance-1",
                    endpoint="https://sandbox.example.com/a2a",
                )
            ]
        )
    ]

    result = session_create.ensure_sandbox_session(
        session_id="user-1",
        tool_id="SkillEnv",
        tool_type="SkillEnv",
        resolve_tool=False,
        include_tos_mount_points=False,
    )

    assert _FakeToolsClient.get_tool_call_count == 0
    assert _FakeToolsClient.create_call_count == 0
    assert _FakeToolsClient.list_sessions_call_count == 1
    assert result == {
        "session_id": "user-1",
        "tool_id": "SkillEnv",
        "instance_id": "instance-1",
        "endpoint": "https://sandbox.example.com/a2a",
    }


def test_ensure_sandbox_session_rejects_unavailable_cached_tool(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    monkeypatch.delenv("AGENTKIT_SANDBOX_TOOL_ID", raising=False)
    monkeypatch.setattr(
        session_create,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    _patch_store_path(monkeypatch, tmp_path)
    tool_store_path = _patch_tool_store_path(monkeypatch, tmp_path)
    tool_store_path.parent.mkdir(parents=True, exist_ok=True)
    tool_store_path.write_text(
        json.dumps(
            {
                "CodeEnv": {
                    "ToolId": "tool-from-cache",
                    "ToolType": "CodeEnv",
                    "Name": "cached-tool",
                    "Status": "Ready",
                }
            }
        ),
        encoding="utf-8",
    )
    _FakeToolsClient.get_tool_response = _FakeGetToolResponse(
        tool_id="tool-from-cache",
        tool_type="CodeEnv",
        status="Deleting",
    )

    result = runner.invoke(
        app,
        ["sandbox", "shell", "--command", "echo 123"],
    )

    assert result.exit_code == 1
    assert "Sandbox tool is not available: tool-from-cache" in result.output
    assert "Status: Deleting" in result.output
    assert _FakeToolsClient.create_call_count == 0
    assert _FakeToolsClient.list_call_count == 0


def test_cli_exec_reports_missing_explicit_tool_id(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    monkeypatch.setattr(
        session_create,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    _patch_store_path(monkeypatch, tmp_path)
    _FakeToolsClient.get_tool_error = Exception(
        "Failed to GetTool: The specified resource does not exist."
    )

    result = runner.invoke(
        app,
        ["sandbox", "exec", "--tool-id", "tool-missing"],
    )

    assert result.exit_code == 1
    assert "Sandbox tool not found: tool-missing" in result.output
    assert "The specified resource does not exist." in result.output
    assert _FakeToolsClient.create_call_count == 0


def test_cli_exec_allows_private_tool_id_during_websearch_check(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_exec as cli_exec
    import agentkit.toolkit.cli.sandbox.tool_resolve as tool_resolve

    stored_session = {
        "session_id": "user-1",
        "tool_id": "tool-private",
        "instance_id": "session-1",
        "endpoint": "https://sandbox.example.com/?token=abc",
    }
    _patch_store_path(monkeypatch, tmp_path)
    _patch_tool_store_path(monkeypatch, tmp_path)
    _patch_exec_session(monkeypatch, cli_exec, stored_session)
    monkeypatch.setattr(
        tool_resolve,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    _FakeToolsClient.get_tool_response = _FakeGetToolResponse(
        tool_id="tool-private",
        tool_type="Private",
        status="Ready",
    )
    captured = {}

    def fake_connect(ws_url, initial_command, on_shell_id=None):
        captured["ws_url"] = ws_url
        captured["initial_command"] = initial_command

    monkeypatch.setattr(cli_exec, "_connect_terminal", fake_connect)

    result = runner.invoke(
        app,
        [
            "sandbox",
            "exec",
            "--tool-id",
            "tool-private",
            "--model-api-key",
            "model-value",
        ],
    )

    assert result.exit_code == 0
    assert captured["ws_url"] == "ws://sandbox.example.com/v1/shell/ws?token=abc"
    assert captured["initial_command"] is None
    assert _FakeToolsClient.get_tool_call_count == 1


def test_cli_shell_reports_raw_get_tool_not_found_response(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    monkeypatch.setattr(
        session_create,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    _patch_store_path(monkeypatch, tmp_path)
    _FakeToolsClient.get_tool_response = {
        "ResponseMetadata": {
            "Error": {
                "Code": "InvalidResource.NotFound",
                "Message": "The specified resource does not exist.",
            }
        }
    }

    result = runner.invoke(
        app,
        ["sandbox", "shell", "--tool-id", "tool-missing", "--command", "pwd"],
    )

    assert result.exit_code == 1
    assert "Sandbox tool not found: tool-missing" in result.output
    assert "The specified resource does not exist." in result.output
    assert _FakeToolsClient.create_call_count == 0


def test_ensure_sandbox_session_ignores_non_ready_cached_tool(
    monkeypatch,
    tmp_path,
) -> None:
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    monkeypatch.delenv("AGENTKIT_SANDBOX_TOOL_ID", raising=False)
    monkeypatch.setattr(
        session_create,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    _patch_store_path(monkeypatch, tmp_path)
    tool_store_path = _patch_tool_store_path(monkeypatch, tmp_path)
    tool_store_path.parent.mkdir(parents=True, exist_ok=True)
    tool_store_path.write_text(
        json.dumps(
            {
                "SkillEnv": {
                    "ToolId": "tool-from-cache",
                    "ToolType": "SkillEnv",
                    "Name": "cached-tool",
                    "Status": "Error",
                }
            }
        ),
        encoding="utf-8",
    )
    _FakeToolsClient.list_response = _FakeListToolsResponse(
        [_FakeListTool(tool_id="tool-from-list", tool_type="SkillEnv")]
    )

    session_create.ensure_sandbox_session(tool_type="SkillEnv")

    assert _FakeToolsClient.list_call_count == 1
    assert _FakeToolsClient.last_request.tool_id == "tool-from-list"
    assert json.loads(tool_store_path.read_text(encoding="utf-8")) == {
        "SkillEnv": {
            "ToolId": "tool-from-list",
            "Name": "listed-tool",
            "Status": "Ready",
            "ToolType": "SkillEnv",
        }
    }


def test_ensure_sandbox_session_lists_tool_by_type_and_caches_result(
    monkeypatch,
    tmp_path,
) -> None:
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    monkeypatch.delenv("AGENTKIT_SANDBOX_TOOL_ID", raising=False)
    monkeypatch.setattr(
        session_create,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    _patch_store_path(monkeypatch, tmp_path)
    tool_store_path = _patch_tool_store_path(monkeypatch, tmp_path)
    _FakeToolsClient.list_response = _FakeListToolsResponse(
        [_FakeListTool(tool_id="tool-from-list", tool_type="SkillEnv")]
    )

    session_create.ensure_sandbox_session(tool_type="SkillEnv")

    assert _FakeToolsClient.last_request.tool_id == "tool-from-list"
    assert _FakeToolsClient.list_call_count == 1
    list_request = _FakeToolsClient.last_list_request
    assert [(item.name, item.values) for item in list_request.filters] == [
        ("ToolType", ["SkillEnv"])
    ]
    assert json.loads(tool_store_path.read_text(encoding="utf-8")) == {
        "SkillEnv": {
            "ToolId": "tool-from-list",
            "Name": "listed-tool",
            "Status": "Ready",
            "ToolType": "SkillEnv",
        }
    }


def test_ensure_sandbox_session_skips_non_ready_listed_tools(
    monkeypatch,
    tmp_path,
) -> None:
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    monkeypatch.delenv("AGENTKIT_SANDBOX_TOOL_ID", raising=False)
    monkeypatch.setattr(
        session_create,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    _patch_store_path(monkeypatch, tmp_path)
    tool_store_path = _patch_tool_store_path(monkeypatch, tmp_path)
    _FakeToolsClient.list_response = _FakeListToolsResponse(
        [
            _FakeListTool(
                tool_id="tool-creating",
                tool_type="SkillEnv",
                name="creating-tool",
                status="Creating",
            ),
            _FakeListTool(
                tool_id="tool-error",
                tool_type="SkillEnv",
                name="error-tool",
                status="Error",
            ),
            _FakeListTool(
                tool_id="tool-ready",
                tool_type="SkillEnv",
                name="ready-tool",
                status="Ready",
            ),
        ]
    )

    session_create.ensure_sandbox_session(tool_type="SkillEnv")

    assert _FakeToolsClient.list_call_count == 1
    assert _FakeToolsClient.last_request.tool_id == "tool-ready"
    assert json.loads(tool_store_path.read_text(encoding="utf-8")) == {
        "SkillEnv": {
            "ToolId": "tool-ready",
            "Name": "ready-tool",
            "Status": "Ready",
            "ToolType": "SkillEnv",
        }
    }


def test_ensure_sandbox_session_creates_tool_when_listed_tools_not_ready(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.sandbox import cli_create
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    monkeypatch.delenv("AGENTKIT_SANDBOX_TOOL_ID", raising=False)
    monkeypatch.setattr(
        session_create,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    _patch_store_path(monkeypatch, tmp_path)
    tool_store_path = _patch_tool_store_path(monkeypatch, tmp_path)
    _FakeToolsClient.list_response = _FakeListToolsResponse(
        [
            _FakeListTool(
                tool_id="tool-creating",
                tool_type="CodeEnv",
                name="creating-tool",
                status="Creating",
            )
        ]
    )

    def fake_create_tool(tool_type="CodeEnv", **_kwargs):
        return {
            "tool_id": "tool-from-create",
            "tool_type": tool_type,
            "name": "created-tool",
            "status": "Ready",
        }

    monkeypatch.setattr(cli_create, "create_tool", fake_create_tool)

    session_create.ensure_sandbox_session(tool_type="CodeEnv")

    assert _FakeToolsClient.list_call_count == 1
    assert _FakeToolsClient.last_request.tool_id == "tool-from-create"
    assert json.loads(tool_store_path.read_text(encoding="utf-8")) == {
        "CodeEnv": {
            "ToolId": "tool-from-create",
            "Name": "created-tool",
            "Status": "Ready",
            "ToolType": "CodeEnv",
        }
    }


def test_ensure_sandbox_session_creates_tool_when_no_tool_exists(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.sandbox import cli_create
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    monkeypatch.delenv("AGENTKIT_SANDBOX_TOOL_ID", raising=False)
    monkeypatch.setattr(
        session_create,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    _patch_store_path(monkeypatch, tmp_path)
    tool_store_path = _patch_tool_store_path(monkeypatch, tmp_path)

    def fake_create_tool(tool_type="CodeEnv", **_kwargs):
        return {
            "tool_id": "tool-from-create",
            "tool_type": tool_type,
            "name": "created-tool",
            "status": "Ready",
        }

    monkeypatch.setattr(cli_create, "create_tool", fake_create_tool)

    session_create.ensure_sandbox_session(tool_type="CodeEnv")

    assert _FakeToolsClient.list_call_count == 1
    assert _FakeToolsClient.last_request.tool_id == "tool-from-create"
    assert json.loads(tool_store_path.read_text(encoding="utf-8")) == {
        "CodeEnv": {
            "ToolId": "tool-from-create",
            "Name": "created-tool",
            "Status": "Ready",
            "ToolType": "CodeEnv",
        }
    }


def test_ensure_sandbox_session_options_override_env(monkeypatch, tmp_path) -> None:
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    monkeypatch.setenv("AGENTKIT_SANDBOX_TOOL_ID", "tool-env")
    monkeypatch.setenv("AGENTKIT_SANDBOX_TTL", "60")
    monkeypatch.setattr(
        session_create,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    _patch_store_path(monkeypatch, tmp_path)

    session_create.ensure_sandbox_session(
        session_id="user-cli",
        tool_id="tool-cli",
        ttl=120,
    )

    request = _FakeToolsClient.last_request
    assert request.tool_id == "tool-cli"
    assert request.ttl == 120
    assert request.user_session_id == "user-cli"


def test_ensure_sandbox_session_passes_envs_to_create_session(
    monkeypatch,
    tmp_path,
) -> None:
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    monkeypatch.setattr(
        session_create,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    _patch_store_path(monkeypatch, tmp_path)
    envs = session_create.build_model_envs(
        model_name="deepseek-v4-pro-260425",
        **{"model_" + "api_key": "model-value"},
    )

    session_create.ensure_sandbox_session(
        session_id="user-cli",
        tool_id="tool-cli",
        envs=envs,
    )

    request_envs = _FakeToolsClient.last_request.envs
    assert [(item.key, item.value) for item in request_envs] == [
        ("OPENCODE_MODEL", "deepseek-v4-pro-260425"),
        ("CODEX_MODEL", "deepseek-v4-pro-260425"),
        ("ANTHROPIC_MODEL", "deepseek-v4-pro-260425"),
        ("OPENCODE_API_KEY", "model-value"),
        ("CODEX_API_KEY", "model-value"),
        ("ANTHROPIC_AUTH_TOKEN", "model-value"),
    ]


def test_build_model_envs_uses_model_api_key_env(monkeypatch) -> None:
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    monkeypatch.setenv("MODEL_API_KEY", "env-model-value")

    envs = session_create.build_model_envs(model_name="deepseek-v4-pro-260425")

    assert [(item.key, item.value) for item in envs] == [
        ("OPENCODE_MODEL", "deepseek-v4-pro-260425"),
        ("CODEX_MODEL", "deepseek-v4-pro-260425"),
        ("ANTHROPIC_MODEL", "deepseek-v4-pro-260425"),
        ("OPENCODE_API_KEY", "env-model-value"),
        ("CODEX_API_KEY", "env-model-value"),
        ("ANTHROPIC_AUTH_TOKEN", "env-model-value"),
    ]


def test_build_model_envs_option_overrides_model_api_key_env(monkeypatch) -> None:
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    monkeypatch.setenv("MODEL_API_KEY", "env-model-value")

    envs = session_create.build_model_envs(**{"model_" + "api_key": "cli-model-value"})

    assert [(item.key, item.value) for item in envs] == [
        ("OPENCODE_API_KEY", "cli-model-value"),
        ("CODEX_API_KEY", "cli-model-value"),
        ("ANTHROPIC_AUTH_TOKEN", "cli-model-value"),
    ]


def test_build_model_envs_uses_model_base_url_and_emits_codex_config(
    monkeypatch,
) -> None:
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    monkeypatch.delenv("MODEL_API_KEY", raising=False)

    envs = session_create.build_model_envs(
        model_name="custom-model",
        model_provider="agent_plan",
        model_base_url="https://models.example.com/v1",
        include_codex_config=True,
    )

    assert [(item.key, item.value) for item in envs] == [
        ("AGENTKIT_SANDBOX_MODEL_PROVIDER", "agent_plan"),
        ("OPENCODE_MODEL", "custom-model"),
        ("CODEX_MODEL", "custom-model"),
        ("ANTHROPIC_MODEL", "custom-model"),
        ("OPENCODE_BASE_URL", "https://models.example.com/v1"),
        ("CODEX_BASE_URL", "https://models.example.com/v1"),
        ("MODEL_BASE_URL", "https://models.example.com/v1"),
        ("ANTHROPIC_BASE_URL", "https://models.example.com/v1"),
        (
            "CODEX_CONFIG_TOML",
            envs[8].value,
        ),
        (
            "CODEX_MODEL_CATALOG_JSON",
            envs[9].value,
        ),
    ]
    assert 'model_provider = "agent_plan"' in envs[8].value
    assert 'model = "custom-model"' in envs[8].value
    assert 'base_url = "https://models.example.com/v1"' in envs[8].value
    assert 'model_catalog_json = "/home/gem/.codex/model-catalog.json"' in envs[8].value


def test_build_model_envs_allows_arbitrary_model_provider_with_base_url(
    monkeypatch,
) -> None:
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    monkeypatch.delenv("MODEL_API_KEY", raising=False)

    envs = session_create.build_model_envs(
        model_name="custom-model",
        model_provider="agent_plan_experimental",
        model_base_url="https://models.example.com/v1",
        include_codex_config=True,
    )

    assert [(item.key, item.value) for item in envs] == [
        ("AGENTKIT_SANDBOX_MODEL_PROVIDER", "agent_plan_experimental"),
        ("OPENCODE_MODEL", "custom-model"),
        ("CODEX_MODEL", "custom-model"),
        ("ANTHROPIC_MODEL", "custom-model"),
        ("OPENCODE_BASE_URL", "https://models.example.com/v1"),
        ("CODEX_BASE_URL", "https://models.example.com/v1"),
        ("MODEL_BASE_URL", "https://models.example.com/v1"),
        ("ANTHROPIC_BASE_URL", "https://models.example.com/v1"),
        (
            "CODEX_CONFIG_TOML",
            envs[8].value,
        ),
    ]
    assert 'model_provider = "agent_plan_experimental"' in envs[8].value
    assert 'model = "custom-model"' in envs[8].value
    assert 'base_url = "https://models.example.com/v1"' in envs[8].value
    assert "model_catalog_json" not in envs[8].value


def test_build_model_envs_renames_reserved_codex_provider(monkeypatch) -> None:
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    monkeypatch.delenv("MODEL_API_KEY", raising=False)

    envs = session_create.build_model_envs(
        model_name="custom-model",
        model_provider="openai",
        model_base_url="https://models.example.com/v1",
        include_codex_config=True,
    )
    env_map = {item.key: item.value for item in envs}

    assert env_map["AGENTKIT_SANDBOX_MODEL_PROVIDER"] == "openai"
    assert 'model_provider = "openai-custom"' in env_map["CODEX_CONFIG_TOML"]
    assert "[model_providers.openai-custom]" in env_map["CODEX_CONFIG_TOML"]
    assert 'name = "openai-custom"' in env_map["CODEX_CONFIG_TOML"]
    assert "[model_providers.openai]" not in env_map["CODEX_CONFIG_TOML"]
    assert "model_catalog_json" not in env_map["CODEX_CONFIG_TOML"]
    assert "CODEX_MODEL_CATALOG_JSON" not in env_map


def test_build_model_envs_allows_arbitrary_model_provider_without_base_url(
    monkeypatch,
) -> None:
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    monkeypatch.delenv("MODEL_API_KEY", raising=False)

    envs = session_create.build_model_envs(
        model_name="custom-model",
        model_provider="agent_plan_experimental",
        include_codex_config=True,
    )

    assert [(item.key, item.value) for item in envs] == [
        ("AGENTKIT_SANDBOX_MODEL_PROVIDER", "agent_plan_experimental"),
        ("OPENCODE_MODEL", "custom-model"),
        ("CODEX_MODEL", "custom-model"),
        ("ANTHROPIC_MODEL", "custom-model"),
        (
            "CODEX_CONFIG_TOML",
            envs[4].value,
        ),
    ]
    assert 'model_provider = "agent_plan_experimental"' in envs[4].value
    assert 'model = "custom-model"' in envs[4].value
    assert 'base_url = "https://ark.cn-beijing.volces.com/api/v3"' in envs[4].value
    assert "model_catalog_json" not in envs[4].value


def test_build_model_envs_allows_model_base_url_without_model_name(monkeypatch) -> None:
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    monkeypatch.delenv("MODEL_API_KEY", raising=False)

    envs = session_create.build_model_envs(
        model_provider="custom_provider",
        model_base_url="https://models.example.com/v1",
        include_codex_config=True,
    )

    assert [(item.key, item.value) for item in envs] == [
        ("AGENTKIT_SANDBOX_MODEL_PROVIDER", "custom_provider"),
        ("OPENCODE_MODEL", "deepseek-v4-flash-260425"),
        ("CODEX_MODEL", "deepseek-v4-flash-260425"),
        ("ANTHROPIC_MODEL", "deepseek-v4-flash-260425"),
        ("OPENCODE_BASE_URL", "https://models.example.com/v1"),
        ("CODEX_BASE_URL", "https://models.example.com/v1"),
        ("MODEL_BASE_URL", "https://models.example.com/v1"),
        ("ANTHROPIC_BASE_URL", "https://models.example.com/v1"),
        (
            "CODEX_CONFIG_TOML",
            envs[8].value,
        ),
    ]
    assert 'model_provider = "custom_provider"' in envs[8].value
    assert 'model = "deepseek-v4-flash-260425"' in envs[8].value
    assert 'base_url = "https://models.example.com/v1"' in envs[8].value
    assert "model_catalog_json" not in envs[8].value


def test_build_model_envs_infers_provider_from_builtin_model_base_url(
    monkeypatch,
) -> None:
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    monkeypatch.delenv("MODEL_API_KEY", raising=False)

    envs = session_create.build_model_envs(
        model_base_url="https://ark.cn-beijing.volces.com/api/coding/v3",
        include_codex_config=True,
    )

    assert [(item.key, item.value) for item in envs] == [
        ("AGENTKIT_SANDBOX_MODEL_PROVIDER", "coding_plan"),
        ("OPENCODE_MODEL", "deepseek-v4-flash"),
        ("CODEX_MODEL", "deepseek-v4-flash"),
        ("ANTHROPIC_MODEL", "deepseek-v4-flash"),
        ("OPENCODE_BASE_URL", "https://ark.cn-beijing.volces.com/api/coding/v3"),
        ("CODEX_BASE_URL", "https://ark.cn-beijing.volces.com/api/coding/v3"),
        ("MODEL_BASE_URL", "https://ark.cn-beijing.volces.com/api/coding/v3"),
        ("ANTHROPIC_BASE_URL", "https://ark.cn-beijing.volces.com/api/coding/v3"),
        (
            "CODEX_CONFIG_TOML",
            envs[8].value,
        ),
        (
            "CODEX_MODEL_CATALOG_JSON",
            envs[9].value,
        ),
    ]
    assert 'model_provider = "coding_plan"' in envs[8].value
    assert (
        'base_url = "https://ark.cn-beijing.volces.com/api/coding/v3"' in envs[8].value
    )


def test_ensure_sandbox_session_skips_tos_mount_when_tool_has_none(
    monkeypatch,
    tmp_path,
) -> None:
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    monkeypatch.setattr(
        session_create,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    _patch_store_path(monkeypatch, tmp_path)

    session_create.ensure_sandbox_session(
        session_id="user-cli",
        tool_id="tool-cli",
    )

    assert _FakeToolsClient.get_tool_call_count == 2
    assert _FakeToolsClient.last_get_tool_request.tool_id == "tool-cli"
    assert _FakeToolsClient.last_request.tos_mount_points is None


def test_ensure_sandbox_session_mounts_tool_tos_by_tool_and_session(
    monkeypatch,
    tmp_path,
) -> None:
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    monkeypatch.setattr(
        session_create,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    _patch_store_path(monkeypatch, tmp_path)
    _FakeToolsClient.get_tool_response = _FakeGetToolResponse(
        tos_mount_config=_FakeToolTosMountConfig(
            [
                _FakeToolMountPoint(
                    bucket_name="agentkit-platform-123",
                    bucket_path="/sandbox-session/default/default",
                    local_mount_path="/home/gem/Downloads",
                )
            ]
        )
    )

    session_create.ensure_sandbox_session(
        session_id="user-cli",
        tool_id="tool-cli",
    )

    assert _FakeToolsClient.get_tool_call_count == 2
    assert _FakeToolsClient.last_get_tool_request.tool_id == "tool-cli"
    mount_points = _FakeToolsClient.last_request.tos_mount_points
    assert len(mount_points) == 1
    assert mount_points[0].bucket_name == "agentkit-platform-123"
    assert (
        mount_points[0].bucket_path
        == "/sandbox-session/tool-tool-cli/session-user-cli/"
    )
    assert mount_points[0].local_mount_path == "/home/gem/Downloads"


def test_ensure_sandbox_session_confirms_create_start_fail_by_user_session_id(
    monkeypatch,
    tmp_path,
) -> None:
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    monkeypatch.setattr(
        session_create,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    monkeypatch.setattr(session_create.time, "sleep", lambda _seconds: None)
    store_path = _patch_store_path(monkeypatch, tmp_path)
    _FakeToolsClient.create_error = Exception(
        'Failed to CreateSession: b\'{"ResponseMetadata":{"Error":'
        '{"Code":"ErrCreateSessionFail","Message":"Session start fail"}}}\''
    )
    _FakeToolsClient.list_sessions_responses = [
        _FakeListSessionsResponse(),
        _FakeListSessionsResponse(
            [
                _FakeSessionInfo(
                    user_session_id="user-cli",
                    session_id="confirmed-instance",
                    endpoint="https://confirmed.example.com",
                )
            ]
        ),
    ]

    result = session_create.ensure_sandbox_session(
        session_id="user-cli",
        tool_id="tool-cli",
    )

    assert _FakeToolsClient.create_call_count == 1
    assert _FakeToolsClient.list_sessions_call_count == 2
    assert [
        (item.name, item.values)
        for item in _FakeToolsClient.last_list_sessions_request.filters
    ] == [("UserSessionId", ["user-cli"])]
    assert result == {
        "session_id": "user-cli",
        "tool_id": "tool-cli",
        "instance_id": "confirmed-instance",
        "endpoint": "https://confirmed.example.com",
    }
    assert json.loads(store_path.read_text(encoding="utf-8")) == {"user-cli": result}


def test_ensure_sandbox_session_waits_for_ready_after_create_start_fail(
    monkeypatch,
    tmp_path,
) -> None:
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    monkeypatch.setattr(
        session_create,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    sleeps = []
    monkeypatch.setattr(session_create.time, "sleep", sleeps.append)
    _patch_store_path(monkeypatch, tmp_path)
    _FakeToolsClient.create_error = Exception(
        'Failed to CreateSession: b\'{"ResponseMetadata":{"Error":'
        '{"Code":"ErrCreateSessionFail","Message":"Session start fail"}}}\''
    )
    _FakeToolsClient.list_sessions_responses = [
        _FakeListSessionsResponse(),
        _FakeListSessionsResponse(
            [
                _FakeSessionInfo(
                    user_session_id="user-cli",
                    session_id="pending-instance",
                    endpoint="https://pending.example.com",
                    status="Creating",
                )
            ]
        ),
        _FakeListSessionsResponse(
            [
                _FakeSessionInfo(
                    user_session_id="user-cli",
                    session_id="ready-instance",
                    endpoint="https://ready.example.com",
                    status="Ready",
                )
            ]
        ),
    ]

    result = session_create.ensure_sandbox_session(
        session_id="user-cli",
        tool_id="tool-cli",
    )

    assert _FakeToolsClient.list_sessions_call_count == 3
    assert sleeps == [5]
    assert result == {
        "session_id": "user-cli",
        "tool_id": "tool-cli",
        "instance_id": "ready-instance",
        "endpoint": "https://ready.example.com",
    }


def test_ensure_sandbox_session_requires_endpoint_after_create_start_fail(
    monkeypatch,
    tmp_path,
) -> None:
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    monkeypatch.setattr(
        session_create,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    sleeps = []
    monkeypatch.setattr(session_create.time, "sleep", sleeps.append)
    _patch_store_path(monkeypatch, tmp_path)
    _FakeToolsClient.create_error = Exception(
        'Failed to CreateSession: b\'{"ResponseMetadata":{"Error":'
        '{"Code":"ErrCreateSessionFail","Message":"Session start fail"}}}\''
    )
    _FakeToolsClient.list_sessions_responses = [
        _FakeListSessionsResponse(),
        _FakeListSessionsResponse(
            [
                _FakeSessionInfo(
                    user_session_id="user-cli",
                    session_id="instance-without-endpoint",
                    endpoint="",
                    status="Ready",
                )
            ]
        ),
    ]

    with pytest.raises(Exception, match="ErrCreateSessionFail"):
        session_create.ensure_sandbox_session(
            session_id="user-cli",
            tool_id="tool-cli",
        )

    assert _FakeToolsClient.list_sessions_call_count == 7
    assert sleeps == [5, 5, 5, 5, 5]


def test_ensure_sandbox_session_reraises_create_start_fail_after_confirm_retries(
    monkeypatch,
    tmp_path,
) -> None:
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    monkeypatch.setattr(
        session_create,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    sleeps = []
    monkeypatch.setattr(session_create.time, "sleep", sleeps.append)
    _patch_store_path(monkeypatch, tmp_path)
    _FakeToolsClient.create_error = Exception(
        'Failed to CreateSession: b\'{"ResponseMetadata":{"Error":'
        '{"Code":"ErrCreateSessionFail","Message":"Session start fail"}}}\''
    )

    with pytest.raises(Exception, match="ErrCreateSessionFail"):
        session_create.ensure_sandbox_session(
            tool_id="tool-cli",
        )

    assert _FakeToolsClient.create_call_count == 1
    assert _FakeToolsClient.list_sessions_call_count == 6
    assert sleeps == [5, 5, 5, 5, 5]


def test_create_command_requires_env_credentials(monkeypatch) -> None:
    from agentkit.toolkit.cli.cli import app
    from agentkit.toolkit.cli.sandbox import cli_create

    class MissingCredentialsTOSService:
        def __init__(self, _config):
            service_key = "tos"
            raise ValueError(
                "\n".join(
                    [
                        f"Volcengine credentials not found (Service: {service_key}).",
                        "Recommended (global, set once):",
                        "  agentkit config --global --set volcengine.access_key=YOUR_ACCESS_KEY",
                        "  agentkit config --global --set volcengine.secret_key=YOUR_SECRET_KEY",
                        "Alternative (per-shell):",
                        "  export VOLCENGINE_ACCESS_KEY=YOUR_ACCESS_KEY",
                        "  export VOLCENGINE_SECRET_KEY=YOUR_SECRET_KEY",
                    ]
                )
            )

    monkeypatch.setattr(cli_create, "TOSService", MissingCredentialsTOSService)

    result = runner.invoke(app, ["sandbox", "create", "--tos-bucket", "my-bucket"])

    assert result.exit_code == 1
    assert "Volcengine credentials not found (Service: tos)." in result.output
    assert "agentkit config --global --set volcengine.access_key" in result.output


def test_sandbox_command_group_is_registered() -> None:
    from agentkit.toolkit.cli.cli import app

    result = runner.invoke(app, ["sandbox", "--help"])

    assert result.exit_code == 0
    assert "create" in result.output
    assert "exec" in result.output
    assert "get" in result.output
    assert "invoke" in result.output
    assert "mount" in result.output
    assert "shell" in result.output
    assert "web" in result.output


@pytest.mark.parametrize(
    "args",
    [
        ["sandbox", "get", "--help"],
        ["sandbox", "shell", "--help"],
        ["sandbox", "web", "--help"],
        ["sandbox", "exec", "--help"],
        ["sandbox", "invoke", "--help"],
        ["sandbox", "mount", "--help"],
    ],
)
def test_sandbox_session_id_options_accept_aliases(args) -> None:
    from agentkit.toolkit.cli.cli import app

    result = runner.invoke(app, args)

    assert result.exit_code == 0
    assert "--session-id" in result.output
    assert "--sid" in result.output
    assert "-s" in result.output


@pytest.mark.parametrize(
    "args",
    [["sandbox", "shell", "--help"], ["sandbox", "exec", "--help"]],
)
def test_sandbox_shell_id_option_is_disabled(args) -> None:
    from agentkit.toolkit.cli.cli import app

    result = runner.invoke(app, args)

    assert result.exit_code == 0
    assert "--shell-id" not in result.output


def test_build_invoke_model_agent_envs_uses_cli_values_first(
    monkeypatch,
) -> None:
    import agentkit.toolkit.cli.sandbox.cli_invoke as cli_invoke

    monkeypatch.setenv("MODEL_AGENT_NAME", "env-model")
    monkeypatch.setenv("MODEL_AGENT_PROVIDER", "env-provider")
    monkeypatch.setenv("MODEL_AGENT_API_BASE", "https://env.example.com")
    monkeypatch.setenv("MODEL_AGENT_API_KEY", "env-key")
    monkeypatch.setenv("MODEL_AGENT_EXTRA_HEADERS", '{"X-Env":"1"}')

    envs = cli_invoke.build_invoke_model_agent_envs(
        model_name="cli-model",
        model_provider="cli-provider",
        model_base_url="https://cli.example.com",
        model_api_key="cli-key",
    )

    assert {item.key: item.value for item in envs} == {
        "MODEL_AGENT_API_BASE": "https://cli.example.com",
        "MODEL_AGENT_API_KEY": "cli-key",
        "MODEL_AGENT_PROVIDER": "cli-provider",
        "MODEL_AGENT_NAME": "cli-model",
        "MODEL_AGENT_EXTRA_HEADERS": '{"X-Env":"1"}',
    }


def test_build_invoke_model_agent_envs_uses_env_values(
    monkeypatch,
    tmp_path,
) -> None:
    import agentkit.toolkit.cli.sandbox.cli_invoke as cli_invoke

    monkeypatch.setenv("MODEL_AGENT_NAME", "env-model")
    monkeypatch.setenv("MODEL_AGENT_PROVIDER", "env-provider")
    monkeypatch.setenv("MODEL_AGENT_API_BASE", "https://env.example.com")
    monkeypatch.setenv("MODEL_AGENT_API_KEY", "env-key")
    monkeypatch.setenv("MODEL_AGENT_EXTRA_HEADERS", '{"X-Env":"1"}')

    envs = cli_invoke.build_invoke_model_agent_envs(
        openclaw_config_file=tmp_path / "missing-openclaw.json",
    )

    assert {item.key: item.value for item in envs} == {
        "MODEL_AGENT_API_BASE": "https://env.example.com",
        "MODEL_AGENT_API_KEY": "env-key",
        "MODEL_AGENT_PROVIDER": "env-provider",
        "MODEL_AGENT_NAME": "env-model",
        "MODEL_AGENT_EXTRA_HEADERS": '{"X-Env":"1"}',
    }


def test_build_invoke_model_agent_envs_uses_openclaw_config(
    monkeypatch,
    tmp_path,
) -> None:
    import agentkit.toolkit.cli.sandbox.cli_invoke as cli_invoke

    _clear_model_agent_envs(monkeypatch, cli_invoke)
    openclaw_path = tmp_path / "openclaw.json"
    openclaw_path.write_text(
        json.dumps(
            {
                "agents": {"defaults": {"model": {"primary": "provider-a/model-a"}}},
                "models": {
                    "provider-a": {
                        "api_base": "https://openclaw.example.com",
                        "api_key": "openclaw-key",
                        "api": "openai-responses",
                        "headers": {"X-Provider": "provider"},
                        "models": {
                            "model-a": {
                                "headers": {"X-Model": "model"},
                            }
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    envs = cli_invoke.build_invoke_model_agent_envs(
        openclaw_config_file=openclaw_path,
    )

    assert {item.key: item.value for item in envs} == {
        "MODEL_AGENT_API_BASE": "https://openclaw.example.com",
        "MODEL_AGENT_API_KEY": "openclaw-key",
        "MODEL_AGENT_PROVIDER": "openai/responses",
        "MODEL_AGENT_NAME": "model-a",
        "MODEL_AGENT_EXTRA_HEADERS": '{"X-Model": "model", "X-Provider": "provider"}',
    }


def test_build_invoke_model_agent_envs_uses_empty_required_values(
    monkeypatch,
    tmp_path,
) -> None:
    import agentkit.toolkit.cli.sandbox.cli_invoke as cli_invoke

    _clear_model_agent_envs(monkeypatch, cli_invoke)

    envs = cli_invoke.build_invoke_model_agent_envs(
        openclaw_config_file=tmp_path / "missing-openclaw.json",
    )

    assert [(item.key, item.value) for item in envs] == [
        ("MODEL_AGENT_API_BASE", ""),
        ("MODEL_AGENT_API_KEY", ""),
        ("MODEL_AGENT_PROVIDER", ""),
        ("MODEL_AGENT_NAME", ""),
    ]


def test_cli_invoke_async_uses_env_tool_id_and_sends_a2a(
    monkeypatch,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.a2a_client as a2a_client
    import agentkit.toolkit.cli.sandbox.cli_invoke as cli_invoke

    _clear_model_agent_envs(monkeypatch, cli_invoke)
    monkeypatch.setenv("AGENTKIT_SANDBOX_TOOL_ID", "tool-env")
    capture = {}
    _patch_invoke_session(
        monkeypatch,
        cli_invoke,
        {
            "session_id": "session-cli",
            "instance_id": "instance-cli",
            "endpoint": "https://sandbox.example.com/base?Authorization=token",
        },
        capture,
    )
    calls = []

    def fake_post(url, json=None, timeout=None):
        calls.append({"url": url, "json": json, "timeout": timeout})
        return _FakeA2AResponse(
            {
                "jsonrpc": "2.0",
                "id": "rpc-1",
                "result": {
                    "kind": "task",
                    "id": "task-1",
                    "contextId": "context-1",
                    "status": {"state": "working"},
                },
            }
        )

    monkeypatch.setattr(a2a_client.requests, "post", fake_post)

    result = runner.invoke(
        app,
        [
            "sandbox",
            "invoke",
            "--session-id",
            "session-cli",
            "--prompt",
            "hello",
            "--async",
            "true",
        ],
    )

    assert result.exit_code == 0
    assert capture["session_id"] == "session-cli"
    assert capture["tool_id"] == "tool-env"
    assert capture["tool_type"] == "SkillEnv"
    assert capture["ttl"] is None
    assert capture["resolve_tool"] is False
    assert capture["include_tos_mount_points"] is False
    assert [(item.key, item.value) for item in capture["envs"]] == [
        ("MODEL_AGENT_API_BASE", ""),
        ("MODEL_AGENT_API_KEY", ""),
        ("MODEL_AGENT_PROVIDER", ""),
        ("MODEL_AGENT_NAME", ""),
    ]
    assert len(calls) == 1
    call = calls[0]
    assert call["url"] == "https://sandbox.example.com/base/a2a?Authorization=token"
    assert call["json"]["method"] == "message/send"
    assert call["json"]["params"]["message"]["parts"] == [
        {"kind": "text", "text": "hello"}
    ]
    assert call["json"]["params"]["metadata"] == {
        "session_id": "session-cli",
        "user_id": "agentkit-sandbox-invoke",
    }
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["task_id"] == "task-1"
    assert payload["context_id"] == "context-1"
    assert payload["session_id"] == "session-cli"
    assert payload["tool_id"] == "tool-env"


def test_cli_invoke_sync_falls_back_to_tool_type_and_polls(
    monkeypatch,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.a2a_client as a2a_client
    import agentkit.toolkit.cli.sandbox.cli_invoke as cli_invoke

    _clear_model_agent_envs(monkeypatch, cli_invoke)
    monkeypatch.delenv("AGENTKIT_SANDBOX_TOOL_ID", raising=False)
    capture = {}
    _patch_invoke_session(
        monkeypatch,
        cli_invoke,
        {
            "session_id": "generated-session",
            "instance_id": "instance-cli",
            "endpoint": "https://sandbox.example.com",
        },
        capture,
    )
    calls = []

    def fake_post(url, json=None, timeout=None):
        calls.append({"url": url, "json": json, "timeout": timeout})
        method = json["method"]
        if method == "message/send":
            return _FakeA2AResponse(
                {
                    "jsonrpc": "2.0",
                    "id": "rpc-send",
                    "result": {
                        "kind": "task",
                        "id": "task-sync",
                        "contextId": "context-sync",
                        "status": {"state": "working"},
                    },
                }
            )
        return _FakeA2AResponse(
            {
                "jsonrpc": "2.0",
                "id": "rpc-get",
                "result": {
                    "kind": "task",
                    "id": "task-sync",
                    "contextId": "context-sync",
                    "status": {"state": "completed"},
                    "artifacts": [
                        {"parts": [{"kind": "text", "text": "done"}]},
                    ],
                },
            }
        )

    monkeypatch.setattr(a2a_client.requests, "post", fake_post)

    result = runner.invoke(
        app,
        ["sandbox", "invoke", "--prompt", "run it", "--ttl", "123"],
    )

    assert result.exit_code == 0
    assert capture["session_id"] is None
    assert capture["tool_id"] == "SkillEnv"
    assert capture["tool_type"] == "SkillEnv"
    assert capture["ttl"] == 123
    assert capture["resolve_tool"] is False
    assert capture["include_tos_mount_points"] is False
    assert [(item.key, item.value) for item in capture["envs"]] == [
        ("MODEL_AGENT_API_BASE", ""),
        ("MODEL_AGENT_API_KEY", ""),
        ("MODEL_AGENT_PROVIDER", ""),
        ("MODEL_AGENT_NAME", ""),
    ]
    assert [call["json"]["method"] for call in calls] == [
        "message/send",
        "tasks/get",
    ]
    assert calls[1]["json"]["params"]["id"] == "task-sync"
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["task_state"] == "completed"
    assert payload["final_result"] == "done"
    assert payload["task_id"] == "task-sync"


def test_cli_invoke_passes_model_agent_envs_from_options(
    monkeypatch,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.a2a_client as a2a_client
    import agentkit.toolkit.cli.sandbox.cli_invoke as cli_invoke

    _clear_model_agent_envs(monkeypatch, cli_invoke)
    capture = {}
    _patch_invoke_session(
        monkeypatch,
        cli_invoke,
        {
            "session_id": "session-cli",
            "instance_id": "instance-cli",
            "endpoint": "https://sandbox.example.com",
        },
        capture,
    )

    monkeypatch.setattr(
        a2a_client.requests,
        "post",
        lambda *_args, **_kwargs: _FakeA2AResponse(
            {
                "jsonrpc": "2.0",
                "id": "rpc-1",
                "result": {
                    "kind": "task",
                    "id": "task-1",
                    "status": {"state": "working"},
                },
            }
        ),
    )

    result = runner.invoke(
        app,
        [
            "sandbox",
            "invoke",
            "--prompt",
            "hello",
            "--async",
            "--model-name",
            "model-cli",
            "--model-provider",
            "provider-cli",
            "--model-base-url",
            "https://models.example.com",
            "--model-api-key",
            "key-cli",
        ],
    )

    assert result.exit_code == 0
    assert {item.key: item.value for item in capture["envs"]} == {
        "MODEL_AGENT_API_BASE": "https://models.example.com",
        "MODEL_AGENT_API_KEY": "key-cli",
        "MODEL_AGENT_PROVIDER": "provider-cli",
        "MODEL_AGENT_NAME": "model-cli",
    }


def test_cli_invoke_task_id_polls_without_prompt(
    monkeypatch,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.a2a_client as a2a_client
    import agentkit.toolkit.cli.sandbox.cli_invoke as cli_invoke

    capture = {}
    _patch_invoke_session(
        monkeypatch,
        cli_invoke,
        {
            "session_id": "session-cli",
            "instance_id": "instance-cli",
            "endpoint": "https://sandbox.example.com",
        },
        capture,
    )
    calls = []

    def fake_post(url, json=None, timeout=None):
        calls.append({"url": url, "json": json, "timeout": timeout})
        return _FakeA2AResponse(
            {
                "jsonrpc": "2.0",
                "id": "rpc-get",
                "result": {
                    "kind": "task",
                    "id": "task-existing",
                    "status": {"state": "completed"},
                    "artifacts": [
                        {"parts": [{"kind": "text", "text": "existing result"}]},
                    ],
                },
            }
        )

    monkeypatch.setattr(a2a_client.requests, "post", fake_post)

    result = runner.invoke(
        app,
        [
            "sandbox",
            "invoke",
            "--sid",
            "session-cli",
            "--task-id",
            "task-existing",
        ],
    )

    assert result.exit_code == 0
    assert capture["session_id"] == "session-cli"
    assert len(calls) == 1
    assert calls[0]["json"]["method"] == "tasks/get"
    assert calls[0]["json"]["params"]["id"] == "task-existing"
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["task_id"] == "task-existing"
    assert payload["final_result"] == "existing result"


def test_cli_invoke_requires_prompt_without_task_id() -> None:
    from agentkit.toolkit.cli.cli import app

    result = runner.invoke(app, ["sandbox", "invoke"])

    assert result.exit_code == 1
    assert "--prompt is required unless --task-id is provided" in result.output


def test_sandbox_exec_tos_mount_option_is_disabled() -> None:
    from agentkit.toolkit.cli.cli import app

    result = runner.invoke(app, ["sandbox", "exec", "--help"])

    assert result.exit_code == 0
    assert "--tos-mount" not in result.output


def test_sandbox_commands_are_not_registered_at_top_level() -> None:
    from agentkit.toolkit.cli.cli import app

    for command in ("create", "exec", "get", "mount", "shell", "web"):
        result = runner.invoke(app, [command])
        assert result.exit_code != 0
        assert "No such command" in result.output


def test_cli_mount_uses_stored_session_tool_and_opens_tosbrowser(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_mount as cli_mount

    store_path = _patch_store_path(monkeypatch, tmp_path)
    _write_session_store(
        store_path,
        {
            "session-cli": {
                "session_id": "session-cli",
                "tool_id": "tool-from-session",
                "instance_id": "instance-cli",
                "endpoint": "https://sandbox.example.com",
            }
        },
    )
    _FakeToolsClient.get_tool_response = _FakeGetToolResponse(
        tos_mount_config=_FakeToolTosMountConfig(
            [_FakeToolMountPoint(bucket_name="sandbox-bucket")]
        )
    )
    monkeypatch.setattr(
        cli_mount,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    discovery_path = tmp_path / ".agentkit" / "sandbox" / "agentkit-cli"
    monkeypatch.setattr(
        cli_mount,
        "_get_discovery_store_path",
        lambda: discovery_path,
    )
    discovery = {
        "issuer": (
            "https://userpool-5513b734-2672-4dce-80b5-47667033bc60"
            ".userpool.auth.id.cn-beijing.volces.com"
        ),
        "client_id": "5cf70436-5191-42d0-8260-b888ee1d0fe3",
        "role_trn": "trn:iam::2107625663:role/agentkit_cli_role",
        "provider_trn": "trn:iam::2107625663:oidc-provider/sandbox_cli_oidc",
        "region": "cn-beijing",
        "transport": "sts",
        "scope": "openid profile email offline_access",
    }
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(discovery).encode("utf-8")

    def fake_urlopen(url, *args, **kwargs):
        captured["url"] = url
        return FakeResponse()

    def fake_open(command):
        captured["command"] = command

    monkeypatch.setattr(cli_mount, "urlopen", fake_urlopen)
    monkeypatch.setattr(cli_mount, "_open_tosbrowser", fake_open)

    result = runner.invoke(
        app,
        [
            "sandbox",
            "mount",
            "--session-id",
            "session-cli",
            "--oauth-url",
            "https://example.com/oauth",
        ],
    )

    expected_command = (
        "tosbrowser://open?"
        "path=tos://sandbox-bucket/sandbox-session/tool-tool-from-session/"
        "session-session-cli/"
        "&type=oAuthLogin"
        "&role=trn:iam::2107625663:role/agentkit_cli_role"
        "&userPool=5513b734-2672-4dce-80b5-47667033bc60"
        "&clientId=5cf70436-5191-42d0-8260-b888ee1d0fe3"
    )
    assert result.exit_code == 0
    assert captured["url"] == ("https://example.com/oauth/.well-known/agentkit-cli")
    assert _FakeToolsClient.last_get_tool_request.tool_id == "tool-from-session"
    assert captured["command"] == expected_command
    assert json.loads(discovery_path.read_text(encoding="utf-8")) == discovery
    assert json.loads(result.output) == {
        "tool_id": "tool-from-session",
        "session_id": "session-cli",
        "command": expected_command,
    }


def test_cli_mount_uses_tool_tos_bucket_when_option_omitted(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_mount as cli_mount

    store_path = _patch_store_path(monkeypatch, tmp_path)
    _write_session_store(
        store_path,
        {
            "session-cli": {
                "session_id": "session-cli",
                "tool_id": "tool-from-session",
                "instance_id": "instance-cli",
                "endpoint": "https://sandbox.example.com",
            }
        },
    )
    _FakeToolsClient.get_tool_response = _FakeGetToolResponse(
        tos_mount_config=_FakeToolTosMountConfig(
            [_FakeToolMountPoint(bucket_name="bucket-from-tool")]
        )
    )
    monkeypatch.setattr(
        cli_mount,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    monkeypatch.setattr(
        cli_mount,
        "_get_discovery_store_path",
        lambda: tmp_path / ".agentkit" / "sandbox" / "agentkit-cli",
    )
    discovery = {
        "issuer": (
            "https://userpool-5513b734-2672-4dce-80b5-47667033bc60"
            ".userpool.auth.id.cn-beijing.volces.com"
        ),
        "client_id": "client-id",
        "role_trn": "role-trn",
    }

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(discovery).encode("utf-8")

    opened = {}
    monkeypatch.setattr(cli_mount, "urlopen", lambda _url, *a, **k: FakeResponse())
    monkeypatch.setattr(
        cli_mount,
        "_open_tosbrowser",
        lambda command: opened.setdefault("command", command),
    )

    result = runner.invoke(
        app,
        [
            "sandbox",
            "mount",
            "--session-id",
            "session-cli",
            "--oauth-url",
            "https://example.com/oauth",
        ],
    )

    assert result.exit_code == 0
    assert _FakeToolsClient.last_get_tool_request.tool_id == "tool-from-session"
    assert "path=tos://bucket-from-tool/" in opened["command"]
    assert json.loads(result.output)["tool_id"] == "tool-from-session"


def test_cli_mount_uses_latest_auth_session_when_oauth_url_omitted(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_mount as cli_mount

    store_path = _patch_store_path(monkeypatch, tmp_path)
    _write_session_store(
        store_path,
        {
            "session-cli": {
                "session_id": "session-cli",
                "tool_id": "tool-from-session",
                "instance_id": "instance-cli",
                "endpoint": "https://sandbox.example.com",
            }
        },
    )
    _FakeToolsClient.get_tool_response = _FakeGetToolResponse(
        tos_mount_config=_FakeToolTosMountConfig(
            [_FakeToolMountPoint(bucket_name="bucket-from-tool")]
        )
    )
    monkeypatch.setattr(
        cli_mount,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    monkeypatch.setattr(
        cli_mount,
        "_get_discovery_store_path",
        lambda: tmp_path / ".agentkit" / "sandbox" / "agentkit-cli",
    )

    auth_sessions_dir = tmp_path / "auth" / "sessions"
    auth_sessions_dir.mkdir(parents=True)
    old_session = (
        auth_sessions_dir / "agentkit-cli-1111111111.tos-cn-beijing.volces.com.json"
    )
    latest_session = (
        auth_sessions_dir / "agentkit-cli-2107625663.tos-cn-beijing.volces.com.json"
    )
    old_session.write_text("{}", encoding="utf-8")
    latest_session.write_text("{}", encoding="utf-8")
    os.utime(old_session, (1, 1))
    os.utime(latest_session, (2, 2))
    monkeypatch.setattr(
        cli_mount,
        "_get_auth_sessions_dir",
        lambda: auth_sessions_dir,
    )

    discovery = {
        "issuer": (
            "https://userpool-5513b734-2672-4dce-80b5-47667033bc60"
            ".userpool.auth.id.cn-beijing.volces.com"
        ),
        "client_id": "client-id",
        "role_trn": "role-trn",
    }
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(discovery).encode("utf-8")

    def fake_urlopen(url, *args, **kwargs):
        captured["url"] = url
        return FakeResponse()

    monkeypatch.setattr(cli_mount, "urlopen", fake_urlopen)
    monkeypatch.setattr(
        cli_mount,
        "_open_tosbrowser",
        lambda command: captured.setdefault("command", command),
    )

    result = runner.invoke(
        app,
        [
            "sandbox",
            "mount",
            "--session-id",
            "session-cli",
        ],
    )

    assert result.exit_code == 0
    assert captured["url"] == (
        "https://agentkit-cli-2107625663.tos-cn-beijing.volces.com/"
        ".well-known/agentkit-cli"
    )
    assert "path=tos://bucket-from-tool/" in captured["command"]
    assert json.loads(result.output)["tool_id"] == "tool-from-session"


def test_cli_mount_errors_when_latest_auth_session_name_is_invalid(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_mount as cli_mount

    auth_sessions_dir = tmp_path / "auth" / "sessions"
    auth_sessions_dir.mkdir(parents=True)
    valid_session = (
        auth_sessions_dir / "agentkit-cli-1111111111.tos-cn-beijing.volces.com.json"
    )
    invalid_session = auth_sessions_dir / "default.json"
    valid_session.write_text("{}", encoding="utf-8")
    invalid_session.write_text("{}", encoding="utf-8")
    os.utime(valid_session, (1, 1))
    os.utime(invalid_session, (2, 2))
    monkeypatch.setattr(
        cli_mount,
        "_get_auth_sessions_dir",
        lambda: auth_sessions_dir,
    )

    result = runner.invoke(
        app,
        [
            "sandbox",
            "mount",
            "--session-id",
            "session-cli",
        ],
    )

    assert result.exit_code == 1
    assert "Invalid auth session filename for sandbox mount" in result.output
    assert "Expected agentkit-cli-*volces.com.json" in result.output


def test_cli_mount_errors_when_auth_session_directory_is_missing(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_mount as cli_mount

    auth_sessions_dir = tmp_path / "missing" / "sessions"
    monkeypatch.setattr(
        cli_mount,
        "_get_auth_sessions_dir",
        lambda: auth_sessions_dir,
    )

    result = runner.invoke(
        app,
        [
            "sandbox",
            "mount",
            "--session-id",
            "session-cli",
        ],
    )

    assert result.exit_code == 1
    assert f"Auth session directory not found: {auth_sessions_dir}" in result.output


def test_cli_mount_errors_when_tool_has_no_tos_mount(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_mount as cli_mount

    store_path = _patch_store_path(monkeypatch, tmp_path)
    _write_session_store(
        store_path,
        {
            "session-cli": {
                "session_id": "session-cli",
                "tool_id": "tool-from-session",
                "instance_id": "instance-cli",
                "endpoint": "https://sandbox.example.com",
            }
        },
    )
    _FakeToolsClient.get_tool_response = _FakeGetToolResponse(tos_mount_config=None)
    monkeypatch.setattr(
        cli_mount,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )

    result = runner.invoke(
        app,
        [
            "sandbox",
            "mount",
            "--session-id",
            "session-cli",
            "--oauth-url",
            "https://example.com/oauth",
        ],
    )

    assert result.exit_code == 1
    assert "当前工具未挂载 Tos: tool-from-session" in result.output


def test_cli_mount_syncs_current_tool_sessions_when_session_not_cached(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_mount as cli_mount

    store_path = _patch_store_path(monkeypatch, tmp_path)
    _write_session_store(store_path, {})
    tool_store_path = _patch_tool_store_path(monkeypatch, tmp_path)
    tool_store_path.parent.mkdir(parents=True, exist_ok=True)
    tool_store_path.write_text(
        json.dumps(
            {
                "CodeEnv": {
                    "ToolId": "tool-cache",
                    "ToolType": "CodeEnv",
                    "Name": "cached-tool",
                    "Status": "Ready",
                }
            }
        ),
        encoding="utf-8",
    )
    _FakeToolsClient.get_tool_response = _FakeGetToolResponse(
        tos_mount_config=_FakeToolTosMountConfig(
            [_FakeToolMountPoint(bucket_name="sandbox-bucket")]
        )
    )
    _FakeToolsClient.list_sessions_responses = [
        _FakeListSessionsResponse(
            [
                _FakeSessionInfo(
                    user_session_id="session-cli",
                    session_id="instance-cli",
                    endpoint="https://sandbox.example.com",
                )
            ]
        )
    ]
    monkeypatch.setattr(
        cli_mount,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    monkeypatch.setattr(
        cli_mount,
        "_get_discovery_store_path",
        lambda: tmp_path / ".agentkit" / "sandbox" / "agentkit-cli",
    )
    discovery = {
        "issuer": (
            "https://userpool-5513b734-2672-4dce-80b5-47667033bc60"
            ".userpool.auth.id.cn-beijing.volces.com"
        ),
        "client_id": "client-id",
        "role_trn": "role-trn",
    }

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(discovery).encode("utf-8")

    opened = {}
    monkeypatch.setattr(cli_mount, "urlopen", lambda _url, *a, **k: FakeResponse())
    monkeypatch.setattr(
        cli_mount,
        "_open_tosbrowser",
        lambda command: opened.setdefault("command", command),
    )

    result = runner.invoke(
        app,
        [
            "sandbox",
            "mount",
            "--session-id",
            "session-cli",
            "--oauth-url",
            "https://example.com/oauth",
        ],
    )

    assert result.exit_code == 0
    assert _FakeToolsClient.list_sessions_call_count == 1
    assert _FakeToolsClient.last_get_tool_request.tool_id == "tool-cache"
    assert "tool-tool-cache/session-session-cli" in opened["command"]
    assert json.loads(result.output)["tool_id"] == "tool-cache"
    assert json.loads(store_path.read_text(encoding="utf-8"))["session-cli"] == {
        "session_id": "session-cli",
        "tool_id": "tool-cache",
        "instance_id": "instance-cli",
        "endpoint": "https://sandbox.example.com",
    }


def test_cli_mount_open_tosbrowser_passes_url_as_single_argument(
    monkeypatch,
) -> None:
    import agentkit.toolkit.cli.sandbox.cli_mount as cli_mount

    calls = []

    def fake_run(args, *, check, capture_output, text):
        calls.append((args, check, capture_output, text))

    command = (
        "tosbrowser://open?"
        "path=tos://sandbox-bucket-cn-beijing/sandbox-session/"
        "tool-t-yeoptd0ykgo2eybtiy5m/"
        "session-11732c13-cd6d-45f4-b42f-f104e83b1c4e/"
        "&type=oAuthLogin"
        "&role=trn:iam::2107625663:role/agentkit_cli_role"
        "&userPool=5513b734-2672-4dce-80b5-47667033bc60"
        "&clientId=5cf70436-5191-42d0-8260-b888ee1d0fe3"
    )
    monkeypatch.setattr(cli_mount.subprocess, "run", fake_run)

    cli_mount._open_tosbrowser(command)

    assert calls == [(["open", command], True, True, True)]


def test_cli_mount_returns_install_hint_when_tosbrowser_is_missing(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_mount as cli_mount

    store_path = _patch_store_path(monkeypatch, tmp_path)
    _write_session_store(
        store_path,
        {
            "session-cli": {
                "session_id": "session-cli",
                "tool_id": "tool-from-session",
                "instance_id": "instance-cli",
                "endpoint": "https://sandbox.example.com",
            }
        },
    )
    _FakeToolsClient.get_tool_response = _FakeGetToolResponse(
        tos_mount_config=_FakeToolTosMountConfig(
            [_FakeToolMountPoint(bucket_name="sandbox-bucket")]
        )
    )
    monkeypatch.setattr(
        cli_mount,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    monkeypatch.setattr(
        cli_mount,
        "_get_discovery_store_path",
        lambda: tmp_path / ".agentkit" / "sandbox" / "agentkit-cli",
    )
    discovery = {
        "issuer": (
            "https://userpool-5513b734-2672-4dce-80b5-47667033bc60"
            ".userpool.auth.id.cn-beijing.volces.com"
        ),
        "client_id": "client-id",
        "role_trn": "role-trn",
    }

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(discovery).encode("utf-8")

    original_error = (
        "No application knows how to open URL "
        "tosbrowser://open?path=tos://sandbox-bucket/"
        "(Error Domain=NSOSStatusErrorDomain Code=-10814 "
        '"kLSApplicationNotFoundErr")'
    )

    monkeypatch.setattr(cli_mount, "urlopen", lambda _url, *a, **k: FakeResponse())
    monkeypatch.setattr(
        cli_mount,
        "_open_tosbrowser",
        lambda _command: (_ for _ in ()).throw(
            cli_mount.TosBrowserNotFoundError(original_error)
        ),
    )

    result = runner.invoke(
        app,
        [
            "sandbox",
            "mount",
            "--session-id",
            "session-cli",
            "--oauth-url",
            "https://example.com/oauth",
        ],
    )

    assert result.exit_code == 1
    output = json.loads(result.output)
    assert output["tool_id"] == "tool-from-session"
    assert output["session_id"] == "session-cli"
    assert output["error_msg"] == "Failed to open TosBrowser"
    assert output["original_error"] == original_error
    assert output["install_hint"] == "请安装 TosBrowser 应用"
    assert output["download_url"] == cli_mount.TOS_BROWSER_DOWNLOAD_URL
    assert output["command"].startswith("tosbrowser://open?")


def test_open_tosbrowser_detects_missing_tosbrowser_from_open_error(
    monkeypatch,
) -> None:
    import agentkit.toolkit.cli.sandbox.cli_mount as cli_mount

    original_error = (
        "No application knows how to open URL tosbrowser://open?path=tos://"
        "sandbox-bucket-cn-beijing/sandbox-session/tool-t-example/session-test/"
        "&type=oAuthLogin (Error Domain=NSOSStatusErrorDomain Code=-10814 "
        '"kLSApplicationNotFoundErr")'
    )

    def fake_run(*_args, **_kwargs):
        raise cli_mount.subprocess.CalledProcessError(
            returncode=1,
            cmd=["open", "tosbrowser://open"],
            stderr=original_error,
        )

    monkeypatch.setattr(cli_mount.subprocess, "run", fake_run)

    with pytest.raises(cli_mount.TosBrowserNotFoundError) as exc_info:
        cli_mount._open_tosbrowser("tosbrowser://open")

    assert str(exc_info.value) == original_error


def test_cli_mount_reports_missing_session_after_sync(monkeypatch, tmp_path) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_mount as cli_mount

    store_path = _patch_store_path(monkeypatch, tmp_path)
    _write_session_store(store_path, {})
    _patch_tool_store_path(monkeypatch, tmp_path)
    _FakeToolsClient.list_response = _FakeListToolsResponse()
    monkeypatch.setattr(
        cli_mount,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )

    result = runner.invoke(
        app,
        [
            "sandbox",
            "mount",
            "--session-id",
            "session-cli",
            "--oauth-url",
            "https://example.com/oauth",
        ],
    )

    assert result.exit_code == 1
    assert json.loads(result.output) == {
        "tool_id": None,
        "session_id": "session-cli",
        "error_msg": "Sandbox session not found: session-cli",
    }


def test_cli_mount_tos_bucket_option_is_disabled() -> None:
    from agentkit.toolkit.cli.cli import app

    result = runner.invoke(app, ["sandbox", "mount", "--help"])

    assert result.exit_code == 0
    assert "--tos-bucket" not in result.output
    assert "--tool-id" not in result.output
    assert "--tool-type" not in result.output


def test_ensure_sandbox_session_reuses_existing_remote_session(
    monkeypatch,
    tmp_path,
) -> None:
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    class ExistingResponse:
        user_session_id = "same-user-session"
        session_id = "session-existing"
        endpoint = "https://remote.example.com"

    monkeypatch.setattr(
        session_create,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    monkeypatch.delenv("AGENTKIT_SANDBOX_TOOL_ID", raising=False)
    store_path = _patch_store_path(monkeypatch, tmp_path)
    store_path.write_text(
        json.dumps(
            {
                "same-user-session": {
                    "session_id": "same-user-session",
                    "tool_id": "tool-stored",
                    "instance_id": "session-existing",
                    "endpoint": "https://local.example.com",
                }
            }
        ),
        encoding="utf-8",
    )
    _FakeToolsClient.get_response = ExistingResponse()

    result = session_create.ensure_sandbox_session(
        session_id="same-user-session",
    )

    assert _FakeToolsClient.create_call_count == 0
    assert _FakeToolsClient.get_call_count == 1
    assert _FakeToolsClient.get_tool_call_count == 1
    assert _FakeToolsClient.last_get_request.tool_id == "tool-stored"
    assert _FakeToolsClient.last_get_request.session_id == "session-existing"
    assert result == {
        "session_id": "same-user-session",
        "tool_id": "tool-stored",
        "instance_id": "session-existing",
        "endpoint": "https://remote.example.com",
    }

    stored = json.loads(store_path.read_text(encoding="utf-8"))
    assert stored["same-user-session"] == result


def test_ensure_sandbox_session_syncs_missing_local_session_before_create(
    monkeypatch,
    tmp_path,
) -> None:
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    class ExistingResponse:
        user_session_id = "remote-user"
        session_id = "remote-instance"
        endpoint = "https://remote.example.com"

    monkeypatch.setattr(
        session_create,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    store_path = _patch_store_path(monkeypatch, tmp_path)
    _FakeToolsClient.list_sessions_responses = [
        _FakeListSessionsResponse(
            [
                _FakeSessionInfo(
                    user_session_id="remote-user",
                    session_id="remote-instance",
                    endpoint="https://listed.example.com",
                )
            ]
        )
    ]
    _FakeToolsClient.get_response = ExistingResponse()

    result = session_create.ensure_sandbox_session(
        session_id="remote-user",
        tool_id="tool-cli",
    )

    assert _FakeToolsClient.list_sessions_call_count == 1
    assert _FakeToolsClient.create_call_count == 0
    assert _FakeToolsClient.get_call_count == 1
    assert _FakeToolsClient.get_tool_call_count == 1
    assert _FakeToolsClient.last_list_sessions_request.tool_id == "tool-cli"
    assert _FakeToolsClient.last_get_request.tool_id == "tool-cli"
    assert _FakeToolsClient.last_get_request.session_id == "remote-instance"
    assert result == {
        "session_id": "remote-user",
        "tool_id": "tool-cli",
        "instance_id": "remote-instance",
        "endpoint": "https://remote.example.com",
    }
    assert json.loads(store_path.read_text(encoding="utf-8")) == {"remote-user": result}


def test_ensure_sandbox_session_recreates_when_remote_session_missing(
    monkeypatch,
    tmp_path,
) -> None:
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    class NewResponse:
        user_session_id = "same-user-session"
        session_id = "session-new"
        endpoint = "https://new.example.com"

    monkeypatch.setattr(
        session_create,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    store_path = _patch_store_path(monkeypatch, tmp_path)
    store_path.write_text(
        json.dumps(
            {
                "same-user-session": {
                    "session_id": "same-user-session",
                    "tool_id": "tool-stored",
                    "instance_id": "session-old",
                    "endpoint": "https://old.example.com",
                }
            }
        ),
        encoding="utf-8",
    )
    _FakeToolsClient.get_error = Exception("Session not found")
    _FakeToolsClient.response = NewResponse()

    result = session_create.ensure_sandbox_session(
        session_id="same-user-session",
        tool_id="tool-new",
    )

    assert _FakeToolsClient.get_call_count == 2
    assert _FakeToolsClient.get_tool_call_count == 3
    assert _FakeToolsClient.create_call_count == 1
    assert _FakeToolsClient.list_sessions_call_count == 1
    assert _FakeToolsClient.last_get_request.tool_id == "tool-new"
    assert _FakeToolsClient.last_get_request.session_id == "session-old"
    assert _FakeToolsClient.last_request.tool_id == "tool-new"

    stored = json.loads(store_path.read_text(encoding="utf-8"))
    assert list(stored) == ["same-user-session"]
    assert stored["same-user-session"] == {
        "session_id": "same-user-session",
        "tool_id": "tool-new",
        "instance_id": "session-new",
        "endpoint": "https://new.example.com",
    }
    assert result == stored["same-user-session"]


def test_ensure_sandbox_session_syncs_existing_session_after_stale_instance(
    monkeypatch,
    tmp_path,
) -> None:
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    class ExistingResponse:
        user_session_id = "same-user-session"
        session_id = "session-remote"
        endpoint = "https://remote.example.com"

    monkeypatch.setattr(
        session_create,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    store_path = _patch_store_path(monkeypatch, tmp_path)
    store_path.write_text(
        json.dumps(
            {
                "same-user-session": {
                    "session_id": "same-user-session",
                    "tool_id": "tool-stored",
                    "instance_id": "session-stale",
                    "endpoint": "https://stale.example.com",
                }
            }
        ),
        encoding="utf-8",
    )
    _FakeToolsClient.get_error = Exception("Session not found")
    _FakeToolsClient.list_sessions_responses = [
        _FakeListSessionsResponse(
            [
                _FakeSessionInfo(
                    user_session_id="same-user-session",
                    session_id="session-remote",
                    endpoint="https://listed.example.com",
                )
            ]
        )
    ]

    def fake_get_session(_self, request):
        _FakeToolsClient.last_get_request = request
        _FakeToolsClient.get_call_count += 1
        if request.session_id == "session-stale":
            raise Exception("Session not found")
        return ExistingResponse()

    monkeypatch.setattr(_FakeToolsClient, "get_session", fake_get_session)

    result = session_create.ensure_sandbox_session(
        session_id="same-user-session",
    )

    assert _FakeToolsClient.create_call_count == 0
    assert _FakeToolsClient.list_sessions_call_count == 1
    assert _FakeToolsClient.get_call_count == 2
    assert _FakeToolsClient.last_get_request.tool_id == "tool-stored"
    assert _FakeToolsClient.last_get_request.session_id == "session-remote"
    assert result == {
        "session_id": "same-user-session",
        "tool_id": "tool-stored",
        "instance_id": "session-remote",
        "endpoint": "https://remote.example.com",
    }
    assert json.loads(store_path.read_text(encoding="utf-8")) == {
        "same-user-session": result
    }


def test_cli_get_returns_stored_session(monkeypatch, tmp_path) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_get as cli_get

    store_path = _patch_store_path(monkeypatch, tmp_path)
    stored_result = {
        "session_id": "user-1",
        "tool_id": "tool-1",
        "instance_id": "session-1",
        "endpoint": "https://sandbox.example.com",
    }
    remote_result = {
        "session_id": "user-1",
        "tool_id": "tool-1",
        "instance_id": "remote-session-1",
        "endpoint": "https://remote.example.com",
    }
    store_path.write_text(
        json.dumps({"user-1": stored_result}, indent=2),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        cli_get,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    _FakeToolsClient.list_sessions_responses = [
        _FakeListSessionsResponse(
            [
                _FakeSessionInfo(
                    user_session_id="user-1",
                    session_id="remote-session-1",
                    endpoint="https://remote.example.com",
                )
            ]
        )
    ]

    result = runner.invoke(
        app,
        ["sandbox", "get", "--session-id", "user-1"],
    )

    assert result.exit_code == 0
    assert json.loads(result.output) == remote_result
    assert json.loads(store_path.read_text(encoding="utf-8")) == {
        "user-1": remote_result
    }


def test_cli_get_syncs_remote_sessions_with_pagination(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_get as cli_get

    store_path = _patch_store_path(monkeypatch, tmp_path)
    store_path.write_text(
        json.dumps(
            {
                "stale-user": {
                    "session_id": "stale-user",
                    "tool_id": "tool-1",
                    "instance_id": "stale-instance",
                    "endpoint": "https://stale.example.com",
                },
                "user-2": {
                    "session_id": "user-2",
                    "tool_id": "tool-1",
                    "instance_id": "old-instance-2",
                    "endpoint": "https://old.example.com",
                    "terminal_shell_id": ["shell-local"],
                },
                "other-user": {
                    "session_id": "other-user",
                    "tool_id": "other-tool",
                    "instance_id": "other-instance",
                    "endpoint": "https://other.example.com",
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        cli_get,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    _FakeToolsClient.list_sessions_responses = [
        _FakeListSessionsResponse(
            [
                _FakeSessionInfo(
                    user_session_id="user-1",
                    session_id="instance-1",
                    endpoint="https://one.example.com",
                )
            ],
            next_token="page-2",
        ),
        _FakeListSessionsResponse(
            [
                _FakeSessionInfo(
                    user_session_id="user-2",
                    session_id="instance-2",
                    endpoint="https://two.example.com",
                )
            ]
        ),
    ]

    result = runner.invoke(
        app,
        ["sandbox", "get", "--session-id", "user-2", "--tool-id", "tool-1"],
    )

    assert result.exit_code == 0
    assert json.loads(result.output) == {
        "session_id": "user-2",
        "tool_id": "tool-1",
        "instance_id": "instance-2",
        "endpoint": "https://two.example.com",
        "terminal_shell_id": ["shell-local"],
    }
    assert [
        request.next_token for request in _FakeToolsClient.list_sessions_requests
    ] == [None, "page-2"]
    stored = json.loads(store_path.read_text(encoding="utf-8"))
    assert "stale-user" not in stored
    assert stored["other-user"]["tool_id"] == "other-tool"
    assert stored["user-1"] == {
        "session_id": "user-1",
        "tool_id": "tool-1",
        "instance_id": "instance-1",
        "endpoint": "https://one.example.com",
    }
    assert stored["user-2"]["terminal_shell_id"] == ["shell-local"]


def test_cli_get_ignores_remote_sessions_without_user_session_id(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_get as cli_get

    store_path = _patch_store_path(monkeypatch, tmp_path)
    store_path.write_text(
        json.dumps(
            {
                "user-1": {
                    "session_id": "user-1",
                    "tool_id": "tool-1",
                    "instance_id": "old-instance",
                    "endpoint": "https://old.example.com",
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        cli_get,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    _FakeToolsClient.list_sessions_responses = [
        _FakeListSessionsResponse(
            [
                _FakeSessionInfo(
                    user_session_id="",
                    session_id="instance-without-user-session",
                    endpoint="https://ignored.example.com",
                ),
                _FakeSessionInfo(
                    user_session_id=None,
                    session_id="another-instance-without-user-session",
                    endpoint="https://ignored-too.example.com",
                ),
                _FakeSessionInfo(
                    user_session_id="user-1",
                    session_id="instance-1",
                    endpoint="https://one.example.com",
                ),
            ]
        )
    ]

    result = runner.invoke(
        app,
        ["sandbox", "get", "--session-id", "user-1", "--tool-id", "tool-1"],
    )

    assert result.exit_code == 0
    stored = json.loads(store_path.read_text(encoding="utf-8"))
    assert list(stored) == ["user-1"]
    assert stored["user-1"] == {
        "session_id": "user-1",
        "tool_id": "tool-1",
        "instance_id": "instance-1",
        "endpoint": "https://one.example.com",
    }
    assert json.loads(result.output) == stored["user-1"]


def test_cli_get_without_session_id_returns_all_synced_sessions(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_get as cli_get

    store_path = _patch_store_path(monkeypatch, tmp_path)
    store_path.write_text(
        json.dumps(
            {
                "local-other": {
                    "session_id": "local-other",
                    "tool_id": "other-tool",
                    "instance_id": "local-instance",
                    "endpoint": "https://local.example.com",
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        cli_get,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    _FakeToolsClient.list_sessions_responses = [
        _FakeListSessionsResponse(
            [
                _FakeSessionInfo(
                    user_session_id="remote-user-1",
                    session_id="remote-instance-1",
                    endpoint="https://one.example.com",
                ),
                _FakeSessionInfo(
                    user_session_id="",
                    session_id="ignored-instance",
                    endpoint="https://ignored.example.com",
                ),
            ]
        )
    ]

    result = runner.invoke(app, ["sandbox", "get", "--tool-id", "tool-1"])

    assert result.exit_code == 0
    expected = {
        "local-other": {
            "session_id": "local-other",
            "tool_id": "other-tool",
            "instance_id": "local-instance",
            "endpoint": "https://local.example.com",
        },
        "remote-user-1": {
            "session_id": "remote-user-1",
            "tool_id": "tool-1",
            "instance_id": "remote-instance-1",
            "endpoint": "https://one.example.com",
        },
    }
    assert json.loads(result.output) == expected
    assert json.loads(store_path.read_text(encoding="utf-8")) == expected
    assert _FakeToolsClient.list_sessions_call_count == 1


def test_cli_get_without_session_id_returns_empty_store(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_get as cli_get

    _patch_store_path(monkeypatch, tmp_path)
    _patch_tool_store_path(monkeypatch, tmp_path)
    monkeypatch.setattr(
        cli_get,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    _FakeToolsClient.list_response = _FakeListToolsResponse()

    result = runner.invoke(app, ["sandbox", "get"])

    assert result.exit_code == 0
    assert json.loads(result.output) == {}
    assert _FakeToolsClient.list_sessions_call_count == 0


def test_cli_get_reports_missing_session(monkeypatch, tmp_path) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_get as cli_get

    store_path = _patch_store_path(monkeypatch, tmp_path)
    _patch_tool_store_path(monkeypatch, tmp_path)
    store_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        cli_get,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )

    result = runner.invoke(
        app,
        ["sandbox", "get", "--session-id", "missing-user"],
    )

    assert result.exit_code == 1
    assert json.loads(result.output) == {
        "tool_id": None,
        "session_id": "missing-user",
        "error_msg": "Sandbox session not found: missing-user",
    }


def test_cli_get_missing_session_includes_resolved_tool_id(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_get as cli_get

    store_path = _patch_store_path(monkeypatch, tmp_path)
    store_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        cli_get,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )

    result = runner.invoke(
        app,
        [
            "sandbox",
            "get",
            "--session-id",
            "missing-user",
            "--tool-id",
            "tool-1",
        ],
    )

    assert result.exit_code == 1
    assert json.loads(result.output) == {
        "tool_id": "tool-1",
        "session_id": "missing-user",
        "error_msg": "Sandbox session not found: missing-user",
    }


def test_cli_web_returns_session_browser_url(monkeypatch, tmp_path) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_web as cli_web
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    store_path = _patch_store_path(monkeypatch, tmp_path)
    store_path.write_text(
        json.dumps(
            {
                "user-1": {
                    "session_id": "user-1",
                    "tool_id": "tool-1",
                    "instance_id": "old-instance",
                    "endpoint": "https://old.example.com",
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        session_create,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    _FakeToolsClient.get_response = _FakeGetSessionResponse()
    _FakeToolsClient.get_response.user_session_id = "user-1"
    _FakeToolsClient.get_response.session_id = "instance-1"
    _FakeToolsClient.get_response.endpoint = (
        "https://sandbox.example.com/base?"
        "faasInstanceName=vefaas-test-sandbox&"
        "Authorization=auth-token&resize=none"
    )
    opened_urls = []
    monkeypatch.setattr(
        cli_web.webbrowser,
        "open",
        lambda url: opened_urls.append(url) or True,
    )

    result = runner.invoke(
        app,
        ["sandbox", "web", "--session-id", "user-1", "--tool-id", "tool-1"],
    )

    assert result.exit_code == 0
    assert json.loads(result.output) == {
        "url": (
            "https://sandbox.example.com/base/vnc/index.html?"
            "autoconnect=true&resize=scale&reconnect=1&"
            "faasInstanceName=vefaas-test-sandbox&Authorization=auth-token&"
            "path=websockify%3FfaasInstanceName%3Dvefaas-test-sandbox"
            "%26Authorization%3Dauth-token"
        ),
        "tool_id": "tool-1",
        "session_id": "user-1",
        "is_new": False,
    }
    assert opened_urls == [json.loads(result.output)["url"]]


def test_cli_web_uses_stored_tool_id_when_tool_id_omitted(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_web as cli_web
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    store_path = _patch_store_path(monkeypatch, tmp_path)
    store_path.write_text(
        json.dumps(
            {
                "user-1": {
                    "session_id": "user-1",
                    "tool_id": "tool-stored",
                    "instance_id": "old-instance",
                    "endpoint": "https://old.example.com",
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        session_create,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    _FakeToolsClient.get_response = _FakeGetSessionResponse()
    _FakeToolsClient.get_response.user_session_id = "user-1"
    _FakeToolsClient.get_response.session_id = "instance-1"
    _FakeToolsClient.get_response.endpoint = "https://sandbox.example.com"
    opened_urls = []
    monkeypatch.setattr(
        cli_web.webbrowser,
        "open",
        lambda url: opened_urls.append(url) or True,
    )

    result = runner.invoke(app, ["sandbox", "web", "--session-id", "user-1"])

    assert result.exit_code == 0
    assert _FakeToolsClient.last_get_request.tool_id == "tool-stored"
    assert json.loads(result.output) == {
        "url": (
            "https://sandbox.example.com/vnc/index.html?"
            "autoconnect=true&resize=scale&reconnect=1"
        ),
        "tool_id": "tool-stored",
        "session_id": "user-1",
        "is_new": False,
    }
    assert opened_urls == [json.loads(result.output)["url"]]


def test_cli_web_accepts_tool_id_underscore_alias(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_web as cli_web
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    _patch_store_path(monkeypatch, tmp_path)
    monkeypatch.setattr(
        session_create,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    _FakeToolsClient.list_sessions_responses = [
        _FakeListSessionsResponse(
            [
                _FakeSessionInfo(
                    user_session_id="user-1",
                    session_id="instance-1",
                    endpoint="https://sandbox.example.com",
                )
            ]
        )
    ]
    monkeypatch.setattr(cli_web.webbrowser, "open", lambda _url: True)

    result = runner.invoke(
        app,
        ["sandbox", "web", "--session-id", "user-1", "--tool_id", "tool-1"],
    )

    assert result.exit_code == 0
    assert _FakeToolsClient.last_list_sessions_request.tool_id == "tool-1"
    assert json.loads(result.output)["tool_id"] == "tool-1"
    assert json.loads(result.output)["is_new"] is False


def test_cli_web_creates_missing_session_with_requested_id(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_web as cli_web
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    _patch_store_path(monkeypatch, tmp_path)
    monkeypatch.setattr(
        session_create,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    _FakeToolsClient.list_sessions_responses = [_FakeListSessionsResponse([])]

    class CreatedResponse:
        user_session_id = "user-1"
        session_id = "instance-new"
        endpoint = "https://sandbox.example.com"

    _FakeToolsClient.response = CreatedResponse()
    monkeypatch.setattr(cli_web.webbrowser, "open", lambda _url: True)

    result = runner.invoke(
        app,
        ["sandbox", "web", "--session-id", "user-1", "--tool-id", "tool-1"],
    )

    assert result.exit_code == 0
    assert _FakeToolsClient.create_call_count == 1
    assert _FakeToolsClient.last_request.user_session_id == "user-1"
    assert json.loads(result.output) == {
        "url": (
            "https://sandbox.example.com/vnc/index.html?"
            "autoconnect=true&resize=scale&reconnect=1"
        ),
        "tool_id": "tool-1",
        "session_id": "user-1",
        "is_new": True,
    }


def test_cli_web_opens_default_browser(monkeypatch, tmp_path) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_web as cli_web
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    _patch_store_path(monkeypatch, tmp_path)
    monkeypatch.setattr(
        session_create,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    _FakeToolsClient.list_sessions_responses = [
        _FakeListSessionsResponse(
            [
                _FakeSessionInfo(
                    user_session_id="user-1",
                    session_id="instance-1",
                    endpoint="https://sandbox.example.com?token=abc",
                )
            ]
        )
    ]
    opened_urls = []
    monkeypatch.setattr(
        cli_web.webbrowser,
        "open",
        lambda url: opened_urls.append(url) or True,
    )

    result = runner.invoke(
        app,
        [
            "sandbox",
            "web",
            "--session-id",
            "user-1",
            "--tool-id",
            "tool-1",
        ],
    )

    expected_url = (
        "https://sandbox.example.com/vnc/index.html?"
        "autoconnect=true&resize=scale&reconnect=1&token=abc"
    )
    assert result.exit_code == 0
    assert opened_urls == [expected_url]
    assert json.loads(result.output) == {
        "url": expected_url,
        "tool_id": "tool-1",
        "session_id": "user-1",
        "is_new": False,
    }


def test_cli_web_open_reports_browser_failure(monkeypatch, tmp_path) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_web as cli_web
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    _patch_store_path(monkeypatch, tmp_path)
    monkeypatch.setattr(
        session_create,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    _FakeToolsClient.list_sessions_responses = [
        _FakeListSessionsResponse(
            [
                _FakeSessionInfo(
                    user_session_id="user-1",
                    session_id="instance-1",
                    endpoint="https://sandbox.example.com",
                )
            ]
        )
    ]
    monkeypatch.setattr(cli_web.webbrowser, "open", lambda _url: False)

    result = runner.invoke(
        app,
        [
            "sandbox",
            "web",
            "--session-id",
            "user-1",
            "--tool-id",
            "tool-1",
        ],
    )

    assert result.exit_code == 1
    assert "Failed to open browser" in result.output


def test_cli_web_requires_session_id() -> None:
    from agentkit.toolkit.cli.cli import app

    result = runner.invoke(app, ["sandbox", "web"])

    assert result.exit_code != 0
    assert "Missing option" in result.output
    assert "--session-id" in result.output


def test_cli_shell_posts_to_session_endpoint(monkeypatch, tmp_path) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_shell as cli_shell

    store_path = _patch_store_path(monkeypatch, tmp_path)
    stored_session = {
        "session_id": "user-1",
        "tool_id": "tool-1",
        "instance_id": "session-1",
        "endpoint": "https://sandbox.example.com/?token=abc",
    }
    store_path.write_text(
        json.dumps({"user-1": stored_session}),
        encoding="utf-8",
    )
    captured_session = {}
    _patch_shell_session(
        monkeypatch,
        cli_shell,
        stored_session,
        capture=captured_session,
    )

    captured = {}

    class FakeResponse:
        text = '{"success": true}'

        def json(self):
            return {
                "success": True,
                "message": "Command executed",
                "data": {
                    "session_id": "shell-1",
                    "command": "echo 123",
                    "status": "completed",
                    "output": "123",
                    "exit_code": 0,
                },
                "hint": None,
            }

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(cli_shell.requests, "post", fake_post)

    result = runner.invoke(
        app,
        [
            "sandbox",
            "shell",
            "--session-id",
            "user-1",
            "--tool-type",
            "SkillEnv",
            "--command",
            "echo 123",
            "--exec-dir",
            "/workspace",
        ],
    )

    assert result.exit_code == 0
    assert captured_session["tool_type"] == "SkillEnv"
    assert captured["url"] == "https://sandbox.example.com/v1/shell/exec?token=abc"
    assert captured["json"] == {
        "id": "",
        "exec_dir": "/workspace",
        "command": "echo 123",
    }

    payload = json.loads(result.output)
    assert payload["data"]["shell_id"] == "shell-1"
    assert "session_id" not in payload["data"]


def test_cli_shell_rejects_shell_id_option() -> None:
    from agentkit.toolkit.cli.cli import app

    result = runner.invoke(
        app,
        [
            "sandbox",
            "shell",
            "--session-id",
            "user-1",
            "--command",
            "echo 123",
            "--shell-id",
            "shell-1",
        ],
    )

    assert result.exit_code != 0
    assert "No such option" in result.output
    assert "--shell-id" in result.output


def test_cli_shell_uploads_sources_before_command(monkeypatch, tmp_path) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_shell as cli_shell

    file_one = tmp_path / "one.txt"
    file_two = tmp_path / "two.txt"
    file_one.write_text("one", encoding="utf-8")
    file_two.write_text("two", encoding="utf-8")
    stored_session = {
        "session_id": "user-1",
        "tool_id": "tool-1",
        "instance_id": "session-1",
        "endpoint": "https://sandbox.example.com",
    }
    _patch_shell_session(monkeypatch, cli_shell, stored_session)
    events = []

    def fake_upload_source_before_exec(session, *, workspace, src_dirs, dst_dir):
        events.append(
            (
                "upload",
                session,
                workspace,
                [str(src_dir) for src_dir in src_dirs],
                dst_dir,
            )
        )

    class FakeResponse:
        text = '{"success": true}'

        def json(self):
            return {
                "success": True,
                "data": {
                    "session_id": "shell-1",
                    "status": "completed",
                    "output": "done",
                    "exit_code": 0,
                },
            }

    def fake_post(url, json, timeout):
        events.append(("post", url, json, timeout))
        return FakeResponse()

    monkeypatch.setattr(
        cli_shell,
        "_upload_source_before_exec",
        fake_upload_source_before_exec,
    )
    monkeypatch.setattr(cli_shell.requests, "post", fake_post)

    result = runner.invoke(
        app,
        [
            "sandbox",
            "shell",
            "--session-id",
            "user-1",
            "--command",
            "echo done",
            "--src-dir",
            str(file_one),
            str(file_two),
            "--workspace",
            "/workspace",
            "--dst-dir",
            "project",
        ],
    )

    assert result.exit_code == 0
    assert events == [
        (
            "upload",
            stored_session,
            "/workspace",
            [str(file_one), str(file_two)],
            "project",
        ),
        (
            "post",
            "https://sandbox.example.com/v1/shell/exec",
            {"id": "", "exec_dir": "", "command": "echo done"},
            cli_shell.SANDBOX_EXEC_TIMEOUT_SECONDS,
        ),
    ]
    payload = json.loads(result.output)
    assert payload["data"]["shell_id"] == "shell-1"


def test_cli_shell_uploads_directory_as_directory_before_command(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_exec as cli_exec
    import agentkit.toolkit.cli.sandbox.cli_shell as cli_shell

    source_dir = tmp_path / "shell_dir"
    source_dir.mkdir()
    (source_dir / "hello.txt").write_text("hello", encoding="utf-8")
    stored_session = {
        "session_id": "user-1",
        "tool_id": "tool-1",
        "instance_id": "session-1",
        "endpoint": "https://sandbox.example.com",
    }
    _patch_shell_session(monkeypatch, cli_shell, stored_session)
    monkeypatch.setattr(
        cli_exec,
        "_new_remote_archive_path",
        lambda _prefix: "/tmp/agentkit-upload.tar",
    )
    captured = {}

    def fake_upload_remote_file(_session, *, local_path, remote_path):
        assert remote_path == "/tmp/agentkit-upload.tar"
        with tarfile.open(local_path, mode="r") as tar:
            captured["archive_names"] = sorted(
                member.name for member in tar.getmembers()
            )

    def fake_exec_shell_command(_session, command):
        captured["extract_command"] = command
        return {"success": True}

    class FakeResponse:
        text = '{"success": true}'

        def json(self):
            return {
                "success": True,
                "data": {
                    "session_id": "shell-1",
                    "status": "completed",
                    "output": "done",
                    "exit_code": 0,
                },
            }

    def fake_post(url, json, timeout):
        captured["post"] = (url, json, timeout)
        return FakeResponse()

    monkeypatch.setattr(cli_exec, "_upload_remote_file", fake_upload_remote_file)
    monkeypatch.setattr(cli_exec, "_exec_shell_command", fake_exec_shell_command)
    monkeypatch.setattr(cli_shell.requests, "post", fake_post)

    result = runner.invoke(
        app,
        [
            "sandbox",
            "shell",
            "--session-id",
            "user-1",
            "--command",
            "echo done",
            "--src-dir",
            str(source_dir),
            "--workspace",
            "/workspace",
            "--dst-dir",
            "tmp",
        ],
    )

    assert result.exit_code == 0
    assert captured["archive_names"] == ["shell_dir", "shell_dir/hello.txt"]
    assert captured["extract_command"] == (
        "mkdir -p /workspace/tmp && tar -xf /tmp/agentkit-upload.tar "
        "-C /workspace/tmp; status=$?; rm -f /tmp/agentkit-upload.tar; "
        "[ $status -eq 0 ]"
    )
    assert captured["post"] == (
        "https://sandbox.example.com/v1/shell/exec",
        {"id": "", "exec_dir": "", "command": "echo done"},
        cli_shell.SANDBOX_EXEC_TIMEOUT_SECONDS,
    )


def test_cli_shell_git_config_file_does_not_reuse_shell_exec_id(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_shell as cli_shell
    import agentkit.toolkit.cli.sandbox.git_config as git_config

    config_path = tmp_path / "git.json"
    config_path.write_text(
        json.dumps({"user": {"name": "Ada Lovelace", "email": "ada@example.com"}}),
        encoding="utf-8",
    )
    stored_session = {
        "session_id": "user-1",
        "tool_id": "tool-1",
        "instance_id": "session-1",
        "endpoint": "https://sandbox.example.com",
    }
    _patch_shell_session(monkeypatch, cli_shell, stored_session)
    events = []

    def fake_exec_shell_command(session, command, *, shell_id="", **_kwargs):
        events.append(("git-config", session, command, shell_id))
        return {"data": {"session_id": "shell-from-git", "exit_code": 0}}

    class FakeResponse:
        text = '{"success": true}'

        def json(self):
            return {
                "success": True,
                "data": {
                    "session_id": "shell-from-git",
                    "status": "completed",
                    "output": "done",
                    "exit_code": 0,
                },
            }

    def fake_post(url, json, timeout):
        events.append(("post", url, json, timeout))
        return FakeResponse()

    monkeypatch.setattr(git_config, "_exec_shell_command", fake_exec_shell_command)
    monkeypatch.setattr(cli_shell.requests, "post", fake_post)

    result = runner.invoke(
        app,
        [
            "sandbox",
            "shell",
            "--session-id",
            "user-1",
            "--git-config",
            str(config_path),
            "--command",
            "git status",
        ],
    )

    assert result.exit_code == 0
    assert events == [
        (
            "git-config",
            stored_session,
            "git config --global user.name 'Ada Lovelace'; "
            "git config --global user.email ada@example.com",
            "",
        ),
        (
            "post",
            "https://sandbox.example.com/v1/shell/exec",
            {"id": "", "exec_dir": "", "command": "git status"},
            cli_shell.SANDBOX_EXEC_TIMEOUT_SECONDS,
        ),
    ]
    payload = json.loads(result.output)
    assert payload["data"]["shell_id"] == "shell-from-git"


def test_cli_shell_git_config_missing_file_errors(monkeypatch, tmp_path) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_shell as cli_shell

    stored_session = {
        "session_id": "user-1",
        "tool_id": "tool-1",
        "instance_id": "session-1",
        "endpoint": "https://sandbox.example.com",
    }
    _patch_shell_session(monkeypatch, cli_shell, stored_session)
    posted = {"value": False}
    monkeypatch.setattr(
        cli_shell.requests,
        "post",
        lambda *_args, **_kwargs: posted.update(value=True),
    )

    result = runner.invoke(
        app,
        [
            "sandbox",
            "shell",
            "--session-id",
            "user-1",
            "--git-config",
            str(tmp_path / "missing.ini"),
            "--command",
            "git status",
        ],
    )

    assert result.exit_code == 1
    assert "Git config file not found" in result.output
    assert posted["value"] is False


def test_resolve_git_config_local_reads_git_values(monkeypatch) -> None:
    import agentkit.toolkit.cli.sandbox.git_config as git_config

    calls = []

    class FakeCompletedProcess:
        def __init__(self, stdout="", stderr="", returncode=0):
            self.stdout = stdout
            self.stderr = stderr
            self.returncode = returncode

    def fake_run(args, **_kwargs):
        calls.append(args)
        if args == ["git", "config", "--list"]:
            return FakeCompletedProcess(
                stdout="user.name=Ada Lovelace\nuser.email=ada@example.com\n"
            )
        if args == ["git", "config", "--get", "user.name"]:
            return FakeCompletedProcess(stdout="Ada Lovelace\n")
        if args == ["git", "config", "--get", "user.email"]:
            return FakeCompletedProcess(stdout="ada@example.com\n")
        raise AssertionError(args)

    monkeypatch.setattr(git_config.shutil, "which", lambda _name: "/usr/bin/git")
    monkeypatch.setattr(git_config.subprocess, "run", fake_run)

    assert git_config.resolve_git_config("local") == (
        "Ada Lovelace",
        "ada@example.com",
    )
    assert calls == [
        ["git", "config", "--list"],
        ["git", "config", "--get", "user.name"],
        ["git", "config", "--get", "user.email"],
    ]


def test_resolve_git_config_local_rejects_empty_git_config(monkeypatch) -> None:
    import agentkit.toolkit.cli.sandbox.git_config as git_config

    class FakeCompletedProcess:
        stdout = ""
        stderr = ""
        returncode = 0

    monkeypatch.setattr(git_config.shutil, "which", lambda _name: "/usr/bin/git")
    monkeypatch.setattr(
        git_config.subprocess,
        "run",
        lambda *_args, **_kwargs: FakeCompletedProcess(),
    )

    with pytest.raises(ValueError, match="Local git config is empty"):
        git_config.resolve_git_config("local")


def test_resolve_git_config_ini_supports_flat_user_keys(tmp_path) -> None:
    import agentkit.toolkit.cli.sandbox.git_config as git_config

    config_path = tmp_path / "gitconfig"
    config_path.write_text(
        "user.name = Ada Lovelace\nuser.email = ada@example.com\n",
        encoding="utf-8",
    )

    assert git_config.resolve_git_config(str(config_path)) == (
        "Ada Lovelace",
        "ada@example.com",
    )


def test_cli_shell_rejects_extra_source_without_src_dir(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_shell as cli_shell

    file_one = tmp_path / "one.txt"
    file_one.write_text("one", encoding="utf-8")
    stored_session = {
        "session_id": "user-1",
        "tool_id": "tool-1",
        "instance_id": "session-1",
        "endpoint": "https://sandbox.example.com",
    }
    _patch_shell_session(monkeypatch, cli_shell, stored_session)
    posted = {"value": False}

    def fake_post(*_args, **_kwargs):
        posted["value"] = True

    monkeypatch.setattr(cli_shell.requests, "post", fake_post)

    result = runner.invoke(
        app,
        [
            "sandbox",
            "shell",
            "--session-id",
            "user-1",
            "--command",
            "echo done",
            str(file_one),
        ],
    )

    assert result.exit_code == 1
    assert "Additional source paths require --src-dir" in result.output
    assert posted["value"] is False


def test_cli_shell_requires_command() -> None:
    from agentkit.toolkit.cli.cli import app

    result = runner.invoke(
        app,
        ["sandbox", "shell", "--session-id", "user-1"],
    )

    assert result.exit_code != 0
    assert "--command" in result.output


def test_cli_shell_creates_session_when_session_id_omitted(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.session_create as session_create
    import agentkit.toolkit.cli.sandbox.cli_shell as cli_shell

    store_path = _patch_store_path(monkeypatch, tmp_path)
    monkeypatch.setattr(
        session_create,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    captured = {}

    class FakeResponse:
        text = '{"success": true}'

        def json(self):
            return {
                "success": True,
                "message": "Command executed",
                "data": {
                    "session_id": "shell-1",
                    "command": "echo 123",
                    "status": "completed",
                    "output": "123",
                    "exit_code": 0,
                },
                "hint": None,
            }

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(cli_shell.requests, "post", fake_post)

    result = runner.invoke(
        app,
        [
            "sandbox",
            "shell",
            "--tool-id",
            "tool-cli",
            "--command",
            "echo 123",
        ],
    )

    assert result.exit_code == 0
    assert _FakeToolsClient.create_call_count == 1
    assert _FakeToolsClient.get_call_count == 0
    assert _FakeToolsClient.last_request.tool_id == "tool-cli"
    assert _FakeToolsClient.last_request.user_session_id
    assert captured["url"] == "https://sandbox.example.com/v1/shell/exec"

    payload = json.loads(result.output)
    assert payload["data"]["shell_id"] == "shell-1"
    stored = json.loads(store_path.read_text(encoding="utf-8"))
    assert stored["user-session-from-api"]["tool_id"] == "tool-cli"


def test_cli_exec_connects_to_ws_endpoint(monkeypatch, tmp_path) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_exec as cli_exec

    store_path = _patch_store_path(monkeypatch, tmp_path)
    stored_session = {
        "session_id": "user-1",
        "tool_id": "tool-1",
        "instance_id": "session-1",
        "endpoint": "https://sandbox.example.com/?token=abc",
    }
    store_path.write_text(
        json.dumps({"user-1": stored_session}),
        encoding="utf-8",
    )
    _patch_exec_session(monkeypatch, cli_exec, stored_session)
    captured = {}

    def fake_connect(ws_url, initial_command, on_shell_id=None):
        captured["ws_url"] = ws_url
        captured["initial_command"] = initial_command
        captured["on_shell_id"] = on_shell_id

    monkeypatch.setattr(cli_exec, "_connect_terminal", fake_connect)

    result = runner.invoke(
        app,
        ["sandbox", "exec", "--session-id", "user-1"],
    )

    assert result.exit_code == 0
    assert captured["ws_url"] == "ws://sandbox.example.com/v1/shell/ws?token=abc"
    assert captured["initial_command"] is None
    assert captured["on_shell_id"] is not None


def test_cli_exec_runs_command_option(monkeypatch, tmp_path) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_exec as cli_exec

    store_path = _patch_store_path(monkeypatch, tmp_path)
    stored_session = {
        "session_id": "user-1",
        "tool_id": "tool-1",
        "instance_id": "session-1",
        "endpoint": "https://sandbox.example.com/?token=abc",
    }
    store_path.write_text(
        json.dumps({"user-1": stored_session}),
        encoding="utf-8",
    )
    _patch_exec_session(monkeypatch, cli_exec, stored_session)
    captured = {}

    def fake_connect(ws_url, initial_command, on_shell_id=None):
        captured["ws_url"] = ws_url
        captured["initial_command"] = initial_command

    monkeypatch.setattr(cli_exec, "_connect_terminal", fake_connect)

    result = runner.invoke(
        app,
        [
            "sandbox",
            "exec",
            "--session-id",
            "user-1",
            "--command",
            "codex",
        ],
    )

    assert result.exit_code == 0
    assert captured["ws_url"] == "ws://sandbox.example.com/v1/shell/ws?token=abc"
    assert captured["initial_command"] == "codex"


def test_cli_exec_tmux_mode_wraps_command(monkeypatch, tmp_path) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_exec as cli_exec

    store_path = _patch_store_path(monkeypatch, tmp_path)
    stored_session = {
        "session_id": "user-1",
        "tool_id": "tool-1",
        "instance_id": "session-1",
        "endpoint": "https://sandbox.example.com/?token=abc",
    }
    store_path.write_text(
        json.dumps({"user-1": stored_session}),
        encoding="utf-8",
    )
    _patch_exec_session(monkeypatch, cli_exec, stored_session)
    captured = {}

    def fake_connect(ws_url, initial_command, on_shell_id=None):
        captured["ws_url"] = ws_url
        captured["initial_command"] = initial_command

    monkeypatch.setattr(cli_exec, "_connect_terminal", fake_connect)

    result = runner.invoke(
        app,
        [
            "sandbox",
            "exec",
            "--session-id",
            "user-1",
            "--mode",
            "tmux",
            "--command",
            "codex --dangerously-bypass-approvals-and-sandbox",
        ],
    )

    assert result.exit_code == 0
    assert captured["ws_url"] == "ws://sandbox.example.com/v1/shell/ws?token=abc"
    assert captured["initial_command"] == (
        "tmux has-session -t user-1 2>/dev/null && tmux a -t user-1 "
        "|| tmux new -s user-1 codex --dangerously-bypass-approvals-and-sandbox"
    )


def test_cli_exec_empty_mode_keeps_command(monkeypatch, tmp_path) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_exec as cli_exec

    store_path = _patch_store_path(monkeypatch, tmp_path)
    stored_session = {
        "session_id": "user-1",
        "tool_id": "tool-1",
        "instance_id": "session-1",
        "endpoint": "https://sandbox.example.com/?token=abc",
    }
    store_path.write_text(
        json.dumps({"user-1": stored_session}),
        encoding="utf-8",
    )
    _patch_exec_session(monkeypatch, cli_exec, stored_session)
    captured = {}

    def fake_connect(ws_url, initial_command, on_shell_id=None):
        captured["initial_command"] = initial_command

    monkeypatch.setattr(cli_exec, "_connect_terminal", fake_connect)

    result = runner.invoke(
        app,
        [
            "sandbox",
            "exec",
            "--session-id",
            "user-1",
            "--mode",
            "",
            "--command",
            "codex",
        ],
    )

    assert result.exit_code == 0
    assert captured["initial_command"] == "codex"


def test_cli_exec_rejects_unknown_mode() -> None:
    from agentkit.toolkit.cli.cli import app

    result = runner.invoke(
        app,
        ["sandbox", "exec", "--mode", "screen"],
    )

    assert result.exit_code == 1
    assert "--mode must be empty or tmux" in result.output


def test_cli_sandbox_run_reads_yaml_and_prints_dry_run(tmp_path) -> None:
    from agentkit.toolkit.cli.cli import app

    config_path = tmp_path / "sandbox-run.yaml"
    config_path.write_text(
        """
exec:
  - name: left
    cwd: .
    session_id: user-left
    tool_id: tool-1
    command: codex
    mode: tmux
    src_dir: ./workspace
    extra_sources:
      - ./README.md
    dst_dir: project
  - name: right
    args:
      - --session-id
      - user-right
      - --command
      - opencode
""",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "sandbox",
            "run",
            "--config",
            str(config_path),
            "--terminal",
            "2",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    assert "agentkit sandbox exec" in result.output
    assert "--session-id user-left" in result.output
    assert "--tool-id tool-1" in result.output
    assert "--mode tmux" in result.output
    assert "--command codex" in result.output
    assert "--src-dir ./workspace ./README.md" in result.output
    assert "--dst-dir project" in result.output
    assert "--session-id user-right --command opencode" in result.output


def test_cli_sandbox_run_errors_when_terminal_exceeds_yaml_entries(
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app

    config_path = tmp_path / "sandbox-run.yaml"
    config_path.write_text(
        """
tabs:
  - session_id: user-left
""",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "sandbox",
            "run",
            "--config",
            str(config_path),
            "--terminal",
            "4",
            "--dry-run",
        ],
    )

    assert result.exit_code == 1
    assert "contains 1 exec entries" in result.output
    assert "--terminal requested 4" in result.output


def test_cli_sandbox_run_opens_terminal_tmux_grid_without_system_events(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_run as cli_run

    config_path = tmp_path / "sandbox-run.yaml"
    config_path.write_text(
        """
exec:
  - session_id: user-left
  - session_id: user-right
""",
        encoding="utf-8",
    )
    captured = {}

    def fake_run(args, check):
        captured["args"] = args
        captured["check"] = check

    def fake_mkdtemp(prefix):
        scripts_dir.mkdir()
        return str(scripts_dir)

    scripts_dir = tmp_path / "tmux-scripts"
    monkeypatch.setattr(cli_run.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(cli_run.shutil, "which", lambda _name: "/opt/homebrew/bin/tmux")
    monkeypatch.setattr(cli_run.tempfile, "mkdtemp", fake_mkdtemp)
    monkeypatch.setattr(cli_run.subprocess, "run", fake_run)

    result = runner.invoke(
        app,
        [
            "sandbox",
            "run",
            "--config",
            str(config_path),
            "--terminal",
            "2",
        ],
    )

    assert result.exit_code == 0
    assert captured["check"] is True
    script = captured["args"][2]
    assert captured["args"][:2] == ["osascript", "-e"]
    assert "System Events" not in script
    assert "make new tab" not in script
    assert script.count("do script") == 1
    assert f"/bin/zsh {scripts_dir / 'run.zsh'}" in script

    launcher = (scripts_dir / "run.zsh").read_text(encoding="utf-8")
    assert "TMUX_BIN=/opt/homebrew/bin/tmux" in launcher
    assert "new-session -d -s" in launcher
    assert launcher.count("split-window") == 1
    assert "select-layout" in launcher
    assert "attach-session" in launcher

    pane_1 = (scripts_dir / "pane-1.zsh").read_text(encoding="utf-8")
    pane_2 = (scripts_dir / "pane-2.zsh").read_text(encoding="utf-8")
    assert "agentkit sandbox exec --session-id user-left" in pane_1
    assert "agentkit sandbox exec --session-id user-right" in pane_2


def test_cli_sandbox_run_executes_single_entry_inline_on_non_macos(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_run as cli_run

    config_path = tmp_path / "sandbox-run.yaml"
    config_path.write_text(
        """
exec:
  - session_id: run-model-base-url
    model_name: run-model
    model_base_url: https://run.example.com/v1
    command: "printenv CODEX_MODEL; exit"
""",
        encoding="utf-8",
    )
    captured = {}

    def fake_run(args, check):
        captured["args"] = args
        captured["check"] = check

    monkeypatch.setattr(cli_run.platform, "system", lambda: "Linux")
    monkeypatch.setattr(cli_run.subprocess, "run", fake_run)

    result = runner.invoke(
        app,
        [
            "sandbox",
            "run",
            "--config",
            str(config_path),
            "--terminal",
            "1",
        ],
    )

    assert result.exit_code == 0
    assert captured["check"] is True
    assert captured["args"][:2] == ["/bin/sh", "-c"]
    command = captured["args"][2]
    assert "agentkit sandbox exec" in command
    assert "--session-id run-model-base-url" in command
    assert "--model-name run-model" in command
    assert "--model-base-url https://run.example.com/v1" in command


def test_cli_exec_git_config_file_does_not_reuse_shell_exec_id_for_ws(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_exec as cli_exec
    import agentkit.toolkit.cli.sandbox.git_config as git_config

    config_path = tmp_path / "git.toml"
    config_path.write_text(
        '[user]\nname = "Ada Lovelace"\nemail = "ada@example.com"\n',
        encoding="utf-8",
    )
    store_path = _patch_store_path(monkeypatch, tmp_path)
    stored_session = {
        "session_id": "user-1",
        "tool_id": "tool-1",
        "instance_id": "session-1",
        "endpoint": "https://sandbox.example.com/?token=abc",
    }
    store_path.write_text(
        json.dumps({"user-1": stored_session}),
        encoding="utf-8",
    )
    _patch_exec_session(monkeypatch, cli_exec, stored_session)
    captured = {}

    def fake_exec_shell_command(session, command, *, shell_id="", **_kwargs):
        captured["git_config"] = (session, command, shell_id)
        return {"data": {"session_id": "shell-from-git", "exit_code": 0}}

    def fake_connect(ws_url, initial_command, on_shell_id=None):
        captured["ws_url"] = ws_url
        captured["initial_command"] = initial_command
        captured["on_shell_id"] = on_shell_id

    monkeypatch.setattr(git_config, "_exec_shell_command", fake_exec_shell_command)
    monkeypatch.setattr(cli_exec, "_connect_terminal", fake_connect)

    result = runner.invoke(
        app,
        [
            "sandbox",
            "exec",
            "--session-id",
            "user-1",
            "--git-config",
            str(config_path),
            "--command",
            "codex",
        ],
    )

    assert result.exit_code == 0
    assert captured["git_config"] == (
        stored_session,
        "git config --global user.name 'Ada Lovelace'; "
        "git config --global user.email ada@example.com",
        "",
    )
    assert captured["ws_url"] == "ws://sandbox.example.com/v1/shell/ws?token=abc"
    assert captured["initial_command"] == "codex"
    assert captured["on_shell_id"] is not None
    stored = json.loads(store_path.read_text(encoding="utf-8"))
    assert "terminal_shell_id" not in stored["user-1"]


def test_cli_exec_uploads_directory_before_connecting(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_exec as cli_exec

    upload_dir = tmp_path / "upload-src"
    upload_dir.mkdir()
    (upload_dir / "hello.txt").write_text("hello", encoding="utf-8")
    stored_session = {
        "session_id": "user-1",
        "tool_id": "tool-1",
        "instance_id": "session-1",
        "endpoint": "https://sandbox.example.com/?token=abc",
    }
    _patch_exec_session(monkeypatch, cli_exec, stored_session)
    monkeypatch.setattr(
        cli_exec,
        "_new_remote_archive_path",
        lambda _prefix: "/tmp/agentkit-upload.tar",
    )

    events = []

    def fake_upload_remote_file(session, *, local_path, remote_path):
        assert session == stored_session
        assert local_path.exists()
        assert remote_path == "/tmp/agentkit-upload.tar"
        events.append(("upload", remote_path))
        with tarfile.open(local_path, mode="r") as tar:
            events.append(
                ("archive", sorted(member.name for member in tar.getmembers()))
            )

    def fake_exec_shell_command(session, command):
        assert session == stored_session
        events.append(("extract", command))
        return {"success": True}

    def fake_connect(ws_url, initial_command, on_shell_id=None):
        events.append(("connect", ws_url, initial_command))

    monkeypatch.setattr(cli_exec, "_upload_remote_file", fake_upload_remote_file)
    monkeypatch.setattr(cli_exec, "_exec_shell_command", fake_exec_shell_command)
    monkeypatch.setattr(cli_exec, "_connect_terminal", fake_connect)

    result = runner.invoke(
        app,
        [
            "sandbox",
            "exec",
            "--session-id",
            "user-1",
            "--src-dir",
            str(upload_dir),
            "--command",
            "codex",
        ],
    )

    assert result.exit_code == 0
    assert events == [
        ("upload", "/tmp/agentkit-upload.tar"),
        ("archive", ["upload-src", "upload-src/hello.txt"]),
        (
            "extract",
            "mkdir -p /home/gem && tar -xf /tmp/agentkit-upload.tar "
            "-C /home/gem; status=$?; rm -f /tmp/agentkit-upload.tar; "
            "[ $status -eq 0 ]",
        ),
        ("connect", "ws://sandbox.example.com/v1/shell/ws?token=abc", "codex"),
    ]


def test_cli_exec_upload_dir_resolves_relative_dst_dir_inside_workspace(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_exec as cli_exec

    upload_dir = tmp_path / "upload-src"
    upload_dir.mkdir()
    (upload_dir / "hello.txt").write_text("hello", encoding="utf-8")
    stored_session = {
        "session_id": "user-1",
        "tool_id": "tool-1",
        "instance_id": "session-1",
        "endpoint": "https://sandbox.example.com",
    }
    _patch_exec_session(monkeypatch, cli_exec, stored_session)
    monkeypatch.setattr(
        cli_exec,
        "_new_remote_archive_path",
        lambda _prefix: "/tmp/agentkit-upload.tar",
    )
    monkeypatch.setattr(
        cli_exec,
        "_upload_remote_file",
        lambda *_args, **_kwargs: None,
    )
    captured = {}

    def fake_exec_shell_command(_session, command):
        captured["command"] = command
        return {"success": True}

    def fake_connect(_ws_url, initial_command=None, on_shell_id=None):
        captured["connected"] = True

    monkeypatch.setattr(cli_exec, "_exec_shell_command", fake_exec_shell_command)
    monkeypatch.setattr(cli_exec, "_connect_terminal", fake_connect)

    result = runner.invoke(
        app,
        [
            "sandbox",
            "exec",
            "--session-id",
            "user-1",
            "--src-dir",
            str(upload_dir),
            "--workspace",
            "/workspace",
            "--dst-dir",
            "project",
        ],
    )

    assert result.exit_code == 0
    assert (
        captured["command"]
        == "mkdir -p /workspace/project && tar -xf /tmp/agentkit-upload.tar "
        "-C /workspace/project; status=$?; rm -f /tmp/agentkit-upload.tar; "
        "[ $status -eq 0 ]"
    )
    assert captured["connected"] is True


def test_cli_exec_uploads_repeated_sources_before_connecting(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_exec as cli_exec

    file_one = tmp_path / "one.txt"
    file_two = tmp_path / "two.txt"
    file_one.write_text("one", encoding="utf-8")
    file_two.write_text("two", encoding="utf-8")
    stored_session = {
        "session_id": "user-1",
        "tool_id": "tool-1",
        "instance_id": "session-1",
        "endpoint": "https://sandbox.example.com",
    }
    _patch_exec_session(monkeypatch, cli_exec, stored_session)
    monkeypatch.setattr(
        cli_exec,
        "_new_remote_archive_path",
        lambda _prefix: "/tmp/agentkit-upload.tar",
    )
    uploaded = {}
    captured = {}

    def fake_upload_remote_file(_session, *, local_path, remote_path):
        uploaded["local_path"] = local_path
        uploaded["remote_path"] = remote_path

    def fake_exec_shell_command(_session, command):
        captured["command"] = command
        return {"success": True}

    def fake_connect(_ws_url, initial_command=None, on_shell_id=None):
        captured["connected"] = True

    monkeypatch.setattr(cli_exec, "_upload_remote_file", fake_upload_remote_file)
    monkeypatch.setattr(cli_exec, "_exec_shell_command", fake_exec_shell_command)
    monkeypatch.setattr(cli_exec, "_connect_terminal", fake_connect)

    result = runner.invoke(
        app,
        [
            "sandbox",
            "exec",
            "--session-id",
            "user-1",
            "--src-dir",
            str(file_one),
            str(file_two),
            "--workspace",
            "/workspace",
            "--dst-dir",
            "project",
        ],
    )

    assert result.exit_code == 0
    assert uploaded["remote_path"] == "/tmp/agentkit-upload.tar"
    assert not uploaded["local_path"].exists()
    assert (
        captured["command"]
        == "mkdir -p /workspace/project && tar -xf /tmp/agentkit-upload.tar "
        "-C /workspace/project; status=$?; rm -f /tmp/agentkit-upload.tar; "
        "[ $status -eq 0 ]"
    )
    assert captured["connected"] is True


def test_cli_exec_upload_rejects_duplicate_source_names(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_exec as cli_exec

    dir_one = tmp_path / "one"
    dir_two = tmp_path / "two"
    dir_one.mkdir()
    dir_two.mkdir()
    file_one = dir_one / "same.txt"
    file_two = dir_two / "same.txt"
    file_one.write_text("one", encoding="utf-8")
    file_two.write_text("two", encoding="utf-8")
    stored_session = {
        "session_id": "user-1",
        "tool_id": "tool-1",
        "instance_id": "session-1",
        "endpoint": "https://sandbox.example.com",
    }
    _patch_exec_session(monkeypatch, cli_exec, stored_session)
    connected = {"value": False}
    monkeypatch.setattr(
        cli_exec,
        "_connect_terminal",
        lambda *_args, **_kwargs: connected.update(value=True),
    )

    result = runner.invoke(
        app,
        [
            "sandbox",
            "exec",
            "--session-id",
            "user-1",
            "--src-dir",
            str(file_one),
            str(file_two),
        ],
    )

    assert result.exit_code == 1
    assert "Duplicate source name: same.txt" in result.output
    assert connected["value"] is False


def test_cli_exec_rejects_extra_source_without_src_dir(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_exec as cli_exec

    file_one = tmp_path / "one.txt"
    file_one.write_text("one", encoding="utf-8")
    stored_session = {
        "session_id": "user-1",
        "tool_id": "tool-1",
        "instance_id": "session-1",
        "endpoint": "https://sandbox.example.com",
    }
    _patch_exec_session(monkeypatch, cli_exec, stored_session)
    connected = {"value": False}
    monkeypatch.setattr(
        cli_exec,
        "_connect_terminal",
        lambda *_args, **_kwargs: connected.update(value=True),
    )

    result = runner.invoke(
        app,
        [
            "sandbox",
            "exec",
            "--session-id",
            "user-1",
            str(file_one),
        ],
    )

    assert result.exit_code == 1
    assert "Additional source paths require --src-dir" in result.output
    assert connected["value"] is False


def test_cli_exec_upload_rejects_absolute_dst_dir(monkeypatch, tmp_path) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_exec as cli_exec

    upload_dir = tmp_path / "upload-src"
    upload_dir.mkdir()
    stored_session = {
        "session_id": "user-1",
        "tool_id": "tool-1",
        "instance_id": "session-1",
        "endpoint": "https://sandbox.example.com",
    }
    _patch_exec_session(monkeypatch, cli_exec, stored_session)
    connected = {"value": False}
    monkeypatch.setattr(
        cli_exec,
        "_connect_terminal",
        lambda *_args, **_kwargs: connected.update(value=True),
    )

    result = runner.invoke(
        app,
        [
            "sandbox",
            "exec",
            "--session-id",
            "user-1",
            "--src-dir",
            str(upload_dir),
            "--dst-dir",
            "/absolute",
        ],
    )

    assert result.exit_code == 1
    assert "--dst-dir must be relative to --workspace" in result.output
    assert connected["value"] is False


def test_cli_exec_passes_model_options_to_session_create(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_exec as cli_exec

    store_path = _patch_store_path(monkeypatch, tmp_path)
    stored_session = {
        "session_id": "user-1",
        "tool_id": "tool-1",
        "instance_id": "session-1",
        "endpoint": "https://sandbox.example.com/?token=abc",
    }
    store_path.write_text(
        json.dumps({"user-1": stored_session}),
        encoding="utf-8",
    )
    captured_session = {}
    _patch_exec_session(
        monkeypatch,
        cli_exec,
        stored_session,
        capture=captured_session,
    )

    def fake_connect(_ws_url, initial_command=None, on_shell_id=None):
        assert initial_command is None
        assert on_shell_id is not None

    monkeypatch.setattr(cli_exec, "_connect_terminal", fake_connect)

    result = runner.invoke(
        app,
        [
            "sandbox",
            "exec",
            "--session-id",
            "user-1",
            "--tool-type",
            "SkillEnv",
            "--model-provider",
            "coding_plan",
            "--model-name",
            "glm-5.2",
            "--model-api-key",
            "model-value",
        ],
    )

    assert result.exit_code == 0
    assert captured_session["session_id"] == "user-1"
    assert captured_session["tool_type"] == "SkillEnv"
    assert [(item.key, item.value) for item in captured_session["envs"]] == [
        ("AGENTKIT_SANDBOX_MODEL_PROVIDER", "coding_plan"),
        ("OPENCODE_MODEL", "glm-5.2"),
        ("CODEX_MODEL", "glm-5.2"),
        ("ANTHROPIC_MODEL", "glm-5.2"),
        ("OPENCODE_BASE_URL", "https://ark.cn-beijing.volces.com/api/coding/v3"),
        ("CODEX_BASE_URL", "https://ark.cn-beijing.volces.com/api/coding/v3"),
        ("MODEL_BASE_URL", "https://ark.cn-beijing.volces.com/api/coding/v3"),
        ("ANTHROPIC_BASE_URL", "https://ark.cn-beijing.volces.com/api/coding"),
        ("OPENCODE_API_KEY", "model-value"),
        ("CODEX_API_KEY", "model-value"),
        ("ANTHROPIC_AUTH_TOKEN", "model-value"),
    ]


def test_cli_exec_model_name_without_provider_syncs_codex_config(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_exec as cli_exec

    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    store_path = _patch_store_path(monkeypatch, tmp_path)
    stored_session = {
        "session_id": "user-1",
        "tool_id": "tool-1",
        "instance_id": "session-1",
        "endpoint": "https://sandbox.example.com/?token=abc",
    }
    store_path.write_text(
        json.dumps({"user-1": stored_session}),
        encoding="utf-8",
    )
    captured_session = {}
    _patch_exec_session(
        monkeypatch,
        cli_exec,
        stored_session,
        capture=captured_session,
    )
    monkeypatch.setattr(
        cli_exec,
        "_connect_terminal",
        lambda *_args, **_kwargs: None,
    )

    result = runner.invoke(
        app,
        [
            "sandbox",
            "exec",
            "--session-id",
            "user-1",
            "--model-name",
            "glm-5.2",
        ],
    )

    assert result.exit_code == 0
    envs = {item.key: item.value for item in captured_session["envs"]}
    assert list(envs) == [
        "OPENCODE_MODEL",
        "CODEX_MODEL",
        "ANTHROPIC_MODEL",
        "CODEX_CONFIG_TOML",
        "CODEX_MODEL_CATALOG_JSON",
    ]
    assert envs["OPENCODE_MODEL"] == "glm-5.2"
    assert envs["CODEX_MODEL"] == "glm-5.2"
    assert envs["ANTHROPIC_MODEL"] == "glm-5.2"
    assert 'model_provider = "model_square"' in envs["CODEX_CONFIG_TOML"]
    assert "[model_providers.model_square]" in envs["CODEX_CONFIG_TOML"]
    catalog = json.loads(envs["CODEX_MODEL_CATALOG_JSON"])
    assert catalog["models"][0]["slug"] == "glm-5.2"


def test_cli_exec_model_name_uses_cached_tool_model_provider(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_exec as cli_exec

    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    store_path = _patch_store_path(monkeypatch, tmp_path)
    tool_store_path = _patch_tool_store_path(monkeypatch, tmp_path)
    tool_store_path.parent.mkdir(parents=True, exist_ok=True)
    tool_store_path.write_text(
        json.dumps(
            {
                "CodeEnv": {
                    "ToolId": "tool-1",
                    "ToolType": "CodeEnv",
                    "Name": "agent-plan-tool",
                    "Status": "Ready",
                    "ModelProvider": "agent_plan",
                }
            }
        ),
        encoding="utf-8",
    )
    stored_session = {
        "session_id": "user-1",
        "tool_id": "tool-1",
        "instance_id": "session-1",
        "endpoint": "https://sandbox.example.com/?token=abc",
    }
    store_path.write_text(
        json.dumps({"user-1": stored_session}),
        encoding="utf-8",
    )
    captured_session = {}
    _patch_exec_session(
        monkeypatch,
        cli_exec,
        stored_session,
        capture=captured_session,
    )
    monkeypatch.setattr(
        cli_exec,
        "_connect_terminal",
        lambda *_args, **_kwargs: None,
    )

    result = runner.invoke(
        app,
        [
            "sandbox",
            "exec",
            "--tool-id",
            "tool-1",
            "--session-id",
            "user-1",
            "--model-name",
            "glm-5.2",
        ],
    )

    assert result.exit_code == 0
    envs = {item.key: item.value for item in captured_session["envs"]}
    assert envs["AGENTKIT_SANDBOX_MODEL_PROVIDER"] == "agent_plan"
    assert envs["CODEX_MODEL"] == "glm-5.2"
    assert envs["CODEX_BASE_URL"] == ("https://ark.cn-beijing.volces.com/api/plan/v3")
    assert 'model_provider = "agent_plan"' in envs["CODEX_CONFIG_TOML"]
    assert (
        'base_url = "https://ark.cn-beijing.volces.com/api/plan/v3"'
        in envs["CODEX_CONFIG_TOML"]
    )


def test_cli_exec_model_name_inherits_cached_custom_model_base_url(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_exec as cli_exec

    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    store_path = _patch_store_path(monkeypatch, tmp_path)
    tool_store_path = _patch_tool_store_path(monkeypatch, tmp_path)
    tool_store_path.parent.mkdir(parents=True, exist_ok=True)
    tool_store_path.write_text(
        json.dumps(
            {
                "CodeEnv": {
                    "ToolId": "tool-1",
                    "ToolType": "CodeEnv",
                    "Name": "custom-url-tool",
                    "Status": "Ready",
                    "ModelProvider": "model_square",
                    "ModelBaseUrl": "https://models.example.com/v1",
                    "AnthropicBaseUrl": "https://models.example.com/v1",
                }
            }
        ),
        encoding="utf-8",
    )
    stored_session = {
        "session_id": "user-1",
        "tool_id": "tool-1",
        "instance_id": "session-1",
        "endpoint": "https://sandbox.example.com/?token=abc",
    }
    store_path.write_text(
        json.dumps({"user-1": stored_session}),
        encoding="utf-8",
    )
    captured_session = {}
    _patch_exec_session(
        monkeypatch,
        cli_exec,
        stored_session,
        capture=captured_session,
    )
    monkeypatch.setattr(
        cli_exec,
        "_connect_terminal",
        lambda *_args, **_kwargs: None,
    )

    result = runner.invoke(
        app,
        [
            "sandbox",
            "exec",
            "--tool-id",
            "tool-1",
            "--session-id",
            "user-1",
            "--model-name",
            "custom-model",
        ],
    )

    assert result.exit_code == 0
    envs = {item.key: item.value for item in captured_session["envs"]}
    assert envs["AGENTKIT_SANDBOX_MODEL_PROVIDER"] == "model_square"
    assert envs["CODEX_MODEL"] == "custom-model"
    assert envs["CODEX_BASE_URL"] == "https://models.example.com/v1"
    assert envs["ANTHROPIC_BASE_URL"] == "https://models.example.com/v1"
    assert 'model_provider = "model_square"' in envs["CODEX_CONFIG_TOML"]
    assert 'model = "custom-model"' in envs["CODEX_CONFIG_TOML"]
    assert 'base_url = "https://models.example.com/v1"' in envs["CODEX_CONFIG_TOML"]
    assert "CODEX_MODEL_CATALOG_JSON" in envs


def test_cli_exec_model_name_inherits_default_cached_custom_model_base_url(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_exec as cli_exec

    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    _patch_store_path(monkeypatch, tmp_path)
    tool_store_path = _patch_tool_store_path(monkeypatch, tmp_path)
    tool_store_path.parent.mkdir(parents=True, exist_ok=True)
    tool_store_path.write_text(
        json.dumps(
            {
                "CodeEnv": {
                    "ToolId": "tool-1",
                    "ToolType": "CodeEnv",
                    "Name": "custom-url-tool",
                    "Status": "Ready",
                    "ModelProvider": "model_square",
                    "ModelBaseUrl": "https://models.example.com/v1",
                    "AnthropicBaseUrl": "https://models.example.com/v1",
                }
            }
        ),
        encoding="utf-8",
    )
    captured_session = {}
    _patch_exec_session(
        monkeypatch,
        cli_exec,
        {
            "session_id": "generated-1",
            "tool_id": "tool-1",
            "instance_id": "session-1",
            "endpoint": "https://sandbox.example.com/?token=abc",
        },
        capture=captured_session,
    )
    monkeypatch.setattr(
        cli_exec,
        "_connect_terminal",
        lambda *_args, **_kwargs: None,
    )

    result = runner.invoke(
        app,
        [
            "sandbox",
            "exec",
            "--model-name",
            "custom-model",
        ],
    )

    assert result.exit_code == 0
    envs = {item.key: item.value for item in captured_session["envs"]}
    assert captured_session["tool_id"] is None
    assert envs["AGENTKIT_SANDBOX_MODEL_PROVIDER"] == "model_square"
    assert envs["CODEX_MODEL"] == "custom-model"
    assert envs["CODEX_BASE_URL"] == "https://models.example.com/v1"
    assert envs["ANTHROPIC_BASE_URL"] == "https://models.example.com/v1"
    assert 'model_provider = "model_square"' in envs["CODEX_CONFIG_TOML"]
    assert 'model = "custom-model"' in envs["CODEX_CONFIG_TOML"]
    assert 'base_url = "https://models.example.com/v1"' in envs["CODEX_CONFIG_TOML"]
    assert "CODEX_MODEL_CATALOG_JSON" in envs


def test_cli_exec_model_provider_sets_default_model_and_codex_config(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_exec as cli_exec

    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    store_path = _patch_store_path(monkeypatch, tmp_path)
    stored_session = {
        "session_id": "user-1",
        "tool_id": "tool-1",
        "instance_id": "session-1",
        "endpoint": "https://sandbox.example.com/?token=abc",
    }
    store_path.write_text(
        json.dumps({"user-1": stored_session}),
        encoding="utf-8",
    )
    captured_session = {}
    _patch_exec_session(
        monkeypatch,
        cli_exec,
        stored_session,
        capture=captured_session,
    )
    monkeypatch.setattr(
        cli_exec,
        "_connect_terminal",
        lambda *_args, **_kwargs: None,
    )

    result = runner.invoke(
        app,
        [
            "sandbox",
            "exec",
            "--session-id",
            "user-1",
            "--model-provider",
            "agent_plan",
        ],
    )

    assert result.exit_code == 0
    envs = {item.key: item.value for item in captured_session["envs"]}
    assert envs["OPENCODE_MODEL"] == "deepseek-v4-flash"
    assert envs["CODEX_MODEL"] == "deepseek-v4-flash"
    assert envs["ANTHROPIC_MODEL"] == "deepseek-v4-flash"
    assert envs["OPENCODE_BASE_URL"] == (
        "https://ark.cn-beijing.volces.com/api/plan/v3"
    )
    assert envs["ANTHROPIC_BASE_URL"] == ("https://ark.cn-beijing.volces.com/api/plan")
    assert (
        'base_url = "https://ark.cn-beijing.volces.com/api/plan/v3"'
        in envs["CODEX_CONFIG_TOML"]
    )
    catalog = json.loads(envs["CODEX_MODEL_CATALOG_JSON"])
    models = {model["slug"]: model for model in catalog["models"]}
    assert "deepseek-v4-flash" in models
    assert "deepseek-v4-flash-260425" not in models
    assert "glm-5.2" not in models


def test_cli_exec_rejects_model_base_url_without_model_provider() -> None:
    from agentkit.toolkit.cli.cli import app

    result = runner.invoke(
        app,
        [
            "sandbox",
            "exec",
            "--model-base-url",
            "https://models.example.com",
        ],
    )

    assert result.exit_code != 0
    assert (
        "--model-base-url requires --model-provider for non-Ark base URLs"
        in result.output
    )


def test_cli_exec_rejects_non_ark_model_base_url_without_model_provider() -> None:
    from agentkit.toolkit.cli.cli import app

    result = runner.invoke(
        app,
        [
            "sandbox",
            "exec",
            "--model-name",
            "custom-model",
            "--model-base-url",
            "https://models.example.com/v1",
            "--command",
            "echo should-not-run; exit",
        ],
    )

    assert result.exit_code != 0
    assert (
        "--model-base-url requires --model-provider for non-Ark base URLs"
        in result.output
    )


def test_cli_exec_allows_arbitrary_model_provider_without_base_url(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_exec as cli_exec

    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    store_path = _patch_store_path(monkeypatch, tmp_path)
    stored_session = {
        "session_id": "user-1",
        "tool_id": "tool-1",
        "instance_id": "session-1",
        "endpoint": "https://sandbox.example.com/?token=abc",
    }
    store_path.write_text(
        json.dumps({"user-1": stored_session}),
        encoding="utf-8",
    )
    captured_session = {}
    _patch_exec_session(
        monkeypatch,
        cli_exec,
        stored_session,
        capture=captured_session,
    )
    monkeypatch.setattr(
        cli_exec,
        "_connect_terminal",
        lambda *_args, **_kwargs: None,
    )

    result = runner.invoke(
        app,
        [
            "sandbox",
            "exec",
            "--model-provider",
            "custom_provider",
            "--model-name",
            "custom-model",
            "--session-id",
            "user-1",
        ],
    )

    assert result.exit_code == 0
    envs = {item.key: item.value for item in captured_session["envs"]}
    assert envs["AGENTKIT_SANDBOX_MODEL_PROVIDER"] == "custom_provider"
    assert envs["CODEX_MODEL"] == "custom-model"
    assert "CODEX_BASE_URL" not in envs
    assert "ANTHROPIC_BASE_URL" not in envs
    assert 'model_provider = "custom_provider"' in envs["CODEX_CONFIG_TOML"]
    assert 'model = "custom-model"' in envs["CODEX_CONFIG_TOML"]
    assert (
        'base_url = "https://ark.cn-beijing.volces.com/api/v3"'
        in envs["CODEX_CONFIG_TOML"]
    )
    assert "model_catalog_json" not in envs["CODEX_CONFIG_TOML"]
    assert "CODEX_MODEL_CATALOG_JSON" not in envs


def test_cli_exec_custom_provider_base_url_emits_codex_config_without_catalog(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_exec as cli_exec

    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    store_path = _patch_store_path(monkeypatch, tmp_path)
    stored_session = {
        "session_id": "user-1",
        "tool_id": "tool-1",
        "instance_id": "session-1",
        "endpoint": "https://sandbox.example.com/?token=abc",
    }
    store_path.write_text(
        json.dumps({"user-1": stored_session}),
        encoding="utf-8",
    )
    captured_session = {}
    _patch_exec_session(
        monkeypatch,
        cli_exec,
        stored_session,
        capture=captured_session,
    )
    monkeypatch.setattr(
        cli_exec,
        "_connect_terminal",
        lambda *_args, **_kwargs: None,
    )

    result = runner.invoke(
        app,
        [
            "sandbox",
            "exec",
            "--session-id",
            "user-1",
            "--model-provider",
            "custom_provider",
            "--model-name",
            "custom-model",
            "--model-base-url",
            "https://models.example.com/v1",
        ],
    )

    assert result.exit_code == 0
    envs = {item.key: item.value for item in captured_session["envs"]}
    assert envs["AGENTKIT_SANDBOX_MODEL_PROVIDER"] == "custom_provider"
    assert envs["CODEX_MODEL"] == "custom-model"
    assert envs["OPENCODE_BASE_URL"] == "https://models.example.com/v1"
    assert envs["CODEX_BASE_URL"] == "https://models.example.com/v1"
    assert envs["MODEL_BASE_URL"] == "https://models.example.com/v1"
    assert envs["ANTHROPIC_BASE_URL"] == "https://models.example.com/v1"
    assert 'model_provider = "custom_provider"' in envs["CODEX_CONFIG_TOML"]
    assert 'model = "custom-model"' in envs["CODEX_CONFIG_TOML"]
    assert 'base_url = "https://models.example.com/v1"' in envs["CODEX_CONFIG_TOML"]
    assert "model_catalog_json" not in envs["CODEX_CONFIG_TOML"]
    assert "CODEX_MODEL_CATALOG_JSON" not in envs


def test_cli_exec_supports_empty_command(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_exec as cli_exec

    store_path = _patch_store_path(monkeypatch, tmp_path)
    stored_session = {
        "session_id": "user-1",
        "tool_id": "tool-1",
        "instance_id": "session-1",
        "endpoint": "http://sandbox.example.com/base?token=abc",
    }
    store_path.write_text(
        json.dumps({"user-1": stored_session}),
        encoding="utf-8",
    )
    _patch_exec_session(monkeypatch, cli_exec, stored_session)
    captured = {}

    def fake_connect(ws_url, initial_command, on_shell_id=None):
        captured["ws_url"] = ws_url
        captured["initial_command"] = initial_command

    monkeypatch.setattr(cli_exec, "_connect_terminal", fake_connect)

    result = runner.invoke(
        app,
        [
            "sandbox",
            "exec",
            "--session-id",
            "user-1",
            "--command",
            "",
        ],
    )

    assert result.exit_code == 0
    assert captured["ws_url"] == "ws://sandbox.example.com/base/v1/shell/ws?token=abc"
    assert captured["initial_command"] == ""


def test_cli_exec_rejects_shell_id_option() -> None:
    from agentkit.toolkit.cli.cli import app

    result = runner.invoke(
        app,
        [
            "sandbox",
            "exec",
            "--session-id",
            "user-1",
            "--shell-id",
            "shell-1",
        ],
    )

    assert result.exit_code != 0
    assert "No such option" in result.output
    assert "--shell-id" in result.output


def test_cli_exec_clears_remote_shell_id_on_disconnect(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_exec as cli_exec

    store_path = _patch_store_path(monkeypatch, tmp_path)
    stored_session = {
        "session_id": "user-1",
        "tool_id": "tool-1",
        "instance_id": "session-1",
        "endpoint": "https://sandbox.example.com/?token=abc",
    }
    store_path.write_text(
        json.dumps({"user-1": stored_session}, indent=2),
        encoding="utf-8",
    )
    _patch_exec_session(monkeypatch, cli_exec, stored_session)

    def fake_connect(_ws_url, initial_command=None, on_shell_id=None):
        assert on_shell_id is not None
        on_shell_id("shell-from-ws")
        stored = json.loads(store_path.read_text(encoding="utf-8"))
        assert stored["user-1"]["terminal_shell_id"] == ["shell-from-ws"]

    monkeypatch.setattr(cli_exec, "_connect_terminal", fake_connect)

    result = runner.invoke(
        app,
        ["sandbox", "exec", "--session-id", "user-1"],
    )

    assert result.exit_code == 0
    stored = json.loads(store_path.read_text(encoding="utf-8"))
    assert "terminal_shell_id" not in stored["user-1"]
    assert "Shell ID: shell-from-ws" in result.output


def test_cli_exec_does_not_clear_newer_shell_id(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_exec as cli_exec

    store_path = _patch_store_path(monkeypatch, tmp_path)
    stored_session = {
        "session_id": "user-1",
        "tool_id": "tool-1",
        "instance_id": "session-1",
        "endpoint": "https://sandbox.example.com/?token=abc",
    }
    store_path.write_text(
        json.dumps({"user-1": stored_session}, indent=2),
        encoding="utf-8",
    )
    _patch_exec_session(monkeypatch, cli_exec, stored_session)

    def fake_connect(_ws_url, initial_command=None, on_shell_id=None):
        assert on_shell_id is not None
        on_shell_id("shell-from-ws")
        stored = json.loads(store_path.read_text(encoding="utf-8"))
        stored["user-1"]["terminal_shell_id"].append("shell-from-newer-terminal")
        store_path.write_text(json.dumps(stored), encoding="utf-8")

    monkeypatch.setattr(cli_exec, "_connect_terminal", fake_connect)

    result = runner.invoke(
        app,
        ["sandbox", "exec", "--session-id", "user-1"],
    )

    assert result.exit_code == 0
    stored = json.loads(store_path.read_text(encoding="utf-8"))
    assert stored["user-1"]["terminal_shell_id"] == ["shell-from-newer-terminal"]


def test_cli_exec_keeps_stored_shell_ids_without_current_shell_id(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_exec as cli_exec

    store_path = _patch_store_path(monkeypatch, tmp_path)
    stored_session = {
        "session_id": "user-1",
        "tool_id": "tool-1",
        "instance_id": "session-1",
        "endpoint": "https://sandbox.example.com/?token=abc",
        "terminal_shell_id": ["shell-from-store"],
    }
    store_path.write_text(
        json.dumps({"user-1": stored_session}, indent=2),
        encoding="utf-8",
    )
    _patch_exec_session(monkeypatch, cli_exec, stored_session)

    def fake_connect(_ws_url, initial_command=None, on_shell_id=None):
        assert on_shell_id is not None

    monkeypatch.setattr(cli_exec, "_connect_terminal", fake_connect)

    result = runner.invoke(
        app,
        ["sandbox", "exec", "--session-id", "user-1"],
    )

    assert result.exit_code == 0
    stored = json.loads(store_path.read_text(encoding="utf-8"))
    assert stored["user-1"]["terminal_shell_id"] == ["shell-from-store"]


def test_session_store_tracks_terminal_shell_ids_thread_safely(
    monkeypatch,
    tmp_path,
) -> None:
    import agentkit.toolkit.cli.sandbox.sandbox_client as sandbox_client

    store_path = _patch_store_path(monkeypatch, tmp_path)
    store_path.write_text(
        json.dumps(
            {
                "user-1": {
                    "session_id": "user-1",
                    "tool_id": "tool-1",
                    "instance_id": "session-1",
                    "endpoint": "https://sandbox.example.com",
                    "terminal_shell_id": "legacy-shell",
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    shell_ids = [f"shell-{index}" for index in range(20)]
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(
            executor.map(
                lambda shell_id: sandbox_client.add_session_terminal_shell_id(
                    "user-1",
                    shell_id,
                ),
                shell_ids,
            )
        )

    stored = json.loads(store_path.read_text(encoding="utf-8"))
    assert sorted(stored["user-1"]["terminal_shell_id"]) == sorted(
        ["legacy-shell", *shell_ids]
    )

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(
            executor.map(
                lambda shell_id: sandbox_client.remove_session_terminal_shell_id(
                    "user-1",
                    shell_id,
                ),
                shell_ids[:10],
            )
        )

    stored = json.loads(store_path.read_text(encoding="utf-8"))
    assert sorted(stored["user-1"]["terminal_shell_id"]) == sorted(
        ["legacy-shell", *shell_ids[10:]]
    )


def test_cli_exec_creates_session_when_session_id_omitted(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.session_create as session_create
    import agentkit.toolkit.cli.sandbox.cli_exec as cli_exec

    store_path = _patch_store_path(monkeypatch, tmp_path)
    monkeypatch.setattr(
        session_create,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )
    captured = {}

    def fake_connect(ws_url, initial_command, on_shell_id=None):
        captured["ws_url"] = ws_url
        captured["initial_command"] = initial_command
        captured["on_shell_id"] = on_shell_id

    monkeypatch.setattr(cli_exec, "_connect_terminal", fake_connect)

    result = runner.invoke(
        app,
        ["sandbox", "exec", "--tool-id", "tool-cli"],
    )

    assert result.exit_code == 0
    assert _FakeToolsClient.create_call_count == 1
    assert _FakeToolsClient.get_call_count == 0
    assert _FakeToolsClient.last_request.tool_id == "tool-cli"
    assert _FakeToolsClient.last_request.user_session_id
    assert captured["ws_url"] == "ws://sandbox.example.com/v1/shell/ws"
    assert captured["initial_command"] is None
    assert captured["on_shell_id"] is not None

    stored = json.loads(store_path.read_text(encoding="utf-8"))
    assert stored["user-session-from-api"]["tool_id"] == "tool-cli"


def test_cli_exec_creates_tool_when_tool_resolution_is_empty(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    from agentkit.toolkit.cli.sandbox import cli_create
    import agentkit.toolkit.cli.sandbox.session_create as session_create
    import agentkit.toolkit.cli.sandbox.cli_exec as cli_exec

    monkeypatch.delenv("AGENTKIT_SANDBOX_TOOL_ID", raising=False)
    _patch_store_path(monkeypatch, tmp_path)
    _patch_tool_store_path(monkeypatch, tmp_path)
    monkeypatch.setattr(
        session_create,
        "AgentkitToolsClient",
        lambda: _FakeToolsClient(),
    )

    def fake_create_tool(tool_type="CodeEnv", **_kwargs):
        return {
            "tool_id": "tool-from-create",
            "tool_type": tool_type,
            "name": "created-tool",
            "status": "Ready",
        }

    def fake_connect(ws_url, initial_command, on_shell_id=None):
        assert ws_url == "ws://sandbox.example.com/v1/shell/ws"
        assert initial_command is None
        assert on_shell_id is not None

    monkeypatch.setattr(cli_create, "create_tool", fake_create_tool)
    monkeypatch.setattr(cli_exec, "_connect_terminal", fake_connect)

    result = runner.invoke(app, ["sandbox", "exec"])

    assert result.exit_code == 0
    assert _FakeToolsClient.last_request.tool_id == "tool-from-create"


def test_cli_exec_detach_sequence_closes_websocket(monkeypatch) -> None:
    import json as json_module
    import threading
    import agentkit.toolkit.cli.sandbox.cli_exec as cli_exec

    class FakeStdin:
        def fileno(self):
            return 0

    class FakeWs:
        def __init__(self):
            self.messages = []
            self.closed = False

        def send(self, message):
            self.messages.append(json_module.loads(message))

        def close(self):
            self.closed = True

    ws = FakeWs()
    stop_event = threading.Event()

    monkeypatch.setattr(cli_exec.sys, "stdin", FakeStdin())
    monkeypatch.setattr(
        cli_exec.select,
        "select",
        lambda _r, _w, _x, _timeout: ([0], [], []),
    )
    monkeypatch.setattr(cli_exec.os, "read", lambda _fd, _size: b"pwd\x1d")

    cli_exec._stream_stdin(ws, stop_event)

    assert ws.messages == [{"type": "input", "data": "pwd"}]
    assert ws.closed is True
    assert stop_event.is_set()


@pytest.mark.parametrize("exit_command", [b"exit\n", b"exit()\n"])
def test_cli_exec_exit_command_closes_websocket(
    monkeypatch,
    exit_command,
) -> None:
    import threading
    import agentkit.toolkit.cli.sandbox.cli_exec as cli_exec

    class FakeStdin:
        def fileno(self):
            return 0

    class FakeWs:
        def __init__(self):
            self.messages = []
            self.closed = False

        def send(self, message):
            self.messages.append(message)

        def close(self):
            self.closed = True

    ws = FakeWs()
    stop_event = threading.Event()

    monkeypatch.setattr(cli_exec.sys, "stdin", FakeStdin())
    monkeypatch.setattr(
        cli_exec.select,
        "select",
        lambda _r, _w, _x, _timeout: ([0], [], []),
    )
    monkeypatch.setattr(cli_exec.os, "read", lambda _fd, _size: exit_command)

    cli_exec._stream_stdin(ws, stop_event)

    assert ws.messages == []
    assert ws.closed is True
    assert stop_event.is_set()


@pytest.mark.parametrize("exit_command", [b"previous input exit\r", b"x exit()\r"])
def test_cli_exec_exit_command_allows_prefix_buffer(
    monkeypatch,
    exit_command,
) -> None:
    import threading
    import agentkit.toolkit.cli.sandbox.cli_exec as cli_exec

    class FakeStdin:
        def fileno(self):
            return 0

    class FakeWs:
        def __init__(self):
            self.closed = False

        def send(self, _message):
            pass

        def close(self):
            self.closed = True

    ws = FakeWs()
    stop_event = threading.Event()

    monkeypatch.setattr(cli_exec.sys, "stdin", FakeStdin())
    monkeypatch.setattr(
        cli_exec.select,
        "select",
        lambda _r, _w, _x, _timeout: ([0], [], []),
    )
    monkeypatch.setattr(cli_exec.os, "read", lambda _fd, _size: exit_command)

    cli_exec._stream_stdin(ws, stop_event)

    assert ws.closed is True
    assert stop_event.is_set()
