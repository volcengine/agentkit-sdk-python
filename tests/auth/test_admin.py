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

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from agentkit.auth.admin import CliAccessCoords, publish_discovery
from agentkit.auth.errors import AuthError


class TosError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def install_fake_tos(monkeypatch, create_bucket_error: Exception):
    client = MagicMock()
    client.create_bucket.side_effect = create_bucket_error
    tos_module = SimpleNamespace(
        ACLType=SimpleNamespace(ACL_Public_Read="public-read"),
        TosClientV2=MagicMock(return_value=client),
    )
    monkeypatch.setitem(sys.modules, "tos", tos_module)
    return client


def make_coords() -> CliAccessCoords:
    return CliAccessCoords(
        account_id="account",
        region="cn-beijing",
        user_pool_uid="pool",
        issuer="https://issuer.example",
        client_id="client",
        role_trn="role",
        provider_trn="provider",
    )


@pytest.mark.parametrize(
    "error_code",
    ["BucketAlreadyExists", "BucketAlreadyOwnedByYou"],
)
def test_publish_discovery_ignores_explicit_bucket_conflicts(monkeypatch, error_code):
    client = install_fake_tos(
        monkeypatch,
        TosError(error_code, "bucket is already owned"),
    )

    url = publish_discovery(
        make_coords(),
        bucket="existing-bucket",
        custom_domain="agent.example",
        access_key="ak",
        secret_key="sk",
    )

    assert url == "https://agent.example"
    client.put_object.assert_called_once()


def test_publish_discovery_does_not_swallow_authentication_errors(monkeypatch):
    client = install_fake_tos(
        monkeypatch,
        TosError(
            "InvalidAccessKeyId",
            "the specified access key does not exist",
        ),
    )

    with pytest.raises(AuthError, match="could not create the TOS bucket"):
        publish_discovery(
            make_coords(),
            bucket="new-bucket",
            custom_domain="agent.example",
            access_key="invalid-ak",
            secret_key="invalid-sk",
        )

    client.put_object.assert_not_called()
