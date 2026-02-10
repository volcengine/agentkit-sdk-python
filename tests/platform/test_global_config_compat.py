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

import pytest
from agentkit.toolkit.config.global_config import GlobalConfig


class TestGlobalConfigCompatibility:
    def test_legacy_region_migration(self):
        """Test that legacy volcengine.region is correctly migrated to top-level region."""
        legacy_data = {
            "volcengine": {
                "access_key": "ak",
                "secret_key": "sk",
                "region": "cn-shanghai",  # Legacy location
            }
        }

        config = GlobalConfig.from_dict(legacy_data)

        # Verify region is hoisted
        assert config.region == "cn-shanghai"

        # Verify credentials are still there
        assert config.volcengine.access_key == "ak"

    def test_new_region_priority(self):
        """Test that top-level region takes priority over legacy location."""
        mixed_data = {
            "region": "cn-beijing",  # New location
            "volcengine": {
                "access_key": "ak",
                "secret_key": "sk",
                "region": "cn-shanghai",  # Legacy location
            },
        }

        config = GlobalConfig.from_dict(mixed_data)

        # Verify top-level wins
        assert config.region == "cn-beijing"

    def test_byteplus_region_prefers_byteplus_region_when_default_provider(self):
        data = {
            "defaults": {"cloud_provider": "byteplus"},
            "byteplus": {"region": "ap-southeast-1"},
            "volcengine": {"region": "cn-shanghai"},
        }
        config = GlobalConfig.from_dict(data)
        assert config.region == "ap-southeast-1"

    def test_byteplus_region_does_not_fall_back_to_volcengine_region(self):
        data = {
            "defaults": {"cloud_provider": "byteplus"},
            "volcengine": {"region": "cn-shanghai"},
        }
        config = GlobalConfig.from_dict(data)
        assert config.region == ""
