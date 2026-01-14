from __future__ import annotations


def test_platform_context_provider_overrides_env(monkeypatch) -> None:
    from agentkit.platform import VolcConfiguration
    from agentkit.platform.provider import ENV_CLOUD_PROVIDER
    from agentkit.platform.context import default_cloud_provider

    monkeypatch.setenv(ENV_CLOUD_PROVIDER, "volcengine")

    cfg = VolcConfiguration()
    ep = cfg.get_service_endpoint("agentkit")
    assert cfg.provider.value == "volcengine"
    assert not ep.host.endswith(".byteplusapi.com")

    with default_cloud_provider("byteplus"):
        cfg2 = VolcConfiguration()
        ep2 = cfg2.get_service_endpoint("agentkit")
        assert cfg2.provider.value == "byteplus"
        assert ep2.host.endswith(".byteplusapi.com")

    cfg3 = VolcConfiguration()
    ep3 = cfg3.get_service_endpoint("agentkit")
    assert cfg3.provider.value == "volcengine"
    assert not ep3.host.endswith(".byteplusapi.com")
