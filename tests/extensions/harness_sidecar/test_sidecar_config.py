from __future__ import annotations

import json
from pathlib import Path

import pytest
import tomllib

from agentkit.extensions.harness_sidecar.deploy import to_runtime_env
from agentkit.extensions.harness_sidecar.runtime_components import (
    RUNTIME_COMPONENT_DEPENDENCIES,
    RUNTIME_COMPONENT_ORDER,
)
from agentkit.extensions.harness_sidecar.sidecar_config import (
    HarnessSidecarConfig,
    resolve_sidecar_config,
    sidecar_config_to_env,
)


def test_internal_runtime_inventory_matches_single_wheel_contract() -> None:
    assert RUNTIME_COMPONENT_ORDER == (
        "harness_core",
        "ops",
        "goal_runtime",
        "model_proxy",
        "mcp_gateway",
        "browser_runtime",
        "eval_runtime",
        "shadow_runtime",
    )


def test_vertical_runtime_components_depend_only_on_harness_core() -> None:
    assert RUNTIME_COMPONENT_DEPENDENCIES["harness_core"] == ()
    assert {
        component: dependencies
        for component, dependencies in RUNTIME_COMPONENT_DEPENDENCIES.items()
        if component != "harness_core"
    } == {
        component: ("harness_core",)
        for component in RUNTIME_COMPONENT_ORDER
        if component != "harness_core"
    }


def test_public_extras_never_install_the_private_runtime_wheel() -> None:
    pyproject = tomllib.loads(
        (Path(__file__).resolve().parents[3] / "pyproject.toml").read_text(
            encoding="utf-8"
        )
    )

    runtime_requirement = "bytedance.agentkit_harness_sidecar"
    project = pyproject["project"]
    all_requirements = [
        *project.get("dependencies", []),
        *(
            requirement
            for extra in project["optional-dependencies"].values()
            for requirement in extra
        ),
    ]

    assert not any(runtime_requirement in item for item in all_requirements)
    assert project["optional-dependencies"]["harness-sidecar"] == []


def test_core_wheel_package_discovery_includes_sidecar_extension() -> None:
    root = Path(__file__).resolve().parents[3]
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    package_finder = pyproject["tool"]["setuptools"]["packages"]["find"]
    extension_dir = root / "agentkit" / "extensions" / "harness_sidecar"

    assert package_finder["include"] == ["agentkit*"]
    assert (extension_dir / "__init__.py").is_file()
    assert not list(extension_dir.glob("**/pyproject.toml"))


def test_ops_profile_expands_product_defaults() -> None:
    config = HarnessSidecarConfig(profile="ops")

    assert config.model_proxy.enabled is True
    assert config.mcp_gateway.enabled is True
    assert config.mcp_gateway.presets == ["sql_readonly"]
    assert config.mcp_gateway.readonly_segments == ["*"]
    assert config.mcp_gateway.policy["result_quality"]["empty_is_unhealthy"] is True
    assert config.mcp_gateway.policy["budget"]["max_calls_per_session"] == 70
    assert config.runtime_flavor == "harness-sidecar"
    assert config.required_runtime_components == [
        "harness_core",
        "ops",
        "goal_runtime",
        "model_proxy",
        "mcp_gateway",
    ]


def test_explicit_values_override_profile_defaults() -> None:
    config = resolve_sidecar_config(
        {
            "profile": "ops",
            "model_proxy": {"enabled": False},
            "mcp_gateway": {"policy": {"large_result": {"max_bytes": 65_536}}},
        }
    )

    assert config.model_proxy.enabled is False
    assert config.mcp_gateway.policy["large_result"]["max_bytes"] == 65_536
    assert config.mcp_gateway.policy["budget"]["max_calls_per_session"] == 70


def test_unknown_profile_fails_fast() -> None:
    with pytest.raises(ValueError, match="Unknown Harness Sidecar profile"):
        HarnessSidecarConfig(profile="unknown")


def test_runtime_payload_excludes_public_launcher_details() -> None:
    config = HarnessSidecarConfig(
        profile="ops", runtime_command=["python", "fake-runtime.py"]
    )

    payload = config.runtime_payload()

    assert "runtime_command" not in payload
    assert "startup_timeout_seconds" not in payload
    assert payload["profile"] == "ops"
    assert payload["runtime_components"] == config.required_runtime_components


def test_explicit_browser_component_resolves_dependency_closure() -> None:
    config = HarnessSidecarConfig(
        profile="default",
        components=["browser"],
        model_proxy={"enabled": False},
    )

    assert config.runtime_flavor == "harness-sidecar"
    assert config.required_runtime_components == [
        "harness_core",
        "browser_runtime",
    ]


@pytest.mark.parametrize("legacy_alias", ["ops", "ops_kernel"])
def test_legacy_ops_component_alias_resolves_internal_dependency(
    legacy_alias: str,
) -> None:
    config = HarnessSidecarConfig(
        profile="default",
        components=[legacy_alias],
        model_proxy={"enabled": False},
    )

    assert config.required_runtime_components == ["harness_core", "ops"]


