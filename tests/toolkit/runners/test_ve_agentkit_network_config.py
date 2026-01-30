import pytest


def test_build_network_config_private_with_shared_internet_access_enabled():
    from agentkit.toolkit.runners.ve_agentkit import (
        VeAgentkitRuntimeRunner,
        VeAgentkitRunnerConfig,
    )

    runner = VeAgentkitRuntimeRunner()
    cfg = VeAgentkitRunnerConfig(
        runtime_network={
            "mode": "private",
            "vpc_id": "vpc-123",
            "subnet_ids": ["subnet-1"],
            "enable_shared_internet_access": True,
        }
    )

    network = runner._build_network_config_for_create(cfg)
    assert network is not None
    assert network.enable_private_network is True
    assert network.enable_public_network is False
    assert network.vpc_configuration is not None
    assert network.vpc_configuration.enable_shared_internet_access is True


def test_build_network_config_public_with_shared_internet_access_enabled_raises():
    from agentkit.toolkit.runners.ve_agentkit import (
        VeAgentkitRuntimeRunner,
        VeAgentkitRunnerConfig,
    )

    runner = VeAgentkitRuntimeRunner()
    cfg = VeAgentkitRunnerConfig(
        runtime_network={
            "mode": "public",
            "enable_shared_internet_access": True,
        }
    )

    with pytest.raises(ValueError):
        runner._build_network_config_for_create(cfg)


def test_build_network_config_both_with_shared_internet_access_enabled():
    from agentkit.toolkit.runners.ve_agentkit import (
        VeAgentkitRuntimeRunner,
        VeAgentkitRunnerConfig,
    )

    runner = VeAgentkitRuntimeRunner()
    cfg = VeAgentkitRunnerConfig(
        runtime_network={
            "mode": "both",
            "vpc_id": "vpc-123",
            "enable_shared_internet_access": True,
        }
    )

    network = runner._build_network_config_for_create(cfg)
    assert network is not None
    assert network.enable_private_network is True
    assert network.enable_public_network is True
    assert network.vpc_configuration is not None
    assert network.vpc_configuration.enable_shared_internet_access is True
