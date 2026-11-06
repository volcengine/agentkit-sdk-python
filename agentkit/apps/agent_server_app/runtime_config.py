"""只读取平台下发的公开资源配置，用于关联实际执行。"""

import hashlib
import json
import os

_CONFIG_ENV = "AGENTKIT_RUNTIME_DIAGNOSTIC_CONFIG"
_RESOURCE_FIELDS = ("cpu_milli", "memory_mb", "max_concurrency")
_ALLOWED_FIELDS = frozenset(("schema_version", "target_type", *_RESOURCE_FIELDS))


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate configuration field")
        result[key] = value
    return result


def runtime_config_attributes() -> dict[str, str | int]:
    raw = os.getenv(_CONFIG_ENV, "")
    if not raw or len(raw) > 1024:
        return {}
    try:
        config = json.loads(raw, object_pairs_hook=_unique_object)
    except (ValueError, RecursionError):
        # 元数据异常不能阻断 Agent 请求，也不能把原始环境或错误正文写入日志。
        return {}
    if (
        not isinstance(config, dict)
        or set(config) - _ALLOWED_FIELDS
        or type(config.get("schema_version")) is not int
        or config["schema_version"] != 1
    ):
        return {}
    resources: dict[str, int] = {}
    for field in _RESOURCE_FIELDS:
        if field not in config:
            continue
        value = config[field]
        if type(value) is not int or not 0 < value <= 2147483647:
            return {}
        resources[field] = value
    target = config.get("target_type")
    if "target_type" in config and target not in ("latest", "formal"):
        return {}
    attributes: dict[str, str | int] = {
        f"agentkit.runtime.config.{field}": value for field, value in resources.items()
    }
    if resources:
        # 指纹只包含公开且已知的资源值；不将完整 Envs 或凭据参与摘要。
        canonical = json.dumps(resources, sort_keys=True, separators=(",", ":"))
        attributes["agentkit.runtime.config.fingerprint"] = (
            "v1:" + hashlib.sha256(canonical.encode("ascii")).hexdigest()
        )
    if target is not None:
        # 这是物理函数的目标角色，不是业务版本，也不能用于授权。
        attributes["agentkit.runtime.target.type"] = target
    return attributes
