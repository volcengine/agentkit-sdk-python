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


def test_config_show_uses_global_default_cloud_provider(
    tmp_path: Path, monkeypatch
) -> None:
    import agentkit.toolkit.config.global_config as global_cfg_mod
    from agentkit.toolkit.config.global_config import GlobalConfig
    from agentkit.toolkit.config.config_handler import NonInteractiveConfigHandler
    import agentkit.toolkit.config.config_handler as config_handler_mod
    from rich.console import Console

    global_cfg = GlobalConfig()
    global_cfg.defaults.cloud_provider = "byteplus"
    monkeypatch.setattr(global_cfg_mod, "get_global_config", lambda: global_cfg)

    config_path = tmp_path / "agentkit.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "common": {
                    "agent_name": "demo",
                    "entry_point": "agent.py",
                    "launch_type": "cloud",
                },
                "launch_types": {"cloud": {}},
                "docker_build": {},
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    console = Console(record=True, width=120)
    monkeypatch.setattr(config_handler_mod, "console", console)

    handler = NonInteractiveConfigHandler(config_path=str(config_path))
    handler.show_current_config()

    text = console.export_text()
    assert "cloud_provider" in text
    assert "byteplus" in text
