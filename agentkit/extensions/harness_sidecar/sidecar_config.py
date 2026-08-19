"""Public configuration contract for AgentKit Harness Sidecar."""

from __future__ import annotations

import json
import os
import shlex
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .component_catalog import CATALOG_VERSION
from .profiles import expand_sidecar_profile
from .runtime_components import (
    resolve_runtime_components,
    runtime_flavor_for_components,
)
from .selection import ResolvedHarnessPlan, resolve_harness_sidecar_selection


class SidecarConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ModelProxyConfig(SidecarConfigModel):
    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 0
    upstream_base_url: str | None = None
    upstream_base_url_env: str = "MODEL_AGENT_API_BASE"
    upstream_api_key_env: str = "MODEL_AGENT_API_KEY"
    components: list[str] = Field(default_factory=list)
    compression_provider: str = "noop"
    headroom_base_url_env: str = "HARNESS_HEADROOM_BASE_URL"
    fail_open: bool = True
    trace_dir: str = ".harness-service/traces"
    state_path: str = ".harness-service/state.sqlite3"


class MCPGatewayConfig(SidecarConfigModel):
    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 0
    upstreams: list[str] = Field(default_factory=list)
    upstreams_env: str = "MCP_URLS"
    readonly_segments: list[str] = Field(default_factory=list)
    presets: list[str] = Field(default_factory=list)
    fail_open: bool = True
    policy: dict[str, Any] = Field(default_factory=dict)


class HarnessSidecarConfig(SidecarConfigModel):
    enabled: bool = True
    profile: str = "default"
    catalog_version: str = CATALOG_VERSION
    runtime_version: str | None = None
    component_overrides: dict[str, bool] = Field(default_factory=dict)
    fail_open: bool = True
    startup_timeout_seconds: float = 20.0
    runtime_command: list[str] | None = None
    components: list[str] = Field(default_factory=list)
    model_proxy: ModelProxyConfig = Field(default_factory=ModelProxyConfig)
    mcp_gateway: MCPGatewayConfig = Field(default_factory=MCPGatewayConfig)

    @model_validator(mode="before")
    @classmethod
    def _expand_profile(cls, value: Any) -> Any:
        if isinstance(value, cls):
            return value
        raw = dict(value or {})
        profile = str(raw.get("profile") or "default")
        return expand_sidecar_profile(profile, raw)

    def runtime_payload(self) -> dict[str, Any]:
        plan = self.resolved_plan
        if not plan.valid:
            raise ValueError("; ".join(plan.errors))
        return {
            "schema_version": "1",
            "enabled": self.enabled,
            "profile": self.profile,
            "runtime_components": self.required_runtime_components,
            "resolved_plan": plan.model_dump(mode="json", exclude_none=True),
            "model_proxy": self.model_proxy.model_dump(exclude_none=True),
            "mcp_gateway": self.mcp_gateway.model_dump(exclude_none=True),
        }

    @property
    def resolved_plan(self) -> ResolvedHarnessPlan:
        return resolve_harness_sidecar_selection(
            enabled=self.enabled,
            profile=self.profile,
            component_overrides=self.component_overrides,
            catalog_version=self.catalog_version,
            runtime_version=self.runtime_version,
        )

    @property
    def required_runtime_components(self) -> list[str]:
        if not self.enabled:
            return []
        vertical_components = list(self.components)
        if self.profile == "ops":
            vertical_components.append("ops")
        if (
            self.model_proxy.enabled
            and "long_run_control" in self.model_proxy.components
        ):
            vertical_components.append("goal_runtime")
        return resolve_runtime_components(
            model_proxy_enabled=self.model_proxy.enabled,
            mcp_gateway_enabled=self.mcp_gateway.enabled,
            components=vertical_components,
        )

    @property
    def runtime_flavor(self) -> str:
        return runtime_flavor_for_components(self.required_runtime_components)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "HarnessSidecarConfig":
        values = dict(env if env is not None else os.environ)
        profile = values.get("HARNESS_PROFILE") or "default"
        model_enabled = _env_bool(values.get("HARNESS_MODEL_PROXY_ENABLED"), True)
        mcp_enabled = _env_bool(
            values.get("HARNESS_MCP_GATEWAY_ENABLED"), profile == "ops"
        )
        runtime_command = values.get("AGENTKIT_HARNESS_RUNTIME_COMMAND")
        component_overrides = _env_json_object(
            values.get("HARNESS_SIDECAR_COMPONENT_OVERRIDES")
        )
        mcp_upstreams_env = values.get("HARNESS_MCP_UPSTREAMS_ENV", "MCP_URLS")
        mcp_gateway: dict[str, Any] = {
            "enabled": mcp_enabled,
            "upstreams": _csv(values.get(mcp_upstreams_env)),
            "upstreams_env": mcp_upstreams_env,
        }
        if "HARNESS_MCP_READONLY_SEGMENTS" in values:
            mcp_gateway["readonly_segments"] = _csv(
                values.get("HARNESS_MCP_READONLY_SEGMENTS")
            )
        if "HARNESS_MCP_PRESETS" in values:
            mcp_gateway["presets"] = _csv(values.get("HARNESS_MCP_PRESETS"))
        return cls.model_validate(
            {
                "enabled": _env_bool(values.get("HARNESS_SIDECAR_ENABLED"), False),
                "profile": profile,
                "catalog_version": values.get(
                    "HARNESS_SIDECAR_CATALOG_VERSION", CATALOG_VERSION
                ),
                "runtime_version": values.get("HARNESS_SIDECAR_RUNTIME_VERSION"),
                "component_overrides": component_overrides,
                "fail_open": _env_bool(values.get("HARNESS_SIDECAR_FAIL_OPEN"), True),
                "components": _csv(values.get("HARNESS_RUNTIME_COMPONENTS")),
                "runtime_command": shlex.split(runtime_command)
                if runtime_command
                else None,
                "model_proxy": {
                    "enabled": model_enabled,
                    "upstream_base_url_env": values.get(
                        "HARNESS_MODEL_UPSTREAM_BASE_URL_ENV",
                        "MODEL_AGENT_API_BASE",
                    ),
                    "upstream_api_key_env": values.get(
                        "HARNESS_MODEL_UPSTREAM_API_KEY_ENV",
                        "MODEL_AGENT_API_KEY",
                    ),
                    "compression_provider": values.get(
                        "HARNESS_MODEL_COMPRESSION_PROVIDER", "noop"
                    ),
                },
                "mcp_gateway": mcp_gateway,
            }
        )


