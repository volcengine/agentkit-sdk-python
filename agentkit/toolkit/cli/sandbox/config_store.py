# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Persistent sandbox CLI defaults."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import threading
from typing import Any, Callable, Optional, TypeVar

import yaml

from agentkit.toolkit.cli.sandbox.model_config import (
    default_model_provider,
    resolve_model_base_urls,
    resolve_model_name,
)
from agentkit.utils.redact import mask

SANDBOX_CONFIG_PATH = Path(".agentkit") / "sandbox.yaml"
LEGACY_SANDBOX_CONFIG_PATH = Path(".agentkit") / "sandbox" / "sandbox.yaml"
CONFIG_VERSION = 1
DEFAULT_TOOL_TYPE = "CodeEnv"
DEFAULT_CPU = 4
DEFAULT_SESSION_TTL = 28800
VALID_TOOL_TYPES = ("CodeEnv", "SkillEnv", "Private")
VALID_CPU_VALUES = (2, 4, 8, 16)

SECRET_PATHS = {
    ("model", "api_key"),
    ("tool", "websearch_apikey"),
}
SECRET_KEY_TOKENS = (
    "api_key",
    "apikey",
    "access_key",
    "accesskey",
    "secret_key",
    "secretkey",
    "ak",
    "sk",
    "token",
    "authorization",
)


class SandboxConfigError(ValueError):
    """Raised when sandbox config is invalid."""


T = TypeVar("T")


@dataclass(frozen=True)
class ConfigKeySpec:
    path: tuple[str, ...]
    parser: Callable[[str], Any]
    allowed: tuple[Any, ...] | None = None


def _str_value(value: str) -> str:
    resolved = value.strip()
    if not resolved:
        raise SandboxConfigError("value must not be empty")
    return resolved


def _int_value(value: str) -> int:
    try:
        return int(value.strip())
    except ValueError as exc:
        raise SandboxConfigError("value must be an integer") from exc


def _positive_int_value(value: str) -> int:
    result = _int_value(value)
    if result <= 0:
        raise SandboxConfigError("value must be greater than 0")
    return result


def _bool_value(value: str) -> bool:
    resolved = value.strip().lower()
    if resolved in {"true", "1", "yes", "y", "on"}:
        return True
    if resolved in {"false", "0", "no", "n", "off"}:
        return False
    raise SandboxConfigError("value must be a boolean")


def _string_list_value(value: str) -> list[str]:
    resolved = value.strip()
    if not resolved:
        raise SandboxConfigError("value must not be empty")
    if resolved[0] == "[":
        try:
            parsed = json.loads(resolved)
        except json.JSONDecodeError as exc:
            raise SandboxConfigError("value must be a JSON array or CSV list") from exc
        if not isinstance(parsed, list):
            raise SandboxConfigError("value must be a JSON array")
        items = parsed
    else:
        items = [item.strip() for item in resolved.split(",")]

    result: list[str] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, str) or not item.strip():
            raise SandboxConfigError(f"list item #{index} must be a non-empty string")
        result.append(item.strip())
    if not result:
        raise SandboxConfigError("value must contain at least one item")
    return result


