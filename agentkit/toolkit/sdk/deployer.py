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

"""Deploy API - SDK interface for deploying agents."""

from typing import Optional, Dict, Any

from ..executors import DeployExecutor
from ..models import DeployResult
from ..reporter import SilentReporter
from ..context import ExecutionContext


def deploy(
    config_file: Optional[str] = None,
    config_dict: Optional[Dict[str, Any]] = None
) -> DeployResult:
    """
    Deploy agent to target environment.
    
    This function deploys your agent application to the configured environment.
    The deployment can be local (Docker container) or cloud-based depending
    on your workflow configuration.
    
    Args:
        config_file: Path to configuration file (e.g., "agentkit.yaml").
            If not provided, uses default "agentkit.yaml" in current directory.
        config_dict: Configuration as dictionary (highest priority).
            Overrides config_file if both provided.
    
    Returns:
        DeployResult: Deploy operation result containing:
            - success: Whether deployment succeeded
            - endpoint_url: Service endpoint URL if available
            - container_id: Container ID for local deployments
            - service_id: Service ID for cloud deployments
            - error: Error message if failed
    
    Example:
        >>> from agentkit.toolkit import sdk
        >>> 
        >>> # Deploy with default config
        >>> result = sdk.deploy()
        >>> 
        >>> # Deploy with specific config file
        >>> result = sdk.deploy(config_file="my-config.yaml")
        >>> 
        >>> # Check result
        >>> if result.success:
        ...     print(f"Deployed at: {result.endpoint_url}")
        ...     print(f"Container: {result.container_id}")
        ... else:
        ...     print(f"Deploy failed: {result.error}")
    
    Raises:
        No exceptions are raised. All errors are captured in DeployResult.error.
    """
    # SDK 使用 SilentReporter（无控制台输出）
    reporter = SilentReporter()
    ExecutionContext.set_reporter(reporter)
    
    executor = DeployExecutor(reporter=reporter)
    return executor.execute(
        config_dict=config_dict,
        config_file=config_file
    )
