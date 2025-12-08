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
Unified model layer for all operations.

This module defines unified result models for all operations (build, deploy, invoke, status, etc.),
replacing previous scattered implementations:
- workflows/models.py (BuildInfo, DeployInfo, etc.)
- core/models/ (BuildResult, DeployResult, etc.)

Key design principle: Single source of truth - one model per operation type, eliminating
duplication and unnecessary conversions between layers.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


@dataclass
class ConfigUpdates:
    """Configuration updates produced by Strategy execution.

    This class implements the immutability pattern: Strategy methods never modify the input
    configuration objects. Instead, they record configuration changes via ConfigUpdates,
    which the Executor then applies and persists to the configuration file.

    Design rationale:
    - Strategies are pure functions that don't mutate state
    - Configuration changes are captured and applied at the Executor layer
    - This separation enables testing, composition, and clear responsibility boundaries

    Usage example:
        ```python
        # In Strategy
        def build(self, common_config, workflow_config):
            config_updates = ConfigUpdates()

            # Record auto-generated values that need to be persisted
            if workflow_config.runtime_name == AUTO_CREATE_VE:
                runtime_name = generate_runtime_name(...)
                config_updates.add('runtime_name', runtime_name)

            # Perform build operation...
            result = ...
            result.config_updates = config_updates
            return result

        # In Executor
        result = strategy.build(...)
        if result.config_updates:
            self._apply_config_updates(config, launch_type, result.config_updates)
        ```

    Attributes:
        updates: Dictionary of configuration key-value pairs to be updated
    """

    updates: Dict[str, Any] = field(default_factory=dict)

    def add(self, key: str, value: Any) -> "ConfigUpdates":
        """Record a configuration update.

        Args:
            key: Configuration field name (as it appears in workflow config)
            value: New value for the configuration field

        Returns:
            self, enabling method chaining

        Example:
            ```python
            updates = ConfigUpdates()
            updates.add('runtime_name', 'my-runtime')
                   .add('runtime_id', 'rt-123')
                   .add('image_id', 'sha256:abc')
            ```
        """
        self.updates[key] = value
        return self

    def has_updates(self) -> bool:
        """Check if any configuration updates have been recorded.

        Returns:
            True if updates exist, False otherwise
        """
        return bool(self.updates)

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve the update value for a specific configuration key.

        Args:
            key: Configuration field name
            default: Value to return if the key is not found

        Returns:
            The update value, or default if not found
        """
        return self.updates.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        """Convert updates to a dictionary for persistence.

        Returns:
            A copy of the updates dictionary
        """
        return self.updates.copy()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConfigUpdates":
        """Create a ConfigUpdates instance from a dictionary.

        Args:
            data: Dictionary of configuration updates

        Returns:
            ConfigUpdates instance
        """
        return cls(updates=data.copy())

    def merge(self, other: "ConfigUpdates") -> "ConfigUpdates":
        """Merge another ConfigUpdates into this one.

        Args:
            other: Another ConfigUpdates instance to merge

        Returns:
            self, enabling method chaining

        Note:
            If keys overlap, values from 'other' will override existing values
        """
        self.updates.update(other.updates)
        return self

    def __repr__(self) -> str:
        if not self.updates:
            return "ConfigUpdates(no updates)"
        return (
            f"ConfigUpdates({len(self.updates)} updates: {list(self.updates.keys())})"
        )

    def __len__(self) -> int:
        return len(self.updates)

    def __contains__(self, key: str) -> bool:
        return key in self.updates


# ============================================================================
# Preflight Check Models
# ============================================================================


class PreflightMode(Enum):
    """
    Preflight check behavior mode.

    Controls how the Executor handles missing cloud services before executing operations.

    Modes:
    - PROMPT: Show warning and ask user for confirmation (CLI default)
    - FAIL: Raise exception if services are not enabled (SDK strict mode)
    - WARN: Log warning but continue execution (SDK lenient mode)
    - SKIP: Skip preflight check entirely
    """

    PROMPT = "prompt"
    FAIL = "fail"
    WARN = "warn"
    SKIP = "skip"


@dataclass
class PreflightResult:
    """
    Result of preflight service status check.

    Contains information about which cloud services are missing and how to enable them.

    Attributes:
        passed: True if all required services are enabled
        missing_services: List of service names that are not enabled
        auth_url: URL where users can enable the missing services
    """

    passed: bool
    missing_services: List[str] = field(default_factory=list)
    auth_url: str = (
        "https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth"
    )

    @property
    def message(self) -> str:
        """Human-readable message describing the preflight result."""
        if self.passed:
            return "All required services are enabled."
        services = ", ".join(self.missing_services)
        return f"The following services are not enabled: {services}"

    def __bool__(self) -> bool:
        """Allow using PreflightResult in boolean context."""
        return self.passed


# ============================================================================
# Result models (Build, Deploy, Invoke, Status, etc.)
# ============================================================================


@dataclass
class ImageInfo:
    """Image information (value object).

    Encapsulates all image-related information in a unified structure. All workflows
    must use this model to eliminate inconsistent field names like cr_image_full_url,
    full_image_name, etc.

    Attributes:
        repository: Image repository address (without tag), e.g. "registry.com/namespace/app"
        tag: Image tag, e.g. "v1.0", "latest"
        digest: Image digest (optional), e.g. "sha256:abc123..."
    """

    repository: str
    tag: str
    digest: Optional[str] = None

    @property
    def full_name(self) -> str:
        """Full image name in format repository:tag"""
        return f"{self.repository}:{self.tag}"

    @property
    def full_name_with_digest(self) -> str:
        """Full image name with digest in format repository@digest"""
        if self.digest:
            return f"{self.repository}@{self.digest}"
        return self.full_name

    def __str__(self) -> str:
        return self.full_name


@dataclass
class BuildResult:
    """Result of a build operation.

    All workflow implementations (local/cloud/hybrid) return this unified model from
    their build() methods, eliminating previous duplication between BuildInfo and BuildResult.

    Design improvement:
    - Before: Builder returned Tuple[bool, Dict] → Workflow converted to BuildInfo
             → Service converted to BuildResult (multiple conversions)
    - Now: Builder returns BuildResult directly → Workflow returns BuildResult directly
           (single model, no conversions)
    """

    success: bool
    """Whether the build operation succeeded"""

    image: Optional[ImageInfo] = None
    """Built image information (required if success=True)"""

    build_timestamp: Optional[datetime] = None
    """Timestamp when build completed"""

    build_logs: List[str] = field(default_factory=list)
    """Build logs from the build process"""

    build_duration_seconds: Optional[float] = None
    """Build duration in seconds"""

    error: Optional[str] = None
    """Error message (populated if success=False)"""

    error_code: Optional[str] = None
    """Error code (populated if success=False), e.g. "BUILD_FAILED", "DEPENDENCY_MISSING"""

    warnings: List[str] = field(default_factory=list)
    """Warning messages (may be present even if success=True)"""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """Additional metadata (workflow-specific information)"""

    config_updates: Optional["ConfigUpdates"] = None
    """Configuration updates produced by the Strategy (persisted by Executor)"""

    def __bool__(self) -> bool:
        return self.success

    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    def __str__(self) -> str:
        if self.success and self.image:
            return f"BuildResult(success=True, image={self.image})"
        elif self.success:
            return "BuildResult(success=True)"
        else:
            return f"BuildResult(success=False, error={self.error_code or 'UNKNOWN'})"


