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
Hybrid Strategy - Local build + cloud deployment orchestration.

Builds image locally, pushes to Container Registry, then deploys to VE Runtime.
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
    HybridStrategyConfig,
    merge_runtime_envs,
)
from agentkit.toolkit.builders.local_docker import (
    LocalDockerBuilder,
    LocalDockerBuilderConfig,
)
from agentkit.toolkit.runners.ve_agentkit import (
    VeAgentkitRuntimeRunner,
    VeAgentkitRunnerConfig,
)
from agentkit.toolkit.volcengine.services import CRService, CRServiceConfig
from agentkit.toolkit.models import ConfigUpdates
from agentkit.toolkit.config.region_resolver import RegionConfigResolver


class HybridStrategy(Strategy):
    """
    Hybrid orchestration strategy combining local build and cloud deployment.

    Orchestration flow:
    1. build: LocalDockerBuilder.build() → BuildResult
    2. push: Push image to Container Registry
    3. deploy: VeAgentkitRuntimeRunner.deploy() → DeployResult
    4. invoke: VeAgentkitRuntimeRunner.invoke() → InvokeResult
    5. status: VeAgentkitRuntimeRunner.status() → StatusResult

    Characteristics:
    - Combines local build speed with cloud deployment convenience
    - Pure orchestration with no side effects
    - Returns Builder/Runner results directly
    - Exceptions propagate to Executor for handling
    """

    # Hybrid mode required services:
    # - build: cr (Container Registry) for image push
    # - deploy: vefaas (Function Service), ark (Model Service), apmplus_server (APM), id (Identity)
    REQUIRED_SERVICES = {
        "build": ["cr"],
        "deploy": ["vefaas", "ark", "apmplus_server", "id", "vikingdb", "mem0", "apig"],
    }

    def __init__(self, config_manager=None, reporter=None):
        """
        Initialize HybridStrategy.

        Args:
            config_manager: Configuration manager (optional).
            reporter: Reporter instance (passed to Builder/Runner).
        """
        super().__init__(config_manager, reporter)

        # Lazy initialization to avoid requiring environment variables at init time
        self._builder = None
        self._runner = None

    @property
    def builder(self):
        """Lazy-load Builder instance."""
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
        """Lazy-load Runner instance."""
        if self._runner is None:
            self._runner = VeAgentkitRuntimeRunner(reporter=self.reporter)
        return self._runner

    def build(
        self, common_config: CommonConfig, strategy_config: HybridStrategyConfig
    ) -> BuildResult:
        """
        Execute hybrid build (local build + push to Container Registry).

        Orchestration steps:
        1. Build image locally
        2. Prepare CR configuration (without modifying config object)
        3. Push to CR if configuration is valid
        4. Return BuildResult with ConfigUpdates
        """

        config_updates = ConfigUpdates()

        builder_config = self._to_builder_config(common_config, strategy_config)
        result = self.builder.build(builder_config)

        if not result.success:
            return result

        cr_repo_name = self._prepare_cr_config(
            strategy_config.cr_repo_name, common_config.agent_name
        )
        if cr_repo_name != strategy_config.cr_repo_name:
            config_updates.add("cr_repo_name", cr_repo_name)

        should_push, reason = self._should_push_to_cr(strategy_config, cr_repo_name)
        if should_push:
            cr_updates = self._handle_cr_push(
                common_config, result, strategy_config, cr_repo_name
            )
            config_updates.merge(cr_updates)
        else:
            self._report_cr_skip_reason(reason, strategy_config)

        # Persist local build metadata
        if result.build_timestamp:
            config_updates.add("build_timestamp", result.build_timestamp.isoformat())
        if result.image:
            config_updates.add("full_image_name", result.image.full_name)
            if getattr(result.image, "digest", None):
                config_updates.add("image_id", result.image.digest)

        result.config_updates = config_updates if config_updates.has_updates() else None
        return result

    def deploy(
        self, common_config: CommonConfig, strategy_config: HybridStrategyConfig
    ) -> DeployResult:
        """
        Execute hybrid deployment to VE Runtime.

        Orchestration steps:
        1. Validate CR image URL
        2. Convert configuration
        3. Call VeAgentkitRuntimeRunner.deploy()
        4. Return DeployResult with ConfigUpdates
        """

        validation_result = self._validate_cr_image_url(strategy_config)
        if not validation_result.success:
            return validation_result

        runner_config = self._to_runner_config(common_config, strategy_config)

        result = self.runner.deploy(runner_config)

        # Extract and track configuration updates from deployment result
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
        strategy_config: HybridStrategyConfig,
        payload: Any,
        headers: Optional[dict] = None,
        stream: Optional[bool] = None,
    ) -> InvokeResult:
        """
        Invoke the deployed service.

        Orchestration steps:
        1. Convert configuration
        2. Call VeAgentkitRuntimeRunner.invoke()
        3. Return InvokeResult directly
        """
        runner_config = self._to_runner_config(common_config, strategy_config)
        return self.runner.invoke(runner_config, payload, headers, stream)

    def status(
        self, common_config: CommonConfig, strategy_config: HybridStrategyConfig
    ) -> StatusResult:
        """
        Query service status.

        Orchestration steps:
        1. Convert configuration
        2. Call VeAgentkitRuntimeRunner.status()
        3. Return StatusResult directly
        """
        runner_config = self._to_runner_config(common_config, strategy_config)
        return self.runner.status(runner_config)

    def destroy(
        self,
        common_config: CommonConfig,
        strategy_config: HybridStrategyConfig,
        force: bool = False,
    ) -> bool:
        """
        Destroy the VE Runtime.

        Orchestration steps:
        1. Convert configuration
        2. Call VeAgentkitRuntimeRunner.destroy()
        """
        runner_config = self._to_runner_config(common_config, strategy_config)
        success = self.runner.destroy(runner_config)
        return success

    def _prepare_cr_config(self, current_cr_repo_name: str, agent_name: str) -> str:
        """
        Prepare CR configuration by auto-filling repository name if needed.

        Args:
            current_cr_repo_name: Current CR repository name.
            agent_name: Agent name to use as default.

        Returns:
            Prepared CR repository name.
        """
        if not current_cr_repo_name:
            return agent_name or "agentkit-app"
        return current_cr_repo_name

    def _should_push_to_cr(
        self, strategy_config: HybridStrategyConfig, cr_repo_name: str
    ) -> tuple:
        """
        Determine whether to push image to Container Registry.

        Args:
            strategy_config: Strategy configuration.
            cr_repo_name: Prepared CR repository name.

        Returns:
            Tuple of (should_push: bool, reason: str).
        """
        # Validate instance name
        if not strategy_config.cr_instance_name:
            return False, "CR instance name is empty"
        if strategy_config.cr_instance_name == AUTO_CREATE_VE:
            return False, "CR instance name is 'Auto'"
        if "{{" in (strategy_config.cr_instance_name or ""):
            return False, "CR instance name contains unrendered template variables"

        # Validate namespace name
        if not strategy_config.cr_namespace_name:
            return False, "CR namespace name is empty"
        if strategy_config.cr_namespace_name == AUTO_CREATE_VE:
            return False, "CR namespace name is 'Auto'"
        if "{{" in (strategy_config.cr_namespace_name or ""):
            return False, "CR namespace name contains unrendered template variables"

        if not cr_repo_name:
            return False, "CR repository name is empty"

        return True, ""

    def _handle_cr_push(
        self,
        common_config: CommonConfig,
        result: BuildResult,
        strategy_config: HybridStrategyConfig,
        cr_repo_name: str,
    ) -> "ConfigUpdates":
        """
        Handle pushing image to Container Registry.

        Steps:
        1. Push image to CR
        2. Update result.metadata with CR image URL
        3. Return ConfigUpdates for configuration tracking
        4. Report success message

        Args:
            result: Build result containing local image.
            strategy_config: Strategy configuration.
            cr_repo_name: Prepared CR repository name.

        Returns:
            ConfigUpdates object with CR image URL.
        """
        config_updates = ConfigUpdates()

        # Use image_id (SHA) from build result for pushing
        image_id = result.image.digest if result.image else None
        if not image_id:
            return config_updates

        # Ensure CR resources exist (instance/namespace/repo)
        resolver = RegionConfigResolver.from_strategy_config(strategy_config)

        cr_cfg = CRServiceConfig(
            instance_name=strategy_config.cr_instance_name,
            namespace_name=strategy_config.cr_namespace_name,
            repo_name=cr_repo_name,
            auto_create_instance_type=strategy_config.cr_auto_create_instance_type,
            region=resolver.resolve("cr"),
        )
        cr_service = CRService(reporter=self.reporter)
        ensure_result = cr_service.ensure_cr_resources(
            cr_cfg, common_config=common_config
        )
        if not ensure_result.success:
            raise Exception(ensure_result.error or "Failed to ensure CR resources")

        # Ensure public endpoint is enabled for CR instance (controlled by global config)
        try:
            from agentkit.toolkit.config.global_config import get_global_config

            gc = get_global_config()
            do_check = getattr(
                getattr(gc, "defaults", None), "cr_public_endpoint_check", None
            )
        except Exception:
            do_check = None
        if do_check is False:
            self.reporter.info("Skipping CR public endpoint check per global config")
        else:
            public_result = cr_service.ensure_public_endpoint(cr_cfg)
            if not public_result.success:
                raise Exception(
                    public_result.error or "Failed to enable CR public endpoint"
                )

        # Write back any auto-created names to config
        if (
            ensure_result.instance_name
            and ensure_result.instance_name != strategy_config.cr_instance_name
        ):
            config_updates.add("cr_instance_name", ensure_result.instance_name)
        if (
            ensure_result.namespace_name
            and ensure_result.namespace_name != strategy_config.cr_namespace_name
        ):
            config_updates.add("cr_namespace_name", ensure_result.namespace_name)
        if ensure_result.repo_name and ensure_result.repo_name != cr_repo_name:
            config_updates.add("cr_repo_name", ensure_result.repo_name)

        # Push image (inline call to CRService.login_and_push_image)
        self.reporter.info(
            f"Pushing image to CR: {cr_cfg.instance_name}/{cr_cfg.namespace_name}/{cr_cfg.repo_name}:{strategy_config.image_tag}"
        )
        success, push_result = cr_service.login_and_push_image(
            cr_config=cr_cfg,
            image_id=image_id,
            image_tag=strategy_config.image_tag,
            namespace=cr_cfg.namespace_name,
        )
        if not success:
            raise Exception(f"Image push failed: {push_result}")
        cr_image_url = push_result

        config_updates.add("cr_image_full_url", cr_image_url)

        if not result.metadata:
            result.metadata = {}
        result.metadata["cr_image_url"] = cr_image_url

        self.reporter.success(f"CR image URL: {cr_image_url}")

        return config_updates

    def _report_cr_skip_reason(
        self, reason: str, strategy_config: HybridStrategyConfig
    ) -> None:
        """Report reason for skipping CR push."""
        if "{{" in (strategy_config.cr_instance_name or "") or "{{" in (
            strategy_config.cr_namespace_name or ""
        ):
            self.reporter.warning("CR names contain unrendered template variables")
            self.reporter.warning(
                "Ensure Volcengine AK/SK are configured and STS can fetch account_id for template rendering."
            )
        elif strategy_config.cr_instance_name == AUTO_CREATE_VE:
            self.reporter.warning("CR instance name is 'Auto', skipping push to CR")
            self.reporter.warning(
                "Use 'agentkit config' to configure a valid CR instance name"
            )
        else:
            self.reporter.warning(
                f"Invalid CR configuration, skipping push to CR: {reason}"
            )

    def _validate_cr_image_url(
        self, strategy_config: HybridStrategyConfig
    ) -> DeployResult:
        """
        Validate CR image URL is available.

        Hybrid mode requires a CR image. Returns failure if no valid CR image URL exists.
        """
        image_url = strategy_config.cr_image_full_url

        if image_url:
            return DeployResult(success=True)

        from agentkit.toolkit.errors import ErrorCode

        if "{{" in (strategy_config.cr_instance_name or "") or "{{" in (
            strategy_config.cr_namespace_name or ""
        ):
            error_msg = "CR names contain unrendered template variables. Ensure Volcengine AK/SK are configured and STS can fetch account_id."
            error_code = ErrorCode.CONFIG_INVALID
        elif (
            strategy_config.cr_instance_name == AUTO_CREATE_VE
            or not strategy_config.cr_instance_name
        ):
            error_msg = (
                f"Hybrid mode requires valid CR configuration. Current cr_instance_name='{strategy_config.cr_instance_name}' is invalid.\n"
                f"Use 'agentkit config' to configure a valid CR instance name, or switch to local/cloud mode."
            )
            error_code = ErrorCode.CONFIG_INVALID
        else:
            error_msg = "CR image URL not found. Run 'agentkit build' to build and push the image to CR."
            error_code = ErrorCode.RESOURCE_NOT_FOUND

        return DeployResult(success=False, error=error_msg, error_code=error_code)

    def _to_builder_config(
        self, common_config: CommonConfig, strategy_config: HybridStrategyConfig
    ) -> LocalDockerBuilderConfig:
        """
        Convert HybridStrategyConfig to LocalDockerBuilderConfig.
        """
        # Retrieve Docker build config from manager (contains CLI runtime options)
        docker_build_config = None
        if self.config_manager:
            try:
                docker_build_config = self.config_manager.get_docker_build_config()
            except Exception:
                docker_build_config = None
        return LocalDockerBuilderConfig(
            common_config=common_config,
            image_name=common_config.agent_name or "agentkit-app",
            image_tag=strategy_config.image_tag,
            docker_build_config=docker_build_config,
        )

    def _to_runner_config(
        self, common_config: CommonConfig, strategy_config: HybridStrategyConfig
    ) -> VeAgentkitRunnerConfig:
        """
        Convert HybridStrategyConfig to VeAgentkitRunnerConfig with veADK compatibility.
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
            runtime_id=strategy_config.runtime_id or AUTO_CREATE_VE,
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

    # _push_to_cr removed: logic is handled inline within _handle_cr_push
