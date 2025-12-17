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

import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from agentkit.utils.misc import generate_random_id
from agentkit.platform import (
    VolcConfiguration,
)
import agentkit.toolkit.volcengine.cr as ve_cr
import agentkit.toolkit.config as config
from agentkit.toolkit.config import AUTO_CREATE_VE, DEFAULT_CR_INSTANCE_TEMPLATE_NAME
from agentkit.toolkit.config.dataclass_utils import AutoSerializableMixin
from agentkit.toolkit.reporter import Reporter
from agentkit.toolkit.context import ExecutionContext
import time

logger = logging.getLogger(__name__)


@dataclass
class CRServiceConfig(AutoSerializableMixin):
    """Configuration for Container Registry service."""

    instance_name: str = AUTO_CREATE_VE
    namespace_name: str = AUTO_CREATE_VE
    repo_name: str = AUTO_CREATE_VE
    region: str = "cn-beijing"
    auto_create_instance_type: str = (
        "Micro"  # Instance type when auto-creating: "Micro" or "Enterprise"
    )
    vpc_id: str = field(default=AUTO_CREATE_VE, metadata={"system": True})
    subnet_id: str = field(default=AUTO_CREATE_VE, metadata={"system": True})
    image_full_url: str = field(default=None, metadata={"system": True})


@dataclass
class CRServiceResult:
    """Result of Container Registry service operations."""

    success: bool = False
    error: Optional[str] = None
    instance_name: Optional[str] = None
    namespace_name: Optional[str] = None
    repo_name: Optional[str] = None
    registry_url: Optional[str] = None
    image_full_url: Optional[str] = None


class CRErrorHandler:
    """Unified error handler for Container Registry operations.

    Provides two handlers based on operation type (not name source):
    - handle_create_error: For resource creation operations
    - handle_reuse_error: For reusing existing resources
    """

    @staticmethod
    def is_quota_exceeded(error: Exception) -> bool:
        return "QuotaExceeded" in str(error)

    @staticmethod
    def is_already_exists(error: Exception) -> bool:
        return "AlreadyExists" in str(error)

    @staticmethod
    def is_insufficient_balance(error: Exception) -> bool:
        return "Insufficient.Balance" in str(error)

    @staticmethod
    def handle_create_error(
        error: Exception,
        resource_type: str,
        result: CRServiceResult,
        reporter: Reporter,
    ) -> bool:
        """Handle errors during resource creation.

        Used for any creation operation, whether the name is auto-generated
        or user-specified.

        Args:
            error: The exception object.
            resource_type: Type of resource (e.g., "instance", "namespace", "repository").
            result: Result object to store error information.
            reporter: Reporter interface for logging.

        Returns:
            False to indicate creation failure and stop further processing.
        """
        if CRErrorHandler.is_quota_exceeded(error):
            result.error = (
                f"Failed to create CR {resource_type}: account quota exceeded.\n"
            )
            result.error += "  Note: Micro and Enterprise instance quotas are calculated separately.\n"
            result.error += "  To use existing resources(e.g. CR instance, namespace, repository), you can:\n"
            result.error += "    - Run: agentkit config (interactive mode)\n"
            result.error += "    - Run: agentkit config --cr_instance_name <your-instance> (non-interactive mode)\n"
            result.error += "    - Edit: ~/.agentkit/config.yaml (global) or agentkit.yaml (local) directly"
        elif CRErrorHandler.is_insufficient_balance(error):
            result.error = f"Failed to create CR {resource_type}: insufficient balance. Please ensure that you have enough balance in your account to create a container registry instance."
        elif CRErrorHandler.is_already_exists(error):
            result.error = f"Failed to create CR {resource_type}: name already taken. Please choose a different name."
        else:
            result.error = f"Failed to create CR {resource_type}: {str(error)}"
        return False

    @staticmethod
    def handle_reuse_error(
        error: Exception,
        resource_type: str,
        resource_name: str,
        result: CRServiceResult,
        reporter: Reporter,
    ) -> bool:
        """Handle errors when checking/reusing existing resources.

        Args:
            error: The exception object.
            resource_type: Type of resource.
            resource_name: Name of the resource.
            result: Result object to store error information.
            reporter: Reporter interface for logging.

        Returns:
            True if resource exists and can be reused, False otherwise.
        """
        if CRErrorHandler.is_already_exists(error):
            reporter.success(f"CR {resource_type} already exists: {resource_name}")
            return True

        result.error = (
            f"Failed to access CR {resource_type} '{resource_name}': {str(error)}"
        )
        reporter.error(result.error)
        return False


