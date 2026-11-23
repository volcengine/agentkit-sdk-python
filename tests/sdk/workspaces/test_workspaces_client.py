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

"""Unit tests for the AgentKit Workspaces SDK client."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import pytest

from agentkit.sdk.workspaces import (
    AddWorkspaceMemberRequest,
    AgentkitWorkspaceClient,
    BATCH_MEMBER_OPERATIONS,
    BatchUpdateWorkspaceMembersRequest,
    CreateWorkspaceRequest,
    DeleteWorkspaceRequest,
    GetWorkspaceMemberRequest,
    GetWorkspaceRequest,
    GrantSystemAdminRequest,
    ListWorkspaceMembersRequest,
    ListWorkspacesRequest,
    RemoveWorkspaceMemberRequest,
    UpdateWorkspaceMemberRoleRequest,
    UpdateWorkspaceRequest,
    WorkspaceMemberOperationItem,
    WORKSPACE_ROLES,
)
from agentkit.toolkit.errors import ApiError

TOP_REGION_HEADER = "X-Top-Region"


@pytest.fixture()
def client() -> AgentkitWorkspaceClient:
    return AgentkitWorkspaceClient(
        access_key="test-ak", secret_key="test-sk", region="cn-beijing"
    )


def _capture_json(
    monkeypatch,
    client: AgentkitWorkspaceClient,
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
    client: AgentkitWorkspaceClient,
    response: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    calls: List[Dict[str, Any]] = []

    def fake_get(api: str, params=None) -> str:
        calls.append({"api": api, "params": params, "data": ""})
        payload = response if response is not None else {"ResponseMetadata": {}}
        return json.dumps(payload)

    monkeypatch.setattr(client, "_send_get", fake_get)
    return calls


# ---------------------------------------------------------------------------
# Workspace lifecycle
# ---------------------------------------------------------------------------


class TestCreateWorkspace:
    def test_body_and_region_header(self, monkeypatch, client):
        calls = _capture_json(
            monkeypatch,
            client,
            {
                "Result": {"Workspace": {"WorkspaceId": "ws1", "Region": "cn-beijing"}},
                "ResponseMetadata": {},
            },
        )
        resp = client.create_workspace(
            CreateWorkspaceRequest(name="demo", org_id="org1")
        )

        assert calls[0]["api"] == "CreateWorkspace"
        body = json.loads(calls[0]["body"])
        assert body == {"Name": "demo", "OrgId": "org1"}
        assert resp.workspace.workspace_id == "ws1"

        # X-Top-Region is installed for the call and restored afterwards.
        assert TOP_REGION_HEADER not in client.service_info.header

    def test_region_header_restored_after_call(self, monkeypatch, client):
        client.service_info.header["X-Other"] = "keep"
        _capture_json(monkeypatch, client)
        client.create_workspace(
            CreateWorkspaceRequest(name="demo", org_id="org1")
        )
        assert client.service_info.header["X-Other"] == "keep"
        assert TOP_REGION_HEADER not in client.service_info.header

    def test_region_header_value_is_client_region(self, monkeypatch, client):
        seen: Dict[str, str] = {}

        def fake_json(api, params=None, body=None):
            seen[TOP_REGION_HEADER] = client.service_info.header.get(
                TOP_REGION_HEADER
            )
            return json.dumps({"ResponseMetadata": {}})

        monkeypatch.setattr(client, "json", fake_json)
        client.create_workspace(CreateWorkspaceRequest(name="d", org_id="o"))
        assert seen[TOP_REGION_HEADER] == "cn-beijing"

    def test_region_required_guard(self, monkeypatch, client):
        monkeypatch.setattr(client, "region", "")
        with pytest.raises(ValueError, match="X-Top-Region"):
            client.create_workspace(CreateWorkspaceRequest(name="d", org_id="o"))

    def test_project_name_in_body(self, monkeypatch, client):
        calls = _capture_json(monkeypatch, client)
        client.create_workspace(
            CreateWorkspaceRequest(
                name="demo", org_id="org1", project_name="default"
            )
        )
        body = json.loads(calls[0]["body"])
        assert body["ProjectName"] == "default"


class TestListGetWorkspace:
    def test_list_workspaces_get_params(self, monkeypatch, client):
        calls = _capture_request(
            monkeypatch,
            client,
            {
                "Result": {
                    "Workspaces": [{"WorkspaceId": "ws1", "Name": "demo"}],
                    "NextToken": "",
                },
                "ResponseMetadata": {},
            },
        )
        resp = client.list_workspaces(ListWorkspacesRequest(org_id="org1"))

        assert calls[0]["api"] == "ListWorkspaces"
        assert calls[0]["data"] == ""  # GET signs an empty-string body
        assert calls[0]["params"] == {"OrgId": "org1"}
        assert resp.workspaces[0].workspace_id == "ws1"
        assert resp.next_token is None

    def test_list_workspaces_filters(self, monkeypatch, client):
        calls = _capture_request(monkeypatch, client)
        client.list_workspaces(
            ListWorkspacesRequest(
                org_id="org1",
                workspace_type="standard",
                status="Running",
                project_name="default",
                max_results=0,
                next_token="tok",
            )
        )
        assert calls[0]["params"] == {
            "OrgId": "org1",
            "WorkspaceType": "standard",
            "Status": "Running",
            "ProjectName": "default",
            "MaxResults": 0,
            "NextToken": "tok",
        }

    def test_get_workspace_id_precedence(self, monkeypatch, client):
        calls = _capture_request(monkeypatch, client)
        client.get_workspace(
            GetWorkspaceRequest(
                workspace_id="ws1", project_name="default", count_member=True
            )
        )
        # workspaceId wins: ProjectName is not sent; CountMember -> "true".
        assert calls[0]["params"] == {
            "WorkspaceId": "ws1",
            "CountMember": "true",
        }

    def test_get_workspace_by_project_name(self, monkeypatch, client):
        calls = _capture_request(monkeypatch, client)
        client.get_workspace(GetWorkspaceRequest(project_name="default"))
        assert calls[0]["params"] == {"ProjectName": "default"}

    def test_get_workspace_requires_lookup_key(self):
        with pytest.raises(ValueError):
            GetWorkspaceRequest()

    def test_get_workspace_count_member_false_omitted(self, monkeypatch, client):
        calls = _capture_request(monkeypatch, client)
        client.get_workspace(GetWorkspaceRequest(workspace_id="ws1"))
        assert "CountMember" not in calls[0]["params"]


class TestUpdateDeleteWorkspace:
    def test_update_body(self, monkeypatch, client):
        calls = _capture_json(
            monkeypatch,
            client,
            {"Result": {"Workspace": {"WorkspaceId": "ws1", "Name": "new"}}, "ResponseMetadata": {}},
        )
        resp = client.update_workspace(
            UpdateWorkspaceRequest(workspace_id="ws1", name="new")
        )
        body = json.loads(calls[0]["body"])
        assert body == {"WorkspaceId": "ws1", "Name": "new"}
        assert resp.workspace.name == "new"

    def test_update_requires_a_field(self):
        with pytest.raises(ValueError):
            UpdateWorkspaceRequest(workspace_id="ws1")

    def test_update_rejects_empty_values(self):
        with pytest.raises(ValueError):
            UpdateWorkspaceRequest(workspace_id="ws1", name="")

    def test_delete_reports_deleted(self, monkeypatch, client):
        _capture_json(
            monkeypatch,
            client,
            {"Result": {"Deleted": True}, "ResponseMetadata": {}},
        )
        resp = client.delete_workspace(DeleteWorkspaceRequest(workspace_id="ws1"))
        assert resp.deleted is True


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------


class TestGrantSystemAdmin:
    def test_body_and_bindings(self, monkeypatch, client):
        calls = _capture_json(
            monkeypatch,
            client,
            {
                "Result": {
                    "Bindings": [
                        {"BindingId": "b1", "UserId": "iam-1", "AccountId": "123"}
                    ]
                },
                "ResponseMetadata": {},
            },
        )
        resp = client.grant_system_admin(
            GrantSystemAdminRequest(workspace_id="ws1", iam_user_ids=["iam-1"])
        )
        body = json.loads(calls[0]["body"])
        assert body == {"WorkspaceId": "ws1", "IamUserIdList": ["iam-1"]}
        assert resp.bindings[0].binding_id == "b1"
        assert resp.bindings[0].account_id == "123"

    def test_empty_user_list_rejected(self):
        with pytest.raises(ValueError):
            GrantSystemAdminRequest(workspace_id="ws1", iam_user_ids=[])
        with pytest.raises(ValueError):
            GrantSystemAdminRequest(workspace_id="ws1", iam_user_ids=[" "])


class TestWorkspaceMembers:
    def test_add_member_body_and_binding(self, monkeypatch, client):
        calls = _capture_json(
            monkeypatch,
            client,
            {
                "Result": {
                    "Binding": {
                        "BindingId": "b1",
                        "UserId": "u1",
                        "Role": "workspace_admin",
                    }
                },
                "ResponseMetadata": {},
            },
        )
        resp = client.add_workspace_member(
            AddWorkspaceMemberRequest(
                workspace_id="ws1", user_id="u1", role="workspace_admin"
            )
        )
        body = json.loads(calls[0]["body"])
        assert body == {"WorkspaceId": "ws1", "UserId": "u1", "Role": "workspace_admin"}
        assert resp.binding.role == "workspace_admin"

    def test_add_member_invalid_role(self):
        with pytest.raises(ValueError):
            AddWorkspaceMemberRequest(
                workspace_id="ws1", user_id="u1", role="superuser"
            )

    def test_list_members_get_params(self, monkeypatch, client):
        calls = _capture_request(
            monkeypatch,
            client,
            {"Result": {"Bindings": [], "NextToken": "tok2"}, "ResponseMetadata": {}},
        )
        resp = client.list_workspace_members(
            ListWorkspaceMembersRequest(
                workspace_id="ws1", role="workspace_admin", max_results=50
            )
        )
        assert calls[0]["params"] == {
            "WorkspaceId": "ws1",
            "Role": "workspace_admin",
            "MaxResults": 50,
        }
        assert resp.next_token == "tok2"

    def test_list_members_invalid_role_filter(self):
        with pytest.raises(ValueError):
            ListWorkspaceMembersRequest(workspace_id="ws1", role="nope")

    def test_get_member_not_a_member_is_legal(self, monkeypatch, client):
        _capture_request(
            monkeypatch,
            client,
            {
                "Result": {
                    "WorkspaceId": "ws1",
                    "UserId": "u1",
                    "EffectiveRoles": [],
                },
                "ResponseMetadata": {},
            },
        )
        resp = client.get_workspace_member(
            GetWorkspaceMemberRequest(workspace_id="ws1", user_id="u1")
        )
        # Missing Binding is a legal "not a member" answer (no error).
        assert resp.binding is None
        assert resp.effective_roles == []

    def test_get_member_with_binding(self, monkeypatch, client):
        _capture_request(
            monkeypatch,
            client,
            {
                "Result": {
                    "WorkspaceId": "ws1",
                    "UserId": "u1",
                    "Binding": {"BindingId": "b1", "Role": "workspace_user"},
                    "EffectiveRoles": ["workspace_user", "workspace_developer"],
                },
                "ResponseMetadata": {},
            },
        )
        resp = client.get_workspace_member(
            GetWorkspaceMemberRequest(workspace_id="ws1", user_id="u1")
        )
        assert resp.binding.binding_id == "b1"
        assert resp.effective_roles == ["workspace_user", "workspace_developer"]

    def test_update_member_role(self, monkeypatch, client):
        _capture_json(
            monkeypatch,
            client,
            {
                "Result": {
                    "Binding": {"BindingId": "b1", "Role": "workspace_admin"},
                    "EffectiveRoles": ["workspace_admin"],
                },
                "ResponseMetadata": {},
            },
        )
        resp = client.update_workspace_member_role(
            UpdateWorkspaceMemberRoleRequest(
                workspace_id="ws1", user_id="u1", role="workspace_admin"
            )
        )
        assert resp.binding.role == "workspace_admin"
        assert resp.effective_roles == ["workspace_admin"]

    def test_remove_member(self, monkeypatch, client):
        _capture_json(
            monkeypatch,
            client,
            {"Result": {"DeletedBindingId": "b1"}, "ResponseMetadata": {}},
        )
        resp = client.remove_workspace_member(
            RemoveWorkspaceMemberRequest(workspace_id="ws1", user_id="u1")
        )
        assert resp.deleted_binding_id == "b1"


class TestBatchUpdateMembers:
    def test_wire_operations_pascal_case(self, monkeypatch, client):
        calls = _capture_json(
            monkeypatch,
            client,
            {
                "Result": {
                    "SucceededCount": 2,
                    "FailedCount": 0,
                    "Results": [
                        {"Index": 0, "Status": "CREATED", "BindingId": "b1"},
                        {"Index": 1, "Status": "CREATED", "BindingId": "b2"},
                    ],
                },
                "ResponseMetadata": {},
            },
        )
        req = BatchUpdateWorkspaceMembersRequest(
            workspace_id="ws1",
            operations=[
                WorkspaceMemberOperationItem(
                    operation="create", user_id="u1", role="workspace_user"
                ),
                WorkspaceMemberOperationItem(operation="delete", user_id="u2"),
            ],
        )
        resp = client.batch_update_workspace_members(req)

        body = json.loads(calls[0]["body"])
        assert body["WorkspaceId"] == "ws1"
        assert body["Operations"] == [
            {"Operation": "create", "UserId": "u1", "Role": "workspace_user"},
            # delete ops carry no Role key
            {"Operation": "delete", "UserId": "u2"},
        ]
        assert resp.succeeded_count == 2
        assert resp.results[0].binding_id == "b1"

    def test_batch_rules(self):
        # create without role
        with pytest.raises(ValueError):
            BatchUpdateWorkspaceMembersRequest(
                operations=[WorkspaceMemberOperationItem(operation="create", user_id="u1")]
            )
        # delete with role
        with pytest.raises(ValueError):
            BatchUpdateWorkspaceMembersRequest(
                operations=[
                    WorkspaceMemberOperationItem(
                        operation="delete", user_id="u1", role="workspace_user"
                    )
                ]
            )
        # unknown operation kind
        with pytest.raises(ValueError):
            BatchUpdateWorkspaceMembersRequest(
                operations=[WorkspaceMemberOperationItem(operation="upsert", user_id="u1")]
            )
        # >100 operations
        with pytest.raises(ValueError):
            BatchUpdateWorkspaceMembersRequest(
                operations=[
                    WorkspaceMemberOperationItem(
                        operation="delete", user_id=f"u{i}"
                    )
                    for i in range(101)
                ]
            )


# ---------------------------------------------------------------------------
# Validation & error handling
# ---------------------------------------------------------------------------


class TestValidationAndErrors:
    def test_role_constants(self):
        assert set(WORKSPACE_ROLES) == {
            "global_admin",
            "system_admin",
            "workspace_admin",
            "workspace_developer",
            "workspace_user",
        }
        assert set(BATCH_MEMBER_OPERATIONS) == {"create", "update", "delete"}

    def test_list_workspaces_requires_org(self):
        with pytest.raises(ValueError):
            ListWorkspacesRequest(org_id="  ")

    def test_api_error_with_code(self, monkeypatch, client):
        _capture_json(
            monkeypatch,
            client,
            {
                "ResponseMetadata": {
                    "Error": {"Code": "NotFound", "Message": "no workspace"}
                }
            },
        )
        with pytest.raises(ApiError) as exc:
            client.delete_workspace(DeleteWorkspaceRequest(workspace_id="ws1"))
        assert exc.value.error_code == "NotFound"
