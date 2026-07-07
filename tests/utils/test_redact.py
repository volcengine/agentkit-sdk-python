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

"""Regression coverage for :func:`agentkit.utils.redact.redact`.

The field list is driven by the secret key names this repo actually uses in its
config and error messages (e.g. ``volcengine.secret_key``), so a rename there
should be mirrored here.
"""

import pytest

from agentkit.utils.redact import redact

# Each string carries a secret whose value must not survive redaction.
SECRET_CASES = [
    "secret_key=AKLTaBcSecretValue123456",
    "volcengine.secret_key: myLongSecretKeyValue0099",
    "secret_access_key=SKverylongsecretvalue0099",
    "session_token=abcLONGsessiontoken123456",
    'X-Security-Token: STSverylongtokenvalue123XYZ',
    "authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payloadsegment.signaturesegment",
    "api_key=sk-abcdef0123456789abcdef",
    "Signature=" + "a1b2c3d4" * 8,  # 64-hex presigned-URL HMAC
]

# Well-known identifier shapes that must be preserved so logs stay debuggable.
SURVIVOR_CASES = [
    "trace_id 4bf92f3577b34da6a3ce929d0e0e4736",  # 32-hex OTel trace id
    "commit 5eaa7e2abc1234567890abcdef1234567890abcd",  # 40-hex git sha
    "request_id 550e8400-e29b-41d4-a716-446655440000",  # uuid
]


@pytest.mark.parametrize("text", SECRET_CASES)
def test_redact_masks_secret_fields(text):
    assert "***" in redact(text)


@pytest.mark.parametrize("text", SECRET_CASES)
def test_redact_drops_the_secret_value(text):
    # The literal secret value (everything after the delimiter) must be gone.
    delimiter = ":" if ":" in text.split("=", 1)[0] else "="
    value = text.split(delimiter, 1)[1].strip().removeprefix("Bearer ")
    assert value not in redact(text)


@pytest.mark.parametrize("text", SURVIVOR_CASES)
def test_redact_preserves_identifiers(text):
    assert redact(text) == text