class CRConfigCallback:
    """Interface for Container Registry configuration updates."""

    def on_config_update(self, cr_config: Dict[str, Any]) -> None:
        pass


class DefaultCRConfigCallback(CRConfigCallback):
    """Default implementation of CR configuration callback."""

    def __init__(self, config_updater=None):
        self.config_updater = config_updater

    def on_config_update(self, cr_config: Dict[str, Any]) -> None:
        """Notify config updater of CR configuration changes."""
        if self.config_updater:
            self.config_updater("cr_service", cr_config)


class CRService:
    """Unified Container Registry service for resource management."""

    def __init__(
        self,
        config_callback: Optional[CRConfigCallback] = None,
        reporter: Optional[Reporter] = None,
    ):
        """Initialize the Container Registry service.

        Args:
            config_callback: Callback for configuration updates.
            reporter: Reporter interface for logging. If None, uses Reporter from ExecutionContext.
        """
        self.config_callback = config_callback or DefaultCRConfigCallback()
        self.reporter = (
            reporter if reporter is not None else ExecutionContext.get_reporter()
        )
        self._vecr_client = None
        self._init_client()

    def _init_client(self, region: Optional[str] = None) -> None:
        """Initialize the CR client with credentials from environment.

        Args:
            region: Optional region override.
        """
        try:
            if region and isinstance(region, str):
                region = region.strip() or None

            config = VolcConfiguration(region=region)
            creds = config.get_service_credentials("cr")
            endpoint = config.get_service_endpoint("cr")

            self._vecr_client = ve_cr.VeCR(
                access_key=creds.access_key,
                secret_key=creds.secret_key,
                region=endpoint.region,
            )
            # Expose the actual region resolved by VolcConfiguration
            self.actual_region = endpoint.region

        except Exception as e:
            logger.error(f"Failed to initialize CR client: {str(e)}")
            raise

    def ensure_cr_resources(
        self,
        cr_config: CRServiceConfig,
        common_config: Optional[config.CommonConfig] = None,
    ) -> CRServiceResult:
        """Ensure all required CR resources exist or are created.

        Creates instance, namespace, and repository as needed, then retrieves the registry URL.

        Args:
            cr_config: Container Registry service configuration.
            common_config: Common configuration (used to retrieve agent_name, etc.).

        Returns:
            CRServiceResult: Operation result with resource details and registry URL.
        """
        try:
            if getattr(cr_config, "region", None):
                self._init_client(region=cr_config.region)

            result = CRServiceResult()

            if not self._ensure_cr_instance(cr_config, result):
                return result

            if not self._ensure_cr_namespace(cr_config, result):
                return result

            if not self._ensure_cr_repo(cr_config, result, common_config):
                return result

            registry_url = self._vecr_client._get_default_domain(
                instance_name=cr_config.instance_name
            )
            result.registry_url = registry_url

            result.success = True
            return result

        except Exception as e:
            result.error = f"Failed to ensure CR resources: {str(e)}"
            logger.error(result.error)
            return result

    def _ensure_cr_instance(
        self, cr_config: CRServiceConfig, result: CRServiceResult
    ) -> bool:
        """Ensure a CR instance exists, creating one if needed."""
        instance_name = cr_config.instance_name

        if not instance_name or instance_name == AUTO_CREATE_VE:
            # Auto-generate instance name when not configured
            instance_name = CRService.generate_cr_instance_name()
            self.reporter.info(
                f"No CR instance configured. Creating new {cr_config.auto_create_instance_type} instance: {instance_name}"
            )

            try:
                created_instance = self._vecr_client._create_instance(
                    instance_name, instance_type=cr_config.auto_create_instance_type
                )
                cr_config.instance_name = created_instance
                result.instance_name = created_instance
                self._notify_config_update(cr_config)
                self.reporter.success(f"CR instance created: {created_instance}")
            except Exception as e:
                return CRErrorHandler.handle_create_error(
                    e, "instance", result, self.reporter
                )
        else:
            # Use user-specified instance name
            try:
                status = self._vecr_client._check_instance(instance_name)

                if status == "NONEXIST":
                    # Instance doesn't exist, create it
                    self.reporter.warning(
                        f"CR instance does not exist. Creating {cr_config.auto_create_instance_type} instance: {instance_name}"
                    )
                    try:
                        self._vecr_client._create_instance(
                            instance_name,
                            instance_type=cr_config.auto_create_instance_type,
                        )
                        self.reporter.success(f"CR instance created: {instance_name}")
                    except Exception as e:
                        return CRErrorHandler.handle_create_error(
                            e, "instance", result, self.reporter
                        )
                elif status == "Running":
                    self.reporter.success(
                        f"CR instance exists and is running: {instance_name}"
                    )
                else:
                    self.reporter.warning(
                        f"CR instance status: {status}. Waiting for it to be ready..."
                    )

            except Exception as e:
                # Error during status check (not creation)
                if not CRErrorHandler.handle_reuse_error(
                    e, "instance", instance_name, result, self.reporter
                ):
                    return False

        result.instance_name = cr_config.instance_name
        return True

    def _ensure_cr_namespace(
        self, cr_config: CRServiceConfig, result: CRServiceResult
    ) -> bool:
        """Ensure a CR namespace exists, creating one if needed."""
        namespace_name = cr_config.namespace_name

        if not namespace_name or namespace_name == AUTO_CREATE_VE:
            # Auto-generate namespace name with random suffix
            namespace_name = f"agentkit-{generate_random_id(4)}"
            self.reporter.info(
                f"No CR namespace configured. Creating new namespace: {namespace_name}"
            )

            try:
                created_namespace = self._vecr_client._create_namespace(
                    cr_config.instance_name, namespace_name
                )
                cr_config.namespace_name = created_namespace
                result.namespace_name = created_namespace
                self._notify_config_update(cr_config)
                self.reporter.success(f"CR namespace created: {created_namespace}")
            except Exception as e:
                return CRErrorHandler.handle_create_error(
                    e, "namespace", result, self.reporter
                )
        else:
            # Use user-specified namespace name
            try:
                self._vecr_client._create_namespace(
                    cr_config.instance_name, namespace_name
                )
                self.reporter.success(f"CR namespace created: {namespace_name}")
            except Exception as e:
                # AlreadyExists means reuse success, other errors are creation failures
                if CRErrorHandler.is_already_exists(e):
                    self.reporter.success(
                        f"CR namespace already exists: {namespace_name}"
                    )
                else:
                    return CRErrorHandler.handle_create_error(
                        e, "namespace", result, self.reporter
                    )

        result.namespace_name = cr_config.namespace_name
        return True

    def _ensure_cr_repo(
        self,
        cr_config: CRServiceConfig,
        result: CRServiceResult,
        common_config: Optional[config.CommonConfig] = None,
    ) -> bool:
        """Ensure a CR repository exists, creating one if needed."""
        repo_name = cr_config.repo_name

        if not repo_name or repo_name == AUTO_CREATE_VE:
            # Auto-generate repository name based on agent name
            agent_name = common_config.agent_name if common_config else "agentkit"
            repo_name = f"{agent_name}-{generate_random_id(4)}"
            self.reporter.info(
                f"No CR repository configured. Creating new repository: {repo_name}"
            )

            try:
                created_repo = self._vecr_client._create_repo(
                    cr_config.instance_name, cr_config.namespace_name, repo_name
                )
                cr_config.repo_name = created_repo
                result.repo_name = created_repo
                self._notify_config_update(cr_config)
                self.reporter.success(f"CR repository created: {created_repo}")
            except Exception as e:
                return CRErrorHandler.handle_create_error(
                    e, "repository", result, self.reporter
                )
        else:
            # Use user-specified repository name
            try:
                self._vecr_client._create_repo(
                    cr_config.instance_name, cr_config.namespace_name, repo_name
                )
                self.reporter.success(f"CR repository created: {repo_name}")
            except Exception as e:
                # AlreadyExists means reuse success, other errors are creation failures
                if CRErrorHandler.is_already_exists(e):
                    self.reporter.success(f"CR repository already exists: {repo_name}")
                else:
                    return CRErrorHandler.handle_create_error(
                        e, "repository", result, self.reporter
                    )

        result.repo_name = cr_config.repo_name
        return True

    def ensure_public_endpoint(self, cr_config: CRServiceConfig) -> CRServiceResult:
        if getattr(cr_config, "region", None):
            self._init_client(region=cr_config.region)
        result = CRServiceResult()
        try:
            public_endpoint = self._vecr_client._get_public_endpoint(
                instance_name=cr_config.instance_name
            )
            if not public_endpoint["Enabled"]:
                self.reporter.warning(
                    "CR public endpoint is not enabled. Enabling now..."
                )
                self._vecr_client._update_public_endpoint(
                    instance_name=cr_config.instance_name, enabled=True
                )
                self._vecr_client._create_endpoint_acl_policies(
                    instance_name=cr_config.instance_name, acl_policies=["0.0.0.0/0"]
                )

                # Wait up to 120 seconds for the endpoint to be ready
                timeout = 120
                while timeout > 0:
                    public_endpoint = self._vecr_client._get_public_endpoint(
                        instance_name=cr_config.instance_name
                    )
                    if public_endpoint["Status"] == "Enabled":
                        break
                    timeout -= 1
                    time.sleep(1)
                if timeout <= 0:
                    result.error = (
                        "Timeout waiting for CR public endpoint to be enabled"
                    )
                    self.reporter.error(result.error)
                    return result
                self.reporter.success("CR public endpoint enabled successfully")

            result.success = True
            return result

        except Exception as e:
            result.error = f"Failed to configure public endpoint: {str(e)}"
            self.reporter.error(result.error)
            return result

    def login_and_push_image(
        self, cr_config: CRServiceConfig, image_id: str, image_tag: str, namespace: str
    ) -> Tuple[bool, str]:
        """Login to CR and push a Docker image to the registry.

        Args:
            cr_config: Container Registry service configuration.
            image_id: Local Docker image ID.
            image_tag: Tag for the remote image.
            namespace: Namespace in the registry.

        Returns:
            Tuple of (success: bool, remote_image_url_or_error_message: str).
        """
        if getattr(cr_config, "region", None):
            self._init_client(region=cr_config.region)
        try:
            from agentkit.toolkit.docker.container import DockerManager
        except ImportError:
            error_msg = "Docker dependencies are not installed"
            self.reporter.error(error_msg)
            return False, error_msg

        docker_manager = DockerManager()

        # Retrieve login credentials
        registry_url = self._vecr_client._get_default_domain(
            instance_name=cr_config.instance_name
        )
        username, token, expires = self._vecr_client._get_authorization_token(
            instance_name=cr_config.instance_name
        )
        self.reporter.success(
            f"Retrieved CR credentials: username={username}, expires={expires}"
        )

        # Login to registry
        success, message = docker_manager.login_to_registry(
            registry_url=registry_url, username=username, password=token
        )

        if not success:
            error_msg = f"Failed to login to CR: {message}"
            self.reporter.error(error_msg)
            return False, error_msg

        self.reporter.success("Successfully logged in to registry")

        # Push image
        self.reporter.info(f"Pushing image {image_id[:12]} to {registry_url}")
        success, remote_image_full_url = docker_manager.push_image(
            local_image=image_id,
            registry_url=registry_url,
            namespace=namespace,
            remote_image_name=cr_config.repo_name,
            remote_tag=image_tag,
        )

        if success:
            self.reporter.success(f"Image pushed successfully: {remote_image_full_url}")
            cr_config.image_full_url = remote_image_full_url
            self._notify_config_update(cr_config)
            return True, remote_image_full_url
        else:
            error_msg = f"Failed to push image: {remote_image_full_url}"
            self.reporter.error(error_msg)
            return False, error_msg

    def _notify_config_update(self, cr_config: CRServiceConfig) -> None:
        """Notify the config callback of CR configuration changes."""
        try:
            config_dict = cr_config.to_dict()
            self.config_callback.on_config_update(config_dict)
        except Exception as e:
            logger.warning(f"Failed to notify config update: {str(e)}")

    @staticmethod
    def generate_cr_instance_name() -> str:
        """Generate a CR instance name from the default template."""
        from agentkit.utils.template_utils import render_template

        cr_instance_name_template = DEFAULT_CR_INSTANCE_TEMPLATE_NAME
        rendered = render_template(cr_instance_name_template)
        return rendered
