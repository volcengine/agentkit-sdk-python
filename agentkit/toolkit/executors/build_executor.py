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
Build Executor - Unified build operation execution with configuration management and error handling.

Responsibilities:
1. Configuration loading and validation
2. Strategy selection based on launch_type
3. Build execution via Strategy.build()
4. Unified error handling and logging
5. Configuration persistence for build metadata

Design Principle:
- Strategies are immutable: they do not modify input configuration
- Strategies return ConfigUpdates suggestions; Executor applies and persists them
- This separation ensures clean layering and testability

NOT Responsible For:
- Result transformation (Strategies return BuildResult directly)
- Progress reporting (handled by Strategy → Builder chain)
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from agentkit.toolkit.models import BuildResult, PreflightMode
from agentkit.toolkit.reporter import Reporter
from .base_executor import BaseExecutor


@dataclass
class BuildOptions:
    """
    Runtime options for build execution (from CLI, not persisted to config file).

    These options control single-run build behavior, separate from persistent configuration.
    """

    platform: Optional[str] = None
    """Target CPU architecture platform (e.g., linux/amd64, linux/arm64) passed to Docker build"""

    regenerate_dockerfile: bool = False
    """Force regenerate Dockerfile even if it already exists"""


class BuildExecutor(BaseExecutor):
    """
    Build executor orchestrating the build strategy.

    All Executor subclasses inherit:
    - Configuration loading from file or dict with priority handling
    - Configuration validation for required fields
    - Strategy selection based on launch_type
    - Reporter injection for progress tracking
    - Unified error handling and classification
    - Configuration persistence for build metadata
    """

    def __init__(self, reporter: Reporter = None):
        """
        Initialize the executor with optional reporter for progress tracking.

        Args:
            reporter: Reporter instance for progress reporting. If None, uses SilentReporter.
                     This reporter is passed through to Strategy → Builder chain.
        """
        super().__init__(reporter)

    def execute(
        self,
        config_dict: Optional[Dict[str, Any]] = None,
        config_file: Optional[str] = None,
        options: Optional[BuildOptions] = None,
        preflight_mode: PreflightMode = PreflightMode.PROMPT,
    ) -> BuildResult:
        """
        Execute the build operation with unified configuration and error handling.

        Strategy:
        1. Load and validate configuration (priority: config_dict > config_file > default)
        2. Preflight check: verify required cloud services are enabled
        3. Apply runtime options to configuration (not persisted)
        4. Select strategy based on launch_type
        5. Get strongly-typed strategy configuration
        6. Execute build via strategy
        7. Apply and persist configuration updates from build result
        8. Log results and return BuildResult

        Args:
            config_dict: Configuration dictionary (highest priority, overrides config_file)
            config_file: Path to configuration file (medium priority)
            options: Build runtime options (CLI parameters, not persisted)
            preflight_mode: How to handle missing cloud services (default: PROMPT)

        Returns:
            BuildResult: Build result returned directly from Strategy without transformation

        Raises:
            FileNotFoundError: Configuration file does not exist
            ValueError: Configuration is invalid
            Exception: Any exception during build is caught and converted to BuildResult
        """
        if options is None:
            options = BuildOptions()
        try:
            self.logger.info("Loading configuration...")
            config = self._load_config(config_dict, config_file)
            self._validate_config(config)

            # Apply runtime options to configuration (not persisted to file)
            if options.regenerate_dockerfile:
                self.logger.debug("Runtime option: regenerate_dockerfile=True")
                config.set_docker_build_runtime_param("regenerate_dockerfile", True)

            if options.platform:
                self.logger.debug(f"Runtime option: platform={options.platform}")
                config.set_docker_build_runtime_param("platform", options.platform)

            common_config = config.get_common_config()
            launch_type = common_config.launch_type
            self.logger.info(f"Build strategy selected: {launch_type}")

            # Preflight check: verify required cloud services are enabled
            if preflight_mode != PreflightMode.SKIP:
                region = self._resolve_account_region(config, launch_type)
                preflight_result = self._preflight_check(
                    "build", launch_type, region=region
                )
                if not self._handle_preflight_result(preflight_result, preflight_mode):
                    return BuildResult(
                        success=False,
                        error="Build aborted: required services not enabled",
                        error_code="PREFLIGHT_ABORTED",
                    )

            strategy = self._get_strategy(launch_type, config_manager=config)
            strategy_config = self._get_strategy_config_object(config, launch_type)

            self.logger.info(f"Starting build with {launch_type} strategy...")
            result = strategy.build(common_config, strategy_config)

            # Apply configuration updates from build result
            # This persists build metadata (e.g., generated image name, build timestamp)
            if result.success and result.config_updates:
                self._apply_config_updates(config, launch_type, result.config_updates)

            if result.success:
                if result.image:
                    self.logger.info(
                        f"Build completed successfully: {result.image.full_name}"
                    )
                else:
                    self.logger.info("Build completed successfully")
            else:
                self.logger.error(
                    f"Build failed: {result.error} (code: {result.error_code})"
                )

            return result

        except Exception as e:
            self.logger.exception(f"Build execution error: {e}")
            error_info = self._handle_exception("Build", e)
            return BuildResult(**error_info)
