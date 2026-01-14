from __future__ import annotations

from pathlib import Path

import yaml


def test_interactive_config_strategy_context_uses_resolved_provider(
    tmp_path: Path, monkeypatch
) -> None:
    from agentkit.toolkit.cli import cli_config
    from agentkit.toolkit.config import CommonConfig
    from agentkit.toolkit.config.config import clear_config_cache
    import agentkit.toolkit.config.global_config as global_cfg_mod
    from agentkit.toolkit.config.global_config import GlobalConfig
    import agentkit.toolkit.cli.interactive_config as interactive_config

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

    global_cfg = GlobalConfig()
    global_cfg.defaults.cloud_provider = "byteplus"
    monkeypatch.setattr(global_cfg_mod, "get_global_config", lambda: global_cfg)

    def fake_create_common_config_interactively(existing_config):
        return CommonConfig.from_dict(existing_config or {})

    def fake_generate_config_from_dataclass(
        _dataclass_type, existing_config=None, context=None
    ):
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

    clear_config_cache()
    cli_config._interactive_config(config_file=str(config_path))