class SidecarBindingSpec(SidecarConfigModel):
    schema_version: str = "1"
    status: str
    profile: str
    env: dict[str, str] = Field(default_factory=dict)
    model_proxy_url: str | None = None
    mcp_urls: list[str] = Field(default_factory=list)
    runtime_flavor: str = "unknown"
    runtime_components: list[str] = Field(default_factory=list)
    requested_components: list[str] = Field(default_factory=list)
    effective_components: list[str] = Field(default_factory=list)
    active_components: list[str] = Field(default_factory=list)
    failed_components: list[str] = Field(default_factory=list)
    plan_hash: str | None = None
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)

    @classmethod
    def from_discovery(cls, discovery: Mapping[str, Any]) -> "SidecarBindingSpec":
        model_proxy = dict(discovery.get("model_proxy") or {})
        mcp_gateway = dict(discovery.get("mcp_gateway") or {})
        endpoints = dict(discovery.get("endpoints") or {})
        runtime = dict(discovery.get("runtime") or {})
        return cls(
            schema_version=str(discovery.get("schema_version") or "1"),
            status=str(discovery.get("status") or "error"),
            profile=str(discovery.get("profile") or "default"),
            env={
                str(key): str(value)
                for key, value in dict(discovery.get("env") or {}).items()
            },
            model_proxy_url=model_proxy.get("url") or endpoints.get("model_proxy_url"),
            mcp_urls=[
                str(item)
                for item in (mcp_gateway.get("urls") or endpoints.get("mcp_urls") or [])
            ],
            runtime_flavor=str(runtime.get("flavor") or "unknown"),
            runtime_components=[
                str(item)
                for item in (
                    runtime.get("installed_internal_components")
                    or runtime.get("installed_components")
                    or []
                )
            ],
            requested_components=[
                str(item) for item in discovery.get("requested_components") or []
            ],
            effective_components=[
                str(item) for item in discovery.get("effective_components") or []
            ],
            active_components=[
                str(item) for item in discovery.get("active_components") or []
            ],
            failed_components=[
                str(item) for item in discovery.get("failed_components") or []
            ],
            plan_hash=discovery.get("plan_hash"),
            diagnostics=[dict(item) for item in discovery.get("diagnostics") or []],
        )


