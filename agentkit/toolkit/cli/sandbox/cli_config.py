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

"""Config command for sandbox CLI."""

from __future__ import annotations

import typer
import yaml

from agentkit.toolkit.cli.sandbox.config_store import (
    SandboxConfigError,
    configured_sandbox_config,
    effective_sandbox_config,
    ensure_sandbox_config_initialized,
    get_sandbox_config_path,
    redact_sandbox_config,
    set_config_value,
    unset_config_value,
    write_sandbox_config,
)
from agentkit.toolkit.cli.sandbox.sandbox_client import error


def _dump_yaml(payload: object) -> None:
    typer.echo(
        yaml.safe_dump(
            payload,
            sort_keys=False,
            allow_unicode=True,
        ).rstrip()
    )


def _format_config_value(canonical: str, value: object) -> object:
    if canonical in {"model-api-key", "websearch-apikey"}:
        return "<redacted>"
    return value


def _parse_set_field(field: str) -> tuple[str, str]:
    if "=" not in field:
        raise SandboxConfigError("--set value must use KEY=VALUE format")
    key, value = field.split("=", 1)
    if not key.strip():
        raise SandboxConfigError("--set key must not be empty")
    return key, value


def _apply_config_options(
    set_fields: list[str],
    unset_keys: list[str],
    list_config: bool,
) -> None:
    path = get_sandbox_config_path()
    data = None
    wrote = False

    if set_fields:
        try:
            path, data, _created = ensure_sandbox_config_initialized()
            for field in set_fields:
                key, value = _parse_set_field(field)
                canonical, parsed = set_config_value(data, key, value)
                typer.echo(
                    f"Set {canonical}: {_format_config_value(canonical, parsed)}"
                )
        except SandboxConfigError as exc:
            error(str(exc))

    if unset_keys:
        if data is None:
            if not path.exists():
                error(f"Sandbox config not found: {path}")
            try:
                data = configured_sandbox_config()
            except SandboxConfigError as exc:
                error(str(exc))
        try:
            for key in unset_keys:
                canonical, removed = unset_config_value(data, key)
                if removed:
                    typer.echo(f"Unset {canonical}")
                else:
                    typer.echo(f"{canonical} was not set")
        except SandboxConfigError as exc:
            error(str(exc))

    if data is not None:
        write_sandbox_config(data, path)
        wrote = True

    if wrote:
        typer.echo(f"Wrote {path}")

    if list_config:
        try:
            _dump_yaml(redact_sandbox_config(effective_sandbox_config()))
        except SandboxConfigError as exc:
            error(str(exc))


def config_command(
    ctx: typer.Context,
    set_fields: list[str] = typer.Option(
        [],
        "--set",
        metavar="KEY=VALUE",
        help="Set a config value. Can be repeated.",
    ),
    unset_keys: list[str] = typer.Option(
        [],
        "--unset",
        metavar="KEY",
        help="Unset a config value. Can be repeated.",
    ),
    list_config: bool = typer.Option(
        False,
        "--list",
        help="List the current effective sandbox config.",
    ),
) -> None:
    """Configure default values for sandbox commands."""
    has_options = bool(set_fields or unset_keys or list_config)
    if not has_options:
        typer.echo(ctx.get_help())
        raise typer.Exit()
    _apply_config_options(set_fields, unset_keys, list_config)
