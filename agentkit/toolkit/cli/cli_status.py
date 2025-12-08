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

"""AgentKit CLI - Status command implementation."""

import typer
from pathlib import Path
from rich.console import Console

# Note: Avoid importing heavy packages at the top to keep CLI startup fast

console = Console()


def status_command(
    config_file: Path = typer.Option("agentkit.yaml", help="Configuration file"),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed information"
    ),
):
    """Show current status of the agent runtime."""
    from agentkit.toolkit.executors import StatusExecutor
    from agentkit.toolkit.cli.console_reporter import ConsoleReporter
    from rich.table import Table
    from rich.panel import Panel

    try:
        # Set execution context - CLI uses ConsoleReporter (with colored output and progress)
        from agentkit.toolkit.context import ExecutionContext

        reporter = ConsoleReporter()
        ExecutionContext.set_reporter(reporter)

        executor = StatusExecutor(reporter=reporter)
        result = executor.execute(config_file=str(config_file))

        if not result.success:
            console.print(f"[red]❌ Status query failed: {result.error}[/red]")
            raise typer.Exit(1)

        # Status display (compatible with enum and string)
        status_str = (
            result.status.value
            if hasattr(result.status, "value")
            else str(result.status)
        )

        status_color = {
            "running": "green",
            "stopped": "yellow",
            "not_deployed": "dim",
            "error": "red",
            "unknown": "dim",
        }.get(status_str, "white")

        status_icon = {
            "running": "✅",
            "stopped": "⏸️",
            "not_deployed": "⚫",
            "error": "❌",
            "unknown": "❓",
        }.get(status_str, "●")

        console.print(
            f"\n[bold {status_color}]{status_icon} Service Status: {status_str.upper()}[/bold {status_color}]\n"
        )

        # Basic information table
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")

        # Display different information based on deployment mode
        if result.container_id:  # Local mode
            details = result.metadata or {}
            container_info = details.get("container", {})
            image_info = details.get("image", {})

            if result.endpoint_url:
                table.add_row("🌐 Endpoint", result.endpoint_url)
            if result.container_id:
                table.add_row("📦 Container ID", result.container_id[:12])
            if container_info.get("name"):
                table.add_row("📛 Container Name", container_info["name"])
            if result.uptime_seconds:
                # Format uptime to human-readable format
                uptime = result.uptime_seconds
                hours = uptime // 3600
                minutes = (uptime % 3600) // 60
                seconds = uptime % 60
                uptime_str = (
                    f"{hours}h {minutes}m {seconds}s"
                    if hours > 0
                    else f"{minutes}m {seconds}s"
                )
                table.add_row("⏱️ Uptime", uptime_str)

            # Port mappings
            ports = container_info.get("ports", {})
            if ports:
                port_mappings = []
                for container_port, host_bindings in ports.items():
                    if host_bindings:
                        for binding in host_bindings:
                            host_ip = binding.get("HostIp", "0.0.0.0")
                            host_port = binding.get("HostPort", "")
                            if host_ip == "0.0.0.0":
                                port_mappings.append(f"{host_port}->{container_port}")
                            else:
                                port_mappings.append(
                                    f"{host_ip}:{host_port}->{container_port}"
                                )
                if port_mappings:
                    table.add_row("🔌 Ports", ", ".join(port_mappings))

            # Image information
            if image_info.get("name"):
                table.add_row("💿 Image", image_info["name"])
            if image_info.get("id"):
                table.add_row("🏷️  Image ID", image_info["id"])
            if image_info.get("size"):
                size_mb = image_info["size"] / (1024 * 1024)
                table.add_row("📊 Size", f"{size_mb:.1f} MB")

        elif result.service_id:  # Cloud mode
            if result.endpoint_url:
                table.add_row("🌐 Endpoint", result.endpoint_url)
            if result.service_id:
                table.add_row("☁️ Service ID", result.service_id)
            if result.uptime_seconds:
                # Format uptime to human-readable format
                uptime = result.uptime_seconds
                hours = uptime // 3600
                minutes = (uptime % 3600) // 60
                seconds = uptime % 60
                uptime_str = (
                    f"{hours}h {minutes}m {seconds}s"
                    if hours > 0
                    else f"{minutes}m {seconds}s"
                )
                table.add_row("⏱️ Uptime", uptime_str)

            # Extract other information from metadata
            details = result.metadata or {}
            if details.get("runtime_name"):
                table.add_row("📛 Runtime Name", details["runtime_name"])
            if details.get("image_url"):
                table.add_row("💿 Image", details["image_url"])

            # Display data plane health check status
            ping_status = details.get("ping_status")
            if ping_status is not None:
                if ping_status is True:
                    health_status = "[green]✔️ Healthy[/green]"
                elif ping_status is False:
                    health_status = "[red]❌ Unhealthy[/red]"
                else:
                    health_status = "[dim]❓ Unknown[/dim]"
                table.add_row("💚 Health Check", health_status)

        console.print(table)

        # Verbose mode displays detailed information
        if verbose and result.metadata:
            console.print("\n[dim]ℹ️  Detailed Information:[/dim]")
            import json

            console.print(
                Panel(
                    json.dumps(result.metadata, indent=2, ensure_ascii=False),
                    title="Metadata",
                    border_style="dim",
                )
            )

        console.print()  # Empty line

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Interrupted by user (Ctrl+C)[/yellow]\n")

    except typer.Exit:
        # Re-raise typer.Exit, do not catch it
        raise
    except Exception as e:
        console.print(f"[red]❌ Status query failed: {e}[/red]")
        raise typer.Exit(1)
