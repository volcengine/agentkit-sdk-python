from agentkit.platform.provider import CloudProvider
from agentkit.toolkit.config.cloud_provider import resolve_cloud_provider_for_project


def test_resolve_cloud_provider_prefers_env() -> None:
    resolved = resolve_cloud_provider_for_project(
        project_provider="byteplus",
        global_provider="byteplus",
        env_provider="volcengine",
    )
    assert resolved.provider == CloudProvider.VOLCENGINE
    assert resolved.source == "env"


def test_resolve_cloud_provider_prefers_project_over_global() -> None:
    resolved = resolve_cloud_provider_for_project(
        project_provider="byteplus",
        global_provider="volcengine",
        env_provider=None,
    )
    assert resolved.provider == CloudProvider.BYTEPLUS
    assert resolved.source == "project"


def test_resolve_cloud_provider_uses_global_when_project_missing() -> None:
    resolved = resolve_cloud_provider_for_project(
        project_provider=None,
        global_provider="byteplus",
        env_provider=None,
    )
    assert resolved.provider == CloudProvider.BYTEPLUS
    assert resolved.source == "global"


def test_resolve_cloud_provider_falls_back_to_default() -> None:
    resolved = resolve_cloud_provider_for_project(
        project_provider=None,
        global_provider=None,
        env_provider=None,
    )
    assert resolved.provider == CloudProvider.VOLCENGINE
    assert resolved.source == "default"
