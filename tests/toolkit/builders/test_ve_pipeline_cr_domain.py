import pytest


@pytest.mark.parametrize(
    "env_provider, expected_suffix",
    [
        ("volcengine", "cr.volces.com"),
        ("byteplus", "cr.bytepluses.com"),
    ],
)
def test_resolve_cr_domain_from_env(monkeypatch, env_provider, expected_suffix):
    monkeypatch.setenv("AGENTKIT_CLOUD_PROVIDER", env_provider)

    from agentkit.toolkit.builders.ve_pipeline import VeCPCRBuilder, VeCPCRBuilderConfig

    builder = VeCPCRBuilder()
    cfg = VeCPCRBuilderConfig(
        common_config=None,
        cr_instance_name="ins",
        cr_region="ap-southeast-1",
        cr_namespace_name="ns",
        cr_repo_name="repo",
    )

    domain = builder._resolve_cr_domain(cfg, "ap-southeast-1")
    assert domain == f"ins-ap-southeast-1.{expected_suffix}"


def test_resolve_cr_domain_prefers_common_config_provider(monkeypatch):
    monkeypatch.delenv("AGENTKIT_CLOUD_PROVIDER", raising=False)
    monkeypatch.delenv("CLOUD_PROVIDER", raising=False)

    from agentkit.toolkit.builders.ve_pipeline import VeCPCRBuilder, VeCPCRBuilderConfig
    from agentkit.toolkit.config import CommonConfig

    builder = VeCPCRBuilder()
    common = CommonConfig(
        agent_name="agentkit-app",
        entry_point="agent.py",
        cloud_provider="byteplus",
    )
    cfg = VeCPCRBuilderConfig(
        common_config=common,
        cr_instance_name="ins",
        cr_region="ap-southeast-1",
        cr_namespace_name="ns",
        cr_repo_name="repo",
    )

    domain = builder._resolve_cr_domain(cfg, "ap-southeast-1")
    assert domain == "ins-ap-southeast-1.cr.bytepluses.com"


def test_resolve_cr_domain_prefers_explicit_builder_provider(monkeypatch):
    monkeypatch.setenv("AGENTKIT_CLOUD_PROVIDER", "volcengine")

    from agentkit.toolkit.builders.ve_pipeline import VeCPCRBuilder, VeCPCRBuilderConfig
    from agentkit.toolkit.config import CommonConfig

    builder = VeCPCRBuilder()
    common = CommonConfig(
        agent_name="agentkit-app",
        entry_point="agent.py",
        cloud_provider="volcengine",
    )
    cfg = VeCPCRBuilderConfig(
        common_config=common,
        cloud_provider="byteplus",
        cr_instance_name="ins",
        cr_region="ap-southeast-1",
        cr_namespace_name="ns",
        cr_repo_name="repo",
    )

    domain = builder._resolve_cr_domain(cfg, "ap-southeast-1")
    assert domain == "ins-ap-southeast-1.cr.bytepluses.com"
