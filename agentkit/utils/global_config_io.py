from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Tuple


_cache: Tuple[Optional[float], dict] = (None, {})


def get_default_global_config_path() -> Path:
    return Path.home() / ".agentkit" / "config.yaml"


def read_global_config_dict(
    config_path: Optional[Path] = None,
    *,
    force_reload: bool = False,
) -> dict:
    global _cache

    path = config_path or get_default_global_config_path()

    try:
        mtime = path.stat().st_mtime
    except FileNotFoundError:
        if force_reload:
            _cache = (None, {})
        return {}
    except Exception:
        return {}

    cached_mtime, cached_data = _cache
    if not force_reload and cached_mtime == mtime:
        return cached_data

    try:
        import yaml

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        parsed = data if isinstance(data, dict) else {}
        _cache = (mtime, parsed)
        return parsed
    except Exception:
        return {}


def write_global_config_dict(
    data: dict,
    config_path: Optional[Path] = None,
) -> None:
    global _cache

    path = config_path or get_default_global_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    import yaml

    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(
            data,
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

    try:
        path.chmod(0o600)
    except Exception:
        pass

    try:
        mtime = path.stat().st_mtime
        _cache = (mtime, data)
    except Exception:
        pass


def get_path_value(data: Any, *keys: str) -> Any:
    cur = data
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def get_global_config_value(
    *keys: str,
    fallback_keys: Optional[Tuple[str, ...]] = None,
    config_path: Optional[Path] = None,
) -> Any:
    data = read_global_config_dict(config_path)
    v = get_path_value(data, *keys)
    if v is not None and v != "":
        return v
    if fallback_keys:
        v2 = get_path_value(data, *fallback_keys)
        if v2 is not None and v2 != "":
            return v2
    return None


def get_global_config_str(
    *keys: str,
    fallback_keys: Optional[Tuple[str, ...]] = None,
    config_path: Optional[Path] = None,
) -> str:
    data = read_global_config_dict(config_path)
    v = get_path_value(data, *keys)
    if isinstance(v, str) and v:
        return v
    if fallback_keys:
        v2 = get_path_value(data, *fallback_keys)
        if isinstance(v2, str) and v2:
            return v2
    return ""


def get_global_config_bool(
    *keys: str,
    fallback_keys: Optional[Tuple[str, ...]] = None,
    config_path: Optional[Path] = None,
):
    data = read_global_config_dict(config_path)
    v = get_path_value(data, *keys)
    if isinstance(v, bool):
        return v
    if fallback_keys:
        v2 = get_path_value(data, *fallback_keys)
        if isinstance(v2, bool):
            return v2
    return None
