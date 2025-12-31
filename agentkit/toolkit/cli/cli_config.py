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

"""AgentKit CLI - Config command implementation."""

from typing import Optional, List
import typer
from rich.console import Console

from agentkit.toolkit.config import get_config
from agentkit.toolkit.config.config_handler import (
    ConfigParamHandler,
    NonInteractiveConfigHandler,
)

# Note: Avoid importing heavy packages at the top of the file to prevent command slowdown

console = Console()


def config_command(
    config_file: Optional[str] = typer.Option(
        None, "--config", "-c", help="Path to config file"
    ),
    # Mode control
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Force interactive mode"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview config changes without saving"
    ),
    show: bool = typer.Option(
        False, "--show", "-s", help="Display current configuration"
    ),
    # Global config support
    global_config: bool = typer.Option(
        False,
        "--global",
        "-g",
        help="Operate on global config (~/.agentkit/config.yaml)",
    ),
    set_field: Optional[str] = typer.Option(
        None,
        "--set",
        help="Set field (format: key=value, e.g., cr.instance_name=my-cr)",
    ),
    init_global: bool = typer.Option(
        False, "--init", help="Initialize global config file (create template)"
    ),
    # CommonConfig parameters
    agent_name: Optional[str] = typer.Option(
        None, "--agent_name", help="Agent application name"
    ),
    entry_point: Optional[str] = typer.Option(
        None, "--entry_point", help="Entry point file (e.g., agent.py)"
    ),
    description: Optional[str] = typer.Option(
        None, "--description", help="Application description"
    ),
    language: Optional[str] = typer.Option(
        None, "--language", help="Programming language: Python/Golang"
    ),
    language_version: Optional[str] = typer.Option(
        None,
        "--language_version",
        help="Language version (e.g., Python: 3.10-3.13, Go: 1.x)",
    ),
    python_version: Optional[str] = typer.Option(
        None,
        "--python_version",
        help="[Deprecated] Python version, use --language_version instead",
    ),
    dependencies_file: Optional[str] = typer.Option(
        None, "--dependencies_file", help="Dependencies file (e.g., requirements.txt)"
    ),
    launch_type: Optional[str] = typer.Option(
        None, "--launch_type", help="Deployment mode: local/hybrid/cloud"
    ),
    # Application-level environment variables (CommonConfig)
    runtime_envs: Optional[List[str]] = typer.Option(
        None,
        "--runtime_envs",
        "-e",
        help="App-level env vars KEY=VALUE, shared across all deployment modes (can be used multiple times)",
    ),
    # Strategy-level environment variables
    strategy_runtime_envs: Optional[List[str]] = typer.Option(
        None,
        "--strategy-runtime-envs",
        help="Strategy-level env vars KEY=VALUE, used only for current deployment mode (can be used multiple times)",
    ),
    # Hybrid/Cloud Strategy parameters
    region: Optional[str] = typer.Option(
        None, "--region", help="Region (e.g., cn-beijing)"
    ),
    tos_bucket: Optional[str] = typer.Option(
        None, "--tos_bucket", help="TOS bucket name"
    ),
    image_tag: Optional[str] = typer.Option(
        None, "--image_tag", help="Image tag (e.g., 0.0.1)"
    ),
    cr_instance_name: Optional[str] = typer.Option(
        None, "--cr_instance_name", "--ve_cr_instance_name", help="CR instance name"
    ),
    cr_namespace_name: Optional[str] = typer.Option(
        None, "--cr_namespace_name", "--ve_cr_namespace_name", help="CR namespace"
    ),
    cr_repo_name: Optional[str] = typer.Option(
        None, "--cr_repo_name", "--ve_cr_repo_name", help="CR repository name"
    ),
    cr_auto_create_instance_type: Optional[str] = typer.Option(
        None,
        "--cr_auto_create_instance_type",
        help="CR instance type when auto-creating: Micro/Enterprise",
    ),
    # Runtime configuration parameters
    runtime_name: Optional[str] = typer.Option(
        None, "--runtime_name", "--ve_runtime_name", help="Runtime instance name"
    ),
    runtime_role_name: Optional[str] = typer.Option(
        None,
        "--runtime_role_name",
        "--ve_runtime_role_name",
        help="Runtime authorization role name",
    ),
    runtime_apikey_name: Optional[str] = typer.Option(
        None,
        "--runtime_apikey_name",
        "--ve_runtime_apikey_name",
        help="Runtime API key secret name",
    ),
    runtime_auth_type: Optional[str] = typer.Option(
        None,
        "--runtime_auth_type",
        help="Runtime authentication type: key_auth/custom_jwt",
    ),
    runtime_jwt_discovery_url: Optional[str] = typer.Option(
        None,
        "--runtime_jwt_discovery_url",
        help="OIDC Discovery URL when runtime_auth_type is custom_jwt",
    ),
    runtime_jwt_allowed_clients: Optional[List[str]] = typer.Option(
        None,
        "--runtime_jwt_allowed_clients",
        help="Allowed OAuth2 client IDs when runtime_auth_type is custom_jwt (can be used multiple times)",
    ),
):
    """Configure AgentKit (supports interactive and non-interactive modes).
    
    Examples:
    
    \b
    # Interactive configuration (default)
    agentkit config
    
    \b
    # Non-interactive configuration (full example)
    agentkit config \\
        --agent_name myAgent \\
        --entry_point agent.py \\
        --language Python \\
        --language_version 3.12 \\
        --launch_type cloud \\
        --region cn-beijing \\
        --tos_bucket agentkit \\
        --image_tag 0.0.1 \\
        --runtime_name my-runtime \\
        --runtime_role_name my-role \\
        --runtime_apikey_name my-apikey \\
        --runtime_envs API_KEY=xxxxx \\
        --runtime_envs MODEL_ENDPOINT=https://api.example.com
    
    \b
    # Configure Golang application
    agentkit config \\
        --agent_name myGoAgent \\
        --entry_point main.go \\
        --language Golang \\
        --language_version 1.24
    
    \b
    # App-level vs Strategy-level environment variables
    # --runtime_envs/-e: App-level (shared across all deployment modes)
    # --strategy-runtime-envs: Strategy-level (used only for current deployment mode)
    agentkit config \\
        -e API_KEY=shared_key \\
        --strategy-runtime-envs DEBUG=true
    
    \b
    # Configure runtime parameters for cloud/hybrid deployment
    agentkit config \\
        --runtime_name my-custom-runtime \\
        --runtime_role_name my-custom-role \\
        --runtime_apikey_name my-custom-apikey
    
    \b
    # Incremental update (modify specific config only)
    agentkit config --language_version 3.13
    
    \b
    # Preview config changes
    agentkit config --entry_point agent.py --dry-run
    
    \b
    # Display current configuration
    agentkit config --show
    """

    try:
        # Handle global config operations
        if global_config:
            _handle_global_config(show, set_field, init_global)
            return

        # Handle --show option
        if show:
            handler = NonInteractiveConfigHandler(config_path=config_file)
            handler.show_current_config()
            return

        # Collect CLI parameters
        cli_params = ConfigParamHandler.collect_cli_params(
            agent_name=agent_name,
            entry_point=entry_point,
            description=description,
            language=language,
            language_version=language_version,
            python_version=python_version,  # Backward compatibility
            dependencies_file=dependencies_file,
            launch_type=launch_type,
            runtime_envs=runtime_envs,
            strategy_runtime_envs=strategy_runtime_envs,
            region=region,
            tos_bucket=tos_bucket,
            image_tag=image_tag,
            cr_instance_name=cr_instance_name,
            cr_namespace_name=cr_namespace_name,
            cr_repo_name=cr_repo_name,
            cr_auto_create_instance_type=cr_auto_create_instance_type,
            runtime_name=runtime_name,
            runtime_role_name=runtime_role_name,
            runtime_apikey_name=runtime_apikey_name,
            runtime_auth_type=runtime_auth_type,
            runtime_jwt_discovery_url=runtime_jwt_discovery_url,
            runtime_jwt_allowed_clients=runtime_jwt_allowed_clients,
        )

        has_cli_params = ConfigParamHandler.has_cli_params(cli_params)

        # Determine which mode to use: interactive or non-interactive
        if interactive or (not has_cli_params and not interactive):
            # Interactive mode (preserves original behavior)
            _interactive_config(config_file)
        else:
            # Non-interactive mode
            handler = NonInteractiveConfigHandler(config_path=config_file)
            success = handler.update_config(
                common_params=cli_params["common"],
                strategy_params=cli_params["strategy"],
                dry_run=dry_run,
            )

            if not success:
                raise typer.Exit(code=1)

    except KeyboardInterrupt:
        console.print("\n\n[yellow]⚠️  Configuration cancelled[/yellow]")
        raise typer.Exit(code=130)  # Standard exit code for Ctrl+C


