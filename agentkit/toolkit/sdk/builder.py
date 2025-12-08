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

"""Build API - SDK interface for building agent images."""

from typing import Optional, Dict, Any

from ..executors import BuildExecutor, BuildOptions
from ..models import BuildResult
from ..reporter import SilentReporter
from ..context import ExecutionContext


def build(
    config_file: Optional[str] = None,
    config_dict: Optional[Dict[str, Any]] = None,
    platform: str = "auto",
    regenerate_dockerfile: bool = False
) -> BuildResult:
    """
    Build agent image.
    
    This function builds a Docker image for your agent application according
    to the configuration. The build can happen locally or in the cloud depending
    on your strongly configuration.
    
    Args:
        config_file: Path to configuration file (e.g., "agentkit.yaml").
            If not provided, uses default "agentkit.yaml" in current directory.
        config_dict: Configuration as dictionary (highest priority).
            Overrides config_file if both provided.
        platform: Build platform: "auto", "local", or "cloud".
            Default is "auto" which selects based on strongly configuration.
        regenerate_dockerfile: Force regenerate Dockerfile even if it exists.
            Default is False.
    
    Returns:
        BuildResult: Build operation result containing:
            - success: Whether build succeeded
            - image_name: Full image name if successful
            - image_id: Image ID/digest if successful
            - error: Error message if failed
            - build_logs: Build logs if available
    
    Example:
        >>> from agentkit.toolkit import sdk
        >>> 
        >>> # Build with default config
        >>> result = sdk.build()
        >>> 
        >>> # Build with specific config file
        >>> result = sdk.build(config_file="my-config.yaml")
        >>> 
        >>> # Check result
        >>> if result.success:
        ...     print(f"Image built: {result.image_name}")
        ... else:
        ...     print(f"Build failed: {result.error}")
        ...     for log in result.build_logs or []:
        ...         print(log)
    
    Raises:
        No exceptions are raised. All errors are captured in BuildResult.error.
    """
    # SDK 使用 SilentReporter（无控制台输出）
    reporter = SilentReporter()
    ExecutionContext.set_reporter(reporter)

    options = BuildOptions(
        platform=platform,
        regenerate_dockerfile=regenerate_dockerfile
    )
    
    executor = BuildExecutor(reporter=reporter)
    return executor.execute(
        config_dict=config_dict,
        config_file=config_file,
        options=options
    )
