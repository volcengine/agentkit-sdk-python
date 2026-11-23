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

"""Unit tests for the AgentKit Users (user pool) SDK client."""

from __future__ import annotations

import base64
import json
from typing import Any, Dict, List, Optional

import pytest
import requests

from agentkit.auth.errors import NetworkError
from agentkit.sdk.users import (
    AddUsersToGroupRequest,
    AgentkitUsersClient,
    ChangeUsersGroupRequest,
    CreateUsersRequest,
    DeleteUserRequest,
    GetUserRequest,
    ImportUsersRequest,
    ListUsersRequest,
    RemoveUsersFromGroupRequest,
    UpdateUserRequest,
    UserForCreateUsers,
)
from agentkit.toolkit.errors import ApiError

CSV_TEMPLATE = "preferred_username,email,phone_number,name\nexample-user,user@example.com,+6582288124,Example Use\n"


@pytest.fixture()
def client() -> AgentkitUsersClient:
    return AgentkitUsersClient(
        access_key="test-ak", secret_key="test-sk", region="cn-beijing"
    )


def _capture_json(
    monkeypatch,
    client: AgentkitUsersClient,
    response: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Replace ``client.json`` with a recorder returning ``response``."""
    calls: List[Dict[str, Any]] = []

    def fake_json(api: str, params=None, body=None) -> str:
        calls.append({"api": api, "params": params, "body": body})
        payload = response if response is not None else {"ResponseMetadata": {}}
        return json.dumps(payload)

    monkeypatch.setattr(client, "json", fake_json)
    return calls


def _capture_request(
    monkeypatch,
    client: AgentkitUsersClient,
    response: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Replace ``client.request`` (GET channel) with a recorder."""
    calls: List[Dict[str, Any]] = []

    def fake_get(api: str, params=None) -> str:
        calls.append({"api": api, "params": params, "data": ""})
        payload = response if response is not None else {"ResponseMetadata": {}}
        return json.dumps(payload)

    monkeypatch.setattr(client, "_send_get", fake_get)
    return calls


# ---------------------------------------------------------------------------
# POST actions: wire body shape
# ---------------------------------------------------------------------------


class TestCreateUsers:
    def test_mixed_casing_body(self, monkeypatch, client):
        """Envelope keys are PascalCase, the array key is lowercase
        ``users`` and item keys are snake_case."""
        calls = _capture_json(
            monkeypatch,
            client,
            {"Result": {"Results": [{"UserId": "u1"}]}, "ResponseMetadata": {}},
        )
        req = CreateUsersRequest(
            users=[UserForCreateUsers(preferred_username="alice", name="Alice")]
        )
        resp = client.create_users(req)

        assert len(calls) == 1
        assert calls[0]["api"] == "CreateUsers"
        body = json.loads(calls[0]["body"])
        assert body == {
            "users": [{"preferred_username": "alice", "name": "Alice"}]
        }
        assert resp.results[0].user_id == "u1"

    def test_user_pool_id_alias_and_optional_drop(self, monkeypatch, client):
        calls = _capture_json(monkeypatch, client)
        req = CreateUsersRequest(
            user_pool_id="pool-1",
            users=[UserForCreateUsers(preferred_username="bob", name="B")],
        )
        client.create_users(req)
        body = json.loads(calls[0]["body"])
        assert body["UserPoolId"] == "pool-1"

    def test_user_pool_id_blank_falls_back_to_default(self, monkeypatch, client):
        calls = _capture_json(monkeypatch, client)
        req = CreateUsersRequest(
            user_pool_id="   ",
            users=[UserForCreateUsers(preferred_username="bob", name="B")],
        )
        client.create_users(req)
        body = json.loads(calls[0]["body"])
        assert "UserPoolId" not in body

    def test_partial_success_results(self, monkeypatch, client):
        _capture_json(
            monkeypatch,
            client,
            {
                "Result": {
                    "Results": [
                        {"UserId": "u1"},
                        {
                            "Error": {"Code": "AlreadyExists", "Message": "dupe"},
                        },
                    ]
                },
                "ResponseMetadata": {},
            },
        )
        req = CreateUsersRequest(
            users=[
                UserForCreateUsers(preferred_username="user-a", name="A"),
                UserForCreateUsers(preferred_username="user-b", name="B"),
            ]
        )
        resp = client.create_users(req)
        assert resp.results[0].error is None
        assert resp.results[1].error.code == "AlreadyExists"

    def test_optional_fields_dropped_when_unset(self, monkeypatch, client):
        calls = _capture_json(monkeypatch, client)
        req = CreateUsersRequest(
            users=[
                UserForCreateUsers(
                    preferred_username="carol", name="C", email="c@x.com"
                )
            ]
        )
        client.create_users(req)
        body = json.loads(calls[0]["body"])
        item = body["users"][0]
        assert item["email"] == "c@x.com"
        assert "phone" not in item
        assert "external_provider_id" not in item


class TestUpdateDeleteUser:
    def test_empty_string_clears_field(self, monkeypatch, client):
        """Empty string means "clear the field" and must survive
        serialization; None fields must be dropped."""
        calls = _capture_json(monkeypatch, client)
        req = UpdateUserRequest(
            user_id="u1", name="", email=None, phone="+8613800138000"
        )
        client.update_user(req)

        body = json.loads(calls[0]["body"])
        assert body["UserId"] == "u1"
        assert body["Name"] == ""
        assert "Email" not in body
        assert body["Phone"] == "+8613800138000"

    def test_delete_user_body(self, monkeypatch, client):
        calls = _capture_json(monkeypatch, client)
        client.delete_user(DeleteUserRequest(user_id="u1", user_pool_id="p1"))
        body = json.loads(calls[0]["body"])
        assert body == {"UserPoolId": "p1", "UserId": "u1"}

    def test_empty_update_response(self, monkeypatch, client):
        _capture_json(monkeypatch, client, {"Result": {}, "ResponseMetadata": {}})
        resp = client.update_user(UpdateUserRequest(user_id="u1"))
        assert resp.model_dump(by_alias=True) == {}  # empty Result parses to empty model


class TestGroupMembership:
    @pytest.mark.parametrize(
        "action,method",
        [
            ("AddUsersToGroup", "add_users_to_group"),
            ("RemoveUsersFromGroup", "remove_users_from_group"),
        ],
    )
    def test_group_body(self, monkeypatch, client, action, method):
        calls = _capture_json(
            monkeypatch,
            client,
            {
                "Result": {
                    "Results": [
                        {"UserId": "u1", "Success": True},
                        {"UserId": "u2", "Error": {"Code": "NotFound"}},
                    ]
                },
                "ResponseMetadata": {},
            },
        )
        req = (
            AddUsersToGroupRequest(group_id="g1", user_ids=["u1", "u2"])
            if action == "AddUsersToGroup"
            else RemoveUsersFromGroupRequest(group_id="g1", user_ids=["u1", "u2"])
        )
        resp = getattr(client, method)(req)

        assert calls[0]["api"] == action
        body = json.loads(calls[0]["body"])
        assert body["GroupId"] == "g1"
        assert body["UserIds"] == ["u1", "u2"]
        assert resp.results[0].success is True
        assert resp.results[1].error.code == "NotFound"

    def test_group_results_parsed(self, monkeypatch, client):
        _capture_json(
            monkeypatch,
            client,
            {
                "Result": {
                    "Results": [
                        {"UserId": "u1", "Success": True},
                        {"UserId": "u2", "Error": {"Code": "NotFound"}},
                    ]
                },
                "ResponseMetadata": {},
            },
        )
        resp = client.add_users_to_group(
            AddUsersToGroupRequest(group_id="g1", user_ids=["u1", "u2"])
        )
        assert resp.results[0].success is True
        assert resp.results[1].error.code == "NotFound"

    def test_change_users_group_body(self, monkeypatch, client):
        calls = _capture_json(
            monkeypatch, client, {"Result": {"Results": []}, "ResponseMetadata": {}}
        )
        client.change_users_group(
            ChangeUsersGroupRequest(
                origin_group_id="g1", target_group_id="g2", user_ids=["u1"]
            )
        )
        body = json.loads(calls[0]["body"])
        assert body == {"OriginGroupId": "g1", "TargetGroupId": "g2", "UserIds": ["u1"]}


class TestImportUsers:
    def test_valid_csv_body(self, monkeypatch, client):
        calls = _capture_json(
            monkeypatch,
            client,
            {
                "Result": {
                    "SuccessCount": 1,
                    "FailureCount": 0,
                    "SuccessfulUserIds": ["u1"],
                    "Errors": [],
                },
                "ResponseMetadata": {},
            },
        )
        req = ImportUsersRequest(
            users_base64=base64.b64encode(CSV_TEMPLATE.encode()).decode(),
            content_type="CSV",
        )
        resp = client.import_users(req)

        body = json.loads(calls[0]["body"])
        assert body["UsersBase64"]
        assert body["ContentType"] == "CSV"
        assert resp.success_count == 1
        assert resp.successful_user_ids == ["u1"]

    def test_import_errors_parsed(self, monkeypatch, client):
        _capture_json(
            monkeypatch,
            client,
            {
                "Result": {
                    "SuccessCount": 0,
                    "FailureCount": 1,
                    "Errors": [
                        {
                            "Index": 1,
                            "Field": "email",
                            "ErrorType": "InvalidFormat",
                            "ErrorMessage": "bad email",
                        }
                    ],
                },
                "ResponseMetadata": {},
            },
        )
        resp = client.import_users(
            ImportUsersRequest(
                users_base64=base64.b64encode(CSV_TEMPLATE.encode()).decode(),
                content_type="csv",  # case-insensitive
            )
        )
        err = resp.errors[0]
        assert err.index == 1
        assert err.error_type == "InvalidFormat"


# ---------------------------------------------------------------------------
# GET actions: query-string params, no body
# ---------------------------------------------------------------------------


class TestListUsers:
    def test_query_params_and_no_body(self, monkeypatch, client):
        calls = _capture_request(
            monkeypatch,
            client,
            {
                "Result": {
                    "Users": [
                        {
                            "UserId": "u1",
                            "PreferredUsername": "alice",
                            "Email": "a@x.com",
                        }
                    ],
                    "NextToken": "",
                },
                "ResponseMetadata": {},
            },
        )
        resp = client.list_users(ListUsersRequest(max_results=0, email="a@x.com"))

        assert len(calls) == 1
        assert calls[0]["api"] == "ListUsers"
        assert calls[0]["data"] == ""  # GET signs sha256("") empty-string body
        params = calls[0]["params"]
        assert params["Email"] == "a@x.com"
        assert params["MaxResults"] == 0  # 0 is a valid "server default" value
        assert "UserPoolId" not in params
        assert resp.users[0].user_id == "u1"
        assert resp.next_token is None  # empty NextToken -> None

    def test_all_params_pascal_case(self, monkeypatch, client):
        calls = _capture_request(monkeypatch, client)
        client.list_users(
            ListUsersRequest(
                user_pool_id="p1",
                preferred_username="alice",
                name="Alice",
                max_results=50,
                next_token="tok",
            )
        )
        params = calls[0]["params"]
        assert params == {
            "UserPoolId": "p1",
            "PreferredUsername": "alice",
            "Name": "Alice",
            "MaxResults": 50,
            "NextToken": "tok",
        }

    def test_next_token_round_trip(self, monkeypatch, client):
        _capture_request(
            monkeypatch,
            client,
            {"Result": {"Users": [], "NextToken": "tok2"}, "ResponseMetadata": {}},
        )
        resp = client.list_users(ListUsersRequest(next_token="tok"))
        assert resp.next_token == "tok2"


class TestGetUser:
    def test_query_params(self, monkeypatch, client):
        calls = _capture_request(
            monkeypatch,
            client,
            {
                "Result": {
                    "UserId": "u1",
                    "PreferredUsername": "alice",
                    "WorkspaceIds": ["w1", "w2"],
                },
                "ResponseMetadata": {},
            },
        )
        resp = client.get_user(GetUserRequest(user_id="u1"))
        assert calls[0]["data"] == ""
        assert calls[0]["params"] == {"UserId": "u1"}
        assert resp.workspace_ids == ["w1", "w2"]


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_api_error_with_code(self, monkeypatch, client):
        _capture_json(
            monkeypatch,
            client,
            {
                "ResponseMetadata": {
                    "Error": {"Code": "AccessDenied", "Message": "nope"}
                }
            },
        )
        with pytest.raises(ApiError) as exc:
            client.delete_user(DeleteUserRequest(user_id="u1"))
        assert exc.value.error_code == "AccessDenied"

    def test_credential_error_retries_then_succeeds(self, monkeypatch, client):
        attempts: List[Dict[str, Any]] = []

        def flaky_json(api, params=None, body=None):
            attempts.append({"api": api})
            if len(attempts) == 1:
                raise Exception("SignatureDoesNotMatch")
            return json.dumps({"Result": {}, "ResponseMetadata": {}})

        monkeypatch.setattr(client, "json", flaky_json)
        client.delete_user(DeleteUserRequest(user_id="u1"))
        assert len(attempts) == 2

    def test_network_error_typed(self, monkeypatch, client):
        def dead_json(api, params=None, body=None):
            raise requests.exceptions.ConnectionError("boom")

        monkeypatch.setattr(client, "json", dead_json)
        with pytest.raises(NetworkError):
            client.delete_user(DeleteUserRequest(user_id="u1"))


# ---------------------------------------------------------------------------
# Client-side validation mirrors
# ---------------------------------------------------------------------------


class TestValidation:
    def test_username_shape(self):
        with pytest.raises(ValueError):
            UserForCreateUsers(preferred_username="a", name="A")  # too short
        with pytest.raises(ValueError):
            UserForCreateUsers(preferred_username="1abcde", name="A")  # digit start
        with pytest.raises(ValueError):
            UserForCreateUsers(preferred_username="a..b", name="A")  # consecutive dots
        with pytest.raises(ValueError):
            UserForCreateUsers(preferred_username="bad name!", name="A")  # bad char

    def test_update_username_cannot_be_cleared(self):
        with pytest.raises(ValueError):
            UpdateUserRequest(user_id="u1", preferred_username="")

    def test_create_batch_bounds(self):
        too_many = [
            UserForCreateUsers(preferred_username=f"u{i}", name="N")
            for i in range(1001)
        ]
        with pytest.raises(ValueError):
            CreateUsersRequest(users=too_many)
        with pytest.raises(ValueError):
            CreateUsersRequest(users=[])

    def test_group_batch_bounds(self):
        too_many = [f"u{i}" for i in range(101)]
        with pytest.raises(ValueError):
            AddUsersToGroupRequest(group_id="g", user_ids=too_many)
        with pytest.raises(ValueError):
            AddUsersToGroupRequest(group_id="g", user_ids=[""])
        with pytest.raises(ValueError):
            ChangeUsersGroupRequest(origin_group_id="a", target_group_id="b", user_ids=[])

    def test_list_users_filters_non_empty(self):
        with pytest.raises(ValueError):
            ListUsersRequest(email="   ")
        with pytest.raises(ValueError):
            ListUsersRequest(next_token="  ")
        with pytest.raises(ValueError):
            ListUsersRequest(max_results=101)
        assert ListUsersRequest(max_results=100).max_results == 100

    def test_import_users_validation(self):
        valid = base64.b64encode(CSV_TEMPLATE.encode()).decode()
        req = ImportUsersRequest(users_base64=valid, content_type="CSV")
        assert req.users_base64 == valid

        with pytest.raises(ValueError):
            ImportUsersRequest(users_base64="not base64!!", content_type="CSV")
        with pytest.raises(ValueError):
            # header-only CSV
            ImportUsersRequest(
                users_base64=base64.b64encode(b"preferred_username,email\n").decode(),
                content_type="CSV",
            )
        with pytest.raises(ValueError):
            ImportUsersRequest(users_base64=valid, content_type="JSON")