def _interactive_config(config_file: Optional[str] = None):
    """Interactive configuration mode."""
    config = get_config(config_path=config_file)

    # Use CLI-layer interactive config creation function
    from agentkit.toolkit.cli.interactive_config import (
        create_common_config_interactively,
    )

    common_config = create_common_config_interactively(
        config.get_common_config().to_dict()
    )
    config.update_common_config(common_config)

    strategy_name = common_config.launch_type

    # Use CLI-layer interactive config generation
    from agentkit.toolkit.cli.interactive_config import generate_config_from_dataclass
    from agentkit.toolkit.config.strategy_configs import (
        LocalStrategyConfig,
        CloudStrategyConfig,
        HybridStrategyConfig,
    )

    # Map strategy_name to config class
    strategy_config_classes = {
        "local": LocalStrategyConfig,
        "cloud": CloudStrategyConfig,
        "hybrid": HybridStrategyConfig,
    }

    # Get current strategy config data
    current_strategy_config_dict = config.get_strategy_config(strategy_name)

    # Get corresponding config class
    config_class = strategy_config_classes.get(strategy_name)
    if not config_class:
        console.print(f"[red]❌ Unknown launch type: {strategy_name}[/red]")
        raise typer.Exit(1)

    # Generate new strategy config
    strategy_config = generate_config_from_dataclass(
        config_class, current_strategy_config_dict
    )
    config.update_strategy_config(strategy_name, strategy_config)


