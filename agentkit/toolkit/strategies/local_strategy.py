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
Local Docker orchestration strategy.

Pure orchestration logic that delegates to LocalDockerBuilder and LocalDockerRunner.
Error handling, progress reporting, and logging are handled by the Executor layer.
"""

from typing import Any, Optional
from agentkit.toolkit.strategies.base_strategy import Strategy
from agentkit.toolkit.models import (
    BuildResult,
    DeployResult,
    InvokeResult,
    StatusResult,
)
from agentkit.toolkit.config import (
    CommonConfig,
    LocalStrategyConfig,
    merge_runtime_envs,
)
from agentkit.toolkit.builders.local_docker import (
    LocalDockerBuilder,
    LocalDockerBuilderConfig,
)
from agentkit.toolkit.runners.local_docker import (
    LocalDockerRunner,
    LocalDockerRunnerConfig,
)


class LocalStrategy(Strategy):
    """
    Local Docker orchestration strategy.

    Orchestration flow:
    1. build: LocalDockerBuilder.build() → BuildResult
    2. deploy: LocalDockerRunner.deploy() → DeployResult
    3. invoke: LocalDockerRunner.invoke() → InvokeResult
    4. status: LocalDockerRunner.status() → StatusResult

    Characteristics:
    - Pure orchestration with no side effects
    - Directly returns Builder/Runner results
    - Exceptions are propagated to the Executor layer
    """

    # Local mode does not require any cloud services
    REQUIRED_SERVICES = {}

    def __init__(self, config_manager=None, reporter=None):
        """
        Initialize LocalStrategy.

        Args:
            config_manager: Configuration manager (optional)
            reporter: Reporter instance to pass to Builder/Runner
        """
        super().__init__(config_manager, reporter)

        # Lazy initialization to avoid requiring environment variables at init time
        self._builder = None
        self._runner = None

    @property
    def builder(self):
        """Lazy-load LocalDockerBuilder instance."""
        if self._builder is None:
            project_dir = None
            if self.config_manager:
                project_dir = self.config_manager.get_project_dir()

            self._builder = LocalDockerBuilder(
                project_dir=project_dir, reporter=self.reporter
            )
        return self._builder

    @property
    def runner(self):
        """Lazy-load LocalDockerRunner instance."""
        if self._runner is None:
            self._runner = LocalDockerRunner(reporter=self.reporter)
        return self._runner

    def build(
        self, common_config: CommonConfig, strategy_config: LocalStrategyConfig
    ) -> BuildResult:
        """
        Execute local Docker build.

        Steps:
        1. Convert configuration to builder format
        2. Call LocalDockerBuilder.build()
        3. Extract and track configuration updates from build result
        4. Return BuildResult
        """
        from agentkit.toolkit.models import ConfigUpdates

        builder_config = self._to_builder_config(common_config, strategy_config)
        result = self.builder.build(builder_config)

        # Extract and track configuration updates from build result
        config_updates = ConfigUpdates()

        if result.success:
            if result.build_timestamp:
                config_updates.add(
                    "build_timestamp", result.build_timestamp.isoformat()
                )

            if result.image:
                config_updates.add("full_image_name", result.image.full_name)
                config_updates.add("image_id", result.image.digest or "")

        result.config_updates = config_updates if config_updates.has_updates() else None

        return result

    def deploy(
        self, common_config: CommonConfig, strategy_config: LocalStrategyConfig
    ) -> DeployResult:
        """
        Execute local Docker deployment.

        Steps:
        1. Convert configuration to runner format
        2. Call LocalDockerRunner.deploy()
        3. Extract and track configuration updates from deployment result
        4. Return DeployResult
        """
        from agentkit.toolkit.models import ConfigUpdates

        runner_config = self._to_runner_config(common_config, strategy_config)
        result = self.runner.deploy(runner_config)

        # Extract and track configuration updates from deployment result
        config_updates = ConfigUpdates()

        if result.success:
            if result.deploy_timestamp:
                config_updates.add(
                    "deploy_timestamp", result.deploy_timestamp.isoformat()
                )

            if result.container_id:
                config_updates.add("container_id", result.container_id)

            if result.metadata and "container_name" in result.metadata:
                config_updates.add("container_name", result.metadata["container_name"])

            if result.endpoint_url:
                config_updates.add("endpoint", result.endpoint_url)

        result.config_updates = config_updates if config_updates.has_updates() else None

        return result

    def invoke(
        self,
        common_config: CommonConfig,
        strategy_config: LocalStrategyConfig,
        payload: Any,
        headers: Optional[dict] = None,
        stream: Optional[bool] = None,
    ) -> InvokeResult:
        """
        Invoke the deployed service.

        Args:
            common_config: Common application configuration
            strategy_config: Strategy-specific configuration
            payload: Request payload
            headers: Optional HTTP headers
            stream: Optional streaming flag

        Returns:
            InvokeResult with response data
        """
        runner_config = self._to_runner_config(common_config, strategy_config)
        return self.runner.invoke(runner_config, payload, headers, stream)

    def status(
        self, common_config: CommonConfig, strategy_config: LocalStrategyConfig
    ) -> StatusResult:
        """
        Query the service status.

        Returns:
            StatusResult with current container status
        """
        runner_config = self._to_runner_config(common_config, strategy_config)
        return self.runner.status(runner_config)

    def stop(
        self, common_config: CommonConfig, strategy_config: LocalStrategyConfig
    ) -> bool:
        """
        Stop the container without destroying it.

        Returns:
            True if stop was successful, False otherwise
        """
        runner_config = self._to_runner_config(common_config, strategy_config)
        return self.runner.stop(runner_config)

    def destroy(
        self,
        common_config: CommonConfig,
        strategy_config: LocalStrategyConfig,
        force: bool = False,
    ) -> bool:
        """
        Destroy the container and related resources.

        Args:
            force: Force destruction even if container is running

        Returns:
            True if destruction was successful, False otherwise
        """
        runner_config = self._to_runner_config(common_config, strategy_config)
        return self.runner.destroy(runner_config)

    def _to_builder_config(
        self, common_config: CommonConfig, strategy_config: LocalStrategyConfig
    ) -> LocalDockerBuilderConfig:
        """
        Convert configuration to builder format.

        Centralizes configuration mapping and allows overriding with CLI options.
        """
        # Retrieve Docker build config from manager (contains CLI runtime options)
        docker_build_config = None
        if self.config_manager:
            docker_build_config = self.config_manager.get_docker_build_config()

        return LocalDockerBuilderConfig(
            common_config=common_config,
            image_name=common_config.agent_name or "agentkit-app",
            image_tag=strategy_config.image_tag,
            docker_build_config=docker_build_config,
        )

    def _to_runner_config(
        self, common_config: CommonConfig, strategy_config: LocalStrategyConfig
    ) -> LocalDockerRunnerConfig:
        """
        Convert configuration to runner format.

        Centralizes configuration mapping and merges environment variables from
        both application and strategy levels with veADK compatibility.
        """
        # Get project directory from config manager if available
        project_dir = None
        if self.config_manager:
            project_dir = self.config_manager.get_project_dir()

        merged_envs = merge_runtime_envs(
            common_config, strategy_config.to_dict(), project_dir
        )

        return LocalDockerRunnerConfig(
            common_config=common_config,
            full_image_name=strategy_config.full_image_name,
            container_name=strategy_config.container_name,
            container_id=strategy_config.container_id,
            ports=strategy_config.ports,
            volumes=strategy_config.volumes,
            environment=merged_envs,
            invoke_port=strategy_config.invoke_port,
        )
