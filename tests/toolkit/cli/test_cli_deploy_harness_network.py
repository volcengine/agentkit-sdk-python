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

"""Tests for Harness Runtime network deployment options."""

from typer.testing import CliRunner

from agentkit.toolkit.cli import cli_deploy
from agentkit.toolkit.cli.cli import app
from agentkit.toolkit.harness.config_builder import build_agentkit_config


runner = CliRunner()


def test_harness_network_options_are_forwarded(monkeypatch):
    captured = {}

    def fake_deploy_harness(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(cli_deploy, "_deploy_harness", fake_deploy_harness)

    result = runner.invoke(
        app,
        [
            "deploy",
            "--harness",
            "test-agent",
            "--runtime-network-mode",
            "private",
            "--runtime-vpc-id",
            "vpc-123",
            "--runtime-subnet-id",
            "subnet-a",
            "--runtime-subnet-id",
            "subnet-b",
            "--runtime-enable-shared-internet-access",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["runtime_network_mode"] == "private"
    assert captured["runtime_vpc_id"] == "vpc-123"
    assert captured["runtime_subnet_ids"] == ["subnet-a", "subnet-b"]
    assert captured["runtime_enable_shared_internet_access"] is True


def test_network_options_require_harness():
    result = runner.invoke(app, ["deploy", "--runtime-network-mode", "private"])

    assert result.exit_code != 0
    assert "Runtime network options require --harness" in result.output


def test_config_builder_includes_runtime_network():
    runtime_network = {
        "mode": "private",
        "vpc_id": "vpc-123",
        "subnet_ids": ["subnet-a"],
        "enable_shared_internet_access": True,
    }

    config = build_agentkit_config(
        runtime_name="test-agent",
        region="cn-shanghai",
        envs={},
        runtime_network=runtime_network,
    )

    assert config["launch_types"]["cloud"]["runtime_network"] == runtime_network


def test_config_builder_omits_empty_runtime_network():
    config = build_agentkit_config(
        runtime_name="test-agent", region="cn-shanghai", envs={}
    )

    assert "runtime_network" not in config["launch_types"]["cloud"]
