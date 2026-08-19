"""Public ``agentkit harness sidecar`` commands."""

from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path
from typing import Annotated

import typer

from agentkit.toolkit.harness import HarnessDeployAborted

from .component_catalog import (
    CATALOG_VERSION,
    get_harness_sidecar_catalog,
)
from .deploy import deploy_harness
from .selection import resolve_harness_sidecar_selection
from .sidecar import (
    HarnessSidecarError,
    doctor_harness_sidecar,
    run_with_harness_sidecar,
    start_harness_sidecar,
)
from .sidecar_config import (
    HarnessSidecarConfig,
    sidecar_config_to_env,
)


harness_app = typer.Typer(help="AgentKit Harness capabilities.")
sidecar_app = typer.Typer(help="Configure and run zero-intrusion Harness Sidecar.")
harness_app.add_typer(sidecar_app, name="sidecar")


@sidecar_app.command("catalog")
def catalog(
    profile: Annotated[str, typer.Option("--profile")] = "ops",
) -> None:
    """Print the Runtime-independent Product Component Catalog."""

    try:
        value = get_harness_sidecar_catalog(profile)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error
    typer.echo(value.model_dump_json(indent=2))


@sidecar_app.command("resolve")
def resolve_selection(
    profile: Annotated[str, typer.Option("--profile")] = "ops",
    enabled: Annotated[bool, typer.Option("--enabled/--disabled")] = True,
    component: Annotated[
        list[str] | None,
        typer.Option(
            "--component", help="Product component override as ID=true|false."
        ),
    ] = None,
    catalog_version: Annotated[
        str, typer.Option("--catalog-version")
    ] = CATALOG_VERSION,
    runtime_version: Annotated[str | None, typer.Option("--runtime-version")] = None,
) -> None:
    """Resolve Product Component overrides into a deterministic plan."""

    overrides: dict[str, bool] = {}
    for raw in component or []:
        component_id, separator, selected = raw.partition("=")
        normalized = selected.strip().lower()
        if not separator or normalized not in {"true", "false"}:
            raise typer.BadParameter(
                f"invalid component override '{raw}'; expected ID=true|false"
            )
        overrides[component_id.strip()] = normalized == "true"
    plan = resolve_harness_sidecar_selection(
        enabled=enabled,
        profile=profile,
        component_overrides=overrides,
        catalog_version=catalog_version,
        runtime_version=runtime_version,
    )
    typer.echo(plan.model_dump_json(indent=2, exclude_none=True))
    if not plan.valid:
        raise typer.Exit(1)


def _config(
    *,
    profile: str | None,
    config_path: Path | None,
    model_proxy: bool | None,
    mcp_gateway: bool | None,
    model_upstream_env: str | None,
    compression_provider: str | None,
    mcp_upstreams_env: str | None,
    presets: list[str] | None,
    readonly_segments: list[str] | None,
) -> HarnessSidecarConfig:
    raw: dict = {}
    if config_path is not None:
        value = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise typer.BadParameter("sidecar config must be a JSON object")
        raw.update(value)
    if profile is not None:
        raw["profile"] = profile
    else:
        raw.setdefault("profile", "ops")

    model_overrides = {}
    if model_proxy is not None:
        model_overrides["enabled"] = model_proxy
    if model_upstream_env is not None:
        model_overrides["upstream_base_url_env"] = model_upstream_env
    if compression_provider is not None:
        model_overrides["compression_provider"] = compression_provider
    if model_overrides:
        raw.setdefault("model_proxy", {}).update(model_overrides)

    mcp_overrides = {}
    if mcp_gateway is not None:
        mcp_overrides["enabled"] = mcp_gateway
    if mcp_upstreams_env is not None:
        mcp_overrides["upstreams_env"] = mcp_upstreams_env
    if presets is not None:
        mcp_overrides["presets"] = presets
    if readonly_segments is not None:
        mcp_overrides["readonly_segments"] = readonly_segments
    if mcp_overrides:
        raw.setdefault("mcp_gateway", {}).update(mcp_overrides)
    return HarnessSidecarConfig.model_validate(raw)


