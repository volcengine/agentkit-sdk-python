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

from urllib.parse import parse_qs, urlsplit

import pytest
import typer

from agentkit.sdk.tools import types as tools_types


class _FakeTipResponse:
    status_code = 200
    text = "{}"

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _FakeTipSession:
    def __init__(self):
        self.calls = []

    def post(self, url, *, json, headers, timeout):
        self.calls.append(
            {
                "url": url,
                "json": json,
                "headers": headers,
                "timeout": timeout,
            }
        )
        return _FakeTipResponse(
            {
                "Result": {
                    "SessionId": "instance-1",
                    "UserSessionId": "user-1",
                    "Endpoint": "https://sandbox.example.com",
                }
            }
        )


def test_tip_client_create_session_uses_apig_endpoint_and_bearer_token(
    monkeypatch,
):
    import agentkit.toolkit.cli.sandbox.agentkit_client as agentkit_client

    fake_session = _FakeTipSession()
    monkeypatch.setenv("SANDBOX_APIG_ENDPOINT", "https://apig.example.com/sandbox")
    monkeypatch.setenv("TIP_TOKEN", "tip-token")
    monkeypatch.setattr(
        agentkit_client.requests,
        "Session",
        lambda: fake_session,
    )

    client = agentkit_client.TipAgentkitToolsClient()
    response = client.create_session(
        tools_types.CreateSessionRequest(
            tool_id="tool-1",
            ttl=60,
            ttl_unit="second",
            user_session_id="user-1",
        )
    )

    assert response.session_id == "instance-1"
    assert response.user_session_id == "user-1"
    assert response.endpoint == "https://sandbox.example.com"
    assert len(fake_session.calls) == 1

    call = fake_session.calls[0]
    parsed = urlsplit(call["url"])
    query = parse_qs(parsed.query)
    assert parsed.scheme == "https"
    assert parsed.netloc == "apig.example.com"
    assert parsed.path == "/sandbox"
    assert query["Action"] == ["CreateSession"]
    assert query["Version"] == ["2025-10-30"]
    assert call["headers"]["Authorization"] == "Bearer tip-token"
    assert call["json"] == {
        "ToolId": "tool-1",
        "Ttl": 60,
        "TtlUnit": "second",
        "UserSessionId": "user-1",
    }


def test_tip_client_delete_session_uses_apig_endpoint_and_bearer_token(
    monkeypatch,
):
    import agentkit.toolkit.cli.sandbox.agentkit_client as agentkit_client

    fake_session = _FakeTipSession()
    monkeypatch.setenv("SANDBOX_APIG_ENDPOINT", "https://apig.example.com/sandbox")
    monkeypatch.setenv("TIP_TOKEN", "tip-token")
    monkeypatch.setattr(
        agentkit_client.requests,
        "Session",
        lambda: fake_session,
    )

    client = agentkit_client.TipAgentkitToolsClient()
    client.delete_session(
        tools_types.DeleteSessionRequest(
            tool_id="tool-1",
            session_id="instance-1",
        )
    )

    assert len(fake_session.calls) == 1
    call = fake_session.calls[0]
    parsed = urlsplit(call["url"])
    query = parse_qs(parsed.query)
    assert query["Action"] == ["DeleteSession"]
    assert query["Version"] == ["2025-10-30"]
    assert call["headers"]["Authorization"] == "Bearer tip-token"
    assert call["json"] == {
        "ToolId": "tool-1",
        "SessionId": "instance-1",
    }


def test_tip_client_pause_and_resume_session_use_apig_endpoint(monkeypatch):
    import agentkit.toolkit.cli.sandbox.agentkit_client as agentkit_client

    fake_session = _FakeTipSession()
    monkeypatch.setenv("SANDBOX_APIG_ENDPOINT", "https://apig.example.com/sandbox")
    monkeypatch.setenv("TIP_TOKEN", "tip-token")
    monkeypatch.setattr(
        agentkit_client.requests,
        "Session",
        lambda: fake_session,
    )

    client = agentkit_client.TipAgentkitToolsClient()
    client.pause_session(
        tools_types.PauseSessionRequest(
            tool_id="tool-1",
            session_id="instance-1",
        )
    )
    client.resume_session(
        tools_types.ResumeSessionRequest(
            tool_id="tool-1",
            session_id="instance-1",
            ttl=30,
            ttl_unit="minute",
        )
    )

    pause_call, resume_call = fake_session.calls
    assert parse_qs(urlsplit(pause_call["url"]).query)["Action"] == ["PauseSession"]
    assert pause_call["json"] == {
        "SessionId": "instance-1",
        "ToolId": "tool-1",
    }
    assert parse_qs(urlsplit(resume_call["url"]).query)["Action"] == ["ResumeSession"]
    assert resume_call["json"] == {
        "SessionId": "instance-1",
        "ToolId": "tool-1",
        "Ttl": 30,
        "TtlUnit": "minute",
    }


