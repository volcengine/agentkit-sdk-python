from __future__ import annotations


def test_common_cloud_provider_uses_global_default_when_unset(monkeypatch) -> None:
    import agentkit.toolkit.config.global_config as global_cfg_mod
    from agentkit.toolkit.config.global_config import GlobalConfig
    from agentkit.toolkit.config.config import CommonConfig

    global_cfg = GlobalConfig()
    global_cfg.defaults.cloud_provider = "byteplus"
    monkeypatch.setattr(global_cfg_mod, "get_global_config", lambda: global_cfg)

    cfg = CommonConfig.from_dict({})
    assert cfg.cloud_provider == "byteplus"
    assert cfg.to_persist_dict()["cloud_provider"] == ""


def test_common_cloud_provider_preserves_explicit_project_value(monkeypatch) -> None:
    import agentkit.toolkit.config.global_config as global_cfg_mod
    from agentkit.toolkit.config.global_config import GlobalConfig
    from agentkit.toolkit.config.config import CommonConfig

    global_cfg = GlobalConfig()
    global_cfg.defaults.cloud_provider = "byteplus"
    monkeypatch.setattr(global_cfg_mod, "get_global_config", lambda: global_cfg)

    cfg = CommonConfig.from_dict({"cloud_provider": "volcengine"})
    assert cfg.cloud_provider == "volcengine"
    assert cfg.to_persist_dict()["cloud_provider"] == "volcengine"


def test_common_cloud_provider_treats_empty_as_unset(monkeypatch) -> None:
    import agentkit.toolkit.config.global_config as global_cfg_mod
    from agentkit.toolkit.config.global_config import GlobalConfig
    from agentkit.toolkit.config.config import CommonConfig

    global_cfg = GlobalConfig()
    global_cfg.defaults.cloud_provider = "byteplus"
    monkeypatch.setattr(global_cfg_mod, "get_global_config", lambda: global_cfg)

    cfg = CommonConfig.from_dict({"cloud_provider": ""})
    assert cfg.cloud_provider == "byteplus"
    assert cfg.to_persist_dict()["cloud_provider"] == ""


def test_resolved_cloud_provider_env_precedence_over_global_default(
    monkeypatch,
) -> None:
    import agentkit.toolkit.config.global_config as global_cfg_mod
    from agentkit.toolkit.config.global_config import GlobalConfig
    from agentkit.toolkit.config.config import AgentkitConfigManager

    global_cfg = GlobalConfig()
    global_cfg.defaults.cloud_provider = "byteplus"
    monkeypatch.setattr(global_cfg_mod, "get_global_config", lambda: global_cfg)
    monkeypatch.setattr(global_cfg_mod, "global_config_exists", lambda: True)

    monkeypatch.setenv("AGENTKIT_CLOUD_PROVIDER", "volcengine")

    cm = AgentkitConfigManager.from_dict(
        {
            "common": {
                "agent_name": "demo",
                "entry_point": "agent.py",
                "launch_type": "cloud",
            }
        }
    )
    resolved = cm.get_resolved_cloud_provider()
    assert resolved.provider.value == "volcengine"
    assert resolved.source == "env"
