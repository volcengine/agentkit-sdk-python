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

"""Offline tests for ``AgentkitSkillsClient``.

The client is exercised through its public methods only; the volcengine
transport (``Service.json``) is stubbed at the same seam used by
``tests/client/test_base_service_client_errors.py``, so no network is
performed. The client exposes ~20 methods; the core create/delete/list
triple is covered here since every method funnels through the same
``_invoke_api`` path. Covers request construction, response parsing and
error mapping.

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
from agentkit.sdk.skills.client import AgentkitSkillsClient
from agentkit.sdk.skills.types import (
    CreateSkillRequest,
    DeleteSkillRequest,
    DeleteSkillResponse,
    GetSkillRequest,
    ListSkillsRequest,
)
from agentkit.toolkit.errors import ApiError


@pytest.fixture
def client():
    return AgentkitSkillsClient(
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


def test_create_skill_sends_action_and_payload(client):
    calls = _stub_transport(client, {"Id": "skill-1"})

    resp = client.create_skill(
        CreateSkillRequest(name="my-skill", tos_url="tos://bucket/skill.zip")
    )

    assert calls == [
        {
            "api": "CreateSkill",
            "params": {},
            # PascalCase aliases on the wire; unset optional fields excluded.
            "body": {"Name": "my-skill", "TosUrl": "tos://bucket/skill.zip"},
        }
    ]
    assert resp.id == "skill-1"
    info = client.api_info["CreateSkill"]
    assert info.method == "POST"
    assert info.path == "/"
    assert info.query == {"Action": "CreateSkill", "Version": client.api_version}


def test_delete_skill_sends_id(client):
    calls = _stub_transport(client, {})

    resp = client.delete_skill(DeleteSkillRequest(id="skill-1"))

    assert calls == [
        {"api": "DeleteSkill", "params": {}, "body": {"Id": "skill-1"}}
    ]
    # DeleteSkillResponse carries no fields; a typed empty object is returned.
    assert isinstance(resp, DeleteSkillResponse)


def test_list_skills_parses_items_and_total_count(client):
    _stub_transport(
        client,
        {
            "TotalCount": 1,
            "Items": [
                {
                    "Id": "skill-1",
                    "Name": "my-skill",
                    "Status": "Ready",
                    "Description": "demo",
                    "CreateTimeStamp": "1700000000",
                    "UpdateTimeStamp": "1700000001",
                    "Versions": ["v1", "v2"],
                    "ProjectName": "default",
                }
            ],
        },
    )

    resp = client.list_skills(ListSkillsRequest(page_number=1, page_size=10))

    assert resp.total_count == 1
    assert len(resp.items) == 1
    skill = resp.items[0]
    assert skill.id == "skill-1"
    assert skill.name == "my-skill"
    assert skill.status == "Ready"
    assert skill.versions == ["v1", "v2"]
    assert skill.project_name == "default"


def test_backend_error_metadata_raises_apierror_with_code(client):
    def _json(self, api, params, body):
        return json.dumps(
            {
                "ResponseMetadata": {
                    "Error": {
                        "Code": "InvalidSkill.NotFound",
                        "Message": "no such skill",
                    }
                }
            }
        )

    client.json = types.MethodType(_json, client)

    with pytest.raises(ApiError) as excinfo:
        client.get_skill(GetSkillRequest(id="skill-404"))

    assert excinfo.value.error_code == "InvalidSkill.NotFound"
    assert "GetSkill" in str(excinfo.value)
    assert "no such skill" in str(excinfo.value)


def test_transport_failure_raises_networkerror(client):
    _stub_transport_raising(
        client, requests.exceptions.ConnectionError("socket reset")
    )

    with pytest.raises(NetworkError) as excinfo:
        client.get_skill(GetSkillRequest(id="skill-1"))

    assert isinstance(excinfo.value.__cause__, requests.exceptions.ConnectionError)
    # Transport detail must not leak into the domain message.
    assert "socket reset" not in str(excinfo.value)