@dataclass
class DeployResult:
    """Result of a deploy operation.

    All workflow implementations return this unified model from their deploy() methods.
    """

    success: bool
    """Whether the deploy operation succeeded"""

    endpoint_url: Optional[str] = None
    """Service endpoint URL (populated if success=True)"""

    service_id: Optional[str] = None
    """Service ID (for cloud deployments)"""

    container_id: Optional[str] = None
    """Container ID (for local deployments)"""

    container_name: Optional[str] = None
    """Container name (for local deployments)"""

    deploy_timestamp: Optional[datetime] = None
    """Timestamp when deployment completed"""

    error: Optional[str] = None
    """Error message (populated if success=False)"""

    error_code: Optional[str] = None
    """Error code (populated if success=False)"""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """Additional metadata"""

    config_updates: Optional["ConfigUpdates"] = None
    """Configuration updates produced by the Strategy (persisted by Executor)"""

    def __bool__(self) -> bool:
        return self.success

    def __str__(self) -> str:
        if self.success:
            endpoint = self.endpoint_url or self.container_id or self.service_id
            return f"DeployResult(success=True, endpoint={endpoint})"
        else:
            return f"DeployResult(success=False, error={self.error_code or 'UNKNOWN'})"


@dataclass
class InvokeResult:
    """Result of an invoke operation.

    All workflow implementations return this unified model from their invoke() methods.
    """

    success: bool
    """Whether the invoke operation succeeded"""

    response: Any = None
    """Response data (can be dict, generator, or other types)"""

    is_streaming: bool = False
    """Whether the response is streaming"""

    response_time_ms: Optional[float] = None
    """Response time in milliseconds"""

    status_code: Optional[int] = None
    """HTTP status code (if applicable)"""

    error: Optional[str] = None
    """Error message (populated if success=False)"""

    error_code: Optional[str] = None
    """Error code (populated if success=False)"""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """Additional metadata"""

    def __bool__(self) -> bool:
        return self.success

    def stream(self):
        """Get an iterator for streaming responses.

        Returns:
            Iterator over the response data

        Raises:
            ValueError: If is_streaming is False
        """
        if not self.is_streaming:
            raise ValueError(
                "This is not a streaming response. Check is_streaming before calling stream()."
            )

        # Check if response is iterable (generator, list, etc.) but not string/bytes/dict
        if hasattr(self.response, "__iter__") and not isinstance(
            self.response, (str, bytes, dict)
        ):
            return self.response
        else:
            # Response is not iterable, return empty iterator
            return iter([])

    def __str__(self) -> str:
        if self.success:
            return f"InvokeResult(success=True, streaming={self.is_streaming})"
        else:
            return f"InvokeResult(success=False, error={self.error_code or 'UNKNOWN'})"


