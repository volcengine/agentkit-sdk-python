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

"""AgentKit Configuration Manager"""

from pathlib import Path
from typing import Dict, Any, Optional, Union
import os
import yaml
from .dataclass_utils import AutoSerializableMixin
from dataclasses import dataclass, field
from .docker_build_config import DockerBuildConfig

STRATEGY_NAME_IN_YAML = "launch_types"


@dataclass
class CommonConfig(AutoSerializableMixin):
    """Common configuration - automatic prompt generation support"""

    agent_name: str = field(
        default="",
        metadata={
            "description": "Agent application name",
            "icon": "🤖",
            "validation": {
                "required": True,
                "pattern": r"^[a-zA-Z0-9_-]+$",
                "message": "Only letters, numbers, underscore(_) and hyphen(-) are allowed",
            },
        },
    )
    entry_point: str = field(
        default="agent.py",
        metadata={
            "description": "Agent application entry file (path allowed), e.g. simple_agent.py or main.go or build.sh",
            "icon": "📝",
            "validation": {
                "required": True,
                # allow relative paths with directories and either .py or .go endings
                "pattern": r"^[\w\-/\.]+?\.(py|go|sh)$",
                "message": "Must be a Python (.py) or Go (.go) file path or shell script (.sh), containing only letters, numbers, underscore(_), hyphen(-), dot(.) and '/' for directories",
            },
        },
    )
    description: str = field(
        default="", metadata={"description": "Application description", "icon": "📄"}
    )
    language: str = field(
        default="Python",
        metadata={
            "description": "Agent application Language, defaults to Python",
            "icon": "✏️",
            "choices": [
                {"value": "Python", "description": "Python"},
                {"value": "Golang", "description": "Go (Golang)"},
            ],
        },
    )
    language_version: str = field(
        default="",
        metadata={
            "description": "Agent application Language version",
            "icon": "🐍",
            "validation": {
                "type": "conditional",
                "depends_on": "language",
                "rules": {
                    "Python": {
                        "choices": ["3.10", "3.11", "3.12", "3.13"],
                        "message": "Python version must be 3.10, 3.11, 3.12, or 3.13",
                    },
                    "Golang": {
                        "choices": ["1.24"],
                        "message": "Golang version must be '1.24'",
                    },
                },
            },
        },
    )
    agent_type: str = field(
        default="Basic App",
        metadata={
            "description": "Agent application Type",
            "icon": "📩",
            "hidden": True,
        },
    )
    dependencies_file: str = field(
        default="",
        metadata={"description": "Agent application Dependencies file", "icon": "📦"},
    )
    runtime_envs: Dict[str, str] = field(
        default_factory=dict,
        metadata={
            "description": "Application-level runtime environment variables (shared across all deployment modes)",
            "icon": "🔐",
            "hidden": False,
        },
    )
    launch_type: str = field(
        default="cloud",
        metadata={
            "description": "Deployment and runtime mode, defaults to local (local build and deploy), optional hybrid (local build, cloud deploy)",
            "icon": "🚀",
            "choices": [
                {"value": "local", "description": "Local build and deploy"},
                {"value": "hybrid", "description": "Local build, cloud deploy"},
                {
                    "value": "cloud",
                    "description": "Cloud build and deploy base on Volcano Engine Agentkit Platform",
                },
            ],
        },
    )

    _config_metadata = {
        "name": "Basic Configuration",
        "welcome_message": "Welcome to AgentKit Configuration Wizard",
        "next_step_hint": "This wizard will help you configure your Agent application. Follow the prompts or press Enter to use default values.",
        "completion_message": "Great! Common configuration completed!",
        "next_action_hint": "Now configuring the selected deployment mode.",
    }

    @staticmethod
    def _recommended_for_language(language: str) -> Dict[str, str]:
        """Return recommended language_version and dependencies_file for supported languages."""
        mapping = {
            "python": {
                "language_version": "3.12",
                "dependencies_file": "requirements.txt",
            },
            "golang": {"language_version": "1.24", "dependencies_file": "go.mod"},
        }
        return mapping.get((language or "python").lower(), mapping["python"])

    def __post_init__(self):
        """Ensure language-specific defaults for language_version and dependencies_file."""
        rec = self._recommended_for_language(self.language)
        lv = (self.language_version or "").strip()
        df = (self.dependencies_file or "").strip()
        lang = (self.language or "python").lower()

        if not lv:
            self.language_version = rec["language_version"]
        else:
            if lang == "golang" and (lv.startswith("3.") or lv == "3.12"):
                self.language_version = rec["language_version"]
            if lang == "python" and lv.startswith("1."):
                self.language_version = rec["language_version"]

        if not df:
            self.dependencies_file = rec["dependencies_file"]
        else:
            if lang == "golang" and df == "requirements.txt":
                self.dependencies_file = rec["dependencies_file"]
            if lang == "python" and df == "go.mod":
                self.dependencies_file = rec["dependencies_file"]

    def set_language(self, language: str):
        """Change language and apply recommended defaults."""
        self.language = language
        rec = self._recommended_for_language(language)
        lv = (self.language_version or "").strip()
        df = (self.dependencies_file or "").strip()

        if (
            not lv
            or lv in ("3.12", "1.24")
            or lv.startswith("3.")
            and language.lower() == "go"
        ):
            self.language_version = rec["language_version"]
        if not df or df in ("requirements.txt", "go.mod"):
            self.dependencies_file = rec["dependencies_file"]


