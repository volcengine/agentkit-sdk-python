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

"""AgentKit CLI - Deploy command implementation."""

from pathlib import Path
import typer
from rich.console import Console

# Note: Avoid importing heavy packages at the top to keep CLI startup fast

console = Console()


def deploy_command(
    config_file: Path = typer.Option("agentkit.yaml", help="Configuration file"),
):
    """Deploy the Agent to target environment."""
    from agentkit.toolkit.executors import DeployExecutor
    from agentkit.toolkit.cli.console_reporter import ConsoleReporter
    from agentkit.toolkit.context import ExecutionContext

    console.print(f"[green]Deploying with {config_file}[/green]")

    # Set execution context - CLI uses ConsoleReporter (with colored output and progress)
    reporter = ConsoleReporter()
    ExecutionContext.set_reporter(reporter)

    executor = DeployExecutor(reporter=reporter)
    result = executor.execute(config_file=str(config_file))

    # Format output
    if result.success:
        console.print("[green]✅ Deployment successful[/green]")
        if result.endpoint_url:
            console.print(f"[green]Endpoint: {result.endpoint_url}[/green]")
        if result.container_id:
            console.print(f"[green]Container ID: {result.container_id}[/green]")
        if result.service_id:
            console.print(f"[green]Service ID: {result.service_id}[/green]")
    else:
        console.print(f"[red]❌ Deployment failed: {result.error}[/red]")
        # deploy_logs may not exist, use getattr for safe access
        deploy_logs = getattr(result, "deploy_logs", None) or result.metadata.get(
            "deploy_logs", []
        )
        if deploy_logs:
            for log in deploy_logs:
                if log.strip():
                    console.print(f"[red]{log}[/red]")
        raise typer.Exit(1)
