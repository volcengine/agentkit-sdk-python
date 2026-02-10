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

from agentkit.platform.context import default_cloud_provider
from agentkit.toolkit.config.strategy_configs import (
    CloudStrategyConfig,
    HybridStrategyConfig,
)


def test_cloud_strategy_region_default_follows_provider_context():
    with default_cloud_provider("byteplus"):
        cfg = CloudStrategyConfig.from_dict({}, skip_render=True)
        assert cfg.region == "ap-southeast-1"
        assert cfg.to_persist_dict()["region"] == ""

    with default_cloud_provider("volcengine"):
        cfg = CloudStrategyConfig.from_dict({}, skip_render=True)
        assert cfg.region == "cn-beijing"
        assert cfg.to_persist_dict()["region"] == ""


def test_cloud_strategy_region_explicit_value_is_preserved_and_persisted():
    cfg = CloudStrategyConfig.from_dict({"region": "cn-shanghai"}, skip_render=True)
    assert cfg.region == "cn-shanghai"
    assert cfg.to_persist_dict()["region"] == "cn-shanghai"


def test_cloud_strategy_empty_region_is_treated_as_unset():
    with default_cloud_provider("byteplus"):
        cfg = CloudStrategyConfig.from_dict({"region": ""}, skip_render=True)
        assert cfg.region == "ap-southeast-1"
        assert cfg.to_persist_dict()["region"] == ""


def test_hybrid_strategy_region_default_and_alias_behavior():
    with default_cloud_provider("byteplus"):
        cfg = HybridStrategyConfig.from_dict({}, skip_render=True)
        assert cfg.region == "ap-southeast-1"
        assert cfg.to_persist_dict()["region"] == ""

    cfg = HybridStrategyConfig.from_dict({"ve_region": "cn-shanghai"}, skip_render=True)
    assert cfg.region == "cn-shanghai"
    assert cfg.to_persist_dict()["region"] == "cn-shanghai"