class AgentkitConfigManager:
    """Agentkit configuration manager - fully dynamic, no predefined strategy structure"""

    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        if config_path is None or config_path == "":
            config_path = Path.cwd() / "agentkit.yaml"
        self.config_path = Path(config_path)

        self.project_dir = self._resolve_project_dir()

        self._data: Dict[str, Any] = {}
        self._load_config()

    def _resolve_project_dir(self) -> Path:
        """Resolve project directory (configuration file location)."""
        if self.config_path.is_file():
            return self.config_path.parent
        elif self.config_path.exists():
            return self.config_path
        else:
            return (
                self.config_path.parent
                if self.config_path.parent.exists()
                else Path.cwd()
            )

    def get_project_dir(self) -> Path:
        """Get project root directory."""
        return self.project_dir

    @classmethod
    def from_dict(
        cls,
        config_dict: Dict[str, Any],
        base_config_path: Optional[Union[str, Path]] = None,
    ) -> "AgentkitConfigManager":
        """Create config manager from dictionary.

        This method supports creating a configuration manager directly from a
        dictionary, optionally merging with an existing configuration file.

        Args:
            config_dict: Configuration dictionary. Should contain 'common' and
                        optionally 'launch_types' keys matching the YAML structure.
            base_config_path: Optional path to existing config file to use as base.
                            If provided and exists, config_dict will be deep-merged
                            into the base configuration.

        Returns:
            AgentkitConfigManager instance with the specified configuration.
            Note: This instance is NOT saved to disk automatically.

        Example:
            >>> # Create from pure dict
            >>> config = AgentkitConfigManager.from_dict({
            ...     "common": {
            ...         "agent_name": "my_agent",
            ...         "launch_type": "hybrid"
            ...     }
            ... })
            >>>
            >>> # Create by merging with existing config
            >>> config = AgentkitConfigManager.from_dict(
            ...     config_dict={"common": {"launch_type": "hybrid"}},
            ...     base_config_path="agentkit.yaml"
            ... )
        """
        instance = cls.__new__(cls)
        instance.config_path = (
            Path(base_config_path) if base_config_path else Path("agentkit.yaml")
        )
        instance.project_dir = instance._resolve_project_dir()

        if base_config_path and Path(base_config_path).exists():
            with open(base_config_path, "r", encoding="utf-8") as f:
                base_data = yaml.safe_load(f) or {}
            instance._data = instance._deep_merge(base_data, config_dict)
        else:
            if "common" not in config_dict:
                config_dict = {
                    "common": CommonConfig().to_dict(),
                    STRATEGY_NAME_IN_YAML: config_dict.get(STRATEGY_NAME_IN_YAML, {}),
                }
            instance._data = config_dict

            if STRATEGY_NAME_IN_YAML not in instance._data:
                instance._data[STRATEGY_NAME_IN_YAML] = {}

        return instance

    def _load_config(self):
        """Load configuration file"""
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._data = yaml.safe_load(f) or {}
        else:
            self._data = self._get_default_config()
            self._save_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "common": CommonConfig().to_dict(),
            STRATEGY_NAME_IN_YAML: {},
            "docker_build": {},
        }

    def _save_config(self):
        """Save configuration file"""
        os.makedirs(self.config_path.parent, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(
                self._data,
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )

    def get_common_config(self) -> CommonConfig:
        """Get common configuration"""
        return CommonConfig.from_dict(self._data.get("common", {}))

    def update_common_config(self, config: CommonConfig):
        """Update common configuration"""
        self._data["common"] = config.to_dict()
        self._save_config()

    def get_docker_build_config(self) -> DockerBuildConfig:
        """Get Docker build configuration"""
        return DockerBuildConfig.from_dict(self._data.get("docker_build", {}))

    def update_docker_build_config(self, config: DockerBuildConfig):
        """Update Docker build configuration"""
        self._data["docker_build"] = config.to_dict()
        self._save_config()

    def set_docker_build_runtime_param(self, key: str, value: Any):
        """Set runtime parameter for docker_build (not persisted to file)

        Args:
            key: Parameter name
            value: Parameter value
        """
        if "docker_build" not in self._data:
            self._data["docker_build"] = {}
        self._data["docker_build"][key] = value

    def get_strategy_config(self, strategy_name: str) -> Dict[str, Any]:
        """Get specified strategy configuration."""
        return self._data.get(STRATEGY_NAME_IN_YAML, {}).get(strategy_name, {})

    def update_strategy_config(
        self, strategy_name: str, config: Dict[str, Any], filter_empty: bool = True
    ):
        """Update strategy configuration using deep merge strategy.

        Args:
            strategy_name: Strategy name
            config: Configuration dict
            filter_empty: Whether to filter empty values (default True)
        """
        if STRATEGY_NAME_IN_YAML not in self._data:
            self._data[STRATEGY_NAME_IN_YAML] = {}

        if filter_empty:
            config = self._filter_config_values(config)

        existing_config = self._data[STRATEGY_NAME_IN_YAML].get(strategy_name, {})
        merged_config = self._deep_merge(existing_config, config)
        merged_config = self._reorder_by_dataclass_fields(strategy_name, merged_config)

        self._data[STRATEGY_NAME_IN_YAML][strategy_name] = merged_config
        self._save_config()

    def _filter_config_values(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Filter empty and meaningless values from configuration."""
        filtered = {}

        for key, value in config.items():
            if value == "" or value is None:
                continue

            if isinstance(value, dict):
                filtered_nested = self._filter_config_values(value)
                if filtered_nested:
                    filtered[key] = filtered_nested
            else:
                filtered[key] = value

        return filtered

    def _deep_merge(
        self, base: Dict[str, Any], update: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Deep merge two dictionaries."""
        result = base.copy()

        for key, value in update.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def _reorder_by_dataclass_fields(
        self, strategy_name: str, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Reorder configuration dict by dataclass field order."""
        from dataclasses import fields

        config_class = None
        if strategy_name == "local":
            from agentkit.toolkit.config import LocalStrategyConfig

            config_class = LocalStrategyConfig
        elif strategy_name == "cloud":
            from agentkit.toolkit.config import CloudStrategyConfig

            config_class = CloudStrategyConfig
        elif strategy_name == "hybrid":
            from agentkit.toolkit.config import HybridStrategyConfig

            config_class = HybridStrategyConfig
        else:
            return config

        field_names = [f.name for f in fields(config_class)]
        ordered_config = {}

        for field_name in field_names:
            if field_name in config:
                ordered_config[field_name] = config[field_name]

        for key, value in config.items():
            if key not in ordered_config:
                ordered_config[key] = value

        return ordered_config

    def list_strategies(self) -> list[str]:
        """List all configured strategy names"""
        return list(self._data.get(STRATEGY_NAME_IN_YAML, {}).keys())

    def strategy_exists(self, strategy_name: str) -> bool:
        """Check if strategy exists"""
        return strategy_name in self._data.get(STRATEGY_NAME_IN_YAML, {})

    def get_config_path(self) -> Path:
        """Get configuration file path"""
        return self.config_path

    def reload(self):
        """Reload configuration"""
        self._load_config()

    def reset_to_default(self):
        """Reset to default configuration"""
        self._data = self._get_default_config()
        self._save_config()

    def get_raw_data(self) -> Dict[str, Any]:
        """Get raw configuration data."""
        return self._data.copy()

    def set_raw_value(self, key_path: str, value: Any):
        """Directly set value at any path."""
        keys = key_path.split(".")
        current = self._data

        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        current[keys[-1]] = value
        self._save_config()

    def get_raw_value(self, key_path: str, default: Any = None) -> Any:
        """Get value at any path."""
        keys = key_path.split(".")
        current = self._data

        try:
            for key in keys:
                current = current[key]
            return current
        except (KeyError, TypeError):
            return default


_config_instances: Dict[str, AgentkitConfigManager] = {}


def get_config(
    config_path: Optional[str] = None, force_reload: bool = False
) -> AgentkitConfigManager:
    """Get configuration instance with singleton pattern.

    Args:
        config_path: Path to configuration file. If None, uses "agentkit.yaml".
        force_reload: If True, reload configuration from disk even if cached.

    Returns:
        AgentkitConfigManager instance.
    """
    if not config_path:
        config_path = "agentkit.yaml"

    from pathlib import Path

    cache_key = str(Path(config_path).resolve()) if config_path else "default"

    if not force_reload and cache_key in _config_instances:
        return _config_instances[cache_key]

    instance = AgentkitConfigManager(config_path)
    _config_instances[cache_key] = instance

    return instance


def clear_config_cache():
    """Clear the config instance cache."""
    global _config_instances
    _config_instances.clear()
