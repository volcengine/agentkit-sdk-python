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

"""Status Executor - Unified orchestration for status query operations.

This module provides a unified interface for querying deployment status across different
launch types (Local, Cloud, Hybrid). It handles configuration loading, strategy selection,
and error handling in a consistent manner.

Key Responsibilities:
1. Load and validate configuration from dict or file
2. Select appropriate Strategy based on launch_type
3. Execute status query via Strategy.status()
4. Unified error handling and classification
5. Structured logging with context

Design Principles:
- Immutability: Configuration is loaded once and passed through the chain
- Separation of Concerns: Each component has a single responsibility
- Reporter Injection: Progress tracking flows through Strategy → Runner chain
"""

from typing import Optional, Dict, Any
from agentkit.toolkit.models import StatusResult
from agentkit.toolkit.reporter import Reporter
from .base_executor import BaseExecutor


class StatusExecutor(BaseExecutor):
    """Orchestrates status query operations across deployment platforms.

    Inherits from BaseExecutor and provides unified status query execution:
    - Configuration loading with priority: config_dict > config_file > default
    - Strategy selection based on launch_type
    - Unified error handling and exception classification
    - Structured logging with context information
    - Reporter injection for progress tracking

    The executor does NOT:
    - Transform results (Strategy returns StatusResult directly)
    - Handle user-facing error messages (delegated to CLI layer)
    """

    def __init__(self, reporter: Reporter = None):
        """Initialize StatusExecutor.

        Args:
            reporter: Reporter instance for progress tracking. Flows through
                     Strategy → Runner chain for unified progress reporting.
        """
        super().__init__(reporter)

    def execute(
        self,
        config_dict: Optional[Dict[str, Any]] = None,
        config_file: Optional[str] = None,
    ) -> StatusResult:
        """Execute status query operation.

        Steps:
        1. Load and validate configuration (priority: config_dict > config_file > default)
        2. Extract common configuration and launch_type
        3. Select appropriate Strategy based on launch_type
        4. Retrieve strategy configuration object (read-only, skip template rendering)
        5. Execute status query via Strategy.status()
        6. Return result directly without transformation

        Args:
            config_dict: Configuration dictionary (highest priority)
            config_file: Path to configuration file

        Returns:
            StatusResult: Status query result from Strategy (no transformation)

        Raises:
            ConfigurationError: If configuration is invalid or missing required fields
            StrategyError: If strategy selection or execution fails
            Exception: Other execution errors are caught and converted to StatusResult
        """
        try:
            self.logger.info("Loading configuration...")
            config = self._load_config(config_dict, config_file)

            common_config = config.get_common_config()
            launch_type = common_config.launch_type
            self.logger.info(f"Status strategy selected: {launch_type}")

            # Inject reporter into strategy for progress tracking through Strategy → Runner chain
            strategy = self._get_strategy(launch_type, config_manager=config)

            # Status is a read-only operation; skip template rendering for performance
            strategy_config = self._get_strategy_config_object(
                config, launch_type, skip_render=True
            )

            self.logger.info(f"Starting status query with {launch_type} strategy...")
            result = strategy.status(common_config, strategy_config)

            if result.success:
                self.logger.info(f"Status query completed: {result.status}")
            else:
                self.logger.error(
                    f"Status query failed: {result.error} (code: {result.error_code})"
                )

            return result

        except Exception as e:
            # Log the error but don't output user-facing messages here.
            # The CLI layer handles user-facing error messages to avoid duplication.
            self.logger.exception(f"Status query execution error: {e}")

            error_info = self._handle_exception("Status query", e)
            return StatusResult(**error_info)
