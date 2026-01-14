from agentkit.platform.context import default_cloud_provider
from agentkit.toolkit.config.strategy_configs import (
    CloudStrategyConfig,
    HybridStrategyConfig,
)


def test_cloud_strategy_region_default_follows_provider_context():
    with default_cloud_provider("byteplus"):
        cfg = CloudStrategyConfig.from_dict({}, skip_render=True)
        assert cfg.region == "ap-southeast-1"
        assert cfg.to_persist_dict()["region"] == ""

    with default_cloud_provider("volcengine"):
        cfg = CloudStrategyConfig.from_dict({}, skip_render=True)
        assert cfg.region == "cn-beijing"
        assert cfg.to_persist_dict()["region"] == ""


def test_cloud_strategy_region_explicit_value_is_preserved_and_persisted():
    cfg = CloudStrategyConfig.from_dict({"region": "cn-shanghai"}, skip_render=True)
    assert cfg.region == "cn-shanghai"
    assert cfg.to_persist_dict()["region"] == "cn-shanghai"


def test_cloud_strategy_empty_region_is_treated_as_unset():
    with default_cloud_provider("byteplus"):
        cfg = CloudStrategyConfig.from_dict({"region": ""}, skip_render=True)
        assert cfg.region == "ap-southeast-1"
        assert cfg.to_persist_dict()["region"] == ""


def test_hybrid_strategy_region_default_and_alias_behavior():
    with default_cloud_provider("byteplus"):
        cfg = HybridStrategyConfig.from_dict({}, skip_render=True)
        assert cfg.region == "ap-southeast-1"
        assert cfg.to_persist_dict()["region"] == ""

    cfg = HybridStrategyConfig.from_dict({"ve_region": "cn-shanghai"}, skip_render=True)
    assert cfg.region == "cn-shanghai"
    assert cfg.to_persist_dict()["region"] == "cn-shanghai"
