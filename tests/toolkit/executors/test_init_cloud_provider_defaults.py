from __future__ import annotations

from pathlib import Path

import yaml


def _read_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    assert isinstance(data, dict)
    return data


def test_init_does_not_write_cloud_provider_by_default(
    tmp_path: Path, monkeypatch
) -> None:
    import agentkit.toolkit.executors.init_executor as init_mod
    import agentkit.toolkit.config.global_config as global_cfg_mod
    from agentkit.toolkit.executors.init_executor import InitExecutor
    from agentkit.platform.provider import ENV_CLOUD_PROVIDER, ENV_CLOUD_PROVIDER_ALIAS

    def _raise() -> None:
        raise RuntimeError("no global config")

    monkeypatch.delenv(ENV_CLOUD_PROVIDER, raising=False)
    monkeypatch.delenv(ENV_CLOUD_PROVIDER_ALIAS, raising=False)
    monkeypatch.setattr(init_mod, "global_config_exists", lambda: False)
    monkeypatch.setattr(init_mod, "get_global_config", _raise)
    monkeypatch.setattr(global_cfg_mod, "global_config_exists", lambda: False)
    monkeypatch.setattr(global_cfg_mod, "get_global_config", _raise)

    executor = InitExecutor()
    config_path = tmp_path / "agentkit.yaml"
    executor._create_config_file(
        config_path,
        project_name="demo",
        language="Python",
        language_version="3.12",
        agent_type="Basic App",
        description="d",
        entry_point_name="agent.py",
        dependencies_file_name="requirements.txt",
        runtime_envs=None,
    )

    data = _read_yaml(config_path)
    assert "cloud_provider" not in (data.get("common") or {})
    assert (data.get("launch_types") or {}).get("cloud", {}).get(
        "region"
    ) == "cn-beijing"


def test_init_region_defaults_follow_global_provider(
    tmp_path: Path, monkeypatch
) -> None:
    import agentkit.toolkit.executors.init_executor as init_mod
    import agentkit.toolkit.config.global_config as global_cfg_mod
    from agentkit.toolkit.executors.init_executor import InitExecutor
    from agentkit.toolkit.config.global_config import GlobalConfig
    from agentkit.platform.provider import ENV_CLOUD_PROVIDER, ENV_CLOUD_PROVIDER_ALIAS

    global_cfg = GlobalConfig()
    global_cfg.region = ""
    global_cfg.defaults.cloud_provider = "byteplus"

    monkeypatch.delenv(ENV_CLOUD_PROVIDER, raising=False)
    monkeypatch.delenv(ENV_CLOUD_PROVIDER_ALIAS, raising=False)
    monkeypatch.setattr(init_mod, "global_config_exists", lambda: True)
    monkeypatch.setattr(init_mod, "get_global_config", lambda: global_cfg)
    monkeypatch.setattr(global_cfg_mod, "global_config_exists", lambda: True)
    monkeypatch.setattr(global_cfg_mod, "get_global_config", lambda: global_cfg)

    executor = InitExecutor()
    config_path = tmp_path / "agentkit.yaml"
    executor._create_config_file(
        config_path,
        project_name="demo",
        language="Python",
        language_version="3.12",
        agent_type="Basic App",
        description="d",
        entry_point_name="agent.py",
        dependencies_file_name="requirements.txt",
        runtime_envs=None,
    )

    data = _read_yaml(config_path)
    assert "cloud_provider" not in (data.get("common") or {})
    assert (data.get("launch_types") or {}).get("cloud", {}).get(
        "region"
    ) == "ap-southeast-1"
