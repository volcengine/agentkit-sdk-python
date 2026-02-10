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


@pytest.mark.parametrize(
    "env_provider, expected_suffix",
    [
        ("volcengine", "cr.volces.com"),
        ("byteplus", "cr.bytepluses.com"),
    ],
)
def test_resolve_cr_domain_from_env(monkeypatch, env_provider, expected_suffix):
    monkeypatch.setenv("AGENTKIT_CLOUD_PROVIDER", env_provider)

    from agentkit.toolkit.builders.ve_pipeline import VeCPCRBuilder, VeCPCRBuilderConfig

    builder = VeCPCRBuilder()
    cfg = VeCPCRBuilderConfig(
        common_config=None,
        cr_instance_name="ins",
        cr_region="ap-southeast-1",
        cr_namespace_name="ns",
        cr_repo_name="repo",
    )

    domain = builder._resolve_cr_domain(cfg, "ap-southeast-1")
    assert domain == f"ins-ap-southeast-1.{expected_suffix}"


def test_resolve_cr_domain_prefers_common_config_provider(monkeypatch):
    monkeypatch.delenv("AGENTKIT_CLOUD_PROVIDER", raising=False)
    monkeypatch.delenv("CLOUD_PROVIDER", raising=False)

    from agentkit.toolkit.builders.ve_pipeline import VeCPCRBuilder, VeCPCRBuilderConfig
    from agentkit.toolkit.config import CommonConfig

    builder = VeCPCRBuilder()
    common = CommonConfig(
        agent_name="agentkit-app",
        entry_point="agent.py",
        cloud_provider="byteplus",
    )
    cfg = VeCPCRBuilderConfig(
        common_config=common,
        cr_instance_name="ins",
        cr_region="ap-southeast-1",
        cr_namespace_name="ns",
        cr_repo_name="repo",
    )

    domain = builder._resolve_cr_domain(cfg, "ap-southeast-1")
    assert domain == "ins-ap-southeast-1.cr.bytepluses.com"


def test_resolve_cr_domain_prefers_explicit_builder_provider(monkeypatch):
    monkeypatch.setenv("AGENTKIT_CLOUD_PROVIDER", "volcengine")

    from agentkit.toolkit.builders.ve_pipeline import VeCPCRBuilder, VeCPCRBuilderConfig
    from agentkit.toolkit.config import CommonConfig

    builder = VeCPCRBuilder()
    common = CommonConfig(
        agent_name="agentkit-app",
        entry_point="agent.py",
        cloud_provider="volcengine",
    )
    cfg = VeCPCRBuilderConfig(
        common_config=common,
        cloud_provider="byteplus",
        cr_instance_name="ins",
        cr_region="ap-southeast-1",
        cr_namespace_name="ns",
        cr_repo_name="repo",
    )

    domain = builder._resolve_cr_domain(cfg, "ap-southeast-1")
    assert domain == "ins-ap-southeast-1.cr.bytepluses.com"