def test_tip_client_async_commands_use_apig_endpoint(monkeypatch):
    import agentkit.toolkit.cli.sandbox.agentkit_client as agentkit_client

    class FakeAsyncTipSession(_FakeTipSession):
        def __init__(self):
            super().__init__()
            self.payloads = [
                {"Result": {"TaskId": "task-1", "Status": "running"}},
                {
                    "Result": {
                        "TaskId": "task-1",
                        "Status": "completed",
                        "Output": "done",
                        "ExitCode": 0,
                    }
                },
                {"Result": {"TaskId": "task-1", "Deleted": True}},
            ]

        def post(self, url, *, json, headers, timeout):
            super().post(url, json=json, headers=headers, timeout=timeout)
            return _FakeTipResponse(self.payloads.pop(0))

    fake_session = FakeAsyncTipSession()
    monkeypatch.setenv("SANDBOX_APIG_ENDPOINT", "https://apig.example.com/sandbox")
    monkeypatch.setenv("TIP_TOKEN", "tip-token")
    monkeypatch.setattr(agentkit_client.requests, "Session", lambda: fake_session)

    client = agentkit_client.TipAgentkitToolsClient()
    session = {"tool_id": "tool-1", "user_session_id": "user-1"}
    created = client.async_exec_command(
        tools_types.AsyncExecCommandRequest(**session, command="echo done", ttl=60)
    )
    viewed = client.view_async_command(
        tools_types.ViewAsyncCommandRequest(**session, task_id=created.task_id)
    )
    deleted = client.delete_async_command(
        tools_types.DeleteAsyncCommandRequest(**session, task_id=created.task_id)
    )

    assert created.task_id == "task-1"
    assert viewed.output == "done"
    assert viewed.exit_code == 0
    assert deleted.deleted is True
    assert [
        parse_qs(urlsplit(call["url"]).query)["Action"][0]
        for call in fake_session.calls
    ] == ["AsyncExecCommand", "ViewAsyncCommand", "DeleteAsyncCommand"]
    assert all(
        call["headers"]["Authorization"] == "Bearer tip-token"
        for call in fake_session.calls
    )
    assert fake_session.calls[0]["json"] == {
        "ToolId": "tool-1",
        "UserSessionId": "user-1",
        "Ttl": 60,
        "Command": "echo done",
    }


def test_non_tip_client_forwards_data_plane_host(monkeypatch):
    import agentkit.toolkit.cli.sandbox.agentkit_client as agentkit_client

    monkeypatch.delenv("SANDBOX_APIG_ENDPOINT", raising=False)
    monkeypatch.delenv("TIP_TOKEN", raising=False)
    client = agentkit_client.TipAgentkitToolsClient(
        access_key="ak",
        secret_key="sk",
        region="cn-beijing",
        data_plane_host="custom.example.com",
    )

    assert client.data_plane_host == "custom.example.com"


def test_tip_create_session_skips_get_tool_for_tos_mount_resolution():
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    class FakeTipClient:
        uses_tip_auth = True
        get_tool_called = False
        last_request = None

        def get_tool(self, _request):
            self.get_tool_called = True
            raise AssertionError("get_tool should not be called in TIP mode")

        def create_session(self, request):
            self.last_request = request
            return tools_types.CreateSessionResponse(
                SessionId="instance-1",
                UserSessionId="user-1",
                Endpoint="https://sandbox.example.com",
            )

    client = FakeTipClient()
    result = session_create._create_session(
        client,
        session_id="user-1",
        tool_id="tool-1",
        ttl=60,
    )

    assert result == {
        "session_id": "user-1",
        "tool_id": "tool-1",
        "instance_id": "instance-1",
        "endpoint": "https://sandbox.example.com",
    }
    assert client.get_tool_called is False
    assert client.last_request.tos_mount_points is None


def test_tip_tool_resolution_trusts_explicit_tool_id():
    import agentkit.toolkit.cli.sandbox.tool_resolve as tool_resolve

    class FakeTipClient:
        uses_tip_auth = True

        def get_tool(self, _request):
            raise AssertionError("get_tool should not be called in TIP mode")

    assert (
        tool_resolve.resolve_existing_sandbox_tool_id(
            tool_id="tool-1",
            tool_type=tool_resolve.SandboxToolType.CODE_ENV,
            client=FakeTipClient(),
            env_var_name="AGENTKIT_SANDBOX_TOOL_ID",
        )
        == "tool-1"
    )


def test_tip_tool_resolution_requires_existing_tool_id(monkeypatch, tmp_path):
    import agentkit.toolkit.cli.sandbox.tool_resolve as tool_resolve

    class FakeTipClient:
        uses_tip_auth = True

    store_path = tmp_path / "tools.json"
    monkeypatch.setattr(tool_resolve, "_get_tool_store_path", lambda: store_path)
    monkeypatch.delenv("AGENTKIT_SANDBOX_TOOL_ID", raising=False)

    with pytest.raises(typer.Exit) as exc:
        tool_resolve.resolve_sandbox_tool_id(
            tool_id=None,
            tool_type=tool_resolve.SandboxToolType.CODE_ENV,
            client=FakeTipClient(),
            env_var_name="AGENTKIT_SANDBOX_TOOL_ID",
        )

    assert exc.value.exit_code == 1
