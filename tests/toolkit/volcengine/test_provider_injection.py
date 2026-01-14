from __future__ import annotations


def test_code_pipeline_uses_explicit_provider_over_env(monkeypatch) -> None:
    from agentkit.platform.provider import ENV_CLOUD_PROVIDER
    from agentkit.toolkit.volcengine.code_pipeline import VeCodePipeline

    monkeypatch.setenv(ENV_CLOUD_PROVIDER, "volcengine")

    cp = VeCodePipeline(
        access_key="ak",
        secret_key="sk",
        region="",
        provider="byteplus",
    )
    assert cp.host.endswith(".byteplusapi.com")


def test_cr_uses_explicit_provider_over_env(monkeypatch) -> None:
    from agentkit.platform.provider import ENV_CLOUD_PROVIDER
    from agentkit.toolkit.volcengine.cr import VeCR

    monkeypatch.setenv(ENV_CLOUD_PROVIDER, "volcengine")
    monkeypatch.delenv("VOLCENGINE_CR_REGION", raising=False)
    monkeypatch.delenv("VOLC_CR_REGION", raising=False)
    monkeypatch.delenv("BYTEPLUS_CR_REGION", raising=False)

    cr = VeCR(
        access_key="ak", secret_key="sk", region="ap-southeast-1", provider="byteplus"
    )
    assert cr.host.endswith(".byteplusapi.com")


def test_tos_service_uses_explicit_provider_over_env(monkeypatch) -> None:
    from agentkit.platform.provider import ENV_CLOUD_PROVIDER
    import types

    import agentkit.toolkit.volcengine.services.tos_service as tos_service_mod
    from agentkit.toolkit.volcengine.services.tos_service import (
        TOSService,
        TOSServiceConfig,
    )

    monkeypatch.setenv(ENV_CLOUD_PROVIDER, "volcengine")
    monkeypatch.setenv("BYTEPLUS_ACCESS_KEY", "BP_AK")
    monkeypatch.setenv("BYTEPLUS_SECRET_KEY", "BP_SK")

    class _FakeTosClientV2:
        def __init__(self, access_key, secret_key, endpoint, region):
            self.access_key = access_key
            self.secret_key = secret_key
            self.endpoint = endpoint
            self.region = region

    fake_tos = types.SimpleNamespace(
        TosClientV2=_FakeTosClientV2,
        exceptions=types.SimpleNamespace(),
    )

    monkeypatch.setattr(tos_service_mod, "TOS_AVAILABLE", True)
    monkeypatch.setattr(tos_service_mod, "tos", fake_tos)

    cfg = TOSServiceConfig(bucket="bkt", region="ap-southeast-1", prefix="p")
    svc = TOSService(cfg, provider="byteplus")
    assert svc.config.endpoint == "tos-ap-southeast-1.bytepluses.com"
