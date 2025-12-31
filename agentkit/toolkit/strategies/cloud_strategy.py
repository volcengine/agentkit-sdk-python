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
Cloud Strategy - VE Agentkit orchestration

Pure orchestration logic that delegates to VeCPCRBuilder and VeAgentkitRunner.
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
    AUTO_CREATE_VE,
    CommonConfig,
    CloudStrategyConfig,
    merge_runtime_envs,
)
from agentkit.toolkit.config.region_resolver import RegionConfigResolver
from agentkit.toolkit.builders.ve_pipeline import VeCPCRBuilder, VeCPCRBuilderConfig
from agentkit.toolkit.runners.ve_agentkit import (
    VeAgentkitRuntimeRunner,
    VeAgentkitRunnerConfig,
)
from agentkit.utils.misc import generate_runtime_name


class CloudStrategy(Strategy):
    """
    Cloud orchestration strategy using VE Agentkit.

    Orchestration flow:
    1. build: VeCPCRBuilder.build() → BuildResult
    2. deploy: VeAgentkitRunner.deploy() → DeployResult
    3. invoke: VeAgentkitRunner.invoke() → InvokeResult
    4. status: VeAgentkitRunner.status() → StatusResult

    Characteristics:
    - Pure orchestration with no side effects
    - Directly returns Builder/Runner results
    - Exceptions propagate to Executor layer for handling
    """

    # Cloud mode required services:
    # - build: cr (Container Registry), tos (Object Storage), cp (Code Pipeline)
    # - deploy: vefaas (Function Service), ark (Model Service), apmplus_server (APM), id (Identity)
    REQUIRED_SERVICES = {
        "build": ["cr", "cp"],
        "deploy": ["vefaas", "ark", "apmplus_server", "id", "vikingdb", "mem0", "apig"],
    }

    def __init__(self, config_manager=None, reporter=None):
        """
        Initialize CloudStrategy.

        Args:
            config_manager: Configuration manager (optional).
            reporter: Reporter instance to pass to Builder/Runner.
        """
        super().__init__(config_manager, reporter)

        # Lazy initialization to avoid requiring environment variables at init time
        self._builder = None
        self._runner = None

    @property
    def builder(self):
        """Lazy-load VeCPCRBuilder instance."""
        if self._builder is None:
            project_dir = None
            if self.config_manager:
                project_dir = self.config_manager.get_project_dir()

            self._builder = VeCPCRBuilder(
                project_dir=project_dir, reporter=self.reporter
            )
        return self._builder

    @property
    def runner(self):
        """Lazy-load VeAgentkitRuntimeRunner instance."""
        if self._runner is None:
            self._runner = VeAgentkitRuntimeRunner(reporter=self.reporter)
        return self._runner

    def build(
        self, common_config: CommonConfig, strategy_config: CloudStrategyConfig
    ) -> BuildResult:
        """
        Execute cloud build orchestration.

        Steps:
        1. Prepare runtime name (auto-generate if needed)
        2. Convert configuration to builder format
        3. Call VeCPCRBuilder.build()
        4. Extract and track configuration updates from build result
        """
        from agentkit.toolkit.models import ConfigUpdates

        config_updates = ConfigUpdates()

        # Auto-generate runtime name if not explicitly set
        runtime_name, cp_pipeline_name = self._prepare_runtime_name(
            strategy_config.runtime_name, common_config.agent_name
        )

        # Track generated names if they differ from config
        if runtime_name != strategy_config.runtime_name:
            config_updates.add("runtime_name", runtime_name)
        if cp_pipeline_name != strategy_config.cp_pipeline_name:
            config_updates.add("cp_pipeline_name", cp_pipeline_name)

        # Convert to builder config with prepared values
        builder_config = self._to_builder_config(
            common_config,
            strategy_config,
            runtime_name_override=runtime_name,
            cp_pipeline_name_override=cp_pipeline_name,
        )

        result = self.builder.build(builder_config)

        # Extract build outputs from metadata
        if result.success and result.metadata:
            if "cr_image_url" in result.metadata:
                config_updates.add("cr_image_full_url", result.metadata["cr_image_url"])
            if "cp_pipeline_id" in result.metadata:
                config_updates.add("cp_pipeline_id", result.metadata["cp_pipeline_id"])

        result.config_updates = config_updates if config_updates.has_updates() else None
        return result

    def deploy(
        self, common_config: CommonConfig, strategy_config: CloudStrategyConfig
    ) -> DeployResult:
        """
        Execute cloud deployment orchestration.

        Steps:
        1. Convert configuration to runner format
        2. Call VeAgentkitRunner.deploy()
        3. Extract and track configuration updates from deployment result
        """
        from agentkit.toolkit.models import ConfigUpdates

        runner_config = self._to_runner_config(common_config, strategy_config)
        result = self.runner.deploy(runner_config)

        # Extract deployment outputs from result
        config_updates = ConfigUpdates()
        if result.success:
            if result.service_id:
                config_updates.add("runtime_id", result.service_id)
            if result.endpoint_url:
                config_updates.add("runtime_endpoint", result.endpoint_url)
            if result.metadata:
                if "runtime_apikey" in result.metadata:
                    config_updates.add(
                        "runtime_apikey", result.metadata["runtime_apikey"]
                    )
                if "runtime_name" in result.metadata:
                    config_updates.add("runtime_name", result.metadata["runtime_name"])
                if "runtime_apikey_name" in result.metadata:
                    config_updates.add(
                        "runtime_apikey_name", result.metadata["runtime_apikey_name"]
                    )
                if "runtime_role_name" in result.metadata:
                    config_updates.add(
                        "runtime_role_name", result.metadata["runtime_role_name"]
                    )

        result.config_updates = config_updates if config_updates.has_updates() else None
        return result

    def invoke(
        self,
        common_config: CommonConfig,
        strategy_config: CloudStrategyConfig,
        payload: Any,
        headers: Optional[dict] = None,
        stream: Optional[bool] = None,
    ) -> InvokeResult:
        """
        Execute service invocation.

        Steps:
        1. Convert configuration to runner format
        2. Call VeAgentkitRunner.invoke()
        """
        runner_config = self._to_runner_config(common_config, strategy_config)
        return self.runner.invoke(runner_config, payload, headers, stream)

    def status(
        self, common_config: CommonConfig, strategy_config: CloudStrategyConfig
    ) -> StatusResult:
        """
        Query service status.

        Steps:
        1. Convert configuration to runner format
        2. Call VeAgentkitRunner.status()
        """
        runner_config = self._to_runner_config(common_config, strategy_config)
        return self.runner.status(runner_config)

    def destroy(
        self,
        common_config: CommonConfig,
        strategy_config: CloudStrategyConfig,
        force: bool = False,
    ) -> bool:
        """
        Destroy cloud runtime.

        Steps:
        1. Convert configuration to runner format
        2. Call VeAgentkitRunner.destroy()
        """
        runner_config = self._to_runner_config(common_config, strategy_config)
        return self.runner.destroy(runner_config)

    def _prepare_runtime_name(
        self, current_runtime_name: str, agent_name: str
    ) -> tuple[str, str]:
        """
        Prepare runtime and pipeline names.

        Auto-generates names if not explicitly set. CP Pipeline name must match
        Runtime name to maintain consistency in cloud deployment.

        Args:
            current_runtime_name: Current runtime name from config.
            agent_name: Agent name used for auto-generation.

        Returns:
            (runtime_name, cp_pipeline_name): Prepared names.
        """
        # Auto-generate if not explicitly set
        if current_runtime_name == AUTO_CREATE_VE or current_runtime_name == "":
            runtime_name = generate_runtime_name(agent_name)
        else:
            runtime_name = current_runtime_name

        # CP Pipeline name must match runtime name for cloud consistency
        cp_pipeline_name = runtime_name

        return runtime_name, cp_pipeline_name

    def _to_builder_config(
        self,
        common_config: CommonConfig,
        strategy_config: CloudStrategyConfig,
        runtime_name_override: str = None,
        cp_pipeline_name_override: str = None,
    ) -> VeCPCRBuilderConfig:
        """
        Convert VeAgentkitConfig to VeCPCRBuilderConfig.

        Centralizes configuration mapping to keep orchestration logic clear.
        Allows overriding runtime and pipeline names for auto-generated values.

        Args:
            common_config: Common configuration.
            strategy_config: Strategy configuration.
            runtime_name_override: Override runtime_name if provided.
            cp_pipeline_name_override: Override cp_pipeline_name if provided.
        """
        # Retrieve Docker build config from manager (contains CLI runtime options)
        docker_build_config = None
        if self.config_manager:
            docker_build_config = self.config_manager.get_docker_build_config()

        resolver = RegionConfigResolver.from_strategy_config(strategy_config)

        return VeCPCRBuilderConfig(
            common_config=common_config,
            cp_region=resolver.resolve("cp"),
            tos_bucket=strategy_config.tos_bucket,
            tos_region=resolver.resolve("tos"),
            tos_prefix=strategy_config.tos_prefix,
            cr_instance_name=strategy_config.cr_instance_name,
            cr_namespace_name=strategy_config.cr_namespace_name,
            cr_repo_name=strategy_config.cr_repo_name,
            cr_auto_create_instance_type=strategy_config.cr_auto_create_instance_type,
            cr_region=resolver.resolve("cr"),
            cp_workspace_name=strategy_config.cp_workspace_name,
            cp_pipeline_name=cp_pipeline_name_override
            or strategy_config.cp_pipeline_name,
            cp_pipeline_id=strategy_config.cp_pipeline_id,
            image_tag=strategy_config.image_tag,
            build_timeout=strategy_config.build_timeout,
            docker_build_config=docker_build_config,
        )

    def _to_runner_config(
        self, common_config: CommonConfig, strategy_config: CloudStrategyConfig
    ) -> VeAgentkitRunnerConfig:
        """
        Convert VeAgentkitConfig to VeAgentkitRunnerConfig.

        Centralizes configuration mapping to keep orchestration logic clear.
        Merges environment variables from common and strategy configs with veADK compatibility.
        """
        # Get project directory from config manager if available
        project_dir = None
        if self.config_manager:
            project_dir = self.config_manager.get_project_dir()

        merged_envs = merge_runtime_envs(
            common_config, strategy_config.to_dict(), project_dir
        )

        resolver = RegionConfigResolver.from_strategy_config(strategy_config)

        return VeAgentkitRunnerConfig(
            common_config=common_config,
            runtime_id=strategy_config.runtime_id,
            runtime_name=strategy_config.runtime_name,
            runtime_role_name=strategy_config.runtime_role_name,
            runtime_apikey=strategy_config.runtime_apikey,
            runtime_apikey_name=strategy_config.runtime_apikey_name,
            runtime_endpoint=strategy_config.runtime_endpoint,
            runtime_envs=merged_envs,
            runtime_auth_type=strategy_config.runtime_auth_type,
            runtime_jwt_discovery_url=strategy_config.runtime_jwt_discovery_url,
            runtime_jwt_allowed_clients=strategy_config.runtime_jwt_allowed_clients,
            image_url=strategy_config.cr_image_full_url,
            region=resolver.resolve("agentkit"),
        )
