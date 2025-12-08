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
from ..reporter import SilentReporter
from ..models import LifecycleResult
from ..context import ExecutionContext


def launch(
    config_file: Optional[str] = None,
    config_dict: Optional[Dict[str, Any]] = None,
    platform: str = "auto"
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
        platform: Build platform: "auto", "local", or "cloud".
            Default is "auto" which selects based on workflow configuration.
    
    Returns:
        LifecycleResult: Launch operation result containing:
            - success: Whether launch succeeded
            - operation: "launch"
            - message: Success message with endpoint info
            - error: Error message if failed
            - details: Contains BuildResult and DeployResult
    
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
        ...     print(result.message)
        ...     build_res = result.details['build_result']
        ...     deploy_res = result.details['deploy_result']
        ...     print(f"Image: {build_res.image_name}")
        ...     print(f"Endpoint: {deploy_res.endpoint_url}")
        ... else:
        ...     print(f"Launch failed: {result.error}")
    
    Raises:
        No exceptions are raised. All errors are captured in LifecycleResult.error.
    """
    reporter = SilentReporter()
    ExecutionContext.set_reporter(reporter)
    
    executor = LifecycleExecutor(reporter=reporter)
    return executor.launch(
        config_dict=config_dict,
        config_file=config_file,
        platform=platform
    )


def destroy(
    config_file: Optional[str] = None,
    config_dict: Optional[Dict[str, Any]] = None,
    force: bool = False
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
        force: Force destroy without confirmation prompts.
            Default is False. When used from CLI, user is prompted.
    
    Returns:
        LifecycleResult: Destroy operation result containing:
            - success: Whether destroy succeeded
            - operation: "destroy"
            - message: Success message
            - error: Error message if failed
    
    Example:
        >>> from agentkit.toolkit import sdk
        >>> 
        >>> # Destroy agent runtime
        >>> result = sdk.destroy()
        >>> 
        >>> # Force destroy
        >>> result = sdk.destroy(force=True)
        >>> 
        >>> if result.success:
        ...     print(result.message)
        ... else:
        ...     print(f"Destroy failed: {result.error}")
    
    Raises:
        No exceptions are raised. All errors are captured in LifecycleResult.error.
    """
    reporter = SilentReporter()
    ExecutionContext.set_reporter(reporter)
    
    executor = LifecycleExecutor(reporter=reporter)
    return executor.destroy(
        config_dict=config_dict,
        config_file=config_file
    )


def stop(
    config_file: Optional[str] = None,
    config_dict: Optional[Dict[str, Any]] = None
) -> LifecycleResult:
    """
    Stop agent runtime (without destroying resources).
    
    This function stops the running agent but keeps resources intact,
    allowing for faster restart later.
    
    Args:
        config_file: Path to configuration file (e.g., "agentkit.yaml").
            If not provided, uses default "agentkit.yaml" in current directory.
        config_dict: Configuration as dictionary (highest priority).
            Overrides config_file if both provided.
    
    Returns:
        LifecycleResult: Stop operation result containing:
            - success: Whether stop succeeded
            - operation: "stop"
            - message: Success message
            - error: Error message if failed
    
    Example:
        >>> from agentkit.toolkit import sdk
        >>> 
        >>> # Stop agent runtime
        >>> result = sdk.stop()
        >>> 
        >>> if result.success:
        ...     print(result.message)
        ... else:
        ...     print(f"Stop failed: {result.error}")
    
    Raises:
        No exceptions are raised. All errors are captured in LifecycleResult.error.
    """
    reporter = SilentReporter()
    ExecutionContext.set_reporter(reporter)
    
    executor = LifecycleExecutor(reporter=reporter)
    return executor.stop(
        config_dict=config_dict,
        config_file=config_file
    )
