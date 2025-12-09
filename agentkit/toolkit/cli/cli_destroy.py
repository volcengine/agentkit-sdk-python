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

"""AgentKit CLI - Destroy command implementation."""

from pathlib import Path
import typer
from rich.console import Console

# Note: Avoid importing heavy packages at the top to keep CLI startup fast

console = Console()


def destroy_command(
    config_file: Path = typer.Option("agentkit.yaml", help="Configuration file"),
    force: bool = typer.Option(False, help="Force destroy without confirmation"),
):
    """Destroy running Agent runtime."""
    from agentkit.toolkit import sdk

    console.print("[red]Destroying current runtime...[/red]")
    if not force:
        typer.confirm("Are you sure you want to destroy?", abort=True)

    try:
        # Call SDK (force only controls CLI confirmation, SDK always performs the same destroy)
        result = sdk.destroy(config_file=str(config_file))

        if result.success:
            console.print("[green]✅ Destruction completed successfully![/green]")
        else:
            console.print(f"[red]❌ Destruction failed: {result.error}[/red]")
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]Destruction failed: {e}[/red]")
        raise typer.Exit(1)
