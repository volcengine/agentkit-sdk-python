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


from abc import ABC, abstractmethod
from typing import Any, Optional, Dict, List
from agentkit.toolkit.models import (
    BuildResult,
    DeployResult,
    InvokeResult,
    StatusResult,
)
from agentkit.toolkit.reporter import Reporter, SilentReporter
from agentkit.toolkit.config import CommonConfig


class Strategy(ABC):
    """
    Base Strategy class for pure orchestration logic across deployment platforms.

    Design Principle: Strategies act as thin orchestration layers that delegate
    to Builder/Runner components without transformation or error handling.

    This separation enables:
    - **Testability**: Pure functions with predictable inputs/outputs
    - **Clarity**: Focus solely on business workflow orchestration
    - **Composability**: Multiple strategies can be combined or chained
    - **Flexibility**: Different execution contexts (CLI vs SDK) use same logic

    Reporter Pattern:
    Strategy receives a Reporter and passes it through to Builder/Runner components.
    This allows different execution contexts to control progress reporting:
    - CLI: Injects ConsoleReporter for user-visible progress
    - SDK: Injects SilentReporter for programmatic execution

    Service Requirements:
    Each concrete Strategy defines REQUIRED_SERVICES - a mapping of operation names
    to lists of cloud services that must be enabled. This enables preflight checks
    before executing operations that depend on cloud infrastructure.
    """

    # Service requirements mapping: operation -> list of required service names
    # Override in concrete Strategy subclasses
    REQUIRED_SERVICES: Dict[str, List[str]] = {}

    @classmethod
    def get_required_services(cls, operation: str) -> List[str]:
        """
        Get the list of cloud services required for an operation.

        Args:
            operation: Operation name ('build', 'deploy', etc.)

        Returns:
            List of service names that must be enabled (e.g., ['cr', 'tos', 'cp'])
        """
        return cls.REQUIRED_SERVICES.get(operation, [])

    def __init__(self, config_manager=None, reporter: Reporter = None):
        """
        Initialize Strategy with optional configuration manager and reporter.

        Args:
            config_manager: Configuration manager instance (optional)
            reporter: Reporter instance passed through to Builder/Runner components
        """
        self.config_manager = config_manager
        # Default to SilentReporter for programmatic usage (SDK scenarios)
        self.reporter = reporter or SilentReporter()

    @abstractmethod
    def build(self, common_config: CommonConfig, strategy_config: Any) -> BuildResult:
        """
        Orchestrate the build process by delegating to appropriate Builder.

        Args:
            common_config: Common configuration shared across all strategies
            strategy_config: Strategy-specific configuration (LocalDockerConfig | VeAgentkitConfig | HybridVeAgentkitConfig)

        Returns:
            BuildResult: Unmodified result from Builder.build()
        """
        pass

    @abstractmethod
    def deploy(self, common_config: CommonConfig, strategy_config: Any) -> DeployResult:
        """
        Orchestrate the deployment process by delegating to appropriate Runner.

        Args:
            common_config: Common configuration shared across all strategies
            strategy_config: Strategy-specific configuration (LocalDockerConfig | VeAgentkitConfig | HybridVeAgentkitConfig)

        Returns:
            DeployResult: Unmodified result from Runner.deploy()
        """
        pass

    @abstractmethod
    def invoke(
        self,
        common_config: CommonConfig,
        strategy_config: Any,
        payload: Any,
        headers: Optional[dict] = None,
        stream: Optional[bool] = None,
    ) -> InvokeResult:
        """
        Orchestrate agent invocation by delegating to appropriate Runner.

        Args:
            common_config: Common configuration shared across all strategies
            strategy_config: Strategy-specific configuration
            payload: Request payload to send to the agent
            headers: Optional HTTP headers for the request
            stream: Whether to use streaming response (if supported)

        Returns:
            InvokeResult: Unmodified result from Runner.invoke()
        """
        pass

    @abstractmethod
    def status(self, common_config: CommonConfig, strategy_config: Any) -> StatusResult:
        """
        Orchestrate status query by delegating to appropriate Runner.

        Args:
            common_config: Common configuration shared across all strategies
            strategy_config: Strategy-specific configuration

        Returns:
            StatusResult: Unmodified result from Runner.status()
        """
        pass

    def stop(self, common_config: CommonConfig, strategy_config: Any) -> bool:
        """
        Stop the deployed service while preserving resources for restart.

        Default implementation returns True (no-op). Override in concrete strategies
        that support service lifecycle management.

        Args:
            common_config: Common configuration shared across all strategies
            strategy_config: Strategy-specific configuration

        Returns:
            bool: True if stop succeeded or not applicable
        """
        return True

    def destroy(
        self, common_config: CommonConfig, strategy_config: Any, force: bool = False
    ) -> bool:
        """
        Destroy all resources created by this strategy (containers, images, etc.).

        Default implementation returns True (no-op). Override in concrete strategies
        that create persistent resources requiring cleanup.

        Args:
            common_config: Common configuration shared across all strategies
            strategy_config: Strategy-specific configuration
            force: Whether to force destruction even if resources are in use

        Returns:
            bool: True if destruction succeeded or not applicable
        """
        return True
