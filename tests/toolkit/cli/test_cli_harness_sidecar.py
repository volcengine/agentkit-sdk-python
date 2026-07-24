from __future__ import annotations

import sys
from pathlib import Path

from typer.testing import CliRunner

from agentkit.toolkit.cli.cli import app
from agentkit.toolkit.cli.cli_harness_sidecar import _config


runner = CliRunner()


def test_harness_sidecar_export_env_uses_ops_product_profile() -> None:
    result = runner.invoke(
        app,
        [
            "harness",
            "sidecar",
            "export-env",
            "--profile",
            "ops",
            "--shell",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "export HARNESS_SIDECAR_ENABLED=true" in result.output
    assert "export HARNESS_PROFILE=ops" in result.output
    assert "export HARNESS_MCP_GATEWAY_ENABLED=true" in result.output
    assert "export HARNESS_MCP_READONLY_SEGMENTS='*'" in result.output
    assert "export HARNESS_MCP_PRESETS=sql_readonly" in result.output


def test_harness_sidecar_catalog_and_resolve_commands() -> None:
    catalog = runner.invoke(app, ["harness", "sidecar", "catalog", "--profile", "ops"])
    resolved = runner.invoke(
        app,
        [
            "harness",
            "sidecar",
            "resolve",
            "--profile",
            "ops",
            "--component",
            "verifier=false",
        ],
    )

    assert catalog.exit_code == 0, catalog.output
    assert '"total_component_count": 9' in catalog.output
    assert resolved.exit_code == 0, resolved.output
    assert '"effective_component_count": 5' in resolved.output


def test_harness_sidecar_doctor_uses_runtime_command(tmp_path: Path) -> None:
    runtime = tmp_path / "doctor.py"
    runtime.write_text(
        "import json; print(json.dumps({'status': 'ok', 'version': 'test'}))",
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        ["harness", "sidecar", "doctor"],
        env={"AGENTKIT_HARNESS_RUNTIME_COMMAND": f"{sys.executable} {runtime}"},
    )

    assert result.exit_code == 0, result.output
    assert '"status": "ok"' in result.output


def test_config_file_values_are_preserved_without_explicit_cli_overrides(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "sidecar.json"
    config_path.write_text(
        '{"profile":"default","model_proxy":{"enabled":false},'
        '"mcp_gateway":{"enabled":true,"presets":["sql_readonly"]}}',
        encoding="utf-8",
    )

    config = _config(
        profile=None,
        config_path=config_path,
        model_proxy=None,
        mcp_gateway=None,
        model_upstream_env=None,
        compression_provider=None,
        mcp_upstreams_env=None,
        presets=None,
        readonly_segments=None,
    )

    assert config.profile == "default"
    assert config.model_proxy.enabled is False
    assert config.mcp_gateway.enabled is True
    assert config.mcp_gateway.presets == ["sql_readonly"]


def test_export_env_preserves_profile_from_config_file(tmp_path: Path) -> None:
    config_path = tmp_path / "sidecar.json"
    config_path.write_text(
        '{"profile":"default","mcp_gateway":{"enabled":false}}',
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["harness", "sidecar", "export-env", "--config", str(config_path)],
    )

    assert result.exit_code == 0, result.output
    assert '"HARNESS_PROFILE": "default"' in result.output
    assert '"HARNESS_MCP_GATEWAY_ENABLED": "false"' in result.output
