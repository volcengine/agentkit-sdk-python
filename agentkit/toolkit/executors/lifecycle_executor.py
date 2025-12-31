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
Lifecycle Executor - Manages the complete lifecycle of Agent services.

Combines Build + Deploy operations to provide launch, stop, and destroy functionality.
Each operation is a composition of lower-level executors (BuildExecutor, DeployExecutor, StatusExecutor).
"""

from typing import Optional, Dict, Any, Union, List
from pathlib import Path

from .base_executor import BaseExecutor
from .build_executor import BuildExecutor, BuildOptions
from .deploy_executor import DeployExecutor
from .status_executor import StatusExecutor
from agentkit.toolkit.models import LifecycleResult, PreflightMode, PreflightResult
from agentkit.toolkit.reporter import Reporter


class LifecycleExecutor(BaseExecutor):
    """
    Lifecycle management executor that orchestrates multiple operations.

    Composite operations:
    - launch: Build image and deploy service in one step
    - stop: Stop a running service without removing resources
    - destroy: Stop service and clean up all associated resources
    """

    def __init__(self, reporter: Reporter = None):
        """
        Initialize LifecycleExecutor.

        Args:
            reporter: Reporter instance for progress reporting
        """
        super().__init__(reporter)

        # Reuse other executors, all sharing the same reporter for consistent output
        self.build_executor = BuildExecutor(reporter=self.reporter)
        self.deploy_executor = DeployExecutor(reporter=self.reporter)
        self.status_executor = StatusExecutor(reporter=self.reporter)

    def _combined_preflight_check(
        self,
        launch_type: str,
        operations: List[str],
        region: Optional[str] = None,
    ) -> PreflightResult:
        """
        Perform combined preflight check for multiple operations.

        Combines required services from multiple operations and checks them all at once.
        This is more efficient than checking each operation separately.

        Args:
            launch_type: Launch type (local/cloud/hybrid)
            operations: List of operation names to check (e.g., ['build', 'deploy'])
            region: Optional region override for the check

        Returns:
            PreflightResult with all missing services combined
        """
        strategy_class = self._get_strategy_class(launch_type)

        # Combine required services from all operations
        all_required = set()
        for operation in operations:
            all_required.update(strategy_class.get_required_services(operation))

        if not all_required:
            self.logger.debug(
                f"No required services for {operations} in {launch_type} mode"
            )
            return PreflightResult(passed=True, missing_services=[])

        required_list = list(all_required)
        self.logger.debug(
            f"Checking combined services for {operations}: {required_list}"
        )

        try:
            from agentkit.sdk.account.client import AgentkitAccountClient

            client = AgentkitAccountClient(region=region)
            statuses = client.get_services_status(required_list)

            missing = [name for name, status in statuses.items() if status != "Enabled"]

            if missing:
                self.logger.warning(f"Services not enabled: {missing}")
                return PreflightResult(passed=False, missing_services=missing)

            self.logger.debug(f"All required services are enabled: {required_list}")
            return PreflightResult(passed=True, missing_services=[])

        except Exception as e:
            # If service check fails, log warning but allow to continue
            self.logger.warning(f"Failed to check service status: {e}")
            return PreflightResult(passed=True, missing_services=[])

    def launch(
        self,
        config_dict: Optional[Dict[str, Any]] = None,
        config_file: Optional[Union[str, Path]] = None,
        platform: str = "auto",
        preflight_mode: PreflightMode = PreflightMode.PROMPT,
    ) -> LifecycleResult:
        """
        Launch an Agent service (build + deploy in one step).

        Orchestrates the complete strategy from source code to running service:
        1. Preflight check: verify required cloud services for both build and deploy
        2. Build the Docker image
        3. Deploy the service to the target platform

        Args:
            config_dict: Configuration dictionary (optional)
            config_file: Path to configuration file (optional)
            platform: Docker build platform/architecture string
                (e.g., "linux/amd64", "linux/arm64", or "auto"). This controls
                the Docker build target platform and is independent from the
                launch_type (local/cloud/hybrid) configured in agentkit.yaml.
            preflight_mode: How to handle missing cloud services (default: PROMPT)

        Returns:
            LifecycleResult: Contains build_result and deploy_result with endpoint information

        Raises:
            FileNotFoundError: Configuration file not found
            ValueError: Invalid configuration
        """
        try:
            self.reporter.info("🚀 Starting launch operation...")

            # Preflight check: verify required cloud services for both build and deploy
            # We do this once at the start for better UX (single prompt for all missing services)
            if preflight_mode != PreflightMode.SKIP:
                # Load config first to get launch_type
                config = self._load_config(config_dict, config_file)
                launch_type = config.get_common_config().launch_type

                # Resolve region for preflight check
                region = self._resolve_account_region(config, launch_type)
                preflight_result = self._combined_preflight_check(
                    launch_type, ["build", "deploy"], region=region
                )
                if not self._handle_preflight_result(preflight_result, preflight_mode):
                    return LifecycleResult(
                        success=False,
                        operation="launch",
                        error="Launch aborted: required services not enabled",
                        error_code="PREFLIGHT_ABORTED",
                    )

            # Step 1: Build the Docker image
            # Skip preflight in sub-executor since we already checked
            self.reporter.info("📦 Step 1/2: Building image...")
            build_result = self.build_executor.execute(
                config_dict=config_dict,
                config_file=config_file,
                options=BuildOptions(platform=platform),
                preflight_mode=PreflightMode.SKIP,
            )

            if not build_result.success:
                self.logger.error(f"Build failed: {build_result.error}")
                return LifecycleResult(
                    success=False,
                    operation="launch",
                    build_result=build_result,
                    error=f"Build failed: {build_result.error}",
                    error_code=build_result.error_code,
                )

            # Build success is already reported by BuildExecutor, just log for audit trail
            self.logger.info(
                f"Build completed: image={build_result.image.full_name if build_result.image else 'N/A'}"
            )

            # Step 2: Deploy the service to target platform
            # Skip preflight in sub-executor since we already checked
            self.reporter.info("🚢 Step 2/2: Deploying service...")
            deploy_result = self.deploy_executor.execute(
                config_dict=config_dict,
                config_file=config_file,
                preflight_mode=PreflightMode.SKIP,
            )

            if not deploy_result.success:
                self.logger.error(f"Deploy failed: {deploy_result.error}")
                return LifecycleResult(
                    success=False,
                    operation="launch",
                    build_result=build_result,
                    deploy_result=deploy_result,
                    error=f"Deploy failed: {deploy_result.error}",
                    error_code=deploy_result.error_code,
                )

            # Both build and deploy succeeded
            endpoint = deploy_result.endpoint_url or deploy_result.container_id or "N/A"
            self.reporter.success(f"🎉 Launch successful! Service endpoint: {endpoint}")
            self.logger.info(f"Launch completed successfully: endpoint={endpoint}")

            return LifecycleResult(
                success=True,
                operation="launch",
                build_result=build_result,
                deploy_result=deploy_result,
                metadata={
                    "endpoint": endpoint,
                    "image": build_result.image.full_name
                    if build_result.image
                    else None,
                },
            )

        except Exception as e:
            # Log exception for debugging; error reporting is handled by CLI layer
            self.logger.exception(f"Launch execution error: {e}")

            error_info = self._handle_exception("Launch", e)
            return LifecycleResult(
                success=False,
                operation="launch",
                error=error_info.get("error"),
                error_code=error_info.get("error_code"),
            )

    def stop(
        self,
        config_dict: Optional[Dict[str, Any]] = None,
        config_file: Optional[Union[str, Path]] = None,
    ) -> LifecycleResult:
        """
        Stop a running Agent service without removing resources.

        The service can be restarted later. Configuration and deployment metadata are preserved.

        Args:
            config_dict: Configuration dictionary (optional)
            config_file: Path to configuration file (optional)

        Returns:
            LifecycleResult: Stop operation result

        Raises:
            FileNotFoundError: Configuration file not found
            ValueError: Invalid configuration or unknown launch_type
        """
        try:
            self.reporter.info("🛑 Stopping Agent service...")

            # Load configuration (priority: config_dict > config_file > default)
            self.logger.info("Loading configuration...")
            config = self._load_config(config_dict, config_file)

            # Extract launch_type to determine which strategy to use
            common_config = config.get_common_config()
            launch_type = common_config.launch_type
            self.logger.info(f"Using launch_type: {launch_type}")

            # Get the appropriate strategy (LocalStrategy, CloudStrategy, or HybridStrategy)
            strategy = self._get_strategy(launch_type, config_manager=config)

            # Get strongly-typed strategy configuration object
            strategy_config = self._get_strategy_config_object(config, launch_type)

            # Invoke strategy's stop method with both common and strategy-specific config
            success = strategy.stop(common_config, strategy_config)

            if success:
                self.reporter.success("✅ Service stopped")
                self.logger.info("Service stopped successfully")
                return LifecycleResult(success=True, operation="stop")
            else:
                self.reporter.error("❌ Failed to stop service")
                self.logger.error("Failed to stop service")
                return LifecycleResult(
                    success=False,
                    operation="stop",
                    error="Failed to stop service",
                    error_code="STOP_FAILED",
                )

        except Exception as e:
            # Log exception for debugging; error reporting is handled by CLI layer
            self.logger.exception(f"Stop execution error: {e}")

            error_info = self._handle_exception("Stop", e)
            return LifecycleResult(
                success=False,
                operation="stop",
                error=error_info.get("error"),
                error_code=error_info.get("error_code"),
            )

    def destroy(
        self,
        config_dict: Optional[Dict[str, Any]] = None,
        config_file: Optional[Union[str, Path]] = None,
    ) -> LifecycleResult:
        """
        Destroy Agent service and all associated resources.

        This is a destructive operation that stops the service and removes all resources:
        - Local: Stops and removes containers, cleans up images
        - Cloud: Terminates runtime instances and removes cloud resources
        - Hybrid: Cleans up both local and cloud resources

        After successful destruction, deployment metadata is cleared from configuration.

        Args:
            config_dict: Configuration dictionary (optional)
            config_file: Path to configuration file (optional)

        Returns:
            LifecycleResult: Destroy operation result

        Raises:
            FileNotFoundError: Configuration file not found
            ValueError: Invalid configuration or unknown launch_type
        """
        try:
            self.reporter.info("💥 Destroying Agent service and resources...")

            # Load configuration (priority: config_dict > config_file > default)
            self.logger.info("Loading configuration...")
            config = self._load_config(config_dict, config_file)

            # Extract launch_type to determine which strategy to use
            common_config = config.get_common_config()
            launch_type = common_config.launch_type
            self.logger.info(f"Using launch_type: {launch_type}")

            # Get the appropriate strategy (LocalStrategy, CloudStrategy, or HybridStrategy)
            strategy = self._get_strategy(launch_type, config_manager=config)

            # Get strongly-typed strategy configuration object
            strategy_config = self._get_strategy_config_object(config, launch_type)

            # Invoke strategy's destroy method with both common and strategy-specific config
            success = strategy.destroy(common_config, strategy_config)

            # On successful destruction, clear deployment metadata from configuration
            # This ensures the config is ready for a fresh deployment later
            if success:
                self._clear_deploy_config(config, launch_type)
                self.reporter.success("✅ Service and resources destroyed")
                self.reporter.info("✅ Configuration cleaned")
                self.logger.info("Service and resources destroyed successfully")
                return LifecycleResult(success=True, operation="destroy")
            else:
                self.reporter.error("❌ Failed to destroy service")
                self.logger.error("Failed to destroy service")
                return LifecycleResult(
                    success=False,
                    operation="destroy",
                    error="Failed to destroy service",
                    error_code="DESTROY_FAILED",
                )

        except Exception as e:
            # Log exception for debugging; error reporting is handled by CLI layer
            self.logger.exception(f"Destroy execution error: {e}")

            error_info = self._handle_exception("Destroy", e)
            return LifecycleResult(
                success=False,
                operation="destroy",
                error=error_info.get("error"),
                error_code=error_info.get("error_code"),
            )