CONFIG_KEY_SPECS: dict[str, ConfigKeySpec] = {
    "model-name": ConfigKeySpec(("model", "name"), _str_value),
    "model-base-url": ConfigKeySpec(("model", "base_url"), _str_value),
    "model-provider": ConfigKeySpec(("model", "provider"), _str_value),
    "model-api-key": ConfigKeySpec(("model", "api_key"), _str_value),
    "network-public": ConfigKeySpec(
        ("network", "enable_public"),
        _bool_value,
    ),
    "network-private": ConfigKeySpec(
        ("network", "enable_private"),
        _bool_value,
    ),
    "network-shared-internet": ConfigKeySpec(
        ("network", "enable_shared_internet"),
        _bool_value,
    ),
    "network-vpc-id": ConfigKeySpec(("network", "vpc_id"), _str_value),
    "network-subnet-ids": ConfigKeySpec(
        ("network", "subnet_ids"),
        _string_list_value,
    ),
    "tool-type": ConfigKeySpec(("tool", "type"), _str_value, VALID_TOOL_TYPES),
    "tool-id": ConfigKeySpec(("session", "tool_id"), _str_value),
    "tool-name": ConfigKeySpec(("session", "tool_name"), _str_value),
    "region": ConfigKeySpec(("tool", "region"), _str_value),
    "cpu": ConfigKeySpec(("tool", "cpu"), _int_value, VALID_CPU_VALUES),
    "tos-bucket": ConfigKeySpec(("tool", "tos_bucket"), _str_value),
    "tos-mount": ConfigKeySpec(("tool", "tos_mount"), _str_value),
    "tos-credential-type": ConfigKeySpec(
        ("tool", "tos_credential_type"),
        _str_value,
        ("access-key", "iam-role"),
    ),
    "role-name": ConfigKeySpec(("tool", "role_name"), _str_value),
    "enable-snapshot": ConfigKeySpec(("tool", "enable_snapshot"), _bool_value),
    "websearch-apikey": ConfigKeySpec(("tool", "websearch_apikey"), _str_value),
    "image-url": ConfigKeySpec(("tool", "image_url"), _str_value),
    "tool-image-url": ConfigKeySpec(("tool", "image_url"), _str_value),
    "session-id": ConfigKeySpec(("session", "id"), _str_value),
    "ttl": ConfigKeySpec(("session", "ttl"), _positive_int_value),
    "git-config": ConfigKeySpec(("session", "git_config"), _str_value),
}


def _alias_keys() -> dict[str, str]:
    aliases: dict[str, str] = {}
    for key in CONFIG_KEY_SPECS:
        aliases[key.replace("-", "_")] = key
    aliases.update(
        {
            "websearch-api-key": "websearch-apikey",
            "websearch_api_key": "websearch-apikey",
            "network-enable-public": "network-public",
            "network_enable_public": "network-public",
            "network-enable-private": "network-private",
            "network_enable_private": "network-private",
            "network-enable-shared-internet": "network-shared-internet",
            "network_enable_shared_internet": "network-shared-internet",
            "tool_type": "tool-type",
            "tool_id": "tool-id",
            "tool_name": "tool-name",
            "model_name": "model-name",
            "model_base_url": "model-base-url",
            "model_provider": "model-provider",
            "model_api_key": "model-api-key",
            "session_id": "session-id",
        }
    )
    return aliases


CONFIG_KEY_ALIASES = _alias_keys()


def canonical_config_key(key: str) -> str:
    resolved = key.strip()
    if not resolved:
        raise SandboxConfigError("config key must not be empty")
    canonical = CONFIG_KEY_ALIASES.get(resolved, resolved)
    if canonical not in CONFIG_KEY_SPECS:
        allowed = ", ".join(sorted(CONFIG_KEY_SPECS))
        raise SandboxConfigError(f"unknown config key: {key}. Allowed keys: {allowed}")
    return canonical


def get_sandbox_config_path() -> Path:
    return Path.cwd() / SANDBOX_CONFIG_PATH


def get_legacy_sandbox_config_path() -> Path:
    return Path.cwd() / LEGACY_SANDBOX_CONFIG_PATH


def _deepcopy_dict(data: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(data))


def _default_model_config() -> dict[str, str]:
    provider = default_model_provider()
    model_name = resolve_model_name(None, provider)
    base_url, _anthropic_base_url = resolve_model_base_urls(
        model_provider=provider,
        model_base_url=None,
    )
    return {
        "provider": provider,
        "name": model_name,
        "base_url": base_url,
    }


def build_default_sandbox_config() -> dict[str, Any]:
    return {
        "version": CONFIG_VERSION,
        "model": _default_model_config(),
        "network": {
            "enable_public": True,
            "enable_private": False,
            "enable_shared_internet": False,
        },
        "tool": {
            "type": DEFAULT_TOOL_TYPE,
            "cpu": DEFAULT_CPU,
            "enable_snapshot": False,
        },
        "session": {
            "ttl": DEFAULT_SESSION_TTL,
        },
    }


