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

"""AgentKit CLI - Build command implementation."""

import typer
from pathlib import Path
from rich.console import Console

# Note: Avoid importing heavy packages at the top to keep CLI startup fast

console = Console()


def build_command(
    config_file: Path = typer.Option("agentkit.yaml", help="Configuration file"),
    platform: str = typer.Option(
        None,
        "--platform",
        help="Target platform for Docker build (e.g., linux/amd64, linux/arm64)",
    ),
    regenerate_dockerfile: bool = typer.Option(
        False,
        "--regenerate-dockerfile",
        help="Force regenerate Dockerfile even if it exists",
    ),
):
    """Build Docker image for the Agent."""
    from agentkit.toolkit.executors import BuildExecutor, BuildOptions
    from agentkit.toolkit.cli.console_reporter import ConsoleReporter
    from agentkit.toolkit.context import ExecutionContext

    console.print(f"[cyan]Building image with {config_file}[/cyan]")

    # Construct runtime options
    options = BuildOptions(
        platform=platform, regenerate_dockerfile=regenerate_dockerfile
    )

    # Set execution context - CLI uses ConsoleReporter (with colored output and progress)
    reporter = ConsoleReporter()
    ExecutionContext.set_reporter(reporter)

    executor = BuildExecutor(reporter=reporter)
    result = executor.execute(config_file=str(config_file), options=options)

    # Format output
    if result.success:
        console.print("[green]✅ Build completed successfully![/green]")

        # Support multiple field names (compatible with different Result versions)
        image_name = getattr(result, "image_name", None) or getattr(
            result, "image_url", None
        )
        if image_name:
            console.print(f"[green]📦 Image: {image_name}[/green]")

        image_id = getattr(result, "image_id", None)
        if image_id:
            console.print(f"[dim]Image ID: {image_id}[/dim]")

        image_tag = getattr(result, "image_tag", None)
        if image_tag:
            console.print(f"[dim]Tag: {image_tag}[/dim]")
    else:
        console.print(f"[red]❌ Build failed: {result.error}[/red]")
        if result.build_logs:
            for log in result.build_logs:
                if log.strip():
                    console.print(f"[red]{log}[/red]")
        raise typer.Exit(1)
