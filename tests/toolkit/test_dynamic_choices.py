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

import os

import pytest

from agentkit.toolkit.config.config_validator import ConfigValidator
from agentkit.toolkit.config.strategy_configs import CloudStrategyConfig


class TestDynamicChoices:
    def test_region_choices_by_provider_volcengine(self, monkeypatch):
        obj = CloudStrategyConfig.from_dict({"region": "cn-shanghai"}, skip_render=True)
        errors = ConfigValidator.validate_dataclass(
            obj, context={"cloud_provider": "volcengine"}
        )
        assert errors == []

        obj2 = CloudStrategyConfig.from_dict(
            {"region": "ap-southeast-1"}, skip_render=True
        )
        errors2 = ConfigValidator.validate_dataclass(
            obj2, context={"cloud_provider": "volcengine"}
        )
        assert any("must be one of" in e for e in errors2)

    def test_region_choices_by_provider_byteplus(self, monkeypatch):
        obj = CloudStrategyConfig.from_dict(
            {"region": "ap-southeast-1"}, skip_render=True
        )
        errors = ConfigValidator.validate_dataclass(
            obj, context={"cloud_provider": "byteplus"}
        )
        assert errors == []

        obj2 = CloudStrategyConfig.from_dict({"region": "cn-beijing"}, skip_render=True)
        errors2 = ConfigValidator.validate_dataclass(
            obj2, context={"cloud_provider": "byteplus"}
        )
        assert any("must be one of" in e for e in errors2)

    def test_disable_strict_region_restrictions_allows_free(self, monkeypatch, mocker):
        monkeypatch.setenv("AGENTKIT_CLOUD_PROVIDER", "byteplus")

        from agentkit.toolkit.config.global_config import GlobalConfig

        mock_gc = GlobalConfig()
        mock_gc.defaults.disable_region_strict_restrictions = True
        mocker.patch(
            "agentkit.toolkit.config.global_config.get_global_config",
            return_value=mock_gc,
        )

        obj = CloudStrategyConfig.from_dict({"region": "cn-beijing"}, skip_render=True)
        errors = ConfigValidator.validate_dataclass(
            obj, context={"cloud_provider": "byteplus"}
        )
        assert errors == []
