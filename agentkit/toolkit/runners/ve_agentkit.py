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
import requests
import time
import os
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urljoin

from agentkit.toolkit.config import (
    CommonConfig,
    AUTO_CREATE_VE,
    AUTH_TYPE_KEY_AUTH,
    AUTH_TYPE_CUSTOM_JWT,
    is_valid_config,
    is_invalid_config,
)
from agentkit.toolkit.config.dataclass_utils import AutoSerializableMixin
from agentkit.toolkit.models import DeployResult, InvokeResult, StatusResult
from agentkit.toolkit.reporter import Reporter
from agentkit.toolkit.errors import ErrorCode
from agentkit.utils.misc import (
    generate_runtime_name,
    generate_runtime_role_name,
    generate_apikey_name,
    generate_client_token,
    calculate_nonlinear_progress,
    retry,
)
from agentkit.sdk.runtime.client import AgentkitRuntimeClient
from agentkit.toolkit.volcengine.iam import VeIAM
from .base import Runner

import agentkit.sdk.runtime.types as runtime_types

ARTIFACT_TYPE_DOCKER_IMAGE = "image"
API_KEY_LOCATION = "HEADER"
PROJECT_NAME_DEFAULT = "default"
RUNTIME_STATUS_READY = "Ready"
RUNTIME_STATUS_ERROR = "Error"
RUNTIME_STATUS_UPDATING = "Updating"
RUNTIME_STATUS_UNRELEASED = "UnReleased"

logger = logging.getLogger(__name__)


@dataclass
class VeAgentkitRunnerConfig(AutoSerializableMixin):
    """VeAgentkit Runtime configuration."""

    common_config: Optional[CommonConfig] = field(
        default=None, metadata={"system": True, "description": "Common configuration"}
    )

    # Runtime configuration
    runtime_id: str = field(
        default=AUTO_CREATE_VE,
        metadata={"description": "Runtime ID; 'Auto' means auto-create"},
    )
    runtime_name: str = field(
        default=AUTO_CREATE_VE,
        metadata={"description": "Runtime name; 'Auto' means auto-generate"},
    )
    runtime_role_name: str = field(
        default=AUTO_CREATE_VE,
        metadata={"description": "Runtime role name; 'Auto' means auto-create"},
    )
    runtime_apikey: str = field(default="", metadata={"description": "Runtime API key"})
    runtime_apikey_name: str = field(
        default=AUTO_CREATE_VE,
        metadata={"description": "Runtime API key name; 'Auto' means auto-generate"},
    )
    runtime_endpoint: str = field(
        default="", metadata={"description": "Runtime endpoint URL"}
    )
    runtime_envs: Dict[str, str] = field(
        default_factory=dict, metadata={"description": "Runtime environment variables"}
    )

    # Authentication configuration
    runtime_auth_type: str = field(
        default=AUTH_TYPE_KEY_AUTH,
        metadata={
            "description": "Runtime authentication type: 'key_auth' or 'custom_jwt'"
        },
    )
    runtime_jwt_discovery_url: str = field(
        default="", metadata={"description": "OIDC Discovery URL for JWT validation"}
    )
    runtime_jwt_allowed_clients: List[str] = field(
        default_factory=list, metadata={"description": "Allowed OAuth2 client IDs"}
    )

    # Container image configuration
    image_url: str = field(default="", metadata={"description": "Container image URL"})

    region: str = field(
        default="",
        metadata={
            "system": True,
            "description": "AgentKit service region",
        },
    )

    # Minimum instance count
    min_instance: int = field(
        default=1, metadata={"description": "Minimum number of Runtime instances"}
    )


# VeAgentkitDeployResult has been replaced by unified DeployResult
# Configuration class is retained for backward compatibility