def _common_config(
    profile: str | None,
    config: Path | None,
    model_proxy: bool | None,
    mcp_gateway: bool | None,
    model_upstream_env: str | None,
    compression_provider: str | None,
    mcp_upstreams_env: str | None,
    preset: list[str] | None,
    readonly_segment: list[str] | None,
) -> HarnessSidecarConfig:
    return _config(
        profile=profile,
        config_path=config,
        model_proxy=model_proxy,
        mcp_gateway=mcp_gateway,
        model_upstream_env=model_upstream_env,
        compression_provider=compression_provider,
        mcp_upstreams_env=mcp_upstreams_env,
        presets=preset,
        readonly_segments=readonly_segment,
    )


@sidecar_app.command("doctor")
def doctor(
    profile: Annotated[str, typer.Option("--profile")] = "ops",
) -> None:
    try:
        report = doctor_harness_sidecar({"profile": profile})
    except HarnessSidecarError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from error
    typer.echo(json.dumps(report, ensure_ascii=False, indent=2))


@sidecar_app.command("start")
def start(
    profile: Annotated[str | None, typer.Option("--profile")] = None,
    config: Annotated[Path | None, typer.Option("--config")] = None,
    model_proxy: Annotated[
        bool | None, typer.Option("--model-proxy/--no-model-proxy")
    ] = None,
    mcp_gateway: Annotated[
        bool | None, typer.Option("--mcp-gateway/--no-mcp-gateway")
    ] = None,
    model_upstream_env: Annotated[
        str | None, typer.Option("--model-upstream-env")
    ] = None,
    compression_provider: Annotated[
        str | None, typer.Option("--compression-provider")
    ] = None,
    mcp_upstreams_env: Annotated[
        str | None, typer.Option("--mcp-upstreams-env")
    ] = None,
    preset: Annotated[list[str] | None, typer.Option("--preset")] = None,
    readonly_segment: Annotated[
        list[str] | None, typer.Option("--readonly-segment")
    ] = None,
) -> None:
    resolved = _common_config(
        profile,
        config,
        model_proxy,
        mcp_gateway,
        model_upstream_env,
        compression_provider,
        mcp_upstreams_env,
        preset,
        readonly_segment,
    )
    try:
        with start_harness_sidecar(resolved) as binding:
            typer.echo(binding.spec.model_dump_json(indent=2))
            if binding.process is not None:
                binding.process.wait()
    except (HarnessSidecarError, KeyboardInterrupt) as error:
        if isinstance(error, HarnessSidecarError):
            typer.echo(str(error), err=True)
            raise typer.Exit(1) from error


