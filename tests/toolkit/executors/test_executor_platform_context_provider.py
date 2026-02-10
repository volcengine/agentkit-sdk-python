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

from pathlib import Path

import yaml


def test_executor_platform_context_uses_resolved_provider(
    tmp_path: Path, monkeypatch
) -> None:
    from agentkit.platform.context import get_default_cloud_provider
    from agentkit.platform.provider import CloudProvider
    from agentkit.toolkit.config.config import clear_config_cache, get_config
    import agentkit.toolkit.config.global_config as global_cfg_mod
    from agentkit.toolkit.config.global_config import GlobalConfig
    from agentkit.toolkit.executors.base_executor import BaseExecutor

    config_path = tmp_path / "agentkit.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "common": {
                    "agent_name": "demo",
                    "entry_point": "agent.py",
                    "launch_type": "cloud",
                }
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    global_cfg = GlobalConfig()
    global_cfg.defaults.cloud_provider = "byteplus"

    monkeypatch.setattr(global_cfg_mod, "get_global_config", lambda: global_cfg)

    clear_config_cache()
    cfg = get_config(config_path=str(config_path), force_reload=True)

    ex = BaseExecutor()
    token = ex._enter_platform_context(cfg)
    try:
        assert get_default_cloud_provider() == CloudProvider.BYTEPLUS
    finally:
        ex._exit_platform_context(token)