class VeAgentkitRuntimeRunner(Runner):
    """VeAgentkit Runtime Runner.

    Manages the lifecycle of cloud-based Runtime instances, including:
    - Creating and managing Runtime instances
    - Deploying and updating Runtime configurations
    - Invoking Runtime services
    - Monitoring Runtime status
    - Cleaning up Runtime resources
    """

    def __init__(self, reporter: Optional[Reporter] = None):
        """Initialize VeAgentkitRuntimeRunner.

        Args:
            reporter: Progress reporter for deployment and runtime status. Defaults to SilentReporter (no output).

        Note:
            VeAgentkitRuntimeRunner only requires an image URL to deploy cloud-based Runtime;
            it does not require a local project directory.
        """
        super().__init__(reporter)
        self.agentkit_runtime_client = None

    def _get_runtime_client(self, region: str = "") -> AgentkitRuntimeClient:
        return AgentkitRuntimeClient(region=region or "")

    def deploy(self, config: VeAgentkitRunnerConfig) -> DeployResult:
        """Deploy Runtime.

        Args:
            config: Deployment configuration containing Runtime settings.

        Returns:
            DeployResult: Unified deployment result object.
        """
        try:
            runner_config = config

            if not runner_config.image_url:
                error_msg = "Image URL is required. Please build the image first."
                logger.error(error_msg)
                return DeployResult(
                    success=False, error=error_msg, error_code=ErrorCode.CONFIG_MISSING
                )

            # Prepare Runtime configuration
            if not self._prepare_runtime_config(runner_config):
                error_msg = "Failed to prepare Runtime configuration."
                logger.error(error_msg)
                return DeployResult(
                    success=False, error=error_msg, error_code=ErrorCode.CONFIG_INVALID
                )

            # Ensure IAM role exists for Runtime
            ve_iam = VeIAM(region=config.region)
            if not ve_iam.ensure_role_for_agentkit(runner_config.runtime_role_name):
                error_msg = "Failed to create or ensure Runtime IAM role."
                logger.error(error_msg)
                return DeployResult(
                    success=False,
                    error=error_msg,
                    error_code=ErrorCode.PERMISSION_DENIED,
                )

            # Deploy Runtime: create new or update existing
            if is_invalid_config(runner_config.runtime_id):
                return self._create_new_runtime(runner_config)
            else:
                return self._update_existing_runtime(runner_config)

        except Exception as e:
            error_msg = f"Runtime deployment failed: {str(e)}"
            logger.exception("Runtime deployment failed with exception")
            return DeployResult(
                success=False, error=error_msg, error_code=ErrorCode.DEPLOY_FAILED
            )

    def destroy(self, config: VeAgentkitRunnerConfig) -> bool:
        """Destroy Runtime instance.

        Args:
            config: Destroy configuration containing Runtime ID.

        Returns:
            True if successful, False otherwise.
        """
        try:
            runner_config = config

            if (
                not runner_config.runtime_id
                or runner_config.runtime_id == AUTO_CREATE_VE
            ):
                self.reporter.info("Runtime ID not configured, skipping destroy.")
                return True

            client = self._get_runtime_client(config.region)
            client.delete_runtime(
                runtime_types.DeleteRuntimeRequest(runtime_id=runner_config.runtime_id)
            )
            self.reporter.success(
                f"Runtime destroyed successfully: {runner_config.runtime_id}"
            )
            return True

        except Exception as e:
            if "InvalidAgentKitRuntime.NotFound" in str(e):
                self.reporter.info(
                    f"Runtime not found or already destroyed: {runner_config.runtime_id}"
                )
                return True
            logger.error(f"Failed to destroy Runtime: {str(e)}")
            return False

    def status(self, config: VeAgentkitRunnerConfig) -> StatusResult:
        """Get Runtime status.

        Args:
            config: Status query configuration containing Runtime ID.

        Returns:
            StatusResult: Unified status result object.
        """
        try:
            runner_config = config

            if (
                not runner_config.runtime_id
                or runner_config.runtime_id == AUTO_CREATE_VE
            ):
                return StatusResult(
                    success=True,
                    status="not_deployed",
                    metadata={"message": "Runtime not deployed"},
                )

            client = self._get_runtime_client(config.region)
            runtime = client.get_runtime(
                runtime_types.GetRuntimeRequest(runtime_id=runner_config.runtime_id)
            )

            # Only fetch API key for key_auth mode
            if (
                not runner_config.runtime_apikey
                and runner_config.runtime_auth_type == AUTH_TYPE_KEY_AUTH
            ):
                if (
                    runtime.authorizer_configuration
                    and runtime.authorizer_configuration.key_auth
                ):
                    runner_config.runtime_apikey = (
                        runtime.authorizer_configuration.key_auth.api_key
                    )

            ping_status = None
            public_endpoint = self.get_public_endpoint_of_runtime(runtime)

            # Only perform ping check for key_auth mode with valid API key
            if (
                runner_config.runtime_auth_type == AUTH_TYPE_KEY_AUTH
                and runner_config.runtime_apikey
                and runtime.status == RUNTIME_STATUS_READY
                and public_endpoint
            ):
                try:
                    ping_response = requests.get(
                        urljoin(public_endpoint, "ping"),
                        headers={
                            "Authorization": f"Bearer {runner_config.runtime_apikey}"
                        },
                        timeout=10,
                    )
                    if ping_response.status_code == 200:
                        ping_status = True
                    elif ping_response.status_code in (404, 405):
                        # Fallback: try /health for SimpleApp compatibility
                        try:
                            health_response = requests.get(
                                urljoin(public_endpoint, "health"),
                                headers={
                                    "Authorization": f"Bearer {runner_config.runtime_apikey}"
                                },
                                timeout=10,
                            )
                            if health_response.status_code == 200:
                                ping_status = True
                            else:
                                ping_status = None  # Endpoint reachable but health route not available
                        except Exception:
                            # Endpoint reachable (ping returned 404/405), but health check failed
                            ping_status = None
                    else:
                        # Non-200 status indicates server responded but not healthy
                        ping_status = False
                except Exception as e:
                    logger.error(f"Failed to check endpoint connectivity: {str(e)}")
                    ping_status = False
            elif runner_config.runtime_auth_type == AUTH_TYPE_CUSTOM_JWT:
                # For JWT auth, skip ping check (user provides token via headers)
                ping_status = None

            if runtime.status == RUNTIME_STATUS_READY:
                status = "running"
            elif runtime.status == RUNTIME_STATUS_ERROR:
                status = "error"
            else:
                status = runtime.status.lower()

            return StatusResult(
                success=True,
                status=status,
                endpoint_url=public_endpoint,
                service_id=runner_config.runtime_id,
                health=(
                    "healthy"
                    if ping_status is True
                    else "unhealthy"
                    if ping_status is False
                    else "unknown"
                    if ping_status is None
                    else None
                ),
                metadata={
                    "runtime_id": runner_config.runtime_id,
                    "runtime_name": runtime.name
                    if hasattr(runtime, "name")
                    else runner_config.runtime_name,
                    "raw_status": runtime.status,
                    "image_url": runtime.artifact_url
                    if hasattr(runtime, "artifact_url")
                    else "",
                    "ping_status": ping_status,
                    "timestamp": datetime.now().isoformat(),
                },
            )

        except Exception as e:
            logger.error(f"Failed to get Runtime status: {str(e)}")
            if "InvalidAgentKitRuntime.NotFound" in str(e):
                return StatusResult(
                    success=False,
                    status="not_found",
                    error=f"Runtime not found: {runner_config.runtime_id}",
                    error_code=ErrorCode.RESOURCE_NOT_FOUND,
                    metadata={"runtime_id": runner_config.runtime_id},
                )
            return StatusResult(
                success=False,
                status="error",
                error=str(e),
                error_code=ErrorCode.UNKNOWN_ERROR,
            )

    def invoke(
        self,
        config: VeAgentkitRunnerConfig,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
        stream: Optional[bool] = None,
    ) -> InvokeResult:
        """Invoke Runtime service.

        Args:
            config: Invoke configuration containing Runtime endpoint and API key.
            payload: Request payload.
            headers: Request headers.
            stream: Stream mode. None=auto-detect (default), True=force streaming, False=force non-streaming.

        Returns:
            InvokeResult: Unified invocation result object.
        """
        try:
            runner_config = config
            is_jwt_auth = runner_config.runtime_auth_type == AUTH_TYPE_CUSTOM_JWT

            # Get Runtime endpoint and API key
            endpoint = runner_config.runtime_endpoint
            api_key = runner_config.runtime_apikey

            # For key_auth: require both endpoint and api_key
            # For custom_jwt: only require endpoint (user provides token via headers)
            if not endpoint or (not is_jwt_auth and not api_key):
                if (
                    not runner_config.runtime_id
                    or runner_config.runtime_id == AUTO_CREATE_VE
                ):
                    error_msg = "Runtime is not deployed."
                    logger.error(error_msg)
                    return InvokeResult(
                        success=False,
                        error=error_msg,
                        error_code=ErrorCode.SERVICE_NOT_RUNNING,
                    )

                # Auto-fetch Runtime information if not cached
                try:
                    client = self._get_runtime_client(config.region)
                    runtime = client.get_runtime(
                        runtime_types.GetRuntimeRequest(
                            runtime_id=runner_config.runtime_id
                        )
                    )
                except Exception as e:
                    if "NotFound" in str(e):
                        error_msg = "Configured Runtime has been deleted externally. Please redeploy."
                        logger.error(error_msg)
                        return InvokeResult(
                            success=False,
                            error=error_msg,
                            error_code=ErrorCode.RESOURCE_NOT_FOUND,
                        )
                    raise e
                endpoint = self.get_public_endpoint_of_runtime(runtime)

                # Only fetch API key for key_auth mode
                if not is_jwt_auth:
                    if (
                        runtime.authorizer_configuration
                        and runtime.authorizer_configuration.key_auth
                    ):
                        api_key = runtime.authorizer_configuration.key_auth.api_key

                # Validate based on auth type
                if not endpoint:
                    error_msg = "Failed to obtain Runtime endpoint."
                    logger.error(f"{error_msg}, runtime: {runtime}")
                    return InvokeResult(
                        success=False,
                        error=error_msg,
                        error_code=ErrorCode.CONFIG_MISSING,
                    )
                if not is_jwt_auth and not api_key:
                    error_msg = "Failed to obtain Runtime API key."
                    logger.error(f"{error_msg}, runtime: {runtime}")
                    return InvokeResult(
                        success=False,
                        error=error_msg,
                        error_code=ErrorCode.CONFIG_MISSING,
                    )

            # Construct invoke endpoint URL
            # Auto-detect invoke path based on agent_type: A2A agents use '/', others use '/invoke'
            common_config = runner_config.common_config
            is_a2a = self._is_a2a(common_config)
            invoke_path = "/" if is_a2a else "/invoke"
            invoke_endpoint = (
                urljoin(endpoint, invoke_path.lstrip("/"))
                if invoke_path != "/"
                else endpoint
            )

            # Prepare request headers
            if headers is None:
                headers = {}

            # Check Authorization header for JWT auth
            if not headers.get("Authorization"):
                if is_jwt_auth:
                    error_msg = (
                        "Authorization header with OAuth token is required for JWT authentication. "
                        "Please provide the token via headers={'Authorization': 'Bearer <your_oauth_token>'}."
                    )
                    logger.error(error_msg)
                    return InvokeResult(
                        success=False,
                        error=error_msg,
                        error_code=ErrorCode.AUTH_FAILED,
                    )
                else:
                    headers["Authorization"] = f"Bearer {api_key}"

            # Unified ADK-compatible invocation flow via base class
            ctx = Runner.InvokeContext(
                base_endpoint=endpoint,
                invoke_endpoint=invoke_endpoint,
                headers=headers,
                is_a2a=is_a2a,
                preferred_app_name=(
                    getattr(common_config, "agent_name", None)
                    if common_config
                    else None
                ),
            )
            policy = Runner.TimeoutPolicy()
            success, response_data, is_streaming = self._invoke_with_adk_compat(
                ctx, payload, policy
            )

            if success:
                return InvokeResult(
                    success=True, response=response_data, is_streaming=is_streaming
                )
            else:
                error_msg = str(response_data)
                logger.error(f"Invocation failed: {error_msg}")
                return InvokeResult(
                    success=False, error=error_msg, error_code=ErrorCode.INVOKE_FAILED
                )

        except Exception as e:
            error_msg = f"Runtime invocation failed: {str(e)}"
            logger.exception("Runtime invocation failed with exception")
            return InvokeResult(
                success=False, error=error_msg, error_code=ErrorCode.INVOKE_FAILED
            )

    def _prepare_runtime_config(self, config: VeAgentkitRunnerConfig) -> bool:
        """Prepare Runtime configuration by generating names and keys.

        Args:
            config: Runner configuration.

        Returns:
            True if successful, False otherwise.
        """
        try:
            # Generate Runtime name if not provided
            if config.runtime_name == AUTO_CREATE_VE or not config.runtime_name:
                config.runtime_name = generate_runtime_name(
                    config.common_config.agent_name
                )
                self.reporter.success(f"Generated Runtime name: {config.runtime_name}")

            # Generate IAM role name if not provided
            if (
                config.runtime_role_name == AUTO_CREATE_VE
                or not config.runtime_role_name
            ):
                config.runtime_role_name = generate_runtime_role_name()
                self.reporter.success(
                    f"Generated role name: {config.runtime_role_name}"
                )

            # Generate API key name if not provided
            if (
                config.runtime_apikey_name == AUTO_CREATE_VE
                or not config.runtime_apikey_name
            ):
                config.runtime_apikey_name = generate_apikey_name()
                self.reporter.success(
                    f"Generated API key name: {config.runtime_apikey_name}"
                )

            return True

        except Exception as e:
            logger.error(f"Failed to prepare Runtime configuration: {str(e)}")
            return False

    def _build_authorizer_config_for_create(
        self, config: VeAgentkitRunnerConfig
    ) -> runtime_types.AuthorizerForCreateRuntime:
        """Build authorizer configuration for creating a new Runtime.

        Args:
            config: Runner configuration.

        Returns:
            AuthorizerForCreateRuntime: Authorizer configuration for create request.
        """
        if config.runtime_auth_type == AUTH_TYPE_CUSTOM_JWT:
            return runtime_types.AuthorizerForCreateRuntime(
                custom_jwt_authorizer=runtime_types.AuthorizerCustomJwtAuthorizerForCreateRuntime(
                    discovery_url=config.runtime_jwt_discovery_url,
                    allowed_clients=config.runtime_jwt_allowed_clients
                    if config.runtime_jwt_allowed_clients
                    else None,
                )
            )
        else:
            return runtime_types.AuthorizerForCreateRuntime(
                key_auth=runtime_types.AuthorizerKeyAuthForCreateRuntime(
                    api_key_name=config.runtime_apikey_name,
                    api_key_location=API_KEY_LOCATION,
                )
            )

    def _create_new_runtime(self, config: VeAgentkitRunnerConfig) -> DeployResult:
        """Create a new Runtime instance.

        Args:
            config: Runner configuration.

        Returns:
            DeployResult: Unified deployment result object.
        """
        try:
            self.reporter.info(f"Creating Runtime: {config.runtime_name}")

            client = self._get_runtime_client(config.region)

            # Build Runtime creation request
            envs = [
                runtime_types.EnvsItemForCreateRuntime(key=k, value=v)
                for k, v in config.runtime_envs.items()
            ]

            # Build authorizer configuration based on auth type
            authorizer_config = self._build_authorizer_config_for_create(config)

            create_request = runtime_types.CreateRuntimeRequest(
                name=config.runtime_name,
                description=config.common_config.description
                if is_valid_config(config.common_config.description)
                else f"Auto created by AgentKit CLI for agent project {config.common_config.agent_name}",
                artifact_type=ARTIFACT_TYPE_DOCKER_IMAGE,
                artifact_url=config.image_url,
                role_name=config.runtime_role_name,
                envs=envs,
                project_name=PROJECT_NAME_DEFAULT,
                authorizer_configuration=authorizer_config,
                client_token=generate_client_token(),
                apmplus_enable=True,
                min_instance=config.min_instance,
            )

            # Create Runtime
            runtime_resp = client.create_runtime(create_request)
            config.runtime_id = runtime_resp.runtime_id

            self.reporter.success(f"Runtime created successfully: {config.runtime_id}")
            self.reporter.info("Waiting for Runtime to reach Ready status...")
            self.reporter.info(
                "💡 Tip: Runtime is initializing. Please wait patiently and do not interrupt."
            )

            # Wait for Runtime to be ready
            success, runtime, error = self._wait_for_runtime_status(
                runtime_id=config.runtime_id,
                target_status=RUNTIME_STATUS_READY,
                task_description="Waiting for Runtime to be ready...",
                region=config.region,
                timeout=600,
                error_message="Initialization failed",
            )

            if not success:
                self.reporter.warning(
                    f"Runtime failed to initialize: {config.runtime_id}"
                )
                self.reporter.error(f"Error: {error}")

                self._download_and_show_runtime_failed_logs(runtime, config.runtime_id)

                # Ask user if they want to clean up the failed Runtime
                should_cleanup = self.reporter.confirm(
                    "Do you want to clean up the failed Runtime?", default=False
                )

                if should_cleanup:
                    self.reporter.info(
                        f"Cleaning up failed Runtime: {config.runtime_id}"
                    )
                    try:
                        client.delete_runtime(
                            runtime_types.DeleteRuntimeRequest(
                                runtime_id=config.runtime_id
                            )
                        )
                        self.reporter.success("Runtime cleanup successful.")
                    except Exception as e:
                        if "InvalidAgentKitRuntime.NotFound" not in str(e):
                            self.reporter.error(f"Failed to clean up Runtime: {str(e)}")
                else:
                    self.reporter.info(
                        f"Cleanup skipped, Runtime retained: {config.runtime_id}"
                    )

                return DeployResult(
                    success=False,
                    error=error,
                    error_code=ErrorCode.RUNTIME_NOT_READY,
                    service_id=config.runtime_id,
                )

            # Retrieve endpoint and API key from created Runtime
            public_endpoint = self.get_public_endpoint_of_runtime(runtime)
            self.reporter.info(f"Endpoint: {public_endpoint}")
            config.runtime_endpoint = public_endpoint

            # Only retrieve API key for key_auth mode
            if config.runtime_auth_type == AUTH_TYPE_KEY_AUTH:
                if (
                    runtime.authorizer_configuration
                    and runtime.authorizer_configuration.key_auth
                ):
                    config.runtime_apikey = (
                        runtime.authorizer_configuration.key_auth.api_key
                    )

            return DeployResult(
                success=True,
                endpoint_url=config.runtime_endpoint,
                service_id=config.runtime_id,
                deploy_timestamp=datetime.now(),
                metadata={
                    "runtime_id": config.runtime_id,
                    "runtime_name": config.runtime_name,
                    "runtime_apikey": config.runtime_apikey,
                    "runtime_apikey_name": config.runtime_apikey_name,
                    "runtime_role_name": config.runtime_role_name,
                    "runtime_auth_type": config.runtime_auth_type,
                    "runtime_jwt_discovery_url": config.runtime_jwt_discovery_url,
                    "runtime_jwt_allowed_clients": config.runtime_jwt_allowed_clients,
                    "message": "Runtime created successfully",
                },
            )

        except Exception as e:
            error_msg = f"Failed to create Runtime: {str(e)}"
            logger.exception("Runtime creation failed with exception")
            return DeployResult(
                success=False,
                error=error_msg,
                error_code=ErrorCode.RUNTIME_CREATE_FAILED,
            )

    def _download_and_show_runtime_failed_logs(
        self,
        runtime: Optional[runtime_types.GetRuntimeResponse],
        runtime_id: str,
    ) -> None:
        """Download and display runtime failure logs for debugging.

        Helps users diagnose runtime failures by fetching logs from the remote URL,
        saving them locally, and displaying the first 50 lines for immediate review.
        """
        if (
            not runtime
            or not hasattr(runtime, "failed_log_file_url")
            or not runtime.failed_log_file_url
        ):
            logger.warning(f"No failure log URL available for runtime {runtime_id}")
            return

        self.reporter.info(f"Runtime log URL: {runtime.failed_log_file_url}")
        self.reporter.info("Downloading failure logs...")

        try:
            log_response = requests.get(runtime.failed_log_file_url, timeout=30)
            log_response.raise_for_status()

            # Create logs directory with timestamp-based filename for uniqueness
            log_dir = os.path.join(os.getcwd(), ".agentkit", "logs")
            os.makedirs(log_dir, exist_ok=True)
            log_filename = f"runtime_failed_{runtime_id}_{int(time.time())}.log"
            log_filepath = os.path.join(log_dir, log_filename)

            # Save raw log content first
            with open(log_filepath, "wb") as f:
                f.write(log_response.content)

            # Read back with error handling for encoding issues
            with open(log_filepath, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            self.reporter.show_logs(
                title="Runtime Failure Logs (First 50 lines)", lines=lines, max_lines=50
            )

            self.reporter.success(f"Full logs saved to: {log_filepath}")

        except Exception as e:
            logger.error(f"Failed to download runtime logs for {runtime_id}: {str(e)}")
            self.reporter.warning(f"Could not retrieve failure logs: {str(e)}")

    def _wait_for_runtime_status(
        self,
        runtime_id: str,
        target_status: str,
        task_description: str,
        region: str = "",
        timeout: Optional[int] = None,
        error_message: str = "Failed to wait for Runtime status change",
    ) -> Tuple[bool, Optional[runtime_types.GetRuntimeResponse], Optional[str]]:
        """Wait for Runtime to reach target status (single status version).\n
        Args:
            runtime_id: Runtime ID.
            target_status: Target status.
            task_description: Progress bar task description.
            timeout: Timeout in seconds; None means no timeout.
            error_message: Error message on failure.

        Returns:
            (success, Runtime object, error message or None)
        """
        # Delegate to multi-status version with single status as list
        return self._wait_for_runtime_status_multiple(
            runtime_id=runtime_id,
            target_statuses=[target_status],
            task_description=task_description,
            region=region,
            timeout=timeout,
            error_message=error_message,
        )

    def _wait_for_runtime_status_multiple(
        self,
        runtime_id: str,
        target_statuses: List[str],
        task_description: str,
        region: str = "",
        timeout: Optional[int] = None,
        error_message: str = "Failed to wait for Runtime status change",
    ) -> Tuple[bool, Optional[runtime_types.GetRuntimeResponse], Optional[str]]:
        """Wait for Runtime to reach one of multiple target statuses.

        Args:
            runtime_id: Runtime ID.
            target_statuses: List of target statuses.
            task_description: Progress bar task description.
            timeout: Timeout in seconds; None means no timeout.
            error_message: Error message on failure.

        Returns:
            (success, Runtime object, error message or None)
        """
        last_status = None
        start_time = time.time()
        total_time = timeout if timeout else 300  # For progress bar display
        expected_time = (
            30  # Controls progress curve speed (smaller = faster initial progress)
        )
        runtime = None  # Initialize runtime variable

        # Use reporter.long_task() for progress tracking
        client = self._get_runtime_client(region)

        with self.reporter.long_task(task_description, total=total_time) as task:
            while True:
                runtime = retry(
                    lambda: client.get_runtime(
                        runtime_types.GetRuntimeRequest(runtime_id=runtime_id)
                    )
                )

                # Check if target status reached
                if runtime.status in target_statuses:
                    task.update(completed=total_time)  # 100%
                    self.reporter.success(f"Runtime status: {runtime.status}")
                    return True, runtime, None

                # Check for error status
                if runtime.status == RUNTIME_STATUS_ERROR:
                    task.update(description="Runtime operation failed")
                    return False, runtime, f"Runtime status is Error. {error_message}"

                # Calculate elapsed time
                elapsed_time = time.time() - start_time

                # Check timeout
                if timeout and elapsed_time > timeout:
                    task.update(description="Wait timeout")
                    return False, runtime, f"{error_message} (timeout after {timeout}s)"

                # Update progress description on status change
                if runtime.status != last_status:
                    task.update(description=f"Runtime status: {runtime.status}")
                    last_status = runtime.status

                # Update progress using non-linear curve
                task.update(
                    completed=calculate_nonlinear_progress(
                        elapsed_time, total_time, expected_time
                    )
                )

                time.sleep(3)

    def _needs_runtime_update(
        self, runtime: runtime_types.GetRuntimeResponse, config: VeAgentkitRunnerConfig
    ) -> Tuple[bool, str]:
        """Check if Runtime needs to be updated.

        Args:
            runtime: Existing Runtime object.
            config: New Runner configuration.

        Returns:
            (needs_update, reason_description)
        """

        update_reasons = []

        # Check if image URL changed
        if runtime.artifact_url != config.image_url:
            update_reasons.append(
                f"Image URL changed: {runtime.artifact_url} -> {config.image_url}"
            )

        # Check if environment variables changed
        # System-injected environment variable prefixes that should not be modified by users
        SYSTEM_ENV_PREFIXES = ("OTEL_", "ENABLE_APMPLUS", "APMPLUS_")

        # Convert runtime envs to dict for comparison (filter system env vars)
        runtime_envs = {}
        if hasattr(runtime, "envs") and runtime.envs:
            for env in runtime.envs:
                key = None
                value = None

                # Try lowercase attributes (runtime_all_types response objects)
                if hasattr(env, "key") and hasattr(env, "value"):
                    key, value = env.key, env.value
                # Try uppercase attributes (for compatibility)
                elif hasattr(env, "Key") and hasattr(env, "Value"):
                    key, value = env.Key, env.Value
                # Handle dict type
                elif isinstance(env, dict):
                    key = env.get("key") or env.get("Key", "")
                    value = env.get("value") or env.get("Value", "")

                # Filter out system environment variables
                if key and not key.startswith(SYSTEM_ENV_PREFIXES):
                    runtime_envs[key] = value

        # Compare environment variables (only user-defined ones)
        if runtime_envs != config.runtime_envs:
            # Find specific differences
            added_keys = set(config.runtime_envs.keys()) - set(runtime_envs.keys())
            removed_keys = set(runtime_envs.keys()) - set(config.runtime_envs.keys())
            changed_keys = {
                k
                for k in set(runtime_envs.keys()) & set(config.runtime_envs.keys())
                if runtime_envs[k] != config.runtime_envs.get(k)
            }

            env_changes = []
            if added_keys:
                env_changes.append(f"Added env vars: {', '.join(added_keys)}")
            if removed_keys:
                env_changes.append(f"Removed env vars: {', '.join(removed_keys)}")
            if changed_keys:
                env_changes.append(f"Modified env vars: {', '.join(changed_keys)}")

            update_reasons.append(
                "Environment variables changed: " + "; ".join(env_changes)
            )

        needs_update = len(update_reasons) > 0
        reason = (
            " | ".join(update_reasons) if needs_update else "No configuration changes"
        )

        return needs_update, reason

    def _update_existing_runtime(self, config: VeAgentkitRunnerConfig) -> DeployResult:
        """Update existing Runtime instance.

        Args:
            config: Runner configuration.

        Returns:
            DeployResult: Unified deployment result object.
        """
        try:
            self.reporter.info(f"Updating Runtime: {config.runtime_id}")

            client = self._get_runtime_client(config.region)

            # Get existing Runtime information
            try:
                runtime = client.get_runtime(
                    runtime_types.GetRuntimeRequest(runtime_id=config.runtime_id)
                )
            except Exception as e:
                if "InvalidAgentKitRuntime.NotFound" in str(e):
                    error_msg = f"Runtime not found: {config.runtime_id}"
                    logger.error(error_msg)
                    return DeployResult(
                        success=False,
                        error=error_msg,
                        error_code=ErrorCode.RESOURCE_NOT_FOUND,
                        service_id=config.runtime_id,
                    )
                raise e

            if runtime.artifact_type != ARTIFACT_TYPE_DOCKER_IMAGE:
                error_msg = f"Unsupported Runtime type: {runtime.artifact_type}"
                logger.error(error_msg)
                return DeployResult(
                    success=False, error=error_msg, error_code=ErrorCode.CONFIG_INVALID
                )

            # Check if update is needed
            # needs_update, update_reason = self._needs_runtime_update(runtime, config)
            needs_update = True  # Always update for now

            if not needs_update:
                self.reporter.success(
                    "Runtime configuration is up-to-date, no update needed."
                )
                public_endpoint = self.get_public_endpoint_of_runtime(runtime)
                config.runtime_endpoint = public_endpoint

                # Only retrieve API key for key_auth mode
                if config.runtime_auth_type == AUTH_TYPE_KEY_AUTH:
                    if (
                        runtime.authorizer_configuration
                        and runtime.authorizer_configuration.key_auth
                    ):
                        config.runtime_apikey = (
                            runtime.authorizer_configuration.key_auth.api_key
                        )

                return DeployResult(
                    success=True,
                    endpoint_url=config.runtime_endpoint,
                    service_id=config.runtime_id,
                    deploy_timestamp=datetime.now(),
                    metadata={
                        "runtime_id": config.runtime_id,
                        "runtime_name": config.runtime_name,
                        "runtime_apikey": config.runtime_apikey,
                        "runtime_auth_type": config.runtime_auth_type,
                        "message": "Runtime configuration is up-to-date",
                    },
                )

            self.reporter.info("Starting Runtime update...")

            envs = [
                {"Key": str(k), "Value": str(v)} for k, v in config.runtime_envs.items()
            ]
            client.update_runtime(
                runtime_types.UpdateRuntimeRequest(
                    runtime_id=config.runtime_id,
                    artifact_url=config.image_url,
                    description=config.common_config.description,
                    envs=envs,
                    client_token=generate_client_token(),
                )
            )

            self.reporter.success("Runtime update request submitted.")

            # Phase 1: Wait for Runtime update to complete (status may become UnReleased or directly Ready)
            self.reporter.info("Waiting for Runtime update to complete...")
            success, updated_runtime, error = self._wait_for_runtime_status_multiple(
                runtime_id=config.runtime_id,
                target_statuses=[RUNTIME_STATUS_UNRELEASED, RUNTIME_STATUS_READY],
                task_description="Waiting for Runtime update to complete...",
                region=config.region,
                timeout=600,
                error_message="Update failed",
            )

            if not success:
                self.reporter.warning(f"Runtime update failed: {config.runtime_id}")
                if error:
                    self.reporter.error(f"Errpr: {error}")
                self._download_and_show_runtime_failed_logs(
                    updated_runtime, config.runtime_id
                )
                return DeployResult(
                    success=False,
                    error=error,
                    error_code=ErrorCode.DEPLOY_FAILED,
                    service_id=config.runtime_id,
                )

            # Check current status: if already Ready, update is complete without release step
            if updated_runtime.status == RUNTIME_STATUS_READY:
                self.reporter.success(
                    "Runtime updated directly to Ready status, no release step needed."
                )
            else:
                # Phase 2: Status is UnReleased, need to release the update
                self.reporter.info("Starting Runtime release...")
                client.release_runtime(
                    runtime_types.ReleaseRuntimeRequest(
                        runtime_id=config.runtime_id,
                    )
                )

                # Wait for release to complete
                self.reporter.info(
                    "Waiting for Runtime release to complete, status becoming Ready..."
                )
                self.reporter.info(
                    "💡 Tip: Runtime is being released. Please wait patiently and do not interrupt."
                )

                success, updated_runtime, error = self._wait_for_runtime_status(
                    runtime_id=config.runtime_id,
                    target_status=RUNTIME_STATUS_READY,
                    task_description="Waiting for Runtime release to complete...",
                    region=config.region,
                    timeout=300,
                    error_message="Release failed",
                )

                if not success:
                    self.reporter.warning(f"Runtime update failed: {config.runtime_id}")
                    if error:
                        self.reporter.error(f"Error: {error}")
                    self._download_and_show_runtime_failed_logs(
                        updated_runtime, config.runtime_id
                    )
                    return DeployResult(
                        success=False,
                        error=error,
                        error_code=ErrorCode.DEPLOY_FAILED,
                        service_id=config.runtime_id,
                    )
            # Retrieve endpoint and API key from updated Runtime
            public_endpoint = self.get_public_endpoint_of_runtime(updated_runtime)
            self.reporter.info(f"Endpoint: {public_endpoint}")
            config.runtime_endpoint = public_endpoint

            # Only retrieve API key for key_auth mode
            if config.runtime_auth_type == AUTH_TYPE_KEY_AUTH:
                if (
                    updated_runtime.authorizer_configuration
                    and updated_runtime.authorizer_configuration.key_auth
                ):
                    config.runtime_apikey = (
                        updated_runtime.authorizer_configuration.key_auth.api_key
                    )

            return DeployResult(
                success=True,
                endpoint_url=config.runtime_endpoint,
                service_id=config.runtime_id,
                deploy_timestamp=datetime.now(),
                metadata={
                    "runtime_id": config.runtime_id,
                    "runtime_name": runtime.name
                    if hasattr(runtime, "name")
                    else config.runtime_name,
                    "runtime_apikey": config.runtime_apikey,
                    "runtime_apikey_name": config.runtime_apikey_name,
                    "runtime_role_name": config.runtime_role_name,
                    "runtime_auth_type": config.runtime_auth_type,
                    "runtime_jwt_discovery_url": config.runtime_jwt_discovery_url,
                    "runtime_jwt_allowed_clients": config.runtime_jwt_allowed_clients,
                    "message": "Runtime update completed",
                },
            )

        except Exception as e:
            error_msg = f"Failed to update Runtime: {str(e)}"
            logger.exception("Runtime update failed with exception")
            return DeployResult(
                success=False, error=error_msg, error_code=ErrorCode.DEPLOY_FAILED
            )

    @staticmethod
    def get_public_endpoint_of_runtime(
        runtime: runtime_types.GetRuntimeResponse,
    ) -> str:
        for network_configuration in runtime.network_configurations:
            if network_configuration.network_type == "public":
                return network_configuration.endpoint
        return ""
