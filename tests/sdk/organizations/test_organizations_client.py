# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
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

"""Unit tests for the AgentKit Organizations SDK client."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import pytest

from agentkit.sdk.organizations import (
    AddOrganizationMemberRequest,
    AgentkitOrganizationClient,
    CreateOrganizationRequest,
    DeleteOrganizationRequest,
    GetOrganizationRequest,
    ListOrganizationMembersRequest,
    ORGANIZATION_ADMIN_ROLE,
    RemoveOrganizationMemberRequest,
    UpdateOrganizationEndpointData,
    UpdateOrganizationRequest,
)


@pytest.fixture()
def client() -> AgentkitOrganizationClient:
    return AgentkitOrganizationClient(
        access_key="test-ak", secret_key="test-sk", region="cn-beijing"
    )


def _capture_json(
    monkeypatch,
    client: AgentkitOrganizationClient,
    response: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    calls: List[Dict[str, Any]] = []

    def fake_json(api: str, params=None, body=None) -> str:
        calls.append({"api": api, "params": params, "body": body})
        payload = response if response is not None else {"ResponseMetadata": {}}
        return json.dumps(payload)

    monkeypatch.setattr(client, "json", fake_json)
    return calls


def _capture_request(
    monkeypatch,
    client: AgentkitOrganizationClient,
    response: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    calls: List[Dict[str, Any]] = []

    def fake_get(api: str, params=None) -> str:
        calls.append({"api": api, "params": params, "data": ""})
        payload = response if response is not None else {"ResponseMetadata": {}}
        return json.dumps(payload)

    monkeypatch.setattr(client, "_send_get", fake_get)
    return calls


ORGANIZATION_RESULT = {
    "Result": {
        "Organization": {
            "OrgId": "org1",
            "Name": "demo",
            "UserPoolId": "pool1",
            "Endpoint": {"Id": "ep1", "BaseUrl": "https://example.com"},
        }
    },
    "ResponseMetadata": {},
}


class TestCreateOrganization:
    def test_body_and_response(self, monkeypatch, client):
        calls = _capture_json(
            monkeypatch,
            client,
            {
                "Result": {
                    **ORGANIZATION_RESULT["Result"],
                    "Created": True,
                },
                "ResponseMetadata": {},
            },
        )
        resp = client.create_organization(
            CreateOrganizationRequest(
                project_name="default", skip_create_user_pool=True
            )
        )
        body = json.loads(calls[0]["body"])
        assert body == {"ProjectName": "default", "SkipCreateUserPool": True}
        assert resp.created is True
        assert resp.organization.org_id == "org1"

    def test_idempotent_reuse(self, monkeypatch, client):
        _capture_json(
            monkeypatch,
            client,
            {
                "Result": {
                    "Organization": {"OrgId": "org1"},
                    "Created": False,
                },
                "ResponseMetadata": {},
            },
        )
        resp = client.create_organization(CreateOrganizationRequest())
        assert resp.created is False
        assert resp.organization.org_id == "org1"

    def test_blank_project_name_rejected(self):
        with pytest.raises(ValueError):
            CreateOrganizationRequest(project_name="  ")


class TestGetOrganization:
    def test_no_org_id_probes_current_account(self, monkeypatch, client):
        calls = _capture_request(monkeypatch, client, ORGANIZATION_RESULT)
        resp = client.get_organization(GetOrganizationRequest())
        assert calls[0]["api"] == "GetOrganization"
        assert calls[0]["data"] == ""  # GET signs an empty-string body
        assert calls[0]["params"] == {}
        assert resp.organization.org_id == "org1"
        assert resp.organization.endpoint.base_url == "https://example.com"

    def test_with_org_id(self, monkeypatch, client):
        calls = _capture_request(monkeypatch, client)
        client.get_organization(GetOrganizationRequest(org_id="org9"))
        assert calls[0]["params"] == {"OrgId": "org9"}

    def test_not_provisioned_is_legal(self, monkeypatch, client):
        _capture_request(
            monkeypatch, client, {"Result": {}, "ResponseMetadata": {}}
        )
        resp = client.get_organization(GetOrganizationRequest())
        # Empty Result is a legal "account not provisioned yet" answer.
        assert resp.organization is None

    def test_blank_org_id_rejected(self):
        with pytest.raises(ValueError):
            GetOrganizationRequest(org_id="  ")


class TestUpdateOrganization:
    def test_wire_with_nested_endpoint(self, monkeypatch, client):
        calls = _capture_json(
            monkeypatch,
            client,
            {"Result": {"OrgId": "org1"}, "ResponseMetadata": {}},
        )
        resp = client.update_organization(
            UpdateOrganizationRequest(
                org_id="org1",
                name="renamed",
                endpoint=UpdateOrganizationEndpointData(
                    id="ep1", base_url="https://example.com"
                ),
            )
        )
        body = json.loads(calls[0]["body"])
        assert body == {
            "OrgId": "org1",
            "Name": "renamed",
            "Endpoint": {"Id": "ep1", "BaseUrl": "https://example.com"},
        }
        assert resp.org_id == "org1"

    def test_nothing_to_update_rejected(self):
        with pytest.raises(ValueError):
            UpdateOrganizationRequest(org_id="org1")

    def test_empty_update_fields_rejected(self):
        with pytest.raises(ValueError):
            UpdateOrganizationRequest(org_id="org1", name="")

    def test_endpoint_requires_both_fields(self):
        # UpdateOrganizationEndpointData requires id and base_url together.
        with pytest.raises(ValueError):
            UpdateOrganizationEndpointData(id="ep1")


class TestDeleteOrganization:
    def test_body_and_status(self, monkeypatch, client):
        calls = _capture_json(
            monkeypatch,
            client,
            {"Result": {"Status": "DELETED"}, "ResponseMetadata": {}},
        )
        resp = client.delete_organization(
            DeleteOrganizationRequest(org_id="org1", delete_user_pool=True)
        )
        body = json.loads(calls[0]["body"])
        assert body == {"OrgId": "org1", "DeleteUserPool": True}
        assert resp.status == "DELETED"


class TestOrganizationMembers:
    def test_add_member(self, monkeypatch, client):
        calls = _capture_json(
            monkeypatch,
            client,
            {
                "Result": {
                    "Member": {
                        "BindingId": "b1",
                        "UserId": "u1",
                        "Role": ORGANIZATION_ADMIN_ROLE,
                    }
                },
                "ResponseMetadata": {},
            },
        )
        resp = client.add_organization_member(
            AddOrganizationMemberRequest(
                user_id="u1", role=ORGANIZATION_ADMIN_ROLE
            )
        )
        body = json.loads(calls[0]["body"])
        # No OrgId param: the org resolves from the signed account.
        assert body == {"UserId": "u1", "Role": "organization_admin"}
        assert resp.member.binding_id == "b1"

    def test_add_member_only_admin_role_supported(self):
        with pytest.raises(ValueError):
            AddOrganizationMemberRequest(user_id="u1", role="workspace_admin")

    def test_remove_member(self, monkeypatch, client):
        _capture_json(
            monkeypatch,
            client,
            {"Result": {"Revoked": True}, "ResponseMetadata": {}},
        )
        resp = client.remove_organization_member(
            RemoveOrganizationMemberRequest(
                user_id="u1", role=ORGANIZATION_ADMIN_ROLE
            )
        )
        assert resp.revoked is True

    def test_list_members_get_params(self, monkeypatch, client):
        calls = _capture_request(
            monkeypatch,
            client,
            {"Result": {"Members": [], "NextToken": ""}, "ResponseMetadata": {}},
        )
        resp = client.list_organization_members(
            ListOrganizationMembersRequest(
                role=ORGANIZATION_ADMIN_ROLE, max_results=0
            )
        )
        assert calls[0]["params"] == {
            "Role": "organization_admin",
            "MaxResults": 0,
        }
        assert resp.next_token is None

    def test_list_members_invalid_role(self):
        with pytest.raises(ValueError):
            ListOrganizationMembersRequest(role="workspace_admin")

    def test_list_members_bounds(self):
        with pytest.raises(ValueError):
            ListOrganizationMembersRequest(max_results=101)
