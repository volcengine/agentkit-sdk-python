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

"""
Base Executor - Unified configuration loading, error handling, and strategy selection.

Responsibilities:
1. Configuration loading and validation
2. Strategy selection and instantiation
3. Reporter injection for progress reporting
4. Unified error handling and logging
5. Configuration persistence for deployment metadata

Design Principle:
- Strategies are immutable: they do not modify input configuration
- Strategies return ConfigUpdates suggestions; Executor applies and persists them
- This separation ensures clean layering and testability

NOT Responsible For:
- Result transformation (Strategies return standard Result objects directly)
- Progress reporting (handled by Strategy → Builder/Runner chain)
"""

import logging
from typing import Optional, Dict, Any
from pathlib import Path
from agentkit.toolkit.reporter import Reporter, SilentReporter


class BaseExecutor:
    """
    Base class for all executors providing unified configuration and error handling.
    
    All Executor subclasses inherit:
    - Configuration loading from file or dict with priority handling
    - Configuration validation for required fields
    - Strategy selection based on launch_type
    - Reporter injection for progress tracking
    - Unified error handling and classification
    - Configuration persistence for deployment metadata
    """
    
    def __init__(self, reporter: Reporter = None):
        """
        Initialize the executor with optional reporter for progress tracking.
        
        Args:
            reporter: Reporter instance for progress reporting. If None, uses SilentReporter.
                     This reporter is passed through to Strategy → Builder/Runner chain.
        """
        self.reporter = reporter or SilentReporter()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def _load_config(self, config_dict: Optional[Dict[str, Any]], config_file: Optional[str]):
        """
        Load configuration with priority: config_dict > config_file > default.
        
        Priority Logic:
        1. If config_dict is provided:
           - If config_file also provided: merge mode (config_file as base, config_dict overrides)
           - Otherwise: pure dict mode
        2. If only config_file provided: load from file
        3. Otherwise: load default configuration
        
        Args:
            config_dict: Configuration dictionary to apply (highest priority)
            config_file: Path to configuration file (medium priority)
            
        Returns:
            Configuration object (AgentkitConfigManager)
            
        Raises:
            FileNotFoundError: Configuration file does not exist
            ValueError: Configuration is invalid
        """
        from agentkit.toolkit.config import get_config, AgentkitConfigManager
        
        if config_dict:
            if config_file:
                config_path = Path(config_file)
                if not config_path.exists():
                    raise FileNotFoundError(f"Configuration file not found: {config_file}")
                self.logger.debug(f"Creating config from dict with base file: {config_file}")
                return AgentkitConfigManager.from_dict(
                    config_dict=config_dict,
                    base_config_path=config_path
                )
            else:
                self.logger.debug("Creating config from dict (no base file)")
                return AgentkitConfigManager.from_dict(config_dict=config_dict)
        
        if config_file:
            config_path = Path(config_file)
            if not config_path.exists():
                raise FileNotFoundError(f"Configuration file not found: {config_file}")
            return get_config(config_path=config_path)
        else:
            return get_config()
    
    def _validate_config(self, config) -> None:
        """
        Validate that configuration has all required fields.
        
        Args:
            config: Configuration object
            
        Raises:
            ValueError: Configuration is missing required fields
        """
        common_config = config.get_common_config()
        
        if not common_config.agent_name:
            raise ValueError("Configuration missing required field: agent_name")
        
        if not common_config.entry_point:
            raise ValueError("Configuration missing required field: entry_point")
        
        if not common_config.launch_type:
            raise ValueError("Configuration missing required field: launch_type")
        
        self.logger.debug(f"Configuration validated: agent={common_config.agent_name}, "
                         f"launch_type={common_config.launch_type}")
    
    def _get_strategy(self, launch_type: str, config_manager=None):
        """
        Get strategy instance for the specified launch type.
        
        Args:
            launch_type: Launch type (local/cloud/hybrid)
            config_manager: Configuration manager instance (optional)
            
        Returns:
            Strategy instance with reporter already injected
            
        Raises:
            ValueError: Unknown launch_type
        """
        from agentkit.toolkit.strategies import LocalStrategy, CloudStrategy, HybridStrategy
        
        strategy_map = {
            'local': LocalStrategy,
            'cloud': CloudStrategy,
            'hybrid': HybridStrategy,
        }
        
        strategy_class = strategy_map.get(launch_type)
        if not strategy_class:
            available = ", ".join(strategy_map.keys())
            raise ValueError(
                f"Unknown launch_type '{launch_type}'. "
                f"Available strategies: {available}"
            )
        
        # Inject reporter and config_manager into strategy
        # Reporter is passed through to Builder/Runner for progress tracking
        return strategy_class(
            config_manager=config_manager,
            reporter=self.reporter
        )
    
    def _classify_error(self, error: Exception) -> str:
        """
        Classify exception type into error code for Result object.
        
        Args:
            error: Exception instance
            
        Returns:
            Error code string (e.g., FILE_NOT_FOUND, INVALID_CONFIG)
        """
        if isinstance(error, FileNotFoundError):
            return "FILE_NOT_FOUND"
        elif isinstance(error, ValueError):
            return "INVALID_CONFIG"
        elif isinstance(error, PermissionError):
            return "PERMISSION_DENIED"
        elif isinstance(error, TimeoutError):
            return "TIMEOUT"
        elif isinstance(error, ImportError):
            return "DEPENDENCY_MISSING"
        else:
            return "UNKNOWN_ERROR"
    
    def _handle_exception(self, operation: str, error: Exception) -> Dict[str, Any]:
        """
        Unified exception handling for all operations.
        
        Logs the full exception with traceback and returns a structured error dict
        for Result object construction. Error messages are user-friendly.
        
        Args:
            operation: Operation name (e.g., 'build', 'deploy', 'destroy')
            error: Exception instance
            
        Returns:
            Dictionary with success=False, error message, and error code
        """
        self.logger.error(f"{operation} error: {error}", exc_info=True)
        
        # Provide user-friendly error messages
        error_message = str(error)
        if isinstance(error, FileNotFoundError):
            error_message = f"File not found: {error}"
        elif isinstance(error, ValueError):
            error_message = f"Invalid configuration: {error}"
        elif isinstance(error, PermissionError):
            error_message = f"Permission denied: {error}"
        elif isinstance(error, TimeoutError):
            error_message = f"Operation timeout: {error}"
        elif isinstance(error, ImportError):
            error_message = f"Missing dependency: {error}"
        
        return {
            "success": False,
            "error": error_message,
            "error_code": self._classify_error(error)
        }
    
    def _get_strategy_config_object(self, config, launch_type: str, skip_render: bool = False):
        """
        Get strongly-typed strategy configuration object for the launch type.
        
        Args:
            config: Configuration manager (AgentkitConfigManager)
            launch_type: Strategy type (local/cloud/hybrid)
            skip_render: Skip template rendering for read-only operations (improves performance).
                        Use for status checks and other operations that don't modify config.
            
        Returns:
            Typed configuration object: LocalDockerConfig | VeAgentkitConfig | HybridVeAgentkitConfig
        """
        strategy_config_dict = config.get_strategy_config(launch_type)
        
        if launch_type == "local":
            from agentkit.toolkit.config import LocalStrategyConfig
            return LocalStrategyConfig.from_dict(strategy_config_dict, skip_render=skip_render)
        elif launch_type == "cloud":
            from agentkit.toolkit.config import CloudStrategyConfig
            return CloudStrategyConfig.from_dict(strategy_config_dict, skip_render=skip_render)
        elif launch_type == "hybrid":
            from agentkit.toolkit.config import HybridStrategyConfig
            return HybridStrategyConfig.from_dict(strategy_config_dict, skip_render=skip_render)
        else:
            raise ValueError(f"Unknown launch_type: {launch_type}")
    
    def _clear_deploy_config(self, config, launch_type: str):
        """
        Clear deployment-related configuration after successful destroy operation.
        
        Removes deployment metadata (endpoint, runtime_id, etc.) so the agent
        can be deployed again from scratch. This is called after destroy succeeds.
        
        Args:
            config: Configuration manager (AgentkitConfigManager)
            launch_type: Strategy type (local/cloud/hybrid)
        """
        from agentkit.toolkit.config import AUTO_CREATE_VE
        
        strategy_config = config.get_strategy_config(launch_type)
        
        # Clear common deployment metadata
        strategy_config['deploy_timestamp'] = ""
        
        # Clear launch-type-specific deployment state
        if launch_type == "local":
            strategy_config['container_id'] = ""
            strategy_config['container_name'] = ""
            strategy_config['endpoint'] = ""
        elif launch_type in ["cloud", "hybrid"]:
            strategy_config['runtime_id'] = ""
            strategy_config['runtime_name'] = AUTO_CREATE_VE
            strategy_config['runtime_endpoint'] = ""
            strategy_config['runtime_apikey'] = ""
            strategy_config['runtime_apikey_name'] = AUTO_CREATE_VE
            strategy_config['runtime_role_name'] = AUTO_CREATE_VE
        
        config.update_strategy_config(launch_type, strategy_config)
        self.logger.debug(f"Cleared deploy config for {launch_type}")
    
    def _apply_config_updates(self, config, launch_type: str, config_updates):
        """
        Apply and persist configuration updates from strategy execution.
        
        Design Pattern:
        - Strategies are immutable: they do not modify input configuration
        - Strategies return ConfigUpdates suggestions (e.g., generated endpoint, runtime_id)
        - Executor applies updates and persists them to configuration file
        - This ensures clean separation: Strategy computes, Executor persists
        
        Args:
            config: Configuration manager (AgentkitConfigManager)
            launch_type: Strategy type (local/cloud/hybrid)
            config_updates: ConfigUpdates object with suggested changes
            
        Example:
            ```python
            # In Strategy
            config_updates = ConfigUpdates()
            config_updates.add('runtime_name', 'generated-name')
            result.config_updates = config_updates
            
            # In Executor
            result = strategy.build(...)
            if result.config_updates:
                self._apply_config_updates(config, launch_type, result.config_updates)
            ```
        """
        from agentkit.toolkit.models import ConfigUpdates
        
        if not config_updates:
            return
        
        if not isinstance(config_updates, ConfigUpdates):
            self.logger.warning(f"Expected ConfigUpdates, got {type(config_updates)}")
            return
        
        if not config_updates.has_updates():
            return
        
        # Get typed configuration object for this launch type
        strategy_config_obj = self._get_strategy_config_object(config, launch_type)
        
        # Apply updates to configuration object
        updates_dict = config_updates.to_dict()
        for key, value in updates_dict.items():
            if hasattr(strategy_config_obj, key):
                setattr(strategy_config_obj, key, value)
            else:
                self.logger.warning(f"Config field '{key}' not found in {type(strategy_config_obj).__name__}")
        
        # Persist to configuration file using to_persist_dict()
        # This automatically preserves template values for fields not in updates
        config.update_strategy_config(launch_type, strategy_config_obj.to_persist_dict())
        
        # Log the updates
        updated_keys = list(updates_dict.keys())
        self.logger.info(f"Applied {len(updated_keys)} config updates: {updated_keys}")
        self.logger.debug(f"Config updates detail: {updates_dict}")
