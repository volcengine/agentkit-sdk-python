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

"""Backward-compatible extension hooks used by optional Harness capabilities."""

from inspect import Parameter, signature

from agentkit.toolkit.harness.config_builder import build_agentkit_config
from agentkit.toolkit.harness.deploy import deploy_harness


def test_legacy_config_builder_call_is_unchanged():
    config = build_agentkit_config(
        "legacy-harness",
        "cn-beijing",
        {"EXISTING_ENV": "value"},
        None,
        "Auto",
    )

    cloud = config["launch_types"]["cloud"]
    assert cloud["runtime_id"] == "Auto"
    assert "runtime_network" not in cloud


def test_cloud_config_overrides_are_opt_in():
    config = build_agentkit_config(
        "extended-harness",
        "cn-beijing",
        {},
        cloud_config_overrides={"extension_value": "enabled"},
    )

    assert config["launch_types"]["cloud"]["extension_value"] == "enabled"


def test_new_deploy_hooks_are_optional_keyword_only_parameters():
    parameters = signature(deploy_harness).parameters

    for name in ("runtime_env_builder", "cloud_config_overrides"):
        assert parameters[name].kind is Parameter.KEYWORD_ONLY
        assert parameters[name].default is None