def test_full_optional_component_set_resolves_full_flavor() -> None:
    config = HarnessSidecarConfig(
        profile="ops",
        components=["browser", "eval", "shadow"],
    )

    assert config.runtime_flavor == "harness-sidecar"
    assert config.required_runtime_components[-3:] == [
        "browser_runtime",
        "eval_runtime",
        "shadow_runtime",
    ]


def test_env_round_trip_keeps_product_semantics() -> None:
    env = sidecar_config_to_env(
        {
            "profile": "ops",
            "mcp_gateway": {
                "presets": ["sql_readonly"],
                "readonly_segments": ["bqmcp"],
            },
            "components": ["browser"],
        }
    )
    config = HarnessSidecarConfig.from_env(env)

    assert config.enabled is True
    assert config.profile == "ops"
    assert config.mcp_gateway.presets == ["sql_readonly"]
    assert config.mcp_gateway.readonly_segments == ["bqmcp"]
    assert config.components == ["browser"]


def test_default_env_profile_does_not_enable_mcp_gateway_implicitly() -> None:
    config = HarnessSidecarConfig.from_env({"HARNESS_SIDECAR_ENABLED": "true"})

    assert config.profile == "default"
    assert config.model_proxy.enabled is True
    assert config.mcp_gateway.enabled is False
    assert config.required_runtime_components == [
        "harness_core",
        "goal_runtime",
        "model_proxy",
    ]


def test_ops_env_profile_keeps_profile_readonly_defaults() -> None:
    config = HarnessSidecarConfig.from_env(
        {"HARNESS_SIDECAR_ENABLED": "true", "HARNESS_PROFILE": "ops"}
    )

    assert config.mcp_gateway.enabled is True
    assert config.mcp_gateway.presets == ["sql_readonly"]
    assert config.mcp_gateway.readonly_segments == ["*"]


def test_mcp_upstreams_are_materialized_from_configured_env() -> None:
    config = HarnessSidecarConfig.from_env(
        {
            "HARNESS_SIDECAR_ENABLED": "true",
            "HARNESS_PROFILE": "ops",
            "HARNESS_MCP_UPSTREAMS_ENV": "YUMC_MCP_URLS",
            "YUMC_MCP_URLS": "http://mcp-a.example/mcp, http://mcp-b.example/mcp",
        }
    )

    assert config.mcp_gateway.upstreams_env == "YUMC_MCP_URLS"
    assert config.mcp_gateway.upstreams == [
        "http://mcp-a.example/mcp",
        "http://mcp-b.example/mcp",
    ]


def test_deploy_env_mapping_supports_nested_harness_sidecar() -> None:
    env = to_runtime_env(
        {
            "description": "Yum China operations agent",
            "harness": {
                "enabled": True,
                "profile": "ops",
                "sidecar": {
                    "enabled": True,
                    "model_proxy": {"enabled": True},
                    "mcp_gateway": {"enabled": True},
                },
            },
        }
    )

    assert env["HARNESS_SIDECAR_ENABLED"] == "true"
    assert env["HARNESS_PROFILE"] == "ops"
    assert env["HARNESS_MCP_PRESETS"] == "sql_readonly"
    assert env["HARNESS_MCP_READONLY_SEGMENTS"] == "*"
    assert env["HARNESS_ENABLED"] == "true"
    assert env["DESCRIPTION"] == "Yum China operations agent"
    assert not any(key.startswith("HARNESS_SIDECAR_MCP_GATEWAY_") for key in env)


def test_deploy_env_mapping_supports_boolean_sidecar_shorthand() -> None:
    env = to_runtime_env({"harness": {"profile": "ops", "sidecar": True}})

    assert env["HARNESS_SIDECAR_ENABLED"] == "true"
    assert env["HARNESS_PROFILE"] == "ops"
    assert env["HARNESS_MCP_GATEWAY_ENABLED"] == "true"
    assert env["HARNESS_MCP_PRESETS"] == "sql_readonly"
    assert env["HARNESS_MCP_READONLY_SEGMENTS"] == "*"


def test_product_component_overrides_drive_technical_config_and_plan_env() -> None:
    env = sidecar_config_to_env(
        {
            "profile": "ops",
            "component_overrides": {
                "verifier": False,
                "sql_readonly": False,
            },
        }
    )

    plan = json.loads(env["HARNESS_SIDECAR_PLAN"])
    assert "verifier" not in plan["effective_components"]
    assert "sql_readonly" not in plan["effective_components"]
    assert env["HARNESS_MCP_PRESETS"] == ""
    assert env["HARNESS_MCP_READONLY_SEGMENTS"] == ""


def test_disabled_sidecar_has_no_runtime_or_product_components() -> None:
    config = HarnessSidecarConfig(profile="ops", enabled=False)

    assert config.required_runtime_components == []
    assert config.resolved_plan.effective_components == []