def _handle_global_config(show: bool, set_field: Optional[str], init_global: bool):
    """Handle global config operations: show, set, or initialize."""
    from agentkit.toolkit.config import global_config_exists

    if init_global:
        # Initialize global config file
        _init_global_config()
    elif show:
        # Display global config
        _show_global_config()
    elif set_field:
        # Set config field
        _set_global_field(set_field)
    else:
        # Display usage hints
        if not global_config_exists():
            console.print("[yellow]⚠️  Global config file does not exist[/yellow]")
            console.print("\nQuick create:")
            console.print("  agentkit config --global --init")
            console.print("\nOr create manually:")
            console.print("  mkdir -p ~/.agentkit")
            console.print("  vim ~/.agentkit/config.yaml")
        else:
            console.print("[cyan]💡 Global config file exists[/cyan]")
            console.print("\n[bold]Usage:[/bold]")
            console.print(
                "  • View config:  [yellow]agentkit config --global --show[/yellow]"
            )
            console.print(
                "  • Set field:    [yellow]agentkit config --global --set <field>=<value>[/yellow]"
            )
            console.print(
                "  • Edit file:    [yellow]vim ~/.agentkit/config.yaml[/yellow]"
            )

            console.print("\n[bold]Supported fields:[/bold]")
            console.print("  [dim]Global:[/dim]")
            console.print(
                "    • [green]region[/green]                  - Default region (e.g. cn-beijing, cn-shanghai)"
            )
            console.print("  [dim]Volcengine:[/dim]")
            console.print("    • [green]volcengine.access_key[/green]   - Access Key")
            console.print("    • [green]volcengine.secret_key[/green]   - Secret Key")
            console.print("  [dim]CR:[/dim]")
            console.print(
                "    • [green]cr.instance_name[/green]        - CR instance name"
            )
            console.print("    • [green]cr.namespace_name[/green]       - CR namespace")
            console.print(
                "    • [green]cr.auto_create_instance_type[/green] - Instance type when auto-creating (Micro/Enterprise)"
            )
            console.print("  [dim]TOS:[/dim]")
            console.print("    • [green]tos.bucket[/green]              - Bucket name")
            console.print(
                "    • [green]tos.prefix[/green]              - Object prefix"
            )