@dataclass
class StatusResult:
    """Result of a status query operation.

    All workflow implementations return this unified model from their status() methods.
    """

    success: bool
    """Whether the status query succeeded"""

    status: Optional[str] = None
    """Service status, e.g. "running", "stopped", "not_deployed"""

    endpoint_url: Optional[str] = None
    """Service endpoint URL (if service is running)"""

    service_id: Optional[str] = None
    """Service ID"""

    container_id: Optional[str] = None
    """Container ID (for local deployments)"""

    uptime_seconds: Optional[int] = None
    """Service uptime in seconds"""

    health: Optional[str] = None
    """Health status, e.g. "healthy", "unhealthy"""

    error: Optional[str] = None
    """Error message (populated if success=False)"""

    error_code: Optional[str] = None
    """Error code"""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """Additional metadata"""

    def __bool__(self) -> bool:
        return self.success

    def is_running(self) -> bool:
        return self.success and self.status == "running"

    def __str__(self) -> str:
        if self.success:
            return f"StatusResult(success=True, status={self.status})"
        else:
            return f"StatusResult(success=False, error={self.error_code or 'UNKNOWN'})"


@dataclass
class LifecycleResult:
    """Result of a lifecycle operation (launch/stop/destroy).

    Used for composite operations that combine multiple lower-level operations.
    """

    success: bool
    """Whether the lifecycle operation succeeded"""

    operation: str = ""
    """Operation type, e.g. "launch", "stop", "destroy"""

    build_result: Optional[BuildResult] = None
    """Build result (populated for launch operations)"""

    deploy_result: Optional[DeployResult] = None
    """Deploy result (populated for launch operations)"""

    error: Optional[str] = None
    """Error message"""

    error_code: Optional[str] = None
    """Error code"""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """Additional metadata"""

    def __bool__(self) -> bool:
        return self.success

    def __str__(self) -> str:
        if self.success:
            return f"LifecycleResult(success=True, operation={self.operation})"
        else:
            return f"LifecycleResult(success=False, operation={self.operation}, error={self.error_code})"


@dataclass
class AgentFileInfo:
    """Parsed information about a user's Agent definition file.

    Used during project initialization to understand the structure
    of the user's Agent file and generate appropriate wrappers.
    """

    file_path: str
    """Absolute path to the Agent definition file"""

    agent_var_name: str
    """Name of the Agent variable in the file (e.g., 'agent', 'my_agent')"""

    module_name: str
    """Python module name derived from filename (without .py extension)"""

    file_name: str
    """Filename with extension (e.g., 'websearch_agent.py')"""

    imports: Optional[List[str]] = None
    """List of import statements found in the file"""

    has_runner: bool = False
    """Whether the file already contains a Runner definition"""

    has_entrypoint: bool = False
    """Whether the file already has an entrypoint decorator"""

    detected_tools: Optional[List[str]] = None
    """List of detected tool names used in the Agent"""

    def __str__(self) -> str:
        return f"AgentFileInfo(file={self.file_name}, var={self.agent_var_name})"


@dataclass
class InitResult:
    """Result of an init operation.

    Used for the init command result.
    """

    success: bool
    """Whether the init operation succeeded"""

    project_path: Optional[str] = None
    """Project path"""

    project_name: Optional[str] = None
    """Project name"""

    template: Optional[str] = None
    """Template used for initialization"""

    config_file: Optional[str] = None
    """Path to the generated configuration file"""

    created_files: List[str] = field(default_factory=list)
    """List of created files"""

    error: Optional[str] = None
    """Error message"""

    error_code: Optional[str] = None
    """Error code"""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """Additional metadata"""

    def __bool__(self) -> bool:
        return self.success

    def __str__(self) -> str:
        if self.success:
            return f"InitResult(success=True, project_path={self.project_path})"
        else:
            return f"InitResult(success=False, error={self.error_code})"


__all__ = [
    "ConfigUpdates",
    "PreflightMode",
    "PreflightResult",
    "ImageInfo",
    "BuildResult",
    "DeployResult",
    "InvokeResult",
    "StatusResult",
    "LifecycleResult",
    "InitResult",
    "AgentFileInfo",
]
