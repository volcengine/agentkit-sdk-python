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

"""AgentKit CLI - Main entry point for AgentKit Starter Toolkit."""

import os

import typer
from rich.panel import Panel
from rich.console import Console
from agentkit.utils.logging_config import setup_cli_logging

# Import command modules
from agentkit.toolkit.cli.cli_init import init_command, show_logo
from agentkit.toolkit.cli.cli_invoke import invoke_command
from agentkit.toolkit.cli.cli_config import config_command
from agentkit.toolkit.cli.cli_version import version_command, get_package_version
from agentkit.toolkit.cli.cli_build import build_command
from agentkit.toolkit.cli.cli_deploy import deploy_command
from agentkit.toolkit.cli.cli_launch import launch_command
from agentkit.toolkit.cli.cli_status import status_command
from agentkit.toolkit.cli.cli_destroy import destroy_command
from agentkit.toolkit.cli.cli_memory import memory_app
from agentkit.toolkit.cli.cli_knowledge import knowledge_app
from agentkit.toolkit.cli.cli_tools import tools_app
from agentkit.toolkit.cli.cli_runtime import runtime_app

# Note: Avoid importing heavy packages at the top to keep CLI startup fast

setup_cli_logging()

app = typer.Typer(
    name="agentkit",
    help="AgentKit CLI - Deploy AI agents with ease",
    add_completion=False,
)

console = Console()


# get_package_version is now imported from cli_version


def version_callback(value: bool):
    """Callback for --version flag."""
    if value:
        pkg_version = get_package_version()
        console.print(
            Panel(
                f"[bold cyan]AgentKit SDK[/bold cyan]\n[green]Version: {pkg_version}[/green]",
                title="📦 Version Info",
                border_style="cyan",
            )
        )
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version_flag: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version information",
        callback=version_callback,
        is_eager=True,
    ),
):
    """AgentKit CLI - Deploy AI agents with ease."""
    os.environ.setdefault("AGENTKIT_CLIENT_TYPE", "cli")
    # If no subcommand is provided, show logo
    if ctx.invoked_subcommand is None:
        show_logo()
        pkg_version = get_package_version()
        console.print(f"Version: {pkg_version}\n")
        console.print("Run [bold]agentkit --help[/bold] to see available commands.\n")


# Register commands
app.command(name="init")(init_command)
app.command(name="invoke")(invoke_command)
app.command(name="config")(config_command)
app.command(name="version")(version_command)
app.command(name="build")(build_command)
app.command(name="deploy")(deploy_command)
app.command(name="launch")(launch_command)
app.command(name="status")(status_command)
app.command(name="destroy")(destroy_command)

# Sub-app groups
app.add_typer(memory_app, name="memory")
app.add_typer(knowledge_app, name="knowledge")
app.add_typer(tools_app, name="tools")
app.add_typer(runtime_app, name="runtime")


if __name__ == "__main__":
    app()
