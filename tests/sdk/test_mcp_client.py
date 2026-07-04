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

"""Offline tests for ``AgentkitMCPClient``.

The client is exercised through its public methods only; the volcengine
transport (``Service.json``) is stubbed at the same seam used by
``tests/client/test_base_service_client_errors.py``, so no network is
performed. Covers request construction (action + payload shape), response
parsing (alias -> snake_case field mapping) and error mapping for the core
create/get/delete service methods.

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
from agentkit.sdk.mcp.client import AgentkitMCPClient
from agentkit.sdk.mcp.types import (
    CreateMCPServiceRequest,
    DeleteMCPServiceRequest,
    GetMCPServiceRequest,
)
from agentkit.toolkit.errors import ApiError


@pytest.fixture
def client():
    return AgentkitMCPClient(
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


def test_create_mcp_service_sends_action_and_payload(client):
    calls = _stub_transport(client, {})

    client.create_mcp_service(
        CreateMCPServiceRequest(
            name="my-mcp",
            path="/mcp",
            backend_type="VeFaaS",
            protocol_type="SSE",
        )
    )

    assert calls == [
        {
            "api": "CreateMCPService",
            "params": {},
            # PascalCase aliases on the wire; unset optional fields excluded.
            "body": {
                "Name": "my-mcp",
                "Path": "/mcp",
                "BackendType": "VeFaaS",
                "ProtocolType": "SSE",
            },
        }
    ]
    info = client.api_info["CreateMCPService"]
    assert info.method == "POST"
    assert info.path == "/"
    assert info.query == {"Action": "CreateMCPService", "Version": client.api_version}


def test_create_mcp_service_parses_service_id(client):
    _stub_transport(client, {"MCPServiceId": "mcp-svc-1"})

    resp = client.create_mcp_service(
        CreateMCPServiceRequest(
            name="my-mcp", path="/mcp", backend_type="VeFaaS", protocol_type="SSE"
        )
    )

    assert resp.mcp_service_id == "mcp-svc-1"


def test_get_mcp_service_parses_nested_service(client):
    _stub_transport(
        client,
        {
            "MCPService": {
                "MCPServiceId": "mcp-svc-1",
                "Name": "my-mcp",
                "Path": "/mcp",
                "Status": "Running",
                "ProtocolType": "SSE",
            }
        },
    )

    resp = client.get_mcp_service(GetMCPServiceRequest(mcp_service_id="mcp-svc-1"))

    assert resp.mcp_service.mcp_service_id == "mcp-svc-1"
    assert resp.mcp_service.name == "my-mcp"
    assert resp.mcp_service.path == "/mcp"
    assert resp.mcp_service.status == "Running"


def test_delete_mcp_service_sends_id_and_parses_echo(client):
    calls = _stub_transport(client, {"MCPServiceId": "mcp-svc-1"})

    resp = client.delete_mcp_service(
        DeleteMCPServiceRequest(mcp_service_id="mcp-svc-1")
    )

    assert calls == [
        {
            "api": "DeleteMCPService",
            "params": {},
            "body": {"MCPServiceId": "mcp-svc-1"},
        }
    ]
    assert resp.mcp_service_id == "mcp-svc-1"


def test_backend_error_metadata_raises_apierror_with_code(client):
    def _json(self, api, params, body):
        return json.dumps(
            {
                "ResponseMetadata": {
                    "Error": {
                        "Code": "InvalidMCPService.NotFound",
                        "Message": "no such mcp service",
                    }
                }
            }
        )

    client.json = types.MethodType(_json, client)

    with pytest.raises(ApiError) as excinfo:
        client.get_mcp_service(GetMCPServiceRequest(mcp_service_id="mcp-404"))

    assert excinfo.value.error_code == "InvalidMCPService.NotFound"
    assert "GetMCPService" in str(excinfo.value)
    assert "no such mcp service" in str(excinfo.value)


def test_transport_failure_raises_networkerror(client):
    _stub_transport_raising(client, requests.exceptions.Timeout("read timed out"))

    with pytest.raises(NetworkError) as excinfo:
        client.get_mcp_service(GetMCPServiceRequest(mcp_service_id="mcp-svc-1"))

    assert isinstance(excinfo.value.__cause__, requests.exceptions.Timeout)
    # Transport detail must not leak into the domain message.
    assert "read timed out" not in str(excinfo.value)
