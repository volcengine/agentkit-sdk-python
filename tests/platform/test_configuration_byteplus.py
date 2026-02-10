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

import os

import pytest

from agentkit.platform.configuration import VolcConfiguration
from agentkit.platform.provider import ENV_CLOUD_PROVIDER


class TestConfigurationBytePlus:
    def test_byteplus_default_endpoint_and_region(self, clean_env, mock_global_config):
        os.environ[ENV_CLOUD_PROVIDER] = "byteplus"

        config = VolcConfiguration()
        ep = config.get_service_endpoint("agentkit")

        assert config.provider.value == "byteplus"
        assert ep.host == "agentkit.ap-southeast-1.byteplusapi.com"
        assert ep.scheme == "https"
        assert ep.region == "ap-southeast-1"

    def test_byteplus_region_falls_back_to_top_level_region(
        self, clean_env, mock_global_config
    ):
        os.environ[ENV_CLOUD_PROVIDER] = "byteplus"
        mock_global_config.update({"region": "us-east-1"})

        config = VolcConfiguration()
        ep = config.get_service_endpoint("agentkit")

        assert config.region == "us-east-1"
        assert ep.region == "us-east-1"
        assert ep.host == "agentkit.us-east-1.byteplusapi.com"

    def test_byteplus_service_region_override(self, clean_env, mock_global_config):
        os.environ[ENV_CLOUD_PROVIDER] = "byteplus"
        os.environ["BYTEPLUS_CR_REGION"] = "us-east-1"

        config = VolcConfiguration()
        ep = config.get_service_endpoint("cr")

        assert ep.region == "us-east-1"
        assert ep.host == "cr.us-east-1.byteplusapi.com"

    def test_byteplus_ignores_volcengine_region_rules(
        self, clean_env, mock_global_config
    ):
        os.environ[ENV_CLOUD_PROVIDER] = "byteplus"

        config = VolcConfiguration(region="cn-shanghai")
        cp_ep = config.get_service_endpoint("cp")

        # Volcano Engine has cn-shanghai -> cn-beijing mapping for CP, but BytePlus should not.
        assert cp_ep.region == "cn-shanghai"

    def test_byteplus_creds_from_env(self, clean_env, mock_global_config):
        os.environ[ENV_CLOUD_PROVIDER] = "byteplus"
        os.environ["BYTEPLUS_ACCESS_KEY"] = "BP_AK"
        os.environ["BYTEPLUS_SECRET_KEY"] = "BP_SK"

        config = VolcConfiguration()
        creds = config.get_service_credentials("agentkit")

        assert creds.access_key == "BP_AK"
        assert creds.secret_key == "BP_SK"

    def test_byteplus_creds_from_config(self, clean_env, mock_global_config, mocker):
        os.environ[ENV_CLOUD_PROVIDER] = "byteplus"
        mocker.patch("pathlib.Path.exists", return_value=False)
        mock_global_config.update(
            {"byteplus": {"access_key": "BP_CFG_AK", "secret_key": "BP_CFG_SK"}}
        )

        config = VolcConfiguration()
        creds = config.get_service_credentials("agentkit")

        assert creds.access_key == "BP_CFG_AK"
        assert creds.secret_key == "BP_CFG_SK"

    def test_byteplus_region_policy_is_isolated(self, clean_env, mock_global_config):
        os.environ[ENV_CLOUD_PROVIDER] = "byteplus"

        # Root region_policy should not affect BytePlus.
        mock_global_config.update(
            {"region_policy": {"rules": {"cn-shanghai": {"agentkit": "cn-guangzhou"}}}}
        )

        config = VolcConfiguration(region="cn-shanghai")
        ep = config.get_service_endpoint("agentkit")

        assert ep.region == "cn-shanghai"

        # Provider-specific region_policy should.
        mock_global_config.update(
            {
                "byteplus": {
                    "region_policy": {
                        "rules": {"cn-shanghai": {"agentkit": "ap-southeast-1"}}
                    }
                }
            }
        )
        config2 = VolcConfiguration(region="cn-shanghai")
        ep2 = config2.get_service_endpoint("agentkit")
        assert ep2.region == "ap-southeast-1"


def test_byteplus_unknown_service_raises(clean_env, mock_global_config):
    os.environ[ENV_CLOUD_PROVIDER] = "byteplus"
    config = VolcConfiguration()
    with pytest.raises(ValueError, match="Unsupported service"):
        config.get_service_endpoint("unknown_service")
