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

"""Golden-vector tests for the ve_sign signing algorithm.

The signing path (canonical request -> string-to-sign -> HMAC chain ->
Authorization header) previously had zero direct coverage: a signing bug is a
silent auth failure against the OpenAPI. These tests pin the algorithm with a
fixed timestamp and fixed credentials so any change to canonicalization,
scope, or the HMAC chain shows up as a diff against known-good vectors.

They also pin the thread-safety contract of the parameterized refactor: two
calls with different service/region scopes must not bleed into each other
(the old implementation passed scope via mutable module globals).

No network is performed: ``ve_sign._signed_request`` is stubbed out.
"""

import datetime
import json

import pytest

from agentkit.utils import ve_sign


FIXED_DATE = datetime.datetime(2026, 1, 2, 3, 4, 5)
SCOPE = dict(
    service="test-svc",
    version="2024-01-01",
    region="cn-test",
    host="open.test.example.com",
    content_type="application/json",
    scheme="https",
)


@pytest.fixture
def capture_signed_request(monkeypatch):
    """Stub the transport; capture what the signer hands to it."""
    captured = {}

    def _fake(method, url, headers, params, data):
        captured.update(
            method=method, url=url, headers=headers, params=params, data=data
        )

        class _Resp:
            @staticmethod
            def json():
                return {"ResponseMetadata": {"Action": "ListFoo"}}

        return _Resp()

    monkeypatch.setattr(ve_sign, "_signed_request", _fake)
    return captured


# --------------------------------------------------------------------------- #
# norm_query
# --------------------------------------------------------------------------- #


def test_norm_query_sorts_keys_encodes_and_expands_lists():
    # Keys sorted; list values expanded in given order; space -> %20, + -> %2B.
    assert (
        ve_sign.norm_query({"b": "1", "a": ["y", "x"], "sp ace": "v+1"})
        == "a=y&a=x&b=1&sp%20ace=v%2B1"
    )


# --------------------------------------------------------------------------- #
# request(): golden signing vector
# --------------------------------------------------------------------------- #


def test_request_produces_golden_authorization_header(capture_signed_request):
    ve_sign.request(
        "POST",
        FIXED_DATE,
        {"Limit": "2"},
        {},
        "AKTEST",
        "SKTEST",
        "ListFoo",
        json.dumps({"a": 1}),
        **SCOPE,
    )
    headers = capture_signed_request["headers"]

    assert capture_signed_request["url"] == "https://open.test.example.com/"
    assert headers["X-Date"] == "20260102T030405Z"
    assert headers["Host"] == "open.test.example.com"
    assert headers["Content-Type"] == "application/json"
    assert (
        headers["X-Content-Sha256"]
        == "f9d86028c6e0d64e225186f96acb69338b2c59764df79162107f5c4bb34d1310"
    )
    # Golden vector: any change to canonicalization/scope/HMAC chain breaks this.
    assert headers["Authorization"] == (
        "HMAC-SHA256 Credential=AKTEST/20260102/cn-test/test-svc/request, "
        "SignedHeaders=content-type;host;x-content-sha256;x-date, "
        "Signature=1191b7baccab57749590b7da8aef8af04894e52b208da0f0fd6733f3ef25c8db"
    )
    # Action/Version merged into the query ahead of caller params.
    assert capture_signed_request["params"] == {
        "Action": "ListFoo",
        "Version": "2024-01-01",
        "Limit": "2",
    }


def test_request_scope_is_per_call_not_global(capture_signed_request):
    """Two calls with different scopes must not bleed into each other."""
    ve_sign.request(
        "POST", FIXED_DATE, {}, {}, "AK", "SK", "ActA", "", **SCOPE
    )
    first_auth = capture_signed_request["headers"]["Authorization"]

    other = dict(SCOPE, service="other-svc", region="cn-other")
    ve_sign.request(
        "POST", FIXED_DATE, {}, {}, "AK", "SK", "ActA", "", **other
    )
    second_auth = capture_signed_request["headers"]["Authorization"]

    assert "/cn-test/test-svc/" in first_auth
    assert "/cn-other/other-svc/" in second_auth
    # Module-level legacy defaults were not mutated by parameterized calls.
    assert ve_sign.Service == ""
    assert ve_sign.Region == ""


# --------------------------------------------------------------------------- #
# check_error
# --------------------------------------------------------------------------- #


def test_check_error_raises_on_top_level_error():
    with pytest.raises(ValueError, match="Error in response"):
        ve_sign.check_error({"Error": {"Code": "X"}})


def test_check_error_raises_on_response_metadata_error():
    with pytest.raises(ValueError, match="AccessDenied"):
        ve_sign.check_error(
            {
                "ResponseMetadata": {
                    "Action": "ListFoo",
                    "Error": {"Code": "AccessDenied", "Message": "nope"},
                }
            }
        )


def test_check_error_passes_clean_response():
    ve_sign.check_error({"ResponseMetadata": {"Action": "ListFoo"}, "Result": {}})
