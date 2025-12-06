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
Unified error definitions and exception types.

This module provides standardized error codes and exception classes for AgentKit operations.
Error codes are machine-readable identifiers used in Result objects for programmatic error
handling, monitoring, and internationalization.
"""

from enum import Enum


class ErrorCode(str, Enum):
    """
    Standardized error codes for programmatic error handling.

    These codes are used in Result objects' error_code field to enable:
    - Programmatic error handling and recovery logic
    - Error monitoring and analytics
    - Internationalization (mapping codes to localized messages)

    Each code is self-contained and should be used consistently across
    all error scenarios to ensure reliable error classification.
    """

    # Configuration errors
    CONFIG_INVALID = "CONFIG_INVALID"
    CONFIG_MISSING = "CONFIG_MISSING"
    CONFIG_FILE_NOT_FOUND = "CONFIG_FILE_NOT_FOUND"

    # Network errors
    NETWORK_TIMEOUT = "NETWORK_TIMEOUT"
    NETWORK_CONNECTION = "NETWORK_CONNECTION"

    # Authentication and permission errors
    PERMISSION_DENIED = "PERMISSION_DENIED"
    AUTH_FAILED = "AUTH_FAILED"

    # Build errors
    BUILD_FAILED = "BUILD_FAILED"
    IMAGE_PUSH_FAILED = "IMAGE_PUSH_FAILED"
    DOCKERFILE_NOT_FOUND = "DOCKERFILE_NOT_FOUND"

    # Deployment errors
    DEPLOY_FAILED = "DEPLOY_FAILED"
    CONTAINER_START_FAILED = "CONTAINER_START_FAILED"
    RUNTIME_CREATE_FAILED = "RUNTIME_CREATE_FAILED"
    RUNTIME_NOT_READY = "RUNTIME_NOT_READY"

    # Invocation errors
    INVOKE_FAILED = "INVOKE_FAILED"
    INVOKE_TIMEOUT = "INVOKE_TIMEOUT"
    SERVICE_NOT_RUNNING = "SERVICE_NOT_RUNNING"

    # Resource errors
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    RESOURCE_CONFLICT = "RESOURCE_CONFLICT"
    RESOURCE_QUOTA_EXCEEDED = "RESOURCE_QUOTA_EXCEEDED"

    # Dependency errors
    DEPENDENCY_MISSING = "DEPENDENCY_MISSING"
    DOCKER_NOT_AVAILABLE = "DOCKER_NOT_AVAILABLE"

    # Catch-all for unclassified errors
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class AgentKitError(Exception):
    """
    Base exception class for all AgentKit errors.

    All AgentKit exceptions should inherit from this class to ensure
    consistent error handling and classification across the toolkit.
    """

    def __init__(self, message: str, error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR):
        """
        Initialize an AgentKit error.

        Args:
            message: Human-readable error message
            error_code: Machine-readable error code for programmatic handling
        """
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class ConfigError(AgentKitError):
    """Raised when configuration is invalid or missing required fields."""

    def __init__(self, message: str):
        super().__init__(message, ErrorCode.CONFIG_INVALID)


class DependencyError(AgentKitError):
    """Raised when a required dependency is missing or unavailable."""

    def __init__(self, message: str):
        super().__init__(message, ErrorCode.DEPENDENCY_MISSING)


class BuildError(AgentKitError):
    """Raised when the build process fails."""

    def __init__(self, message: str):
        super().__init__(message, ErrorCode.BUILD_FAILED)


class DeployError(AgentKitError):
    """Raised when the deployment process fails."""

    def __init__(self, message: str):
        super().__init__(message, ErrorCode.DEPLOY_FAILED)


class InvokeError(AgentKitError):
    """Raised when agent invocation fails."""

    def __init__(self, message: str):
        super().__init__(message, ErrorCode.INVOKE_FAILED)


__all__ = [
    "ErrorCode",
    "AgentKitError",
    "ConfigError",
    "DependencyError",
    "BuildError",
    "DeployError",
    "InvokeError",
]
