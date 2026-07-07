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

"""Tests for the credential commands (add / list / delete)."""

import json

from typer.testing import CliRunner

import agentkit.sdk.identity.client as client_mod
from agentkit.toolkit.cli.cli import app
from agentkit.sdk.identity import types as it

runner = CliRunner()


def _config(config_id, name):
    return it.InboundAuthConfigForList.model_validate(
        {
            "InboundAuthConfigId": config_id,
            "ConfigName": name,
            "AuthType": "ApiKey",
            "CreatedAt": "2025-10-30T07:59:24Z",
        }
    )


# --- add credential ---------------------------------------------------------


def test_add_credential_sends_api_key_request(monkeypatch):
    captured = {}

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def create_inbound_auth_config(self, request):
            captured["request"] = request
            return it.CreateInboundAuthConfigResponse.model_validate(
                {"InboundAuthConfigId": "iac-123"}
            )

    # The commands import the client lazily via ``from ...client import``, which
    # re-reads from the source module at call time — so patching it there works.
    monkeypatch.setattr(client_mod, "AgentkitIdentityClient", _FakeClient)

    result = runner.invoke(
        app,
        [
            "add",
            "credential",
            "--type",
            "api-key",
            "--name",
            "my-openai-key",
            "--api-key",
            "sk-123",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "iac-123" in result.output
    req = captured["request"]
    assert req.auth_type == "ApiKey"
    assert req.config_name == "my-openai-key"
    assert req.api_key_auth_configs[0].api_key_name == "my-openai-key"
    assert req.api_key_auth_configs[0].api_key == "sk-123"


def test_add_credential_invalid_type_fails():
    result = runner.invoke(
        app, ["add", "credential", "--type", "oauth", "--name", "x", "--api-key", "y"]
    )
    assert result.exit_code == 1
    assert "invalid --type" in result.output


def test_add_credential_requires_api_key():
    result = runner.invoke(
        app, ["add", "credential", "--type", "api-key", "--name", "x"]
    )
    assert result.exit_code == 1
    assert "--api-key is required" in result.output


# --- list credentials -------------------------------------------------------


def _patch_list(monkeypatch, configs):
    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def list_inbound_auth_configs(self, request):
            return it.ListInboundAuthConfigsResponse.model_validate(
                {
                    "InboundAuthConfigs": [
                        c.model_dump(by_alias=True, exclude_none=True)
                        for c in configs
                    ],
                    "NextToken": "",
                }
            )

    monkeypatch.setattr(client_mod, "AgentkitIdentityClient", _FakeClient)
    return _FakeClient


def test_list_credentials_table(monkeypatch):
    _patch_list(monkeypatch, [_config("iac-1", "my-openai-key")])
    result = runner.invoke(app, ["list", "credentials"])
    assert result.exit_code == 0, result.output
    assert "my-openai-key" in result.output


def test_list_credentials_quiet_prints_names(monkeypatch):
    _patch_list(
        monkeypatch, [_config("iac-1", "key-a"), _config("iac-2", "key-b")]
    )
    result = runner.invoke(app, ["list", "credentials", "--quiet"])
    assert result.exit_code == 0, result.output
    assert result.output.split() == ["key-a", "key-b"]


def test_list_credentials_json(monkeypatch):
    _patch_list(monkeypatch, [_config("iac-1", "key-a")])
    result = runner.invoke(app, ["list", "credentials", "--output", "json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert [c["ConfigName"] for c in data] == ["key-a"]


# --- delete credential ------------------------------------------------------


def test_delete_credential_resolves_name_to_id(monkeypatch):
    deleted = []

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def list_inbound_auth_configs(self, request):
            return it.ListInboundAuthConfigsResponse.model_validate(
                {
                    "InboundAuthConfigs": [
                        _config("iac-1", "key-a").model_dump(by_alias=True),
                        _config("iac-2", "key-b").model_dump(by_alias=True),
                    ],
                    "NextToken": "",
                }
            )

        def delete_inbound_auth_config(self, request):
            deleted.append(request.inbound_auth_config_id)
            return it.DeleteInboundAuthConfigResponse.model_validate(
                {"InboundAuthConfigId": request.inbound_auth_config_id}
            )

    monkeypatch.setattr(client_mod, "AgentkitIdentityClient", _FakeClient)

    result = runner.invoke(app, ["delete", "credential", "key-b", "--force"])
    assert result.exit_code == 0, result.output
    assert deleted == ["iac-2"]


def _single_key_b_client(deleted):
    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def list_inbound_auth_configs(self, request):
            return it.ListInboundAuthConfigsResponse.model_validate(
                {
                    "InboundAuthConfigs": [
                        _config("iac-2", "key-b").model_dump(by_alias=True),
                    ],
                    "NextToken": "",
                }
            )

        def delete_inbound_auth_config(self, request):
            deleted.append(request.inbound_auth_config_id)
            return it.DeleteInboundAuthConfigResponse.model_validate(
                {"InboundAuthConfigId": request.inbound_auth_config_id}
            )

    return _FakeClient


def test_delete_credential_non_interactive_proceeds_without_prompt(monkeypatch):
    # No TTY (CI / pipe) and no --force: must keep the historical behavior of
    # deleting without a prompt, i.e. adding the guard is not a breaking change.
    import agentkit.toolkit.cli.cli_delete as cli_delete

    monkeypatch.setattr(cli_delete, "_stdin_is_interactive", lambda: False)
    deleted = []
    monkeypatch.setattr(
        client_mod, "AgentkitIdentityClient", _single_key_b_client(deleted)
    )

    result = runner.invoke(app, ["delete", "credential", "key-b"])
    assert result.exit_code == 0, result.output
    assert deleted == ["iac-2"]


def test_delete_credential_interactive_decline_aborts(monkeypatch):
    # With a TTY, declining the prompt must abort before any delete happens.
    import agentkit.toolkit.cli.cli_delete as cli_delete

    monkeypatch.setattr(cli_delete, "_stdin_is_interactive", lambda: True)
    deleted = []
    monkeypatch.setattr(
        client_mod, "AgentkitIdentityClient", _single_key_b_client(deleted)
    )

    result = runner.invoke(app, ["delete", "credential", "key-b"], input="n\n")
    assert result.exit_code != 0
    assert deleted == []


def test_delete_credential_not_found(monkeypatch):
    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def list_inbound_auth_configs(self, request):
            return it.ListInboundAuthConfigsResponse.model_validate(
                {"InboundAuthConfigs": [], "NextToken": ""}
            )

        def delete_inbound_auth_config(self, request):  # pragma: no cover
            raise AssertionError("delete should not be called")

    monkeypatch.setattr(client_mod, "AgentkitIdentityClient", _FakeClient)

    result = runner.invoke(app, ["delete", "credential", "ghost"])
    assert result.exit_code == 1
    assert "not found" in result.output
