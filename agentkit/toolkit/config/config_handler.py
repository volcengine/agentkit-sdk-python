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

"""Non-interactive configuration handler."""

from typing import Dict, List, Any, Optional
from rich.console import Console
from rich.table import Table
from rich import box

from agentkit.toolkit.config.config import get_config
from agentkit.toolkit.config.config_validator import ConfigValidator

console = Console()


class ConfigParamHandler:
    """Configuration parameter handler."""

    @staticmethod
    def parse_runtime_envs(env_list: Optional[List[str]]) -> Dict[str, str]:
        """Parse environment variables in KEY=VALUE format.

        Args:
            env_list: List of environment variables, e.g. ["KEY1=VALUE1", "KEY2=VALUE2"]

        Returns:
            Parsed dictionary
        """
        if not env_list:
            return {}

        result = {}
        for env in env_list:
            if "=" not in env:
                console.print(
                    f"[yellow]Warning: Ignoring invalid environment variable format '{env}' (should be KEY=VALUE)[/yellow]"
                )
                continue

            key, value = env.split("=", 1)
            key = key.strip()
            value = value.strip()

            if not key:
                console.print(
                    f"[yellow]Warning: Ignoring environment variable with empty key '{env}'[/yellow]"
                )
                continue

            result[key] = value

        return result

    @staticmethod
    def collect_cli_params(
        agent_name: Optional[str],
        entry_point: Optional[str],
        description: Optional[str],
        language: Optional[str],
        language_version: Optional[str],
        python_version: Optional[str],
        dependencies_file: Optional[str],
        launch_type: Optional[str],
        runtime_envs: Optional[List[str]],
        strategy_runtime_envs: Optional[List[str]],
        region: Optional[str],
        tos_bucket: Optional[str],
        image_tag: Optional[str],
        cr_instance_name: Optional[str],
        cr_namespace_name: Optional[str],
        cr_repo_name: Optional[str],
        cr_auto_create_instance_type: Optional[str],
        runtime_name: Optional[str],
        runtime_role_name: Optional[str],
        runtime_apikey_name: Optional[str],
        runtime_auth_type: Optional[str],
        runtime_jwt_discovery_url: Optional[str],
        runtime_jwt_allowed_clients: Optional[List[str]],
    ) -> Dict[str, Any]:
        """Collect all CLI parameters.

        Args:
            language: Programming language (Python/Golang)
            language_version: Language version
            python_version: [Deprecated] Python version (backward compatibility)

        Returns:
            Dict with 'common' (CommonConfig params) and 'strategy' (strategy-specific params)
        """
        common_params = {}
        strategy_params = {}

        if agent_name is not None:
            common_params["agent_name"] = agent_name
        if entry_point is not None:
            common_params["entry_point"] = entry_point
        if description is not None:
            common_params["description"] = description

        if language is not None:
            common_params["language"] = language

        if language_version is not None:
            common_params["language_version"] = language_version
        elif python_version is not None:
            console.print(
                "[yellow]Warning: --python_version is deprecated, use --language_version[/yellow]"
            )
            common_params["language_version"] = python_version
            if language is None:
                common_params["language"] = "Python"

        if dependencies_file is not None:
            common_params["dependencies_file"] = dependencies_file
        if launch_type is not None:
            common_params["launch_type"] = launch_type

        if runtime_envs is not None:
            common_params["runtime_envs"] = ConfigParamHandler.parse_runtime_envs(
                runtime_envs
            )

        if strategy_runtime_envs is not None:
            strategy_params["runtime_envs"] = ConfigParamHandler.parse_runtime_envs(
                strategy_runtime_envs
            )
        if region is not None:
            strategy_params["region"] = region
        if tos_bucket is not None:
            strategy_params["tos_bucket"] = tos_bucket
        if image_tag is not None:
            strategy_params["image_tag"] = image_tag
        if cr_instance_name is not None:
            strategy_params["cr_instance_name"] = cr_instance_name
        if cr_namespace_name is not None:
            strategy_params["cr_namespace_name"] = cr_namespace_name
        if cr_repo_name is not None:
            strategy_params["cr_repo_name"] = cr_repo_name
        if cr_auto_create_instance_type is not None:
            strategy_params["cr_auto_create_instance_type"] = (
                cr_auto_create_instance_type
            )
        if runtime_name is not None:
            strategy_params["runtime_name"] = runtime_name
        if runtime_role_name is not None:
            strategy_params["runtime_role_name"] = runtime_role_name
        if runtime_apikey_name is not None:
            strategy_params["runtime_apikey_name"] = runtime_apikey_name
        if runtime_auth_type is not None:
            strategy_params["runtime_auth_type"] = runtime_auth_type
        if runtime_jwt_discovery_url is not None:
            strategy_params["runtime_jwt_discovery_url"] = runtime_jwt_discovery_url
        if runtime_jwt_allowed_clients is not None:
            strategy_params["runtime_jwt_allowed_clients"] = runtime_jwt_allowed_clients

        return {"common": common_params, "strategy": strategy_params}

    @staticmethod
    def has_cli_params(params: Dict[str, Any]) -> bool:
        """Check if CLI parameters exist."""
        return bool(params["common"]) or bool(params["strategy"])


