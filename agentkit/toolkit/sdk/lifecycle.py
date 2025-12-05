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

"""Lifecycle API - SDK interface for agent lifecycle management."""

from typing import Optional, Dict, Any

from ..executors import LifecycleExecutor
from ..reporter import SilentReporter, Reporter
from ..models import LifecycleResult, PreflightMode
from ..context import ExecutionContext


def launch(
    config_file: Optional[str] = None,
    config_dict: Optional[Dict[str, Any]] = None,
    platform: str = "auto",
    preflight_mode: PreflightMode = PreflightMode.WARN,
    reporter: Optional[Reporter] = None,
) -> LifecycleResult:
    """
    Launch agent (build + deploy in one operation).

    This is a convenience function that combines build() and deploy()
    into a single operation for faster development workflow.

    Args:
        config_file: Path to configuration file (e.g., "agentkit.yaml").
            If not provided, uses default "agentkit.yaml" in current directory.
        config_dict: Configuration as dictionary (highest priority).
            Overrides config_file if both provided.
        platform: Docker build platform/architecture string
            (e.g., "linux/amd64", "linux/arm64", or "auto"). This controls
            the Docker build target platform and is independent from the
            launch_type (local/cloud/hybrid) configured in agentkit.yaml.

    Returns:
        LifecycleResult: Launch operation result containing:
            - success: Whether launch succeeded
            - operation: "launch"
            - build_result: BuildResult from the build step
            - deploy_result: DeployResult from the deploy step
            - metadata: Extra information (e.g. endpoint, image)
            - error: Error message if failed

    Example:
        >>> from agentkit.toolkit import sdk
        >>>
        >>> # Launch with default config
        >>> result = sdk.launch()
        >>>
        >>> # Launch with specific config
        >>> result = sdk.launch(config_file="my-config.yaml")
        >>>
        >>> # Check result
        >>> if result.success:
        ...     print(f"Operation: {result.operation}")
        ...     build_res = result.build_result
        ...     deploy_res = result.deploy_result
        ...     if build_res and build_res.image:
        ...         print(f"Image: {build_res.image}")
        ...     if deploy_res:
        ...         print(f"Endpoint: {deploy_res.endpoint_url}")
        ...     # Or use metadata from LifecycleResult
        ...     endpoint = result.metadata.get("endpoint")
        ...     if endpoint:
        ...         print(f"Endpoint (from metadata): {endpoint}")
        ... else:
        ...     print(f"Launch failed: {result.error}")

    Raises:
        No exceptions are raised. All errors are captured in LifecycleResult.error.
    """
    if reporter is None:
        reporter = SilentReporter()
    ExecutionContext.set_reporter(reporter)

    executor = LifecycleExecutor(reporter=reporter)
    return executor.launch(
        config_dict=config_dict,
        config_file=config_file,
        platform=platform,
        preflight_mode=preflight_mode,
    )


def destroy(
    config_file: Optional[str] = None,
    config_dict: Optional[Dict[str, Any]] = None,
    reporter: Optional[Reporter] = None,
) -> LifecycleResult:
    """
    Destroy agent runtime and resources.

    This function stops and removes all resources associated with the agent,
    including containers, services, and other cloud resources.

    Args:
        config_file: Path to configuration file (e.g., "agentkit.yaml").
            If not provided, uses default "agentkit.yaml" in current directory.
        config_dict: Configuration as dictionary (highest priority).
            Overrides config_file if both provided.

    Returns:
        LifecycleResult: Destroy operation result containing:
            - success: Whether destroy succeeded
            - operation: "destroy"
            - error: Error message if failed

    Example:
        >>> from agentkit.toolkit import sdk
        >>>
        >>> # Destroy agent runtime
        >>> result = sdk.destroy()
        >>>
        >>> if result.success:
        ...     print(f"Destroy succeeded: {result.operation}")
        ... else:
        ...     print(f"Destroy failed: {result.error}")

    Raises:
        No exceptions are raised. All errors are captured in LifecycleResult.error.
    """
    reporter = SilentReporter()
    ExecutionContext.set_reporter(reporter)

    executor = LifecycleExecutor(reporter=reporter)
    return executor.destroy(config_dict=config_dict, config_file=config_file)