def resolve_sidecar_config(
    value: HarnessSidecarConfig | Mapping[str, Any] | bool | None = None,
    *,
    profile: str | None = None,
) -> HarnessSidecarConfig:
    if isinstance(value, HarnessSidecarConfig):
        if profile is None or value.profile == profile:
            return value
        raw = value.model_dump(exclude_unset=True)
        raw["profile"] = profile
        return HarnessSidecarConfig.model_validate(raw)
    if isinstance(value, bool):
        raw: dict[str, Any] = {"enabled": value}
    else:
        raw = dict(value or {})
    if profile is not None:
        raw["profile"] = profile
    return HarnessSidecarConfig.model_validate(raw)


def sidecar_config_to_env(
    value: HarnessSidecarConfig | Mapping[str, Any] | bool | None,
    *,
    profile: str | None = None,
) -> dict[str, str]:
    config = resolve_sidecar_config(value, profile=profile)
    plan = config.resolved_plan
    if not plan.valid:
        raise ValueError("; ".join(plan.errors))
    env = {
        "HARNESS_SIDECAR_ENABLED": _bool_string(config.enabled),
        "HARNESS_SIDECAR_FAIL_OPEN": _bool_string(config.fail_open),
        "HARNESS_PROFILE": config.profile,
        "HARNESS_SIDECAR_CATALOG_VERSION": config.catalog_version,
        "HARNESS_SIDECAR_COMPONENT_OVERRIDES": json.dumps(
            config.component_overrides,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
        "HARNESS_SIDECAR_PLAN": json.dumps(
            plan.model_dump(mode="json", exclude_none=True),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
        "HARNESS_RUNTIME_COMPONENTS": ",".join(config.components),
        "HARNESS_MODEL_PROXY_ENABLED": _bool_string(config.model_proxy.enabled),
        "HARNESS_MODEL_UPSTREAM_BASE_URL_ENV": (
            config.model_proxy.upstream_base_url_env
        ),
        "HARNESS_MODEL_UPSTREAM_API_KEY_ENV": config.model_proxy.upstream_api_key_env,
        "HARNESS_MODEL_COMPRESSION_PROVIDER": (config.model_proxy.compression_provider),
        "HARNESS_MCP_GATEWAY_ENABLED": _bool_string(config.mcp_gateway.enabled),
        "HARNESS_MCP_UPSTREAMS_ENV": config.mcp_gateway.upstreams_env,
        "HARNESS_MCP_READONLY_SEGMENTS": ",".join(config.mcp_gateway.readonly_segments),
        "HARNESS_MCP_PRESETS": ",".join(config.mcp_gateway.presets),
    }
    if config.runtime_version is not None:
        env["HARNESS_SIDECAR_RUNTIME_VERSION"] = config.runtime_version
    return env


def _csv(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _env_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_json_object(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except ValueError as error:
        raise ValueError("HARNESS_SIDECAR_COMPONENT_OVERRIDES must be JSON") from error
    if not isinstance(parsed, dict):
        raise ValueError("HARNESS_SIDECAR_COMPONENT_OVERRIDES must be a JSON object")
    return {str(key): item for key, item in parsed.items()}


def _bool_string(value: bool) -> str:
    return "true" if value else "false"


__all__ = [
    "HarnessSidecarConfig",
    "MCPGatewayConfig",
    "ModelProxyConfig",
    "SidecarBindingSpec",
    "resolve_sidecar_config",
    "sidecar_config_to_env",
]