class NonInteractiveConfigHandler:
    """Non-interactive configuration handler."""

    def __init__(self, config_path: Optional[str] = None):
        self.config_manager = get_config(config_path=config_path)
        self.validator = ConfigValidator()

    def update_config(
        self,
        common_params: Dict[str, Any],
        strategy_params: Dict[str, Any],
        dry_run: bool = False,
    ) -> bool:
        """Update configuration.

        Args:
            common_params: CommonConfig parameters
            strategy_params: Strategy-specific parameters
            dry_run: Preview mode without saving

        Returns:
            Success status
        """
        common_config = self.config_manager.get_common_config()
        old_config_dict = common_config.to_dict()

        for key, value in common_params.items():
            if hasattr(common_config, key):
                if key == "runtime_envs" and isinstance(value, dict):
                    existing_envs = getattr(common_config, key, {})
                    if isinstance(existing_envs, dict):
                        existing_envs.update(value)
                        setattr(common_config, key, existing_envs)
                    else:
                        setattr(common_config, key, value)
                else:
                    setattr(common_config, key, value)
            else:
                console.print(
                    f"[yellow]Warning: Unknown configuration item '{key}'[/yellow]"
                )

        errors = self.validator.validate_common_config(common_config)
        if errors:
            console.print("[red]Configuration validation failed:[/red]")
            for error in errors:
                console.print(f"  [red]✗[/red] {error}")
            return False

        new_config_dict = common_config.to_dict()
        self._show_config_changes(
            old_config_dict, new_config_dict, "Common Configuration"
        )

        new_strategy_config = None
        if strategy_params:
            strategy_name = common_config.launch_type
            old_strategy_config = self.config_manager.get_strategy_config(strategy_name)
            new_strategy_config = old_strategy_config.copy()

            for key, value in strategy_params.items():
                if key == "runtime_envs" and isinstance(value, dict):
                    existing_envs = new_strategy_config.get("runtime_envs", {})
                    if isinstance(existing_envs, dict):
                        existing_envs.update(value)
                        new_strategy_config["runtime_envs"] = existing_envs
                    else:
                        new_strategy_config["runtime_envs"] = value
                else:
                    new_strategy_config[key] = value

            strategy_obj = None
            if strategy_name == "local":
                from agentkit.toolkit.config import LocalStrategyConfig

                strategy_obj = LocalStrategyConfig.from_dict(
                    new_strategy_config, skip_render=True
                )
            elif strategy_name == "cloud":
                from agentkit.toolkit.config import CloudStrategyConfig

                strategy_obj = CloudStrategyConfig.from_dict(
                    new_strategy_config, skip_render=True
                )
            elif strategy_name == "hybrid":
                from agentkit.toolkit.config import HybridStrategyConfig

                strategy_obj = HybridStrategyConfig.from_dict(
                    new_strategy_config, skip_render=True
                )

            if strategy_obj is not None:
                strategy_errors = self.validator.validate_dataclass(strategy_obj)
                if strategy_errors:
                    console.print("[red]Configuration validation failed:[/red]")
                    for error in strategy_errors:
                        console.print(f"  [red]✗[/red] {error}")
                    return False

            self._show_config_changes(
                old_strategy_config,
                new_strategy_config,
                f"{strategy_name} Mode Configuration",
            )

        if dry_run:
            console.print("\n[yellow]Preview mode: Configuration not saved[/yellow]")
            return True

        self.config_manager.update_common_config(common_config)

        if new_strategy_config is not None:
            self.config_manager.update_strategy_config(
                strategy_name, new_strategy_config
            )

        console.print("\n[green]✅ Configuration updated successfully![/green]")
        console.print(f"Configuration file: {self.config_manager.get_config_path()}")

        return True

    def _show_config_changes(
        self, old_config: Dict[str, Any], new_config: Dict[str, Any], title: str
    ):
        """Display configuration changes.

        Args:
            old_config: Old configuration
            new_config: New configuration
            title: Title
        """
        changes = []
        all_keys = set(old_config.keys()) | set(new_config.keys())

        for key in all_keys:
            if key.startswith("_"):
                continue

            old_value = old_config.get(key)
            new_value = new_config.get(key)

            if old_value != new_value:
                changes.append((key, old_value, new_value))

        if not changes:
            return

        console.print(f"\n[bold cyan]{title} - Changes:[/bold cyan]")
        table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
        table.add_column("Config Item", style="cyan", width=25)
        table.add_column("Old Value", style="yellow", width=30)
        table.add_column("New Value", style="green", width=30)

        for key, old_value, new_value in changes:
            old_str = self._format_value(old_value)
            new_str = self._format_value(new_value)

            if old_value is None or old_value == "":
                old_str = "[dim](not set)[/dim]"
            if new_value is None or new_value == "":
                new_str = "[dim](not set)[/dim]"

            table.add_row(key, old_str, new_str)

        console.print(table)

    def _format_value(self, value: Any) -> str:
        """Format value for display."""
        if value is None:
            return ""
        if isinstance(value, dict):
            if not value:
                return "{}"
            items = list(value.items())[:3]
            result = ", ".join(f"{k}={v}" for k, v in items)
            if len(value) > 3:
                result += f" ... (total {len(value)} items)"
            return result
        if isinstance(value, list):
            if not value:
                return "[]"
            result = ", ".join(str(v) for v in value[:3])
            if len(value) > 3:
                result += f" ... (total {len(value)} items)"
            return result
        return str(value)

    def show_current_config(self):
        """Display current configuration."""
        common_config = self.config_manager.get_common_config()

        console.print("\n[bold cyan]Current Configuration:[/bold cyan]")

        table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
        table.add_column("Config Item", style="cyan", width=25)
        table.add_column("Value", style="green", width=50)

        config_dict = common_config.to_dict()
        for key, value in config_dict.items():
            if not key.startswith("_"):
                table.add_row(key, self._format_value(value))

        console.print(table)

        strategy_name = common_config.launch_type
        if strategy_name:
            strategy_config = self.config_manager.get_strategy_config(strategy_name)
            if strategy_config:
                console.print(
                    f"\n[bold cyan]{strategy_name} Mode Configuration:[/bold cyan]"
                )

                config_table = Table(
                    show_header=True, header_style="bold magenta", box=box.ROUNDED
                )
                config_table.add_column("Config Item", style="cyan", width=25)
                config_table.add_column("Value", style="green", width=50)

                for key, value in strategy_config.items():
                    if not key.startswith("_"):
                        config_table.add_row(key, self._format_value(value))

                console.print(config_table)
