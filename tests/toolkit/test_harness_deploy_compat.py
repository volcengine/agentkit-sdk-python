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

"""Backward-compatibility contracts for Harness Runtime network options."""

from inspect import Parameter, signature

from typer.testing import CliRunner

from agentkit.toolkit.cli.cli import app
from agentkit.toolkit.harness.config_builder import build_agentkit_config
from agentkit.toolkit.harness.deploy import deploy_harness


def test_legacy_config_builder_call_does_not_add_runtime_network():
    config = build_agentkit_config(
        "legacy-harness",
        "cn-beijing",
        {"EXISTING_ENV": "value"},
        None,
        "Auto",
    )

    cloud = config["launch_types"]["cloud"]
    assert "runtime_network" not in cloud
    assert cloud["runtime_id"] == "Auto"


def test_runtime_network_is_opt_in():
    runtime_network = {
        "mode": "private",
        "vpc_id": "vpc-example",
        "subnet_ids": ["subnet-example"],
    }

    config = build_agentkit_config(
        "private-harness",
        "cn-beijing",
        {},
        runtime_network=runtime_network,
    )

    assert config["launch_types"]["cloud"]["runtime_network"] == runtime_network


def test_public_deploy_network_options_are_optional_keyword_only_parameters():
    parameters = signature(deploy_harness).parameters

    for name in (
        "runtime_network_mode",
        "runtime_vpc_id",
        "runtime_subnet_ids",
        "runtime_enable_shared_internet_access",
    ):
        assert parameters[name].kind is Parameter.KEYWORD_ONLY
        assert parameters[name].default is None


def test_cli_helper_preserves_legacy_assume_yes_positional_parameter():
    from agentkit.toolkit.cli.cli_deploy import _deploy_harness

    parameters = list(signature(_deploy_harness).parameters.values())

    assert [parameter.name for parameter in parameters[:7]] == [
        "name",
        "region",
        "access_key",
        "secret_key",
        "discovery_url",
        "allowed_id",
        "assume_yes",
    ]
    assert parameters[6].default is False
    assert all(parameter.kind is Parameter.KEYWORD_ONLY for parameter in parameters[7:])


def test_legacy_cli_invocation_keeps_network_options_unset(monkeypatch):
    import agentkit.toolkit.cli.cli_deploy as cli_deploy

    captured = {}

    def fake_deploy_harness(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(cli_deploy, "_deploy_harness", fake_deploy_harness)

    result = CliRunner().invoke(app, ["deploy", "--harness", "legacy-harness"])

    assert result.exit_code == 0, result.output
    assert captured["runtime_network_mode"] is None
    assert captured["runtime_vpc_id"] is None
    assert not captured["runtime_subnet_ids"]
    assert captured["runtime_enable_shared_internet_access"] is None
