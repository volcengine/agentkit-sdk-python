from __future__ import annotations


def test_base_service_client_uses_platform_context(monkeypatch) -> None:
    from agentkit.platform.provider import ENV_CLOUD_PROVIDER
    from agentkit.platform.context import default_cloud_provider
    from agentkit.sdk.runtime.client import AgentkitRuntimeClient

    monkeypatch.setenv(ENV_CLOUD_PROVIDER, "volcengine")
    monkeypatch.setenv("BYTEPLUS_ACCESS_KEY", "bp-ak")
    monkeypatch.setenv("BYTEPLUS_SECRET_KEY", "bp-sk")

    with default_cloud_provider("byteplus"):
        c = AgentkitRuntimeClient(region="ap-southeast-1")
        assert c.host.endswith(".byteplusapi.com")