def _init_global_config():
    """Initialize global config file with template."""
    from agentkit.toolkit.config import (
        GlobalConfig,
        save_global_config,
        global_config_exists,
    )
    from pathlib import Path

    config_path = Path.home() / ".agentkit" / "config.yaml"

    # Check if file already exists
    if global_config_exists():
        console.print(
            f"[yellow]⚠️  Global config file already exists: {config_path}[/yellow]"
        )
        console.print("\nTo recreate, first delete the existing file:")
        console.print("  rm ~/.agentkit/config.yaml")
        console.print("\nOr edit the existing file directly:")
        console.print("  vim ~/.agentkit/config.yaml")
        return

    # Create default config
    config = GlobalConfig()
    # Set default values
    config.region = "cn-beijing"
    config.tos.prefix = "agentkit-builds"

    # Save config file
    try:
        save_global_config(config)
        console.print(f"[green]✅ Global config file created: {config_path}[/green]")
        console.print(
            "\n[bold cyan]📝 Config template generated with the following items:[/bold cyan]\n"
        )

        console.print("[bold]🌍 Global Settings[/bold]")
        console.print(
            "  region: cn-beijing # Default project region (e.g. cn-beijing, cn-shanghai)"
        )

        console.print("[bold]🔐 Volcengine Credentials[/bold]")
        console.print("  access_key: ''     # Volcengine Access Key")
        console.print("  secret_key: ''     # Volcengine Secret Key")

        console.print("\n[bold]📦 CR Configuration[/bold]")
        console.print("  instance_name: ''  # CR instance name")
        console.print("  namespace_name: '' # CR namespace")
        console.print(
            "  auto_create_instance_type: Micro  # Instance type when auto-creating (Micro/Enterprise)"
        )

        console.print("\n[bold]🗂️  TOS Configuration[/bold]")
        console.print("  bucket: ''         # TOS bucket name")
        console.print("  prefix: agentkit-builds")

        console.print("\n[dim]💡 Tips:[/dim]")
        console.print(f"  • Edit config:   vim {config_path}")
        console.print("  • View config:   agentkit config --global --show")

    except Exception as e:
        console.print(f"[red]❌ Failed to create config file: {e}[/red]")
        raise typer.Exit(code=1)


def _show_global_config():
    """Display global configuration."""
    from agentkit.toolkit.config import get_global_config, global_config_exists

    if not global_config_exists():
        console.print(
            "[yellow]⚠️  Global config file does not exist: ~/.agentkit/config.yaml[/yellow]"
        )
        console.print("\nQuick create:")
        console.print("  agentkit config --global --init")
        return

    config = get_global_config()

    console.print(
        "\n[bold cyan]📋 Global Configuration[/bold cyan] [dim](~/.agentkit/config.yaml)[/dim]\n"
    )

    # Display Global Settings
    console.print("[bold]🌍 Global Settings[/bold]")
    console.print(
        f"  Region:     [yellow]{config.region or '[dim](not set)[/dim]'}[/yellow]"
    )
    console.print()

    # Display Volcengine credentials
    console.print("[bold]🔐 Volcengine Credentials[/bold]")
    if config.volcengine.access_key:
        masked_ak = (
            config.volcengine.access_key[:5] + "***"
            if len(config.volcengine.access_key) > 5
            else "***"
        )
        console.print(f"  Access Key: [yellow]{masked_ak}[/yellow] (set)")
    else:
        console.print("  Access Key: [dim](not set)[/dim]")

    if config.volcengine.secret_key:
        console.print("  Secret Key: [yellow]***[/yellow] (set)")
    else:
        console.print("  Secret Key: [dim](not set)[/dim]")

    # Display CR configuration
    console.print("\n[bold]📦 CR Configuration[/bold]")
    console.print(
        f"  Instance:   [yellow]{config.cr.instance_name or '[dim](not set)[/dim]'}[/yellow]"
    )
    console.print(
        f"  Namespace:  [yellow]{config.cr.namespace_name or '[dim](not set)[/dim]'}[/yellow]"
    )
    console.print(
        f"  Auto-create Type: [yellow]{config.cr.auto_create_instance_type}[/yellow]"
    )

    # Display TOS configuration
    console.print("\n[bold]🗂️  TOS Configuration[/bold]")
    console.print(
        f"  Bucket:     [yellow]{config.tos.bucket or '[dim](not set)[/dim]'}[/yellow]"
    )
    console.print(f"  Prefix:     [yellow]{config.tos.prefix}[/yellow]")

    console.print()


