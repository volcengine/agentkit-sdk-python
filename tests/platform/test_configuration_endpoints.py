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

import pytest
import os
from agentkit.platform.configuration import VolcConfiguration
from agentkit.platform.constants import DEFAULT_REGION
from agentkit.platform.provider import ENV_CLOUD_PROVIDER
from agentkit.platform.provider import ENV_CLOUD_PROVIDER


class TestConfigurationEndpoints:
    def test_region_explicit_priority(self, clean_env, mock_global_config):
        """Test explicit region overrides everything."""
        os.environ["VOLCENGINE_REGION"] = "env_region"

        config = VolcConfiguration(region="explicit_region")
        assert config.region == "explicit_region"

        # Service endpoint should also respect this logical region (unless mapped)
        ep = config.get_service_endpoint("agentkit")
        assert ep.region == "explicit_region"

    def test_endpoint_default_metadata(self, clean_env, mock_global_config):
        """Test default metadata is used correctly."""
        config = VolcConfiguration()
        ep = config.get_service_endpoint("agentkit")

        assert ep.host == "open.volcengineapi.com"
        assert ep.scheme == "https"
        assert ep.region == DEFAULT_REGION

    def test_endpoint_env_override(self, clean_env, mock_global_config):
        """Test environment variables override endpoint details."""
        os.environ["VOLCENGINE_AGENTKIT_HOST"] = "custom.host"
        os.environ["VOLCENGINE_AGENTKIT_SCHEME"] = "http"

        config = VolcConfiguration()
        ep = config.get_service_endpoint("agentkit")

        assert ep.host == "custom.host"
        assert ep.scheme == "http"

    def test_region_mapping_default(self, clean_env, mock_global_config):
        """Test default region mapping rules (e.g. cn-shanghai -> cn-beijing for CP)."""
        config = VolcConfiguration(region="cn-shanghai")

        # Agentkit has no mapping, should stay shanghai
        ak_ep = config.get_service_endpoint("agentkit")
        assert ak_ep.region == "cn-shanghai"

        # CP has mapping in DEFAULT_REGION_RULES
        cp_ep = config.get_service_endpoint("cp")
        assert cp_ep.region == "cn-beijing"

    def test_region_mapping_custom(self, clean_env, mock_global_config):
        """Test user defined region mapping rules."""
        mock_global_config.update(
            {"region_policy": {"rules": {"cn-shanghai": {"agentkit": "cn-guangzhou"}}}}
        )

        config = VolcConfiguration(region="cn-shanghai")
        ep = config.get_service_endpoint("agentkit")

        assert ep.region == "cn-guangzhou"

    def test_service_specific_region(self, clean_env, mock_global_config):
        """Test service specific region override."""
        os.environ["VOLCENGINE_REGION"] = "cn-beijing"
        os.environ["VOLCENGINE_CR_REGION"] = "us-east-1"

        config = VolcConfiguration()

        # Global region is beijing
        assert config.region == "cn-beijing"

        # CR endpoint uses service specific region
        cr_ep = config.get_service_endpoint("cr")
        assert cr_ep.region == "us-east-1"

        # Host template should use the service specific region
        # cr.{region}.volcengineapi.com -> cr.us-east-1.volcengineapi.com
        assert cr_ep.host == "cr.us-east-1.volcengineapi.com"

    def test_endpoint_unknown_service(self, clean_env, mock_global_config):
        """Test that unknown service raises ValueError."""
        config = VolcConfiguration()
        with pytest.raises(ValueError, match="Unsupported service"):
            config.get_service_endpoint("unknown_service")

    def test_endpoint_case_insensitive(self, clean_env, mock_global_config):
        """Test that service lookup is case insensitive."""
        config = VolcConfiguration()
        ep = config.get_service_endpoint("AgentKit")
        assert ep.host == "open.volcengineapi.com"

    def test_byteplus_endpoint_default_metadata(self, clean_env, mock_global_config):
        """Test BytePlus uses an isolated default endpoint registry."""
        os.environ[ENV_CLOUD_PROVIDER] = "byteplus"

        config = VolcConfiguration()
        ep = config.get_service_endpoint("agentkit")

        assert config.provider.value == "byteplus"
        assert ep.host == "agentkit.ap-southeast-1.byteplusapi.com"
        assert ep.scheme == "https"
        assert ep.region == "ap-southeast-1"

    def test_byteplus_env_alias_cloud_provider(self, clean_env, mock_global_config):
        """Test CLOUD_PROVIDER env var alias is supported (case-insensitive)."""
        os.environ["CLOUD_PROVIDER"] = "BytePlus"

        config = VolcConfiguration()
        ep = config.get_service_endpoint("agentkit")

        assert config.provider.value == "byteplus"
        assert ep.host == "agentkit.ap-southeast-1.byteplusapi.com"
