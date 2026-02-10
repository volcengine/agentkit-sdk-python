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


def test_interactive_config_writes_strategy_config(tmp_path: Path, monkeypatch) -> None:
    from agentkit.toolkit.cli import cli_config
    from agentkit.toolkit.config import CommonConfig, get_config
    from agentkit.toolkit.config.config import clear_config_cache
    import agentkit.toolkit.cli.interactive_config as interactive_config

    config_path = tmp_path / "agentkit.yaml"

    clear_config_cache()
    get_config(config_path=str(config_path), force_reload=True)

    def fake_create_common_config_interactively(_existing_config):
        return CommonConfig(
            agent_name="agentkit-app",
            entry_point="agent.py",
            launch_type="cloud",
            cloud_provider="byteplus",
        )

    def fake_generate_config_from_dataclass(
        _dataclass_type, existing_config=None, context=None
    ):
        assert isinstance(existing_config, dict)
        assert context == {"cloud_provider": "byteplus"}
        return {"region": "ap-southeast-1"}

    monkeypatch.setattr(
        interactive_config,
        "create_common_config_interactively",
        fake_create_common_config_interactively,
    )
    monkeypatch.setattr(
        interactive_config,
        "generate_config_from_dataclass",
        fake_generate_config_from_dataclass,
    )

    cli_config._interactive_config(config_file=str(config_path))

    clear_config_cache()
    cfg = get_config(config_path=str(config_path), force_reload=True)
    assert cfg.get_strategy_config("cloud").get("region") == "ap-southeast-1"