def _load_yaml_file(path: Path) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise SandboxConfigError(f"Invalid {path}: {exc}") from exc
    except OSError as exc:
        raise SandboxConfigError(f"Failed to read {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SandboxConfigError(f"Invalid {path}: expected a YAML mapping")
    return payload


def load_sandbox_config(
    path: Optional[Path] = None,
    *,
    include_defaults: bool = False,
) -> dict[str, Any]:
    config_path = path or get_sandbox_config_path()
    if not config_path.exists():
        return build_default_sandbox_config() if include_defaults else {}
    payload = migrate_tool_identifier_config(_load_yaml_file(config_path))
    if include_defaults:
        return merge_sandbox_config(build_default_sandbox_config(), payload)
    return payload


def merge_sandbox_config(
    base: dict[str, Any],
    override: dict[str, Any],
) -> dict[str, Any]:
    result = _deepcopy_dict(base)
    for key, value in override.items():
        if (
            isinstance(value, dict)
            and isinstance(result.get(key), dict)
            and key != "version"
        ):
            result[key] = merge_sandbox_config(result[key], value)
        else:
            result[key] = value
    return result


def _write_yaml_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(
        data,
        sort_keys=False,
        allow_unicode=True,
    )
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        tmp_path.write_text(text, encoding="utf-8")
        try:
            tmp_path.chmod(0o600)
        except OSError:
            pass
        tmp_path.replace(path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
    try:
        path.chmod(0o600)
    except OSError:
        pass


def write_sandbox_config(data: dict[str, Any], path: Optional[Path] = None) -> Path:
    config_path = path or get_sandbox_config_path()
    _write_yaml_atomic(config_path, data)
    return config_path


def _get_path(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _set_path(data: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    current: Any = data
    for key in path[:-1]:
        child = current.get(key)
        if not isinstance(child, dict):
            child = {}
            current[key] = child
        current = child
    current[path[-1]] = value


def _unset_path(data: dict[str, Any], path: tuple[str, ...]) -> bool:
    parents: list[tuple[dict[str, Any], str]] = []
    current: Any = data
    for key in path[:-1]:
        if not isinstance(current, dict) or not isinstance(current.get(key), dict):
            return False
        parents.append((current, key))
        current = current[key]
    if not isinstance(current, dict) or path[-1] not in current:
        return False
    del current[path[-1]]
    for parent, key in reversed(parents):
        child = parent.get(key)
        if isinstance(child, dict) and not child:
            del parent[key]
    return True


def migrate_tool_identifier_config(data: dict[str, Any]) -> dict[str, Any]:
    """Move persisted tool identifiers from tool.* to session.*."""
    tool = data.get("tool")
    if not isinstance(tool, dict):
        return data

    migrations = {
        "id": "tool_id",
        "name": "tool_name",
    }
    if not any(old_key in tool for old_key in migrations):
        return data

    session = data.get("session")
    if not isinstance(session, dict):
        session = {}
        data["session"] = session

    for old_key, new_key in migrations.items():
        value = tool.pop(old_key, None)
        if (
            isinstance(value, str)
            and value.strip()
            and not (isinstance(session.get(new_key), str) and session[new_key].strip())
        ):
            session[new_key] = value.strip()
    return data


def get_config_value(key: str, data: Optional[dict[str, Any]] = None) -> Any:
    canonical = canonical_config_key(key)
    payload = data if data is not None else load_sandbox_config()
    return _get_path(payload, CONFIG_KEY_SPECS[canonical].path)


def set_config_value(
    data: dict[str, Any],
    key: str,
    raw_value: str,
) -> tuple[str, Any]:
    canonical = canonical_config_key(key)
    spec = CONFIG_KEY_SPECS[canonical]
    value = spec.parser(raw_value)
    if spec.allowed is not None and value not in spec.allowed:
        allowed = ", ".join(str(item) for item in spec.allowed)
        raise SandboxConfigError(f"{canonical} must be one of: {allowed}")
    _set_path(data, spec.path, value)
    return canonical, value


def unset_config_value(data: dict[str, Any], key: str) -> tuple[str, bool]:
    canonical = canonical_config_key(key)
    removed = _unset_path(data, CONFIG_KEY_SPECS[canonical].path)
    return canonical, removed


def _merge_legacy_sandbox_yaml(data: dict[str, Any]) -> dict[str, Any]:
    defaults = _load_legacy_sandbox_values(validate=False)
    if not defaults:
        return data
    tool = data.setdefault("tool", {})
    if not isinstance(tool, dict):
        tool = {}
        data["tool"] = tool
    if "tool_type" in defaults:
        tool["type"] = defaults["tool_type"]
    if "image_url" in defaults:
        tool["image_url"] = defaults["image_url"]
    return data


def _load_legacy_sandbox_values(
    *,
    path: Optional[Path] = None,
    validate: bool = True,
) -> dict[str, str] | None:
    legacy_path = path or get_legacy_sandbox_config_path()
    if not legacy_path.exists():
        return None

    legacy = _load_yaml_file(legacy_path)
    values: dict[str, str] = {}
    raw_tool_type = legacy.get("tool_type")
    raw_image_url = legacy.get("image_url")
    if not isinstance(raw_tool_type, str) or not raw_tool_type.strip():
        if validate:
            raise SandboxConfigError(
                f"Invalid {LEGACY_SANDBOX_CONFIG_PATH}: "
                "tool_type must be a non-empty string"
            )
    else:
        tool_type = raw_tool_type.strip()
        if tool_type not in VALID_TOOL_TYPES:
            if validate:
                allowed = ", ".join(VALID_TOOL_TYPES)
                raise SandboxConfigError(f"tool-type must be one of: {allowed}")
            values["tool_type"] = tool_type
        else:
            values["tool_type"] = tool_type

    if not isinstance(raw_image_url, str) or not raw_image_url.strip():
        if validate:
            raise SandboxConfigError(
                f"Invalid {LEGACY_SANDBOX_CONFIG_PATH}: "
                "image_url must be a non-empty string"
            )
    else:
        values["image_url"] = raw_image_url.strip()

    return values or None


def load_legacy_sandbox_image_defaults(
    *,
    path: Optional[Path] = None,
    validate: bool = True,
) -> tuple[str, str] | None:
    values = _load_legacy_sandbox_values(path=path, validate=validate)
    if not values:
        return None
    tool_type = values.get("tool_type")
    image_url = values.get("image_url")
    if not tool_type or not image_url:
        return None
    return tool_type, image_url


def ensure_sandbox_config_initialized() -> tuple[Path, dict[str, Any], bool]:
    path = get_sandbox_config_path()
    if path.exists():
        return path, load_sandbox_config(path, include_defaults=True), False
    data = build_default_sandbox_config()
    data = _merge_legacy_sandbox_yaml(data)
    write_sandbox_config(data, path)
    return path, data, True


def configured_sandbox_config() -> dict[str, Any]:
    return load_sandbox_config(include_defaults=False)


def effective_sandbox_config() -> dict[str, Any]:
    configured = load_sandbox_config(include_defaults=False)
    data = load_sandbox_config(include_defaults=True)
    _apply_environment_overrides(data, configured)
    return data


def _apply_environment_overrides(
    data: dict[str, Any],
    configured: dict[str, Any],
) -> None:
    model_api_key = (os.getenv("MODEL_API_KEY") or "").strip()
    if model_api_key and get_config_value("model-api-key", configured) is None:
        _set_path(data, ("model", "api_key"), model_api_key)

    tool_id = (os.getenv("AGENTKIT_SANDBOX_TOOL_ID") or "").strip()
    if tool_id and get_config_value("tool-id", configured) is None:
        _set_path(data, ("session", "tool_id"), tool_id)

    ttl = (os.getenv("AGENTKIT_SANDBOX_TTL") or "").strip()
    if ttl and get_config_value("ttl", configured) is None:
        try:
            _set_path(data, ("session", "ttl"), int(ttl))
        except ValueError:
            pass

    region = (os.getenv("AGENTKIT_SANDBOX_REGION") or "").strip()
    if region and get_config_value("region", configured) is None:
        _set_path(data, ("tool", "region"), region)


def _is_secret_path(path: tuple[str, ...]) -> bool:
    if path in SECRET_PATHS:
        return True
    joined = "_".join(path).lower()
    last = path[-1].lower() if path else ""
    if last in {"ak", "sk"}:
        return True
    return any(
        token == joined or token in joined
        for token in SECRET_KEY_TOKENS
        if token not in {"ak", "sk"}
    )


def redact_sandbox_config(data: dict[str, Any]) -> dict[str, Any]:
    def redact_value(value: Any, path: tuple[str, ...]) -> Any:
        if isinstance(value, dict):
            return {
                key: redact_value(child, (*path, str(key)))
                for key, child in value.items()
            }
        if _is_secret_path(path) and isinstance(value, str):
            return mask(value)
        return value

    return redact_value(data, ())


def param_was_provided(ctx: Any, param_name: str) -> bool:
    get_source = getattr(ctx, "get_parameter_source", None)
    if get_source is None:
        return False
    try:
        source = get_source(param_name)
    except Exception:
        return False
    return getattr(source, "name", None) == "COMMANDLINE" or str(source).endswith(
        "COMMANDLINE"
    )


def config_default(key: str, *, data: Optional[dict[str, Any]] = None) -> Any:
    payload = data if data is not None else configured_sandbox_config()
    return get_config_value(key, payload)


def config_default_str(
    key: str,
    *,
    data: Optional[dict[str, Any]] = None,
) -> str | None:
    value = config_default(key, data=data)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def config_default_bool(
    key: str,
    *,
    data: Optional[dict[str, Any]] = None,
) -> bool | None:
    value = config_default(key, data=data)
    return value if isinstance(value, bool) else None


def config_default_int(
    key: str,
    *,
    data: Optional[dict[str, Any]] = None,
) -> int | None:
    value = config_default(key, data=data)
    return value if isinstance(value, int) else None


def config_default_list(
    key: str,
    *,
    data: Optional[dict[str, Any]] = None,
) -> list[str] | None:
    value = config_default(key, data=data)
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return list(value)
    return None


def config_default_if_unprovided(
    ctx: Any,
    param_name: str,
    key: str,
    current: T,
    *,
    data: Optional[dict[str, Any]] = None,
    getter: Callable[..., Any] = config_default_str,
    transform: Optional[Callable[[Any], T]] = None,
) -> T:
    if param_was_provided(ctx, param_name):
        return current
    value = getter(key, data=data)
    if value is None:
        return current
    return transform(value) if transform is not None else value


def config_tool_identifier_defaults_if_unprovided(
    ctx: Any,
    *,
    tool_id: Optional[str],
    tool_name: Optional[str],
    data: Optional[dict[str, Any]] = None,
) -> tuple[Optional[str], Optional[str]]:
    if param_was_provided(ctx, "tool_id") or param_was_provided(ctx, "tool_name"):
        return tool_id, tool_name

    configured_tool_id = config_default_str("tool-id", data=data)
    if configured_tool_id:
        return configured_tool_id, tool_name

    configured_tool_name = config_default_str("tool-name", data=data)
    if configured_tool_name:
        return tool_id, configured_tool_name

    return tool_id, tool_name


def config_tool_id_default_if_unprovided(
    ctx: Any,
    *,
    tool_id: Optional[str],
    tool_name: Optional[str],
    data: Optional[dict[str, Any]] = None,
) -> Optional[str]:
    resolved_tool_id, _resolved_tool_name = (
        config_tool_identifier_defaults_if_unprovided(
            ctx,
            tool_id=tool_id,
            tool_name=tool_name,
            data=data,
        )
    )
    return resolved_tool_id


def save_created_tool_config(
    *,
    tool_id: str,
    tool_name: str | None,
) -> Path:
    path, data, _created = ensure_sandbox_config_initialized()
    session = data.setdefault("session", {})
    if not isinstance(session, dict):
        session = {}
        data["session"] = session
    session["tool_id"] = tool_id
    if tool_name:
        session["tool_name"] = tool_name
    write_sandbox_config(data, path)
    return path
