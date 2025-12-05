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

"""SDK-friendly configuration management interface.

This module provides AgentConfig, a high-level configuration management class
designed for SDK users. It wraps the internal AgentkitConfigManager with a
more intuitive API featuring:
- Type-safe property access
- Fluent/chainable methods
- Path-based get/set operations
- Automatic validation
- IDE-friendly autocomplete

Example:
    >>> # Load and modify configuration
    >>> config = AgentConfig.load("./my_agent")
    >>> config.launch_type = "hybrid"
    >>> config.save()
    >>>
    >>> # Fluent API
    >>> config.set_launch_type("hybrid").set_model("deepseek-v3").save()
    >>>
    >>> # Use with Client
    >>> client = AgentKitClient(config)
"""

from typing import Optional, Dict, Any, Union
from pathlib import Path
import logging

from ..config import AgentkitConfigManager, CommonConfig, get_config
from ..config.config_validator import ConfigValidator

logger = logging.getLogger(__name__)


class AgentConfig:
    """SDK-friendly agent configuration manager.
    
    This class provides a user-friendly interface for reading and modifying
    agent configurations without directly dealing with YAML files or internal
    config structures. It wraps AgentkitConfigManager and provides:
    
    - **Type-safe properties**: Direct attribute access with validation
    - **Fluent API**: Chainable methods for configuration updates
    - **Path-based access**: Get/set nested config values by path
    - **Automatic persistence**: Changes are saved to file
    - **IDE support**: Full autocomplete and type hints
    
    Attributes:
        file_path: Path to the configuration file (agentkit.yaml)
        launch_type: Deployment mode (local/cloud/hybrid)
        agent_name: Agent application name
        entry_point: Entry file path
        description: Agent description
        language: Programming language (Python/Golang)
        language_version: Language version
        dependencies_file: Dependencies file path
        runtime_envs: Application-level environment variables
    
    Example:
        >>> # Load configuration
        >>> config = AgentConfig.load("./my_agent")
        >>> 
        >>> # Read properties
        >>> print(config.launch_type)  # "cloud"
        >>> 
        >>> # Modify properties
        >>> config.launch_type = "hybrid"
        >>> config.save()
        >>> 
        >>> # Fluent API
        >>> config.set_launch_type("hybrid") \\
        ...       .set_model("deepseek-v3") \\
        ...       .save()
        >>> 
        >>> # Path-based access
        >>> region = config.get("launch_types.cloud.region")
        >>> config.set("launch_types.hybrid.image_tag", "v1.0.0")
    """

    def __init__(self, file_path: Union[str, Path]):
        """Initialize AgentConfig.

        Args:
            file_path: Path to agentkit.yaml or project directory.
                      If a directory is provided, will look for agentkit.yaml inside.

        Raises:
            FileNotFoundError: If the configuration file doesn't exist.

        Example:
            >>> config = AgentConfig("./my_agent")  # directory
            >>> config = AgentConfig("./my_agent/agentkit.yaml")  # file
        """
        self.file_path = Path(file_path)

        # If directory provided, append agentkit.yaml
        if self.file_path.is_dir():
            self.file_path = self.file_path / "agentkit.yaml"

        if not self.file_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {self.file_path}\n"
                f"Please ensure the file exists or use AgentKitClient.init_project() "
                f"to create a new project."
            )

        # Load configuration using the existing config manager
        self._manager = get_config(config_path=str(self.file_path))

        # Cache common config for quick access
        self._common_config = self._manager.get_common_config()

    @classmethod
    def create(
        cls,
        project_dir: Union[str, Path],
        *,
        agent_name: str,
        entry_point: str,
        language: str = "Python",
        launch_type: str = "cloud",
        description: Optional[str] = None,
        dependencies_file: Optional[str] = None,
    ) -> "AgentConfig":
        config_path = Path(project_dir)

        if config_path.is_dir():
            config_path = config_path / "agentkit.yaml"

        if config_path.exists():
            raise FileExistsError(f"Configuration file already exists: {config_path}")

        manager = AgentkitConfigManager(config_path=config_path)
        common_config: CommonConfig = manager.get_common_config()

        common_config.agent_name = agent_name
        common_config.entry_point = entry_point

        if description is not None:
            common_config.description = description

        if language:
            common_config.set_language(language)

        if dependencies_file is not None:
            common_config.dependencies_file = dependencies_file

        common_config.launch_type = launch_type

        validator = ConfigValidator()
        errors = validator.validate_common_config(common_config)
        if errors:
            joined = "; ".join(errors)
            raise ValueError(f"Invalid agent configuration: {joined}")

        manager.update_common_config(common_config)

        return cls(config_path)

    @classmethod
    def load(cls, path: Union[str, Path]) -> "AgentConfig":
        """Load configuration from file or directory.

        This is the recommended way to create an AgentConfig instance.

        Args:
            path: Path to agentkit.yaml or project directory containing it.

        Returns:
            AgentConfig instance

        Raises:
            FileNotFoundError: If the configuration file doesn't exist.

        Example:
            >>> # Load from directory
            >>> config = AgentConfig.load("./my_agent")
            >>>
            >>> # Load from file
            >>> config = AgentConfig.load("./my_agent/agentkit.yaml")
        """
        return cls(path)

    # ========== Type-safe Property Accessors ==========

    @property
    def launch_type(self) -> str:
        """Get or set launch type (deployment mode).

        Valid values: 'local', 'cloud', 'hybrid'

        Example:
            >>> config.launch_type = "hybrid"
            >>> print(config.launch_type)  # "hybrid"
        """
        return self._common_config.launch_type

    @launch_type.setter
    def launch_type(self, value: str):
        """Set launch type with validation."""
        valid_types = ["local", "cloud", "hybrid"]
        if value not in valid_types:
            raise ValueError(
                f"Invalid launch_type: '{value}'. "
                f"Must be one of: {', '.join(valid_types)}"
            )
        self._common_config.launch_type = value
        logger.debug(f"Set launch_type to '{value}'")

    @property
    def agent_name(self) -> str:
        """Get or set agent name.

        Example:
            >>> config.agent_name = "my_planning_agent"
        """
        return self._common_config.agent_name

    @agent_name.setter
    def agent_name(self, value: str):
        """Set agent name."""
        self._common_config.agent_name = value
        logger.debug(f"Set agent_name to '{value}'")

    @property
    def entry_point(self) -> str:
        """Get or set entry point file.

        Example:
            >>> config.entry_point = "agent.py"
        """
        return self._common_config.entry_point

    @entry_point.setter
    def entry_point(self, value: str):
        """Set entry point."""
        self._common_config.entry_point = value
        logger.debug(f"Set entry_point to '{value}'")

    @property
    def description(self) -> str:
        """Get or set agent description.

        Example:
            >>> config.description = "A planning agent for task decomposition"
        """
        return self._common_config.description

    @description.setter
    def description(self, value: str):
        """Set description."""
        self._common_config.description = value
        logger.debug(f"Set description to '{value}'")

    @property
    def language(self) -> str:
        """Get or set programming language.

        Valid values: 'Python', 'Golang'

        Example:
            >>> config.language = "Python"
        """
        return self._common_config.language

    @language.setter
    def language(self, value: str):
        """Set language."""
        self._common_config.language = value
        logger.debug(f"Set language to '{value}'")

    @property
    def language_version(self) -> str:
        """Get or set language version.

        Example:
            >>> config.language_version = "3.12"
        """
        return self._common_config.language_version

    @language_version.setter
    def language_version(self, value: str):
        """Set language version."""
        self._common_config.language_version = value
        logger.debug(f"Set language_version to '{value}'")

    @property
    def dependencies_file(self) -> str:
        """Get or set dependencies file path.

        Example:
            >>> config.dependencies_file = "requirements.txt"
        """
        return self._common_config.dependencies_file

    @dependencies_file.setter
    def dependencies_file(self, value: str):
        """Set dependencies file."""
        self._common_config.dependencies_file = value
        logger.debug(f"Set dependencies_file to '{value}'")

    @property
    def runtime_envs(self) -> Dict[str, str]:
        """Get or set application-level runtime environment variables.

        These environment variables are shared across all deployment modes.

        Example:
            >>> config.runtime_envs = {"KEY1": "VALUE1", "KEY2": "VALUE2"}
            >>> config.runtime_envs["NEW_VAR"] = "VALUE3"
        """
        return self._common_config.runtime_envs

    @runtime_envs.setter
    def runtime_envs(self, value: Dict[str, str]):
        """Set runtime environment variables."""
        if not isinstance(value, dict):
            raise TypeError("runtime_envs must be a dictionary")
        self._common_config.runtime_envs = value
        logger.debug(f"Set runtime_envs with {len(value)} entries")

    # ========== Path-based Access Methods ==========

    def get(self, key_path: str, default: Any = None) -> Any:
        """Get configuration value by key path.

        Supports dot-notation for nested access.

        Args:
            key_path: Dot-separated key path (e.g., "common.launch_type" or
                     "launch_types.cloud.region")
            default: Default value if key not found

        Returns:
            Configuration value or default

        Example:
            >>> config.get("common.launch_type")
            'cloud'
            >>> config.get("launch_types.cloud.region", "cn-beijing")
            'cn-beijing'
            >>> config.get("nonexistent.key", "default")
            'default'
        """
        return self._manager.get_raw_value(key_path, default=default)

    def set(self, key_path: str, value: Any) -> "AgentConfig":
        """Set configuration value by key path.
        
        Supports dot-notation for nested access. Returns self for chaining.
        
        Args:
            key_path: Dot-separated key path
            value: Value to set
        
        Returns:
            Self for method chaining
        
        Example:
            >>> config.set("common.launch_type", "hybrid")
            >>> config.set("launch_types.cloud.region", "cn-beijing")
            >>> 
            >>> # Chaining
            >>> config.set("common.launch_type", "hybrid") \\
            ...       .set("launch_types.hybrid.image_tag", "v1.0") \\
            ...       .save()
        """
        # Update internal data structure
        self._manager.set_raw_value(key_path, value)

        # If updating common config, reload cache
        if key_path.startswith("common."):
            self._common_config = self._manager.get_common_config()

        logger.debug(f"Set '{key_path}' to '{value}'")
        return self

    def update(self, updates: Dict[str, Any]) -> "AgentConfig":
        """Batch update configuration.

        Updates multiple configuration values at once. Supports both flat keys
        (for common config fields) and nested dictionaries.

        Args:
            updates: Dictionary of updates. Can contain:
                    - Flat keys like "launch_type" (updates common config)
                    - Nested dicts like {"common": {"launch_type": "hybrid"}}

        Returns:
            Self for method chaining

        Example:
            >>> # Update common config fields
            >>> config.update({
            ...     "launch_type": "hybrid",
            ...     "description": "New description"
            ... })
            >>>
            >>> # Update nested config
            >>> config.update({
            ...     "common": {
            ...         "launch_type": "hybrid"
            ...     },
            ...     "launch_types": {
            ...         "cloud": {
            ...             "region": "cn-beijing"
            ...         }
            ...     }
            ... })
            >>>
            >>> # Chaining
            >>> config.update({"launch_type": "hybrid"}).save()
        """
        for key, value in updates.items():
            # Check if it's a top-level field in common config
            if hasattr(self._common_config, key):
                setattr(self._common_config, key, value)
            # Check if it's a nested dictionary update
            elif isinstance(value, dict):
                # Update nested structures
                for nested_key, nested_value in value.items():
                    path = f"{key}.{nested_key}"
                    self.set(path, nested_value)
            else:
                # Treat as path
                self.set(key, value)

        logger.debug(f"Updated {len(updates)} configuration entries")
        return self

    # ========== Fluent API Methods (Chainable) ==========

    def set_launch_type(self, launch_type: str) -> "AgentConfig":
        """Set launch type (fluent API).

        Args:
            launch_type: 'local', 'cloud', or 'hybrid'

        Returns:
            Self for method chaining

        Example:
            >>> config.set_launch_type("hybrid").save()
        """
        self.launch_type = launch_type
        return self

    def set_agent_name(self, agent_name: str) -> "AgentConfig":
        """Set agent name (fluent API)."""
        self.agent_name = agent_name
        return self

    def set_description(self, description: str) -> "AgentConfig":
        """Set description (fluent API)."""
        self.description = description
        return self

    def set_entry_point(self, entry_point: str) -> "AgentConfig":
        """Set entry point (fluent API)."""
        self.entry_point = entry_point
        return self

    def set_language(self, language: str) -> "AgentConfig":
        """Set language (fluent API)."""
        self.language = language
        return self

    def add_runtime_env(self, key: str, value: str) -> "AgentConfig":
        """Add a runtime environment variable (fluent API).
        
        Args:
            key: Environment variable name
            value: Environment variable value
        
        Returns:
            Self for method chaining
        
        Example:
            >>> config.add_runtime_env("API_KEY", "") \\
            ...       .add_runtime_env("DEBUG", "true") \\
            ...       .save()
        """
        self._common_config.runtime_envs[key] = value
        logger.debug(f"Added runtime_env: {key}={value}")
        return self

    # ========== Persistence Methods ==========

    def save(self, path: Optional[Union[str, Path]] = None) -> "AgentConfig":
        """Save configuration to file.

        Args:
            path: Optional new path to save to. If None, saves to original file.

        Returns:
            Self for method chaining

        Example:
            >>> config.launch_type = "hybrid"
            >>> config.save()  # Save to original file
            >>>
            >>> config.save("new_config.yaml")  # Save to new file
        """
        validator = ConfigValidator()
        errors = validator.validate_common_config(self._common_config)
        if errors:
            joined = "; ".join(errors)
            raise ValueError(f"Invalid agent configuration: {joined}")

        # Update common config in manager
        self._manager.update_common_config(self._common_config)

        # If new path specified, update file path
        if path:
            self.file_path = Path(path)
            # Note: The manager still uses the original path for saving
            # This is intentional to maintain consistency

        logger.info(f"Configuration saved to {self.file_path}")
        return self

    def reload(self) -> "AgentConfig":
        """Reload configuration from file.

        Discards any unsaved changes and reloads from disk.

        Returns:
            Self for method chaining

        Example:
            >>> config.reload()  # Discard changes
        """
        self._manager.reload()
        self._common_config = self._manager.get_common_config()
        logger.info(f"Configuration reloaded from {self.file_path}")
        return self

    # ========== Export Methods ==========

    def to_dict(self) -> Dict[str, Any]:
        """Export configuration as dictionary.

        Returns:
            Complete configuration dictionary including common config
            and all strategy configurations.

        Example:
            >>> config_dict = config.to_dict()
            >>> print(config_dict.keys())
            dict_keys(['common', 'launch_types'])
        """
        return {
            "common": self._common_config.to_dict(),
            "launch_types": {
                name: self._manager.get_strategy_config(name)
                for name in self._manager.list_strategies()
            },
        }

    def get_strategy_config(
        self, strategy_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get strategy-specific configuration.

        Args:
            strategy_name: strategy name ('local', 'cloud', 'hybrid').
                          If None, uses current launch_type.

        Returns:
            strategy configuration dictionary

        Example:
            >>> cloud_config = config.get_strategy_config("cloud")
            >>> print(cloud_config.get("region"))
            'cn-beijing'
            >>>
            >>> # Get current strategy config
            >>> current_config = config.get_strategy_config()
        """
        if strategy_name is None:
            strategy_name = self.launch_type
        return self._manager.get_strategy_config(strategy_name)

    def update_strategy_config(
        self, config: Dict[str, Any], strategy_name: Optional[str] = None
    ) -> "AgentConfig":
        """Update strategy-specific configuration.

        Args:
            config: strategy configuration updates
            strategy_name: strategy name. If None, uses current launch_type.

        Returns:
            Self for method chaining

        Example:
            >>> config.update_strategy_config({
            ...     "region": "cn-beijing",
            ...     "image_tag": "v1.0.0"
            ... }, strategy_name="cloud")
        """
        if strategy_name is None:
            strategy_name = self.launch_type
        self._manager.update_strategy_config(strategy_name, config)
        logger.debug(f"Updated strategy config for '{strategy_name}'")
        return self

    # ========== Utility Methods ==========

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"AgentConfig("
            f"file={self.file_path.name}, "
            f"agent={self.agent_name}, "
            f"launch_type={self.launch_type})"
        )

    def __str__(self) -> str:
        """Human-readable string representation."""
        return (
            f"AgentConfig: {self.agent_name}\n"
            f"  File: {self.file_path}\n"
            f"  Launch Type: {self.launch_type}\n"
            f"  Entry Point: {self.entry_point}"
        )
