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
Deploy Executor - Handles deployment operations

Responsibilities:
1. Load and validate configuration
2. Select appropriate Strategy based on launch_type
3. Execute deployment (invoke Strategy.deploy())
4. Apply configuration updates from deployment results
5. Unified error handling and logging

Does NOT:
- Result transformation (Strategy returns DeployResult directly)
- Progress reporting (handled by Strategy → Runner via Reporter)
"""

from typing import Optional, Dict, Any
from agentkit.toolkit.models import DeployResult, PreflightMode
from agentkit.toolkit.reporter import Reporter
from .base_executor import BaseExecutor


class DeployExecutor(BaseExecutor):
    """
    Executor for deployment operations.

    Orchestrates the deployment strategy:
    1. Loads and validates configuration
    2. Selects appropriate Strategy based on launch_type
    3. Executes deployment via Strategy.deploy()
    4. Applies configuration updates from deployment results
    5. Provides unified error handling and logging

    The Reporter is passed through to Strategy → Runner to enable
    progress reporting during deployment.
    """

    def __init__(self, reporter: Reporter = None):
        """
        Initialize DeployExecutor.

        Args:
            reporter: Reporter instance for progress reporting (passed to Strategy)
        """
        super().__init__(reporter)

    def execute(
        self,
        config_dict: Optional[Dict[str, Any]] = None,
        config_file: Optional[str] = None,
        preflight_mode: PreflightMode = PreflightMode.PROMPT,
    ) -> DeployResult:
        """
        Execute deployment operation.

        Strategy:
        1. Load and validate configuration (priority: config_dict > config_file > default)
        2. Preflight check: verify required cloud services are enabled
        3. Extract launch_type from common config
        4. Instantiate appropriate Strategy with Reporter injection
        5. Execute deployment via Strategy.deploy()
        6. Apply any configuration updates returned by Strategy
        7. Return deployment result

        Args:
            config_dict: Configuration dictionary (highest priority)
            config_file: Path to configuration file
            preflight_mode: How to handle missing cloud services (default: PROMPT)

        Returns:
            DeployResult: Deployment result from Strategy (no transformation applied)

        Raises:
            FileNotFoundError: Configuration file not found
            ValueError: Configuration validation failed
            Exception: Any exception during deployment is caught and returned as failed result
        """
        try:
            # Override preflight_mode from global config defaults if configured
            try:
                from agentkit.toolkit.config.global_config import get_global_config

                gc = get_global_config()
                gm = getattr(getattr(gc, "defaults", None), "preflight_mode", None)
                if gm:
                    gm_map = {
                        "prompt": PreflightMode.PROMPT,
                        "fail": PreflightMode.FAIL,
                        "warn": PreflightMode.WARN,
                        "skip": PreflightMode.SKIP,
                    }
                    preflight_mode = gm_map.get(gm.lower(), preflight_mode)
            except Exception:
                pass
            self.logger.info("Loading configuration...")
            config = self._load_config(config_dict, config_file)
            self._validate_config(config)

            common_config = config.get_common_config()
            launch_type = common_config.launch_type
            self.logger.info(f"Deployment strategy selected: {launch_type}")

            # Preflight check: verify required cloud services are enabled
            if preflight_mode != PreflightMode.SKIP:
                region = self._resolve_account_region(config, launch_type)
                preflight_result = self._preflight_check(
                    "deploy", launch_type, region=region
                )
                if not self._handle_preflight_result(preflight_result, preflight_mode):
                    return DeployResult(
                        success=False,
                        error="Deployment aborted: required services not enabled",
                        error_code="PREFLIGHT_ABORTED",
                    )

            strategy = self._get_strategy(launch_type, config_manager=config)
            strategy_config = self._get_strategy_config_object(config, launch_type)

            self.logger.info(f"Starting deployment with {launch_type} strategy...")
            result = strategy.deploy(common_config, strategy_config)

            # Apply configuration updates returned by Strategy (e.g., generated endpoint, runtime_id)
            # This ensures deployment metadata is persisted for future operations
            if result.success and result.config_updates:
                self._apply_config_updates(config, launch_type, result.config_updates)

            if result.success:
                self.reporter.success("Deployment completed successfully")
                if result.endpoint_url:
                    self.logger.info(f"Deployment endpoint: {result.endpoint_url}")
            else:
                # Log error details; CLI layer handles user-facing error messages
                self.logger.error(
                    f"Deployment failed: {result.error} (code: {result.error_code})"
                )

            return result

        except Exception as e:
            # Catch all exceptions and return as failed DeployResult
            # CLI layer handles user-facing error messages to avoid duplication
            self.logger.exception(f"Deployment execution error: {e}")
            error_info = self._handle_exception("Deploy", e)
            return DeployResult(**error_info)