def _set_global_field(field_value: str):
    """Set global config field value."""
    from agentkit.utils.global_config_io import (
        read_global_config_dict,
        write_global_config_dict,
    )

    # Parse key=value format
    if "=" not in field_value:
        console.print("[red]❌ Invalid format, should be: key=value[/red]")
        console.print("\nExamples:")
        console.print("  agentkit config --global --set cr.instance_name=my-cr")
        console.print("  agentkit config --global --set tos.bucket=my-bucket")
        raise typer.Exit(code=1)

    key, value = field_value.split("=", 1)
    parts = key.split(".")

    # Special case for top-level region
    if key == "region":
        pass
    elif len(parts) < 2:
        console.print(f"[red]❌ Invalid field format: {key}[/red]")
        console.print("\nSupported fields:")
        console.print("  • region")
        console.print("  • volcengine.access_key")
        console.print("  • volcengine.secret_key")
        console.print("  • cr.instance_name")
        console.print("  • tos.bucket")
        raise typer.Exit(code=1)

    # Read config as raw dict to preserve unknown fields (e.g. 'services')
    config_dict = read_global_config_dict()

    # Special handling for region compatibility
    if key == "volcengine.region":
        console.print(
            "[yellow]⚠️  'volcengine.region' is deprecated, setting 'region' instead.[/yellow]"
        )
        config_dict["region"] = value
    elif key == "region":
        config_dict["region"] = value
    # Special handling for known 'defaults' section which requires type conversion
    elif parts[0] == "defaults" and len(parts) == 2:
        section = "defaults"
        field = parts[1]

        # Ensure section exists
        if section not in config_dict:
            config_dict[section] = {}

        if field == "launch_type":
            clean_value = value.strip() if value is not None else None
            if clean_value == "":
                clean_value = None
            config_dict[section][field] = clean_value
        elif field == "preflight_mode":
            clean_value = value.strip().lower() if value is not None else None
            if clean_value == "":
                clean_value = None
            # Accept only known modes
            allowed = {"prompt", "fail", "warn", "skip"}
            if clean_value and clean_value not in allowed:
                raise AttributeError(
                    f"Invalid preflight_mode: {value}. Allowed: prompt|fail|warn|skip"
                )
            config_dict[section][field] = clean_value
        elif field == "cr_public_endpoint_check":
            clean_value = value.strip().lower() if value is not None else None
            if clean_value == "":
                clean_value = None
            if clean_value is None:
                config_dict[section][field] = None
            else:
                truthy = {"true", "1", "yes", "y"}
                falsy = {"false", "0", "no", "n"}
                if clean_value in truthy:
                    config_dict[section][field] = True
                elif clean_value in falsy:
                    config_dict[section][field] = False
                else:
                    raise AttributeError(
                        f"Invalid boolean value for cr_public_endpoint_check: {value}"
                    )
        elif field == "iam_role_policies":
            # Simple list parsing for CLI convenience
            if not value:
                config_dict[section][field] = []
            else:
                config_dict[section][field] = [
                    p.strip() for p in value.split(",") if p.strip()
                ]
        else:
            config_dict[section][field] = value
    else:
        # Generic recursive update for all other keys (including deep nested ones like services.tos.host)
        current = config_dict
        for i, part in enumerate(parts[:-1]):
            if part not in current:
                current[part] = {}

            if not isinstance(current[part], dict):
                # If path exists but is not a dict (collision), overwrite it with dict
                # unless it's the last step (which is handled after loop)
                current[part] = {}

            current = current[part]

        # Set the final value
        current[parts[-1]] = value

    # Save raw dict back
    try:
        write_global_config_dict(config_dict)
        console.print(f"[green]✅ Global config updated: {key}={value}[/green]")
    except Exception as e:
        console.print(f"[red]❌ Failed to set config: {e}[/red]")
        raise typer.Exit(code=1)
