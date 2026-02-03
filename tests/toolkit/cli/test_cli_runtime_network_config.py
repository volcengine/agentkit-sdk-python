import pytest


def test_build_network_none_when_no_user_intent():
    from agentkit.toolkit.cli.cli_runtime import _build_network_for_create_runtime

    network = _build_network_for_create_runtime(
        vpc_id=None,
        subnet_ids=None,
        enable_private_network=False,
        enable_public_network=True,
        enable_shared_internet_access=False,
    )
    assert network is None


def test_build_network_private_requires_vpc_id():
    from agentkit.toolkit.cli.cli_runtime import _build_network_for_create_runtime

    with pytest.raises(ValueError):
        _build_network_for_create_runtime(
            vpc_id=None,
            subnet_ids=None,
            enable_private_network=True,
            enable_public_network=True,
            enable_shared_internet_access=False,
        )


def test_build_network_disable_public_requires_private():
    from agentkit.toolkit.cli.cli_runtime import _build_network_for_create_runtime

    with pytest.raises(ValueError):
        _build_network_for_create_runtime(
            vpc_id=None,
            subnet_ids=None,
            enable_private_network=False,
            enable_public_network=False,
            enable_shared_internet_access=False,
        )


def test_build_network_vpc_id_implies_private_enabled():
    from agentkit.toolkit.cli.cli_runtime import _build_network_for_create_runtime

    network = _build_network_for_create_runtime(
        vpc_id="vpc-123",
        subnet_ids=None,
        enable_private_network=False,
        enable_public_network=True,
        enable_shared_internet_access=False,
    )
    assert network is not None
    assert network.enable_private_network is True
    assert network.enable_public_network is True
    assert network.vpc_configuration is not None
    assert network.vpc_configuration.vpc_id == "vpc-123"


def test_build_network_shared_internet_access_sets_vpc_field():
    from agentkit.toolkit.cli.cli_runtime import _build_network_for_create_runtime

    network = _build_network_for_create_runtime(
        vpc_id="vpc-123",
        subnet_ids="subnet-1,subnet-2",
        enable_private_network=True,
        enable_public_network=False,
        enable_shared_internet_access=True,
    )
    assert network is not None
    assert network.enable_private_network is True
    assert network.enable_public_network is False
    assert network.vpc_configuration is not None
    assert network.vpc_configuration.enable_shared_internet_access is True
