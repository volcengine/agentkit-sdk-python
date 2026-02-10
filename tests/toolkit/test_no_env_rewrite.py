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

import os
from pathlib import Path


def test_executor_load_config_does_not_rewrite_cloud_provider_env(monkeypatch) -> None:
    from agentkit.platform.provider import ENV_CLOUD_PROVIDER
    from agentkit.toolkit.executors.base_executor import BaseExecutor

    monkeypatch.setenv(ENV_CLOUD_PROVIDER, "volcengine")

    executor = BaseExecutor()
    executor._load_config(
        config_dict={"common": {"cloud_provider": "byteplus"}},
        config_file=None,
    )

    assert os.environ.get(ENV_CLOUD_PROVIDER) == "volcengine"


def test_noninteractive_config_handler_does_not_rewrite_cloud_provider_env(
    tmp_path: Path, monkeypatch
) -> None:
    from agentkit.platform.provider import ENV_CLOUD_PROVIDER
    from agentkit.toolkit.config import CommonConfig, get_config
    from agentkit.toolkit.config.config_handler import NonInteractiveConfigHandler
    from agentkit.toolkit.config.config import clear_config_cache

    monkeypatch.setenv(ENV_CLOUD_PROVIDER, "volcengine")

    config_path = tmp_path / "agentkit.yaml"
    clear_config_cache()
    manager = get_config(config_path=str(config_path), force_reload=True)
    manager.update_common_config(
        CommonConfig(
            agent_name="agentkit-app",
            entry_point="agent.py",
            launch_type="cloud",
            cloud_provider="volcengine",
        )
    )

    handler = NonInteractiveConfigHandler(config_path=str(config_path))
    ok = handler.update_config(
        common_params={"cloud_provider": "byteplus"},
        strategy_params={},
        dry_run=True,
    )
    assert ok is True
    assert os.environ.get(ENV_CLOUD_PROVIDER) == "volcengine"
