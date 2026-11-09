import json
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from agentkit.sdk.tools.client import AgentkitToolsClient
from agentkit.sdk.tools.types import (
    AsyncExecCommandRequest,
    DeleteAsyncCommandRequest,
    GetToolRequest,
    ViewAsyncCommandRequest,
)
from agentkit.toolkit.errors import ApiError


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("AGENTKIT_CLOUD_PROVIDER", "volcengine")
    return AgentkitToolsClient(
        access_key="test-ak", secret_key="test-sk", region="cn-beijing"
    )


def respond(client, result=None, error=None):
    body = {"Result": result or {}}
    if error:
        body["ResponseMetadata"] = {"Error": error}
    client.session.post = Mock(return_value=Mock(status_code=200, json=lambda: body))


@pytest.mark.parametrize(
    "method,model,action,result",
    [
        (
            "async_exec_command",
            AsyncExecCommandRequest(
                tool_id="t-test", user_session_id="u", command="echo hi", ttl=0
            ),
            "AsyncExecCommand",
            {"TaskId": "task", "Status": "running"},
        ),
        (
            "view_async_command",
            ViewAsyncCommandRequest(tool_id="t-test", session_id="s", task_id="task"),
            "ViewAsyncCommand",
            {"Output": "hi", "ExitCode": 0, "Status": "completed"},
        ),
        (
            "delete_async_command",
            DeleteAsyncCommandRequest(tool_id="t-test", session_id="s", task_id="task"),
            "DeleteAsyncCommand",
            {"TaskId": "task", "Deleted": True},
        ),
    ],
)
def test_wire_contract(client, method, model, action, result):
    respond(client, result)
    response = getattr(client, method)(model)
    assert response.model_dump(by_alias=True, exclude_none=True) == result
    args, kwargs = client.session.post.call_args
    assert args[0].startswith("https://agentkit.cn-beijing.volces.com/")
    assert f"Action={action}" in args[0]
    assert "Version=2025-10-30" in args[0]
    assert kwargs["headers"]["Host"] == "agentkit.cn-beijing.volces.com"
    assert "Credential=test-ak/" in kwargs["headers"]["Authorization"]
    assert json.loads(kwargs["data"]) == model.model_dump(
        by_alias=True, exclude_none=True
    )


def test_management_routing_unchanged_and_data_override(client):
    original_host = client.service_info.host
    client.data_plane_host = "custom.example.com"
    respond(client, {"Deleted": True})
    client.delete_async_command(
        DeleteAsyncCommandRequest(tool_id="t", task_id="task", session_id="s")
    )
    assert client.session.post.call_args.args[0].startswith(
        "https://custom.example.com/"
    )
    client.get_tool(GetToolRequest(tool_id="t"))
    assert client.session.post.call_args.args[0].startswith(f"https://{original_host}/")
    assert client.service_info.host == original_host


def test_repeated_delete_success(client):
    respond(client, {"Deleted": True, "TaskId": "task"})
    request = DeleteAsyncCommandRequest(tool_id="t", task_id="task", session_id="s")
    assert client.delete_async_command(request).deleted is True
    assert client.delete_async_command(request).deleted is True


@pytest.mark.parametrize("missing", ["tool_id", "task_id"])
def test_required_fields(missing):
    values = dict(tool_id="t", task_id="task", session_id="s")
    del values[missing]
    with pytest.raises(ValidationError):
        DeleteAsyncCommandRequest(**values)


@pytest.mark.parametrize(
    "values,code",
    [
        ({}, "EmptySessionId"),
        ({"session_id": "s", "ttl": 86401}, "InvalidTtl"),
        ({"session_id": "s"}, "ResourceNotFound"),
    ],
)
def test_server_validation_errors_are_preserved(client, values, code):
    # These are transport fixtures, not a claim about published error-code names.
    respond(client, error={"Code": code, "Message": "validation failed"})
    with pytest.raises(ApiError) as exc:
        client.delete_async_command(
            DeleteAsyncCommandRequest(tool_id="t", task_id="task", **values)
        )
    assert exc.value.error_code == code


def test_constructor_override_and_sts():
    client = AgentkitToolsClient(
        access_key="ak",
        secret_key="sk",
        region="cn-beijing",
        session_token="token",
        data_plane_host="custom.example.com",
    )
    respond(client, {"Deleted": True})
    client.delete_async_command(
        DeleteAsyncCommandRequest(tool_id="t", task_id="task", session_id="s")
    )
    assert (
        client.session.post.call_args.kwargs["headers"]["X-Security-Token"] == "token"
    )
