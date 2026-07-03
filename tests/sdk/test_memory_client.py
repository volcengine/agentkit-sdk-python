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

"""Offline tests for ``AgentkitMemoryClient``.

The client is exercised through its public methods only; the volcengine
transport (``Service.json``) is stubbed at the same seam used by
``tests/client/test_base_service_client_errors.py``, so no network is
performed. Covers request construction (action + payload shape), response
parsing (alias -> snake_case field mapping) and error mapping for the core
create/get/delete collection methods.

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
from agentkit.sdk.memory.client import AgentkitMemoryClient
from agentkit.sdk.memory.types import (
    CreateMemoryCollectionRequest,
    DeleteMemoryCollectionRequest,
    GetMemoryCollectionRequest,
)
from agentkit.toolkit.errors import ApiError


@pytest.fixture
def client():
    return AgentkitMemoryClient(
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


def test_create_memory_collection_sends_action_and_payload(client):
    calls = _stub_transport(client, {})

    client.create_memory_collection(
        CreateMemoryCollectionRequest(
            name="mem-a",
            description="test collection",
            provider_type="viking",
        )
    )

    assert calls == [
        {
            "api": "CreateMemoryCollection",
            "params": {},
            # PascalCase aliases on the wire; unset optional fields excluded.
            "body": {
                "Name": "mem-a",
                "Description": "test collection",
                "ProviderType": "viking",
            },
        }
    ]
    info = client.api_info["CreateMemoryCollection"]
    assert info.method == "POST"
    assert info.path == "/"
    assert info.query == {
        "Action": "CreateMemoryCollection",
        "Version": client.api_version,
    }


def test_create_memory_collection_parses_result(client):
    _stub_transport(
        client,
        {
            "MemoryId": "mem-1",
            "ProviderCollectionId": "pc-1",
            "ProviderType": "viking",
            "Status": "Creating",
        },
    )

    resp = client.create_memory_collection(
        CreateMemoryCollectionRequest(name="mem-a")
    )

    assert resp.memory_id == "mem-1"
    assert resp.provider_collection_id == "pc-1"
    assert resp.provider_type == "viking"
    assert resp.status == "Creating"


def test_get_memory_collection_parses_fields(client):
    _stub_transport(
        client,
        {
            "MemoryId": "mem-1",
            "Name": "mem-a",
            "Managed": True,
            "Status": "Ready",
            "CreateTime": "2026-01-01T00:00:00Z",
        },
    )

    resp = client.get_memory_collection(GetMemoryCollectionRequest(memory_id="mem-1"))

    assert resp.memory_id == "mem-1"
    assert resp.name == "mem-a"
    assert resp.managed is True
    assert resp.status == "Ready"
    assert resp.create_time == "2026-01-01T00:00:00Z"


def test_delete_memory_collection_sends_id(client):
    calls = _stub_transport(client, {"MemoryId": "mem-1", "Status": "Deleting"})

    resp = client.delete_memory_collection(
        DeleteMemoryCollectionRequest(memory_id="mem-1")
    )

    assert calls == [
        {"api": "DeleteMemoryCollection", "params": {}, "body": {"MemoryId": "mem-1"}}
    ]
    assert resp.memory_id == "mem-1"
    assert resp.status == "Deleting"


def test_backend_error_metadata_raises_apierror_with_code(client):
    def _json(self, api, params, body):
        return json.dumps(
            {
                "ResponseMetadata": {
                    "Error": {
                        "Code": "InvalidMemoryCollection.NotFound",
                        "Message": "no such memory collection",
                    }
                }
            }
        )

    client.json = types.MethodType(_json, client)

    with pytest.raises(ApiError) as excinfo:
        client.get_memory_collection(GetMemoryCollectionRequest(memory_id="mem-404"))

    assert excinfo.value.error_code == "InvalidMemoryCollection.NotFound"
    assert "GetMemoryCollection" in str(excinfo.value)
    assert "no such memory collection" in str(excinfo.value)


def test_transport_failure_raises_networkerror(client):
    _stub_transport_raising(
        client, requests.exceptions.ConnectionError("connection refused")
    )

    with pytest.raises(NetworkError) as excinfo:
        client.get_memory_collection(GetMemoryCollectionRequest(memory_id="mem-1"))

    assert isinstance(excinfo.value.__cause__, requests.exceptions.ConnectionError)
    # Transport detail must not leak into the domain message.
    assert "connection refused" not in str(excinfo.value)
