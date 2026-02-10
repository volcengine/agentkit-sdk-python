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

from __future__ import annotations


def test_platform_context_provider_overrides_env(monkeypatch) -> None:
    from agentkit.platform import VolcConfiguration
    from agentkit.platform.provider import ENV_CLOUD_PROVIDER
    from agentkit.platform.context import default_cloud_provider

    monkeypatch.setenv(ENV_CLOUD_PROVIDER, "volcengine")

    cfg = VolcConfiguration()
    ep = cfg.get_service_endpoint("agentkit")
    assert cfg.provider.value == "volcengine"
    assert not ep.host.endswith(".byteplusapi.com")

    with default_cloud_provider("byteplus"):
        cfg2 = VolcConfiguration()
        ep2 = cfg2.get_service_endpoint("agentkit")
        assert cfg2.provider.value == "byteplus"
        assert ep2.host.endswith(".byteplusapi.com")

    cfg3 = VolcConfiguration()
    ep3 = cfg3.get_service_endpoint("agentkit")
    assert cfg3.provider.value == "volcengine"
    assert not ep3.host.endswith(".byteplusapi.com")
