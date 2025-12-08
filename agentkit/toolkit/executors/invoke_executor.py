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

"""Invoke Executor - Executes invoke operations on deployed agents.

This module provides unified orchestration for agent invocation across different
deployment platforms (Local, Cloud, Hybrid). It follows the Strategy pattern to
abstract platform-specific invocation logic.

Key Responsibilities:
1. Load and validate configuration from multiple sources
2. Select appropriate Strategy based on launch_type
3. Execute invocation (call Strategy.invoke())
4. Unified error handling and classification
5. Structured logging for debugging and monitoring

Design Principle:
- Immutability: Configuration is loaded once and passed through the chain
- Separation of Concerns: Strategy handles platform-specific logic, Executor handles orchestration
- Reporter Injection: Progress reporting flows through Strategy → Runner

What This Executor Does NOT Do:
- Result transformation (Strategy returns InvokeResult directly)
- User-facing error messages (CLI layer handles this)
- Progress reporting (handled by Runner via Reporter)
"""

from typing import Optional, Dict, Any
from agentkit.toolkit.models import InvokeResult
from agentkit.toolkit.reporter import Reporter
from .base_executor import BaseExecutor


class InvokeExecutor(BaseExecutor):
    """Orchestrates agent invocation across different deployment platforms.

    This executor provides a unified interface for invoking agents regardless of their
    deployment platform. It handles configuration loading, strategy selection, and
    error handling while delegating platform-specific invocation logic to the Strategy.

    Inherited Capabilities (from BaseExecutor):
    - Configuration loading with priority: config_dict > config_file > default
    - Strategy selection based on launch_type
    - Strongly configuration object retrieval with type safety
    - Unified error classification and handling
    - Structured logging with context
    """

    def __init__(self, reporter: Reporter = None):
        """Initialize InvokeExecutor.

        Args:
            reporter: Reporter instance for progress reporting. Passed through
                Strategy → Runner chain for unified progress tracking.
        """
        super().__init__(reporter)

    def execute(
        self,
        payload: Dict[str, Any],
        config_dict: Optional[Dict[str, Any]] = None,
        config_file: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        stream: Optional[bool] = None,
    ) -> InvokeResult:
        """Execute an invoke operation on a deployed agent.

        Orchestrates the complete invocation strategy:
        1. Load configuration from multiple sources (priority: config_dict > config_file > default)
        2. Extract common configuration and determine launch_type
        3. Select appropriate Strategy based on launch_type
        4. Retrieve strongly-typed strategy configuration object
        5. Execute invocation through Strategy.invoke()
        6. Log results and return InvokeResult directly

        Args:
            payload: Request payload containing agent input data
            config_dict: Configuration dictionary (highest priority). Overrides config_file.
            config_file: Path to configuration file. Used if config_dict is not provided.
            headers: Optional HTTP headers for the invocation request
            stream: Optional flag to enable streaming response

        Returns:
            InvokeResult: Invocation result returned directly from Strategy without transformation.
                Contains success flag, response data, error information, and streaming status.

        Raises:
            ConfigurationError: If configuration is invalid or missing required fields
            StrategyError: If strategy selection or execution fails
            Exception: Other exceptions are caught and converted to InvokeResult with error info
        """
        try:
            self.logger.info("Loading configuration...")
            config = self._load_config(config_dict, config_file)

            common_config = config.get_common_config()
            launch_type = common_config.launch_type
            self.logger.info(f"Invoke strategy selected: {launch_type}")

            # Select strategy with reporter injection for progress tracking
            strategy = self._get_strategy(launch_type, config_manager=config)

            strategy_config = self._get_strategy_config_object(config, launch_type)

            self.logger.info(f"Starting invocation with {launch_type} strategy...")
            result = strategy.invoke(
                common_config=common_config,
                strategy_config=strategy_config,
                payload=payload,
                headers=headers,
                stream=stream,
            )

            if result.success:
                if result.is_streaming:
                    self.logger.info("Invocation completed successfully (streaming)")
                else:
                    self.logger.info("Invocation completed successfully")
            else:
                # Log error details for debugging; CLI layer handles user-facing messages
                # to avoid duplication and ensure consistent error presentation
                self.logger.error(
                    f"Invocation failed: {result.error} (code: {result.error_code})"
                )

            return result

        except Exception as e:
            # Log exception for debugging; CLI layer handles user-facing error messages
            # to maintain separation of concerns and avoid duplicate error reporting
            self.logger.exception(f"Invocation execution error: {e}")

            error_info = self._handle_exception("Invoke", e)
            return InvokeResult(**error_info)
