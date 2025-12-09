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

"""Status API - SDK interface for querying agent status."""

from typing import Optional, Dict, Any

from ..executors import StatusExecutor
from ..models import StatusResult
from ..reporter import SilentReporter, Reporter
from ..context import ExecutionContext


def status(
    config_file: Optional[str] = None,
    config_dict: Optional[Dict[str, Any]] = None,
    reporter: Optional[Reporter] = None,
) -> StatusResult:
    """
    Query agent runtime status.

    This function retrieves the current status of your deployed agent,
    including whether it's running, endpoint information, and other details.

    Args:
        config_file: Path to configuration file (e.g., "agentkit.yaml").
            If not provided, uses default "agentkit.yaml" in current directory.
        config_dict: Configuration as dictionary (highest priority).
            Overrides config_file if both provided.

    Returns:
        StatusResult: Status query result containing:
            - success: Whether status query succeeded
            - status: Service status string (e.g., "running", "stopped", "not_deployed")
            - endpoint_url: Service endpoint if available
            - container_id: Container ID for local deployments
            - service_id: Service ID for cloud deployments
            - uptime_seconds: Service uptime in seconds if available
            - metadata: Additional status details
            - error: Error message if query failed
        reporter: Optional Reporter for progress/log output. If None, uses
            SilentReporter (no console output). Advanced users can pass
            LoggingReporter or a custom Reporter implementation.

    Example:
        >>> from agentkit.toolkit import sdk
        >>>
        >>> # Query status with default config
        >>> result = sdk.status()
        >>>
        >>> # Query with specific config
        >>> result = sdk.status(config_file="my-config.yaml")
        >>>
        >>> # Check result
        >>> if result.success:
        ...     print(f"Status: {result.status}")
        ...     print(f"Running: {result.is_running()}")
        ...     print(f"Endpoint: {result.endpoint_url}")
        ...     print(f"Uptime (seconds): {result.uptime_seconds}")
        ... else:
        ...     print(f"Status query failed: {result.error}")

    Raises:
        No exceptions are raised. All errors are captured in StatusResult.error.
    """
    if reporter is None:
        reporter = SilentReporter()
    ExecutionContext.set_reporter(reporter)

    executor = StatusExecutor(reporter=reporter)
    return executor.execute(config_dict=config_dict, config_file=config_file)
