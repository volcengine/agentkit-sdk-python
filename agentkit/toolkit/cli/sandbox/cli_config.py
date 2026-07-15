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

"""Config command group for sandbox CLI."""

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

config_app = typer.Typer(
    name="config",
    help="Configure default values for sandbox commands.",
    no_args_is_help=True,
)


def _dump_yaml(payload: object) -> None:
    typer.echo(
        yaml.safe_dump(
            payload,
            sort_keys=False,
            allow_unicode=True,
        ).rstrip()
    )


@config_app.command(name="set")
def config_set_command(
    key: str = typer.Argument(
        ...,
        help="Config key, e.g. model-name, tool-type, network-vpc-id.",
    ),
    value: str = typer.Argument(
        ...,
        help="Config value.",
    ),
) -> None:
    """Set a sandbox config value."""
    try:
        path, data, _created = ensure_sandbox_config_initialized()
        canonical, parsed = set_config_value(data, key, value)
        write_sandbox_config(data, path)
    except SandboxConfigError as exc:
        error(str(exc))

    display = parsed
    if canonical in {"model-api-key", "websearch-apikey"}:
        display = "<redacted>"
    typer.echo(f"Set {canonical}: {display}")
    typer.echo(f"Wrote {path}")


@config_app.command(name="unset")
def config_unset_command(
    key: str = typer.Argument(
        ...,
        help="Config key to remove, e.g. model-api-key.",
    ),
) -> None:
    """Unset a sandbox config value."""
    path = get_sandbox_config_path()
    if not path.exists():
        error(f"Sandbox config not found: {path}")
    try:
        data = configured_sandbox_config()
        canonical, removed = unset_config_value(data, key)
        write_sandbox_config(data, path)
    except SandboxConfigError as exc:
        error(str(exc))

    if removed:
        typer.echo(f"Unset {canonical}")
    else:
        typer.echo(f"{canonical} was not set")
    typer.echo(f"Wrote {path}")


@config_app.command(name="list")
def config_list_command() -> None:
    """List the current effective sandbox config."""
    try:
        data = effective_sandbox_config()
    except SandboxConfigError as exc:
        error(str(exc))
    _dump_yaml(redact_sandbox_config(data))