@sidecar_app.command(
    "run",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def run(
    ctx: typer.Context,
    profile: Annotated[str | None, typer.Option("--profile")] = None,
    config: Annotated[Path | None, typer.Option("--config")] = None,
    model_proxy: Annotated[
        bool | None, typer.Option("--model-proxy/--no-model-proxy")
    ] = None,
    mcp_gateway: Annotated[
        bool | None, typer.Option("--mcp-gateway/--no-mcp-gateway")
    ] = None,
    model_upstream_env: Annotated[
        str | None, typer.Option("--model-upstream-env")
    ] = None,
    compression_provider: Annotated[
        str | None, typer.Option("--compression-provider")
    ] = None,
    mcp_upstreams_env: Annotated[
        str | None, typer.Option("--mcp-upstreams-env")
    ] = None,
    preset: Annotated[list[str] | None, typer.Option("--preset")] = None,
    readonly_segment: Annotated[
        list[str] | None, typer.Option("--readonly-segment")
    ] = None,
) -> None:
    command = list(ctx.args)
    if command and command[0] == "--":
        command.pop(0)
    if not command:
        raise typer.BadParameter("provide a command after '--'")
    resolved = _common_config(
        profile,
        config,
        model_proxy,
        mcp_gateway,
        model_upstream_env,
        compression_provider,
        mcp_upstreams_env,
        preset,
        readonly_segment,
    )
    try:
        exit_code = run_with_harness_sidecar(resolved, command)
    except HarnessSidecarError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from error
    raise typer.Exit(exit_code)


@sidecar_app.command("export-env")
def export_env(
    profile: Annotated[str | None, typer.Option("--profile")] = None,
    config: Annotated[Path | None, typer.Option("--config")] = None,
    shell: Annotated[bool, typer.Option("--shell")] = False,
) -> None:
    raw = {}
    if config is not None:
        raw = json.loads(config.read_text(encoding="utf-8"))
    if profile is not None:
        raw["profile"] = profile
    else:
        raw.setdefault("profile", "ops")
    values = sidecar_config_to_env(raw)
    if shell:
        for key, value in values.items():
            typer.echo(f"export {key}={shlex.quote(value)}")
        return
    typer.echo(json.dumps(values, ensure_ascii=False, indent=2))


def _prompt_harness_update(info: dict) -> bool:
    version = info.get("version")
    version_label = f"v{version}" if version is not None else "unknown"
    return typer.confirm(
        f"Harness '{info['name']}' already exists (current version "
        f"{version_label}). Update it to a new version?",
        default=False,
    )


@sidecar_app.command("deploy")
def deploy(
    name: Annotated[str, typer.Argument(help="Harness spec name.")],
    region: Annotated[str | None, typer.Option("--region")] = None,
    access_key: Annotated[str | None, typer.Option("--volcengine-access-key")] = None,
    secret_key: Annotated[str | None, typer.Option("--volcengine-secret-key")] = None,
    discovery_url: Annotated[str | None, typer.Option("--discovery-url")] = None,
    allowed_id: Annotated[str | None, typer.Option("--allowed-id")] = None,
    runtime_network_mode: Annotated[
        str | None, typer.Option("--runtime-network-mode")
    ] = None,
    runtime_vpc_id: Annotated[str | None, typer.Option("--runtime-vpc-id")] = None,
    runtime_subnet_ids: Annotated[
        list[str] | None,
        typer.Option("--runtime-subnet-id", "--runtime-subnet-ids"),
    ] = None,
    runtime_enable_shared_internet_access: Annotated[
        bool | None,
        typer.Option(
            "--runtime-enable-shared-internet-access/--no-runtime-enable-shared-internet-access"
        ),
    ] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y")] = False,
) -> None:
    """Deploy a Sidecar-enabled Harness with optional Runtime VPC settings."""

    from agentkit.toolkit.cli.console_reporter import ConsoleReporter
    from agentkit.toolkit.context import ExecutionContext

    reporter = ConsoleReporter()
    ExecutionContext.set_reporter(reporter)
    on_conflict = None
    if yes:
        on_conflict = lambda info: True  # noqa: E731
    elif sys.stdin.isatty():
        on_conflict = _prompt_harness_update

    try:
        result = deploy_harness(
            name=name,
            region=region,
            access_key=access_key,
            secret_key=secret_key,
            discovery_url=discovery_url,
            allowed_id=allowed_id,
            runtime_network_mode=runtime_network_mode,
            runtime_vpc_id=runtime_vpc_id,
            runtime_subnet_ids=runtime_subnet_ids,
            runtime_enable_shared_internet_access=(
                runtime_enable_shared_internet_access
            ),
            reporter=reporter,
            on_conflict=on_conflict,
        )
    except HarnessDeployAborted:
        typer.echo("Harness deploy cancelled.")
        return
    except (ValueError, FileNotFoundError, NotADirectoryError) as error:
        typer.echo(f"Harness deploy failed: {error}", err=True)
        raise typer.Exit(1) from error

    if not result.success:
        typer.echo(f"Harness deploy failed: {result.error}", err=True)
        raise typer.Exit(1)

    deploy_result = result.deploy_result
    metadata = (deploy_result and deploy_result.metadata) or {}
    typer.echo(f"Harness Runtime deployed: {metadata.get('runtime_id', name)}")


__all__ = ["harness_app", "sidecar_app"]
