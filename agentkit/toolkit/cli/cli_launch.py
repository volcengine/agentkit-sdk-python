# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
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

"""AgentKit CLI - Launch command implementation."""

from pathlib import Path
import typer
from rich.console import Console

# Note: Avoid importing heavy packages at the top to keep CLI startup fast

console = Console()


def launch_command(
    config_file: Path = typer.Option("agentkit.yaml", help="Configuration file"),
    platform: str = typer.Option("auto", help="Build platform"),
    preflight_mode: str = typer.Option(
        "",
        "--preflight-mode",
        help="Preflight behavior: prompt|fail|warn|skip",
    ),
):
    """Build and deploy in one command."""
    from agentkit.toolkit.executors import LifecycleExecutor
    from agentkit.toolkit.cli.console_reporter import ConsoleReporter
    from agentkit.toolkit.context import ExecutionContext
    from agentkit.toolkit.models import PreflightMode
    from agentkit.toolkit.config.global_config import get_global_config

    console.print("[green]Launching agent...[/green]")

    # Set execution context - CLI uses ConsoleReporter (with colored output and progress)
    reporter = ConsoleReporter()
    ExecutionContext.set_reporter(reporter)

    resolved_mode = PreflightMode.PROMPT
    mode_map = {
        "prompt": PreflightMode.PROMPT,
        "fail": PreflightMode.FAIL,
        "warn": PreflightMode.WARN,
        "skip": PreflightMode.SKIP,
    }

    cli_mode = preflight_mode.strip().lower()
    if cli_mode:
        if cli_mode not in mode_map:
            console.print(
                "[red]Invalid --preflight-mode. Allowed: prompt|fail|warn|skip[/red]"
            )
            raise typer.Exit(2)
        resolved_mode = mode_map[cli_mode]
    else:
        try:
            gm = (
                (
                    getattr(
                        getattr(get_global_config(), "defaults", None),
                        "preflight_mode",
                        None,
                    )
                    or ""
                )
                .strip()
                .lower()
            )
            if gm in mode_map:
                resolved_mode = mode_map[gm]
        except Exception:
            pass

    executor = LifecycleExecutor(reporter=reporter)
    result = executor.launch(
        config_file=str(config_file),
        platform=platform,
        preflight_mode=resolved_mode,
    )

    # Format output
    if result.success:
        console.print("[green]✅ Launch completed successfully![/green]")

        # Show build and deploy details
        if result.build_result:
            build_res = result.build_result
            if hasattr(build_res, "image_name") and build_res.image_name:
                console.print(f"[cyan]Built image: {build_res.image_name}[/cyan]")

        if result.deploy_result:
            deploy_res = result.deploy_result
            if deploy_res.endpoint_url:
                console.print(f"[cyan]Endpoint: {deploy_res.endpoint_url}[/cyan]")
            if deploy_res.container_id:
                console.print(f"[cyan]Container: {deploy_res.container_id}[/cyan]")
    else:
        console.print(f"[red]❌ Launch failed: {result.error}[/red]")
        raise typer.Exit(1)
