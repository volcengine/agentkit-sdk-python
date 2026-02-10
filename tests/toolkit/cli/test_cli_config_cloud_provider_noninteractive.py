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


def test_collect_cli_params_accepts_cloud_provider() -> None:
    from agentkit.toolkit.config.config_handler import ConfigParamHandler

    params = ConfigParamHandler.collect_cli_params(
        agent_name=None,
        entry_point=None,
        description=None,
        language=None,
        language_version=None,
        python_version=None,
        dependencies_file=None,
        launch_type=None,
        cloud_provider="byteplus",
        runtime_envs=None,
        strategy_runtime_envs=None,
        region=None,
        tos_bucket=None,
        image_tag=None,
        cr_instance_name=None,
        cr_namespace_name=None,
        cr_repo_name=None,
        cr_auto_create_instance_type=None,
        runtime_name=None,
        runtime_role_name=None,
        runtime_apikey_name=None,
        runtime_auth_type=None,
        runtime_jwt_discovery_url=None,
        runtime_jwt_allowed_clients=None,
        memory_id=None,
        knowledge_id=None,
        tool_id=None,
        mcp_toolset_id=None,
        runtime_network_mode=None,
        runtime_vpc_id=None,
        runtime_subnet_ids=None,
        runtime_enable_shared_internet_access=None,
    )

    assert params["common"]["cloud_provider"] == "byteplus"


def test_noninteractive_config_updates_project_cloud_provider(tmp_path) -> None:
    import yaml

    from agentkit.toolkit.config.config_handler import NonInteractiveConfigHandler

    cfg_path = tmp_path / "agentkit.yaml"
    cfg_path.write_text(
        "common:\n"
        "  agent_name: my-agent\n"
        "  entry_point: agent.py\n"
        "  cloud_provider: volcengine\n",
        encoding="utf-8",
    )

    handler = NonInteractiveConfigHandler(config_path=str(cfg_path))
    ok = handler.update_config(
        common_params={"cloud_provider": "byteplus"},
        strategy_params={},
        dry_run=False,
    )
    assert ok is True

    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    assert data["common"]["cloud_provider"] == "byteplus"
