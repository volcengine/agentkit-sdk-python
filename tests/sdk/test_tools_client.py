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

"""Offline tests for ``AgentkitToolsClient``.

The client is exercised through its public methods only; the volcengine
transport (``Service.json``) is stubbed at the same seam used by
``tests/client/test_base_service_client_errors.py``, so no network is
performed. Covers request construction (action + payload shape), response
parsing (alias -> snake_case field mapping) and error mapping for the core
create/get/list tool methods.

Explicit credentials are supplied so the vefaas auto-refresh path is never
taken and construction needs neither a credential file nor network.
"""

from __future__ import annotations

import json
import types

# Import the toolkit package first to fully initialise the import graph before
# touching ``agentkit.client`` (the package wiring is order-sensitive).
import agentkit.toolkit  # noqa: F401

import pytest
import requests

from agentkit.auth.errors import NetworkError
from agentkit.sdk.tools.client import AgentkitToolsClient
from agentkit.sdk.tools.types import (
    CreateToolRequest,
    GetToolRequest,
    ListToolsRequest,
)
from agentkit.toolkit.errors import ApiError


@pytest.fixture
def client():
    return AgentkitToolsClient(
        access_key="AK_LOCAL_TEST_ONLY",
        secret_key="SK_LOCAL_TEST_ONLY",
        region="cn-beijing",
    )


def _stub_transport(client, result):
    """Replace the transport with a stub returning a successful envelope.

    Returns the captured calls; each entry records the api action, query
    params and the decoded JSON body handed to the transport layer.
    """
    calls = []

    def _json(self, api, params, body):
        calls.append({"api": api, "params": params, "body": json.loads(body)})
        return json.dumps(
            {"ResponseMetadata": {"RequestId": "req-test"}, "Result": result}
        )

    client.json = types.MethodType(_json, client)
    return calls


def _stub_transport_raising(client, exc):
    def _json(self, api, params, body):
        raise exc

    client.json = types.MethodType(_json, client)


def test_create_tool_sends_action_and_payload(client):
    calls = _stub_transport(client, {"ToolId": "tool-1"})

    resp = client.create_tool(
        CreateToolRequest(
            name="sandbox-a",
            tool_type="Sandbox",
            port=8080,
        )
    )

    assert calls == [
        {
            "api": "CreateTool",
            "params": {},
            # PascalCase aliases on the wire; unset optional fields excluded.
            "body": {"Name": "sandbox-a", "ToolType": "Sandbox", "Port": 8080},
        }
    ]
    assert resp.tool_id == "tool-1"
    info = client.api_info["CreateTool"]
    assert info.method == "POST"
    assert info.path == "/"
    assert info.query == {"Action": "CreateTool", "Version": client.api_version}


def test_get_tool_sends_id_and_parses_fields(client):
    calls = _stub_transport(
        client,
        {
            "ToolId": "tool-1",
            "Name": "sandbox-a",
            "ToolType": "Sandbox",
            "Status": "Ready",
            "Port": 8080,
            "ImageUrl": "registry.example.com/sandbox:latest",
        },
    )

    resp = client.get_tool(GetToolRequest(tool_id="tool-1"))

    assert calls == [
        {"api": "GetTool", "params": {}, "body": {"ToolId": "tool-1"}}
    ]
    assert resp.tool_id == "tool-1"
    assert resp.name == "sandbox-a"
    assert resp.tool_type == "Sandbox"
    assert resp.status == "Ready"
    assert resp.port == 8080
    assert resp.image_url == "registry.example.com/sandbox:latest"


def test_list_tools_parses_tools_and_next_token(client):
    _stub_transport(
        client,
        {
            "NextToken": "tok-9",
            "Tools": [
                {
                    "ToolId": "tool-1",
                    "Name": "sandbox-a",
                    "Status": "Ready",
                    "Port": 8080,
                }
            ],
        },
    )

    resp = client.list_tools(ListToolsRequest(max_results=10))

    assert resp.next_token == "tok-9"
    assert len(resp.tools) == 1
    tool = resp.tools[0]
    assert tool.tool_id == "tool-1"
    assert tool.name == "sandbox-a"
    assert tool.status == "Ready"
    assert tool.port == 8080


def test_backend_error_metadata_raises_apierror_with_code(client):
    def _json(self, api, params, body):
        return json.dumps(
            {
                "ResponseMetadata": {
                    "Error": {
                        "Code": "InvalidTool.NotFound",
                        "Message": "no such tool",
                    }
                }
            }
        )

    client.json = types.MethodType(_json, client)

    with pytest.raises(ApiError) as excinfo:
        client.get_tool(GetToolRequest(tool_id="tool-404"))

    assert excinfo.value.error_code == "InvalidTool.NotFound"
    assert "GetTool" in str(excinfo.value)
    assert "no such tool" in str(excinfo.value)


def test_transport_failure_raises_networkerror(client):
    _stub_transport_raising(
        client, requests.exceptions.ConnectionError("socket reset")
    )

    with pytest.raises(NetworkError) as excinfo:
        client.get_tool(GetToolRequest(tool_id="tool-1"))

    assert isinstance(excinfo.value.__cause__, requests.exceptions.ConnectionError)
    # Transport detail must not leak into the domain message.
    assert "socket reset" not in str(excinfo.value)
