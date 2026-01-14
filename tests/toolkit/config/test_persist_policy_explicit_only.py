from dataclasses import dataclass, field

from agentkit.toolkit.config.dataclass_utils import AutoSerializableMixin


@dataclass
class _Cfg(AutoSerializableMixin):
    cloud_provider: str = field(
        default="volcengine", metadata={"persist": "explicit_only"}
    )


def test_explicit_only_does_not_clear_when_source_missing() -> None:
    cfg = _Cfg(cloud_provider="byteplus")
    persisted = cfg.to_persist_dict()
    assert persisted["cloud_provider"] == "byteplus"


def test_explicit_only_clears_when_source_is_non_local() -> None:
    cfg = _Cfg(cloud_provider="byteplus")
    cfg._value_sources = {"cloud_provider": "default"}
    persisted = cfg.to_persist_dict()
    assert persisted["cloud_provider"] == ""


def test_explicit_only_keeps_when_source_is_local() -> None:
    cfg = _Cfg(cloud_provider="byteplus")
    cfg._value_sources = {"cloud_provider": "local"}
    persisted = cfg.to_persist_dict()
    assert persisted["cloud_provider"] == "byteplus"
