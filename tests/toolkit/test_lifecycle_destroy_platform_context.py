from __future__ import annotations

from dataclasses import dataclass


@dataclass
class _FakeCommonConfig:
    launch_type: str = "cloud"


class _FakeConfigManager:
    def get_common_config(self):
        return _FakeCommonConfig()

    def get_resolved_cloud_provider(self):
        from agentkit.toolkit.config.cloud_provider import ResolvedCloudProvider
        from agentkit.platform.provider import CloudProvider

        return ResolvedCloudProvider(provider=CloudProvider.BYTEPLUS, source="project")


class _FakeStrategy:
    def destroy(self, common_config, strategy_config):
        from agentkit.platform import VolcConfiguration

        cfg = VolcConfiguration()
        assert cfg.provider.value == "byteplus"
        return True

    def stop(self, common_config, strategy_config):
        return True


def test_lifecycle_destroy_sets_and_resets_platform_context(monkeypatch) -> None:
    from agentkit.platform.provider import ENV_CLOUD_PROVIDER
    from agentkit.platform import VolcConfiguration
    from agentkit.toolkit.executors.lifecycle_executor import LifecycleExecutor
    from agentkit.toolkit.reporter import SilentReporter

    monkeypatch.setenv(ENV_CLOUD_PROVIDER, "volcengine")

    before = VolcConfiguration()
    assert before.provider.value == "volcengine"

    ex = LifecycleExecutor(reporter=SilentReporter())
    monkeypatch.setattr(
        ex, "_load_config", lambda *_args, **_kwargs: _FakeConfigManager()
    )
    monkeypatch.setattr(ex, "_get_strategy", lambda *_args, **_kwargs: _FakeStrategy())
    monkeypatch.setattr(ex, "_get_strategy_config_object", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(ex, "_clear_deploy_config", lambda *_args, **_kwargs: None)

    res = ex.destroy(config_file="agentkit.yaml")
    assert res.success is True

    after = VolcConfiguration()
    assert after.provider.value == "volcengine"
