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

import inspect

from agentkit.toolkit.config.choice_resolvers import resolve_field_choices
from agentkit.toolkit.config.strategy_configs import CloudStrategyConfig
from agentkit.toolkit.volcengine.cr import VeCR
from agentkit.toolkit.volcengine.services.cr_service import CRServiceConfig


def test_byteplus_region_choices_only_one() -> None:
    resolved = resolve_field_choices(
        "region",
        metadata={"choices_resolver": "region_by_cloud_provider"},
        current_config=None,
        dataclass_type=CloudStrategyConfig,
        context={"cloud_provider": "byteplus"},
    )
    assert resolved is not None
    assert [c["value"] for c in resolved.choices] == ["ap-southeast-1"]


def test_vecr_default_region_is_none() -> None:
    sig = inspect.signature(VeCR.__init__)
    assert sig.parameters["region"].default is None


def test_cr_service_config_default_region_is_empty() -> None:
    cfg = CRServiceConfig()
    assert cfg.region == ""
