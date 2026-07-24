"""Customer-facing Harness Sidecar product profiles."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


PROFILE_DEFAULTS: dict[str, tuple[str, ...]] = {
    "default": (
        "context_engine",
        "compressor",
        "verifier",
        "long_run_control",
    ),
    "ops": (
        "context_engine",
        "compressor",
        "verifier",
        "long_run_control",
        "mcp_resilience",
        "sql_readonly",
    ),
}

PROFILE_METADATA: dict[str, dict[str, str]] = {
    "default": {
        "display_name": "通用增强",
        "description": "适用于通用对话、知识问答和常规 Agent 的默认增强能力。",
    },
    "ops": {
        "display_name": "运维增强",
        "description": "面向运维诊断、数据库、日志和监控 MCP 的安全增强能力。",
    },
}


def profile_default_components(profile: str) -> tuple[str, ...]:
    try:
        return PROFILE_DEFAULTS[profile]
    except KeyError as error:
        raise ValueError(
            f"Unknown Harness Sidecar profile '{profile}'. "
            f"Known profiles: {', '.join(sorted(PROFILE_DEFAULTS))}"
        ) from error


def expand_sidecar_profile(
    profile: str, overrides: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Expand product selections into the legacy technical config contract."""

    raw = deepcopy(dict(overrides or {}))
    enabled = bool(raw.get("enabled", True))
    component_overrides = raw.get("component_overrides") or {}

    # Import lazily so the Product Catalog can import the profile registry without
    # introducing a module cycle.
    from .selection import resolve_harness_sidecar_selection

    plan = resolve_harness_sidecar_selection(
        enabled=enabled,
        profile=profile,
        component_overrides=component_overrides,
        catalog_version=raw.get("catalog_version"),
        runtime_version=raw.get("runtime_version"),
    )
    if plan.errors:
        raise ValueError("; ".join(plan.errors))

    selected = set(plan.effective_components)
    model_components = [
        component for component in PROFILE_DEFAULTS["default"] if component in selected
    ]
    mcp_enabled = bool({"mcp_resilience", "sql_readonly"} & selected)
    defaults: dict[str, Any] = {
        "enabled": enabled,
        "model_proxy": {
            "enabled": bool(model_components),
            "components": model_components,
            "compression_provider": "noop",
            "fail_open": True,
        },
        "mcp_gateway": {
            "enabled": mcp_enabled,
            "fail_open": True,
            "readonly_segments": ["*"] if "sql_readonly" in selected else [],
            "presets": ["sql_readonly"] if "sql_readonly" in selected else [],
            "policy": _mcp_policy() if "mcp_resilience" in selected else {},
        },
    }
    _deep_merge(defaults, raw)
    defaults["profile"] = profile
    return defaults


def _mcp_policy() -> dict[str, Any]:
    return {
        "result_quality": {
            "empty_is_unhealthy": True,
            "max_consecutive_empty": 2,
        },
        "large_result": {"max_bytes": 50_000},
        "budget": {
            "max_calls_per_session": 70,
            "session_idle_reset_seconds": 300.0,
        },
    }


def _deep_merge(target: dict[str, Any], overrides: Mapping[str, Any]) -> None:
    for key, value in overrides.items():
        current = target.get(key)
        if isinstance(current, dict) and isinstance(value, Mapping):
            _deep_merge(current, value)
        else:
            target[key] = deepcopy(value)


__all__ = [
    "PROFILE_DEFAULTS",
    "PROFILE_METADATA",
    "expand_sidecar_profile",
    "profile_default_components",
]
