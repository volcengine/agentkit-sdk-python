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

"""Invoke API - SDK interface for invoking deployed agents."""

from typing import Optional, Dict, Any

from ..executors import InvokeExecutor
from ..models import InvokeResult
from ..reporter import SilentReporter, Reporter
from ..context import ExecutionContext


def invoke(
    payload: Dict[str, Any],
    config_file: Optional[str] = None,
    config_dict: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    reporter: Optional[Reporter] = None,
) -> InvokeResult:
    """
    Invoke deployed agent with a request.

    This function sends a request to your deployed agent and returns the response.
    The response can be either a complete response or a streaming generator.

    Args:
        payload: Request payload dictionary to send to agent.
            Typically contains fields like "prompt", "messages", etc.
        config_file: Path to configuration file (e.g., "agentkit.yaml").
            If not provided, uses default "agentkit.yaml" in current directory.
        config_dict: Configuration as dictionary (highest priority).
            Overrides config_file if both provided.
        headers: Optional HTTP headers dictionary.
            Common headers: {"user_id": "...", "session_id": "..."}
        reporter: Optional Reporter for progress/log output. If None, uses
            SilentReporter (no console output). Advanced users can pass
            LoggingReporter or a custom Reporter implementation.

    Returns:
        InvokeResult: Invocation result containing:
            - success: Whether invocation succeeded
            - response: Response data (dict or generator)
            - is_streaming: Whether response is streaming
            - error: Error message if failed

    Example:
        >>> from agentkit.toolkit import sdk
        >>>
        >>> # Simple invocation
        >>> result = sdk.invoke(
        ...     payload={"prompt": "Hello, agent!"}
        ... )
        >>>
        >>> # With headers
        >>> result = sdk.invoke(
        ...     payload={"prompt": "What's the weather?"},
        ...     headers={"user_id": ""},
        ... )
        >>>
        >>> # Handle streaming response
        >>> if result.is_streaming:
        ...     for event in result.stream():
        ...         print(event)
        ... else:
        ...     print(result.response)
        >>>
        >>> # For non-streaming responses, access result.response directly
        >>> full_response = result.response

    Raises:
        No exceptions are raised. All errors are captured in InvokeResult.error.
    """
    # SDK uses SilentReporter by default (no console output), but supports custom Reporter
    if reporter is None:
        reporter = SilentReporter()
    ExecutionContext.set_reporter(reporter)

    executor = InvokeExecutor(reporter=reporter)
    # InvokeExecutor.execute uses the stream parameter to control streaming return;
    # SDK always passes None here, allowing the underlying Runner to automatically
    # determine whether to enable streaming based on configuration.
    return executor.execute(
        payload=payload,
        config_dict=config_dict,
        config_file=config_file,
        headers=headers,
        stream=None,  # Automatically determined by Runner
    )
