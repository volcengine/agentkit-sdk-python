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

"""AgentKit CLI - Init command for project initialization."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.text import Text

from agentkit.toolkit.executors import InitExecutor
from agentkit.toolkit.cli.console_reporter import ConsoleReporter

# Note: Avoid importing heavy modules at the top to keep CLI startup fast.

try:
    from pyfiglet import Figlet

    HAS_PYFIGLET = True
except ImportError:
    HAS_PYFIGLET = False

console = Console()


def show_logo():
    """Display AgentKit logo"""
    console.print()

    if HAS_PYFIGLET:
        # Try different fonts in order of preference
        fonts_to_try = ["slant", "speed", "banner3", "big", "standard"]
        figlet = None

        for font in fonts_to_try:
            try:
                figlet = Figlet(font=font)
                break
            except Exception:
                continue

        if figlet is None:
            figlet = Figlet()  # Use default font

        logo_text = figlet.renderText("AgentKit")

        # Apply gradient color effect - more vibrant colors
        lines = logo_text.split("\n")
        colors = ["bright_magenta", "magenta", "bright_blue", "cyan", "bright_cyan"]

        for i, line in enumerate(lines):
            if line.strip():  # Skip empty lines
                # Create a gradient effect
                color_idx = int((i / max(len(lines) - 1, 1)) * (len(colors) - 1))
                color = colors[color_idx]
                console.print(Text(line, style=f"bold {color}"))
    else:
        # Fallback: beautiful box logo if pyfiglet is not installed
        console.print(
            Text("  ╔══════════════════════════════════════╗", style="bold bright_cyan")
        )
        console.print(
            Text("  ║                                      ║", style="bold bright_cyan")
        )
        console.print(
            Text("  ║   ", style="bold bright_cyan")
            + Text("🚀  A G E N T K I T  🤖", style="bold bright_magenta")
            + Text("   ║", style="bold bright_cyan")
        )
        console.print(
            Text("  ║                                      ║", style="bold bright_cyan")
        )
        console.print(
            Text("  ╚══════════════════════════════════════╝", style="bold bright_cyan")
        )

    # Add tagline with emoji
    console.print(Text("     ✨ Build AI Agents with Ease ✨", style="bold yellow"))
    console.print()


# Get templates from Executor layer
def _get_templates():
    """Get templates from InitExecutor."""
    executor = InitExecutor(reporter=ConsoleReporter())
    return executor.get_available_templates()


def display_templates():
    """Display available templates."""
    templates = _get_templates()

    table = Table(
        title="Available Templates", show_header=True, header_style="bold magenta"
    )
    table.add_column("ID", style="cyan", width=6)
    table.add_column("Key", style="bright_cyan", width=20)
    table.add_column("Name", style="green", width=25)
    table.add_column("Type", style="yellow", width=15)
    table.add_column("Language", style="blue", width=15)
    table.add_column("Description", style="white")

    for idx, (key, template) in enumerate(templates.items(), 1):
        table.add_row(
            str(idx),
            key,
            template["name"],
            template["type"],
            template["language"],
            template["description"],
        )

    console.print(table)


def select_template(template_key: Optional[str] = None) -> str:
    """Select a template via CLI option or interactive prompt."""
    templates = _get_templates()

    if template_key:
        # From CLI option
        # 1) direct key match
        if template_key in templates:
            return template_key
        # 2) numeric ID (same as interactive list)
        if template_key.isdigit():
            idx = int(template_key) - 1
            keys = list(templates.keys())
            if 0 <= idx < len(keys):
                return keys[idx]
        # 3) case-insensitive match by Name field
        lowered = template_key.lower()
        for k, t in templates.items():
            if t.get("name", "").lower() == lowered:
                return k
        # Error message: show available keys and ID hint
        console.print(f"[red]Error: Unknown template '{template_key}'[/red]")
        all_keys = list(templates.keys())
        console.print(f"[yellow]Available keys: {', '.join(all_keys)}[/yellow]")
        console.print(
            f"[yellow]Or use ID 1-{len(all_keys)} as shown in the list, or the template Name.[/yellow]"
        )
        raise typer.Exit(1)

    # Interactive selection
    display_templates()
    console.print(
        f"\n[bold cyan]Please select a template by entering ID/Key/Name (ID range: 1-{len(templates)}):[/bold cyan]"
    )

    while True:
        try:
            choice = input("Template (ID/Key/Name): ").strip()
            # ID
            if choice.isdigit():
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(templates):
                    selected_key = list(templates.keys())[choice_idx]
                    console.print(
                        f"[green]Selected: {templates[selected_key]['name']}[/green]"
                    )
                    return selected_key
                console.print(
                    f"[red]Invalid ID. Please enter a number between 1 and {len(templates)}[/red]"
                )
                continue
            # Key
            if choice in templates:
                console.print(f"[green]Selected: {templates[choice]['name']}[/green]")
                return choice
            # Name (case-insensitive)
            lowered = choice.lower()
            for k, t in templates.items():
                if t.get("name", "").lower() == lowered:
                    console.print(f"[green]Selected: {t['name']}[/green]")
                    return k
            console.print(
                "[red]Invalid input. Please enter a valid ID, Key, or Name.[/red]"
            )
        except ValueError:
            console.print("[red]Invalid input. Please enter a number[/red]")
        except typer.Abort:
            console.print("[yellow]Cancelled[/yellow]")
            raise typer.Exit(0)


def init_command(
    project_name: Optional[str] = typer.Argument(None, help="Project name"),
    template: Optional[str] = typer.Option(
        None,
        "--template",
        "-t",
        help="Project template (accepts ID/Key/Name). Keys: basic, basic_stream",
    ),
    directory: Optional[str] = typer.Option(".", help="Target directory"),
    agent_name: Optional[str] = typer.Option(
        None, "--agent-name", help="Agent name (default: 'Agent')"
    ),
    description: Optional[str] = typer.Option(
        None,
        "--description",
        help="Agent description (uses a common default description if not provided), this will be helpful in A2A scenario.",
    ),
    system_prompt: Optional[str] = typer.Option(
        None,
        "--system-prompt",
        help="Agent system prompt (uses a common default system prompt if not provided)",
    ),
    model_name: Optional[str] = typer.Option(
        None,
        "--model-name",
        help="Model name in volcengine ARK platform (default: 'doubao-seed-1-6-250615')",
    ),
    model_api_base: Optional[str] = typer.Option(
        None,
        "--model-api-base",
        help="Base URL for model API requests (e.g., https://ark.cn-beijing.volces.com/api/v3)",
    ),
    model_api_key: Optional[str] = typer.Option(
        None,
        "--model-api-key",
        help="API key for accessing the model",
    ),
    tools: Optional[str] = typer.Option(
        None,
        "--tools",
        help="Comma-separated list of tools to include (e.g., web_search,run_code)",
    ),
    # New parameters for wrapping existing Agent files
    from_agent: Optional[str] = typer.Option(
        None,
        "--from-agent",
        "-f",
        help="Path to existing Python file containing veadk Agent definition",
    ),
    agent_var: Optional[str] = typer.Option(
        None,
        "--agent-var",
        help="Variable name of the Agent object in the file (default: auto-detect)",
    ),
    wrapper_type: Optional[str] = typer.Option(
        "basic",
        "--wrapper-type",
        help="Type of wrapper to generate: basic or stream (default: basic)",
    ),
    list_templates: bool = typer.Option(
        False,
        "--list-templates",
        help="List available templates (ID, Key, Name) and exit",
    ),
):
    """
    Initialize a new Agent project with templates or wrap an existing Agent.

    This command provides two modes:
    1. Template mode: Create a new project from built-in templates
    2. Wrapper mode: Wrap an existing Agent definition file for deployment

    It delegates business logic to InitService while handling all UI interactions.
    """
    # ===== UI Layer: Display logo =====
    show_logo()

    # Optional: list templates and exit
    if list_templates:
        display_templates()
        raise typer.Exit(0)

    # ===== Mode Detection: Template or Wrapper mode =====
    executor = InitExecutor(reporter=ConsoleReporter())

    if from_agent:
        # ===== WRAPPER MODE: Wrap existing Agent file =====
        console.print("[bold cyan]🔄 Wrapping existing Agent file[/bold cyan]\n")

        # Generate project name from Agent file if not provided
        if not project_name:
            # Extract filename without extension and add agentkit- prefix
            agent_file_stem = Path(from_agent).stem
            final_project_name = f"agentkit-{agent_file_stem}"
        else:
            final_project_name = project_name

        # Display wrapping info
        console.print(f"[bold green]Project name: {final_project_name}[/bold green]")
        console.print(f"[bold blue]Agent file: {from_agent}[/bold blue]")
        console.print(f"[bold blue]Wrapper type: {wrapper_type}[/bold blue]")
        if agent_var:
            console.print(f"[bold blue]Agent variable: {agent_var}[/bold blue]")
        console.print()

        # Call wrapper executor
        result = executor.init_from_agent_file(
            project_name=final_project_name,
            agent_file_path=from_agent,
            agent_var_name=agent_var,
            wrapper_type=wrapper_type,
            directory=directory,
        )
    else:
        # ===== TEMPLATE MODE: Create from template =====

        # ===== UI Layer: Interactive template selection =====
        template_key = select_template(template)

        # Get template info for UI display
        templates = _get_templates()
        template_info = templates[template_key]

        # ===== UI Layer: Display creation info =====
        final_project_name = project_name or "simple_agent"
        console.print(
            f"[bold green]Creating project: {final_project_name}[/bold green]"
        )
        console.print(f"[bold blue]Using template: {template_info['name']}[/bold blue]")
        console.print()

        # ===== Business Logic: Call Executor layer =====
        result = executor.init_project(
            project_name=final_project_name,
            template=template_key,
            directory=directory,
            agent_name=agent_name,
            description=description,
            system_prompt=system_prompt,
            model_name=model_name,
            model_api_base=model_api_base,
            model_api_key=model_api_key,
            tools=tools,
        )

    # ===== UI Layer: Display results =====
    if result.success:
        # Success output
        console.print("[bold blue]✨ Project initialized successfully![/bold blue]")
        console.print(
            f"[blue]Template: {result.metadata.get('template_name', 'N/A')}[/blue]"
        )
        console.print(
            f"[blue]Entry point: {result.metadata.get('entry_point', 'N/A')}[/blue]"
        )
        console.print(
            f"[blue]Language: {result.metadata.get('language', 'N/A')} {result.metadata.get('language_version', '')}[/blue]"
        )

        # Display wrapper-specific info
        if from_agent and "agent_file" in result.metadata:
            console.print(
                f"[blue]Agent file: {result.metadata.get('agent_file', 'N/A')}[/blue]"
            )
            console.print(
                f"[blue]Agent variable: {result.metadata.get('agent_var', 'N/A')}[/blue]"
            )

        # Display created files
        if result.created_files:
            console.print("\n[bold cyan]Created files:[/bold cyan]")
            for file in result.created_files:
                console.print(f"  [green]✓[/green] {file}")

        # Display global config info if exists
        from agentkit.toolkit.config import global_config_exists, get_global_config

        if global_config_exists():
            try:
                global_cfg = get_global_config()
                has_config = False

                # Check if any relevant config is set
                config_items = []
                if global_cfg.region:
                    config_items.append(f"Region: [yellow]{global_cfg.region}[/yellow]")
                    has_config = True
                if global_cfg.cr.instance_name:
                    config_items.append(
                        f"CR Instance: [yellow]{global_cfg.cr.instance_name}[/yellow]"
                    )
                    has_config = True
                if global_cfg.cr.namespace_name:
                    config_items.append(
                        f"CR Namespace: [yellow]{global_cfg.cr.namespace_name}[/yellow]"
                    )
                    has_config = True
                if global_cfg.tos.bucket:
                    config_items.append(
                        f"TOS Bucket: [yellow]{global_cfg.tos.bucket}[/yellow]"
                    )
                    has_config = True
                if global_cfg.tos.prefix:
                    config_items.append(
                        f"TOS Prefix: [yellow]{global_cfg.tos.prefix}[/yellow]"
                    )
                    has_config = True
                if has_config:
                    console.print(
                        "\n[bold][cyan]ℹ️  Detected global configuration. The following fields will use global defaults:[/cyan][/bold]"
                    )
                    for item in config_items:
                        console.print(f"  • {item}")
                    console.print(
                        "[dim]  To override, provide explicit values in agentkit.yaml[/dim]"
                    )
            except Exception:
                pass  # Silently ignore if global config loading fails

        # Next steps guidance
        console.print("\n[bold cyan]Next steps:[/bold cyan]")
        console.print("  1. Review and modify the generated files")
        console.print("  2. Use [bold]agentkit config[/bold] to configure your agent")
        console.print("  3. Use [bold]agentkit launch[/bold] to build and deploy")
        console.print()
    else:
        # Error output
        console.print(f"[red]✗ Failed to create project: {result.error}[/red]")
        if result.error_code:
            console.print(f"[yellow]Error code: {result.error_code}[/yellow]")
        raise typer.Exit(1)
