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

"""Offline tests for ``AgentkitKnowledgeClient``.

The client is exercised through its public methods only; the volcengine
transport (``Service.json``) is stubbed at the same seam used by
``tests/client/test_base_service_client_errors.py``, so no network is
performed. Covers request construction (action + payload shape), response
parsing (alias -> snake_case field mapping) and error mapping.

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
from agentkit.sdk.knowledge.client import AgentkitKnowledgeClient
from agentkit.sdk.knowledge.types import (
    AddKnowledgeBaseRequest,
    GetKnowledgeBaseRequest,
    KnowledgeBasesItemForAddKnowledgeBase,
    ListKnowledgeBasesRequest,
)
from agentkit.toolkit.errors import ApiError


@pytest.fixture
def client():
    return AgentkitKnowledgeClient(
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


def test_get_knowledge_base_sends_action_and_payload(client):
    calls = _stub_transport(client, {})

    client.get_knowledge_base(GetKnowledgeBaseRequest(knowledge_id="kb-123"))

    assert calls == [
        {"api": "GetKnowledgeBase", "params": {}, "body": {"KnowledgeId": "kb-123"}}
    ]
    # The action is wired as a plain POST to / with Action/Version query params.
    info = client.api_info["GetKnowledgeBase"]
    assert info.method == "POST"
    assert info.path == "/"
    assert info.query == {"Action": "GetKnowledgeBase", "Version": client.api_version}


def test_add_knowledge_base_serializes_nested_payload_by_alias(client):
    calls = _stub_transport(client, {})

    client.add_knowledge_base(
        AddKnowledgeBaseRequest(
            project_name="default",
            knowledge_bases=[
                KnowledgeBasesItemForAddKnowledgeBase(
                    name="kb-a",
                    provider_knowledge_id="pkb-1",
                    provider_type="viking",
                )
            ],
        )
    )

    assert calls[0]["api"] == "AddKnowledgeBase"
    # PascalCase aliases on the wire; unset optional fields are excluded.
    assert calls[0]["body"] == {
        "ProjectName": "default",
        "KnowledgeBases": [
            {
                "Name": "kb-a",
                "ProviderKnowledgeId": "pkb-1",
                "ProviderType": "viking",
            }
        ],
    }


def test_list_knowledge_bases_parses_result_fields(client):
    _stub_transport(
        client,
        {
            "NextToken": "tok-2",
            "KnowledgeBases": [
                {
                    "KnowledgeId": "kb-1",
                    "Name": "first",
                    "Status": "Ready",
                    "AssociatedRuntimes": [{"Id": "rt-1", "Name": "runtime-1"}],
                }
            ],
        },
    )

    resp = client.list_knowledge_bases(ListKnowledgeBasesRequest())

    assert resp.next_token == "tok-2"
    assert len(resp.knowledge_bases) == 1
    kb = resp.knowledge_bases[0]
    assert kb.knowledge_id == "kb-1"
    assert kb.name == "first"
    assert kb.status == "Ready"
    assert kb.associated_runtimes[0].id == "rt-1"
    assert kb.associated_runtimes[0].name == "runtime-1"


def test_backend_error_metadata_raises_apierror_with_code(client):
    def _json(self, api, params, body):
        return json.dumps(
            {
                "ResponseMetadata": {
                    "Error": {
                        "Code": "InvalidKnowledgeBase.NotFound",
                        "Message": "no such knowledge base",
                    }
                }
            }
        )

    client.json = types.MethodType(_json, client)

    with pytest.raises(ApiError) as excinfo:
        client.get_knowledge_base(GetKnowledgeBaseRequest(knowledge_id="kb-404"))

    assert excinfo.value.error_code == "InvalidKnowledgeBase.NotFound"
    assert "GetKnowledgeBase" in str(excinfo.value)
    assert "no such knowledge base" in str(excinfo.value)


def test_transport_failure_raises_networkerror(client):
    _stub_transport_raising(
        client, requests.exceptions.ConnectionError("socket reset")
    )

    with pytest.raises(NetworkError) as excinfo:
        client.get_knowledge_base(GetKnowledgeBaseRequest(knowledge_id="kb-123"))

    assert isinstance(excinfo.value.__cause__, requests.exceptions.ConnectionError)
    # Transport detail must not leak into the domain message.
    assert "socket reset" not in str(excinfo.value)
