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
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urljoin
from agentkit.toolkit.config import CommonConfig
from agentkit.toolkit.config.dataclass_utils import AutoSerializableMixin
from agentkit.toolkit.models import DeployResult, InvokeResult, StatusResult
from agentkit.toolkit.reporter import Reporter
from agentkit.toolkit.errors import ErrorCode

from .base import Runner
# Docker-related imports are deferred to usage time to avoid dependency issues


logger = logging.getLogger(__name__)


@dataclass
class LocalDockerRunnerConfig(AutoSerializableMixin):
    common_config: Optional[CommonConfig] = field(
        default=None, metadata={"system": True, "description": "Common configuration"}
    )
    full_image_name: str = field(
        default=None, metadata={"system": True, "description": "Full image name"}
    )
    image_id: str = field(default="", metadata={"description": "Image ID"})
    image_name: str = field(default="", metadata={"description": "Image name"})
    image_tag: str = field(default="latest", metadata={"description": "Image tag"})
    container_name: str = field(
        default="",
        metadata={
            "system": True,
            "description": "Container name, uses agent_name if empty",
        },
    )
    container_id: str = field(
        default=None, metadata={"system": True, "description": "Container ID"}
    )
    environment: Dict[str, str] = field(
        default_factory=lambda: {},
        metadata={"system": True, "description": "Environment variables"},
    )
    ports: List[str] = field(
        default_factory=lambda: ["8000:8000"],
        metadata={
            "system": True,
            "description": "Port mappings, format: host-port:container-port, comma-separated, default 8000:8000",
        },
    )
    volumes: List[str] = field(
        default_factory=lambda: [],
        metadata={
            "system": True,
            "description": "Volume mappings, format: host-path:container-path, comma-separated",
        },
    )
    restart_policy: str = field(
        default="unless-stopped",
        metadata={"system": True, "description": "Restart policy"},
    )
    memory_limit: str = field(
        default="1g", metadata={"system": True, "description": "Memory limit"}
    )
    cpu_limit: str = field(
        default="1", metadata={"system": True, "description": "CPU limit"}
    )
    invoke_port: int = field(
        default=8000,
        metadata={"system": True, "description": "Agent application entry port"},
    )


# LocalDockerDeployResult has been replaced by unified DeployResult
# Configuration class is retained for backward compatibility


class LocalDockerRunner(Runner):
    def __init__(self, reporter: Optional[Reporter] = None):
        """Initialize LocalDockerRunner.

        Args:
            reporter: Progress reporter for deployment and invocation updates. Defaults to SilentReporter.

        Note:
            LocalDockerRunner only requires image name/ID to run containers, no project directory needed.
        """
        super().__init__(reporter)
        # Defer Docker imports to avoid failures when Docker dependencies are not installed
        try:
            from agentkit.toolkit.docker.container import DockerManager
        except ImportError:
            raise ImportError(
                "Missing Docker dependencies, please install agentkit[docker] extras"
            )
        self.docker_manager = DockerManager()

    def deploy(self, config: LocalDockerRunnerConfig) -> DeployResult:
        """Deploy Docker container.

        Args:
            config: Deployment configuration object (strongly typed)

        Returns:
            DeployResult: Unified deployment result object
        """
        # Check if Docker is available before attempting deployment
        docker_available, docker_message = self.docker_manager.is_docker_available()
        if not docker_available:
            logger.error("Docker availability check failed")
            self.reporter.error("Docker is not available")
            return DeployResult(
                success=False,
                error=docker_message,
                error_code=ErrorCode.DOCKER_NOT_AVAILABLE,
            )

        try:
            docker_config = config
            common_config = docker_config.common_config

            if common_config is None:
                error_msg = "Missing common configuration"
                logger.error(error_msg)
                return DeployResult(
                    success=False, error=error_msg, error_code=ErrorCode.CONFIG_MISSING
                )

            image_name = (
                docker_config.full_image_name
                or f"{docker_config.image_name}:{docker_config.image_tag}"
            )

            image_exists, image_info, actual_image_id = (
                self.docker_manager.check_image_exists(
                    image_name, docker_config.image_id
                )
            )

            if image_exists:
                if docker_config.image_id and actual_image_id != docker_config.image_id:
                    docker_config.image_id = actual_image_id
                    logger.info(f"Updated image ID: {actual_image_id[:12]}")
                elif not docker_config.image_id:
                    docker_config.image_id = actual_image_id
                    logger.info(f"Found image, ID: {actual_image_id[:12]}")
            else:
                error_msg = f"Image {image_name} does not exist"
                logger.error(error_msg)
                self.reporter.error(f"Image does not exist: {image_name}")
                return DeployResult(
                    success=False,
                    error=error_msg,
                    error_code=ErrorCode.RESOURCE_NOT_FOUND,
                )

            if not docker_config.container_name:
                docker_config.container_name = (
                    f"{common_config.agent_name or 'agentkit-app'}-container"
                )

            try:
                existing_container = self.docker_manager.get_container(
                    docker_config.container_name
                )
                if existing_container:
                    logger.info(
                        f"Container {docker_config.container_name} exists, stopping and removing"
                    )
                    self.docker_manager.stop_container(existing_container["id"])
                    self.docker_manager.remove_container(existing_container["id"])
            except Exception as e:
                logger.warning(
                    f"Error stopping or removing existing container: {str(e)}"
                )

            port_dict = {}
            for port in docker_config.ports:
                if ":" in port:
                    host_port, container_port = port.split(":")
                    port_dict[f"{container_port}/tcp"] = host_port
                elif port.isdigit():
                    port_dict[f"{port}/tcp"] = str(port)
                else:
                    error_msg = f"Invalid port format: {port}"
                    logger.error(error_msg)
                    return DeployResult(
                        success=False,
                        error=error_msg,
                        error_code=ErrorCode.CONFIG_INVALID,
                    )
            container_resources = {
                "mem_limit": docker_config.memory_limit,
                "cpu_quota": int(float(docker_config.cpu_limit) * 100000),
            }

            success, cid = self.docker_manager.create_container(
                image_name=image_name,
                container_name=docker_config.container_name,
                ports=port_dict,
                environment=docker_config.environment,
                volumes={
                    vol.split(":", 1)[0]: {"bind": vol.split(":", 1)[1], "mode": "rw"}
                    for vol in docker_config.volumes
                    if ":" in vol
                },
                restart_policy={"Name": docker_config.restart_policy},
                **container_resources,
            )

            if success:
                logger.info(
                    f"Container deployed successfully: {docker_config.container_name} ({cid[:12]})"
                )
                self.reporter.success(
                    f"Container deployed successfully: {docker_config.container_name}"
                )

                # Build endpoint URL
                host_port = docker_config.invoke_port
                endpoint_url = f"http://localhost:{host_port}"

                return DeployResult(
                    success=True,
                    container_id=cid,
                    container_name=docker_config.container_name,
                    endpoint_url=endpoint_url,
                    deploy_timestamp=datetime.now(),
                )
            else:
                error_msg = f"Container creation failed: {cid}"
                logger.error(error_msg)
                self.reporter.error("Container creation failed")
                return DeployResult(
                    success=False,
                    error=str(cid),
                    error_code=ErrorCode.CONTAINER_START_FAILED,
                )

        except Exception as e:
            error_msg = f"Deployment error: {str(e)}"
            logger.exception("Deployment failed with exception")
            self.reporter.error(f"Deployment error: {e}")
            return DeployResult(
                success=False, error=error_msg, error_code=ErrorCode.DEPLOY_FAILED
            )

    def destroy(self, config: LocalDockerRunnerConfig) -> bool:
        """Destroy Docker container and image.

        Args:
            config: Configuration object (strongly typed)

        Returns:
            bool: True if successful
        """
        try:
            docker_config = config
            common_config = docker_config.common_config

            if common_config is None:
                logger.error("Missing common configuration")
                return False

            project_name = (
                docker_config.container_name
                or f"{common_config.agent_name or 'agentkit-app'}-container"
            )
            image_name = (
                docker_config.full_image_name
                or f"{docker_config.image_name or common_config.agent_name or 'agentkit-app'}:{docker_config.image_tag or 'latest'}"
            )

            logger.info(f"Cleaning up resources: {project_name}")

            container_removed = False
            image_removed = False

            if docker_config.container_id:
                try:
                    logger.info(
                        f"Removing container: {project_name} ({docker_config.container_id[:12]})"
                    )
                    if self.docker_manager.remove_container(
                        docker_config.container_id, force=True
                    ):
                        logger.info(f"Container removed successfully: {project_name}")
                        container_removed = True
                    else:
                        logger.error(f"Failed to remove container: {project_name}")
                except Exception as e:
                    logger.error(f"Error removing container by ID: {str(e)}")

                    try:
                        logger.info(
                            f"Attempting to remove container by name: {project_name}"
                        )
                        if self.docker_manager.remove_container(
                            project_name, force=True
                        ):
                            logger.info(
                                f"Container removed successfully: {project_name}"
                            )
                            container_removed = True
                    except Exception as e2:
                        logger.error(f"Error removing container by name: {str(e2)}")
            else:
                try:
                    containers = self.docker_manager.list_containers(
                        all_containers=True
                    )
                    for container in containers:
                        if container["name"] == project_name:
                            logger.info(f"Removing container: {project_name}")
                            if self.docker_manager.remove_container(
                                container["id"], force=True
                            ):
                                logger.info(
                                    f"Container removed successfully: {project_name}"
                                )
                                container_removed = True
                            break
                except Exception as e:
                    logger.error(f"Error finding and removing container: {str(e)}")

            if docker_config.image_id:
                try:
                    logger.info(
                        f"Removing image: {image_name} ({docker_config.image_id[:12]})"
                    )
                    if self.docker_manager.remove_image(
                        docker_config.image_id, force=True
                    ):
                        logger.info(f"Image removed successfully: {image_name}")
                        image_removed = True
                    else:
                        logger.error(f"Failed to remove image: {image_name}")
                except Exception as e:
                    logger.error(f"Error removing image by ID: {str(e)}")

                    if image_name:
                        try:
                            logger.info(
                                f"Attempting to remove image by name: {image_name}"
                            )
                            if self.docker_manager.remove_image(image_name, force=True):
                                logger.info(f"Image removed successfully: {image_name}")
                                image_removed = True
                        except Exception as e2:
                            logger.error(f"Error removing image by name: {str(e2)}")
            else:
                if image_name:
                    try:
                        logger.info(f"Removing image: {image_name}")
                        if self.docker_manager.remove_image(image_name, force=True):
                            logger.info(f"Image removed successfully: {image_name}")
                            image_removed = True
                    except Exception as e:
                        logger.error(f"Error removing image: {str(e)}")

            logger.info("Local Docker resource cleanup completed")
            return container_removed or image_removed

        except Exception as e:
            logger.error(f"Destruction error: {str(e)}")
            return False

    def status(self, config: LocalDockerRunnerConfig) -> StatusResult:
        """Query container status.

        Args:
            config: Configuration object (strongly typed)

        Returns:
            StatusResult: Unified status result object
        """
        try:
            docker_config = config
            common_config = docker_config.common_config

            if common_config is None:
                error_msg = "Missing common configuration"
                logger.error(error_msg)
                return StatusResult(
                    success=False,
                    error=error_msg,
                    error_code=ErrorCode.CONFIG_MISSING,
                    status="unknown",
                )

            # Use explicitly saved names from config to avoid conflicts between multiple agents
            container_name_in_config = (
                docker_config.container_name
            )  # Must be saved in config
            image_name_in_config = (
                docker_config.full_image_name
            )  # Must be saved in config

            logger.info(
                f"Checking status with config: container_name={container_name_in_config}, image_name={image_name_in_config}"
            )

            image_exists = False
            image_info = None
            actual_image_id = None

            # Prefer using image_id from config for precise lookup
            if docker_config.image_id:
                logger.info(f"Checking image by ID: {docker_config.image_id[:12]}")
                images = self.docker_manager.list_images()
                for img in images:
                    img_id = img.get("id", "").replace("sha256:", "")
                    if img_id.startswith(
                        docker_config.image_id
                    ) or docker_config.image_id.startswith(img_id):
                        image_exists = True
                        image_info = img
                        actual_image_id = img_id
                        logger.info(
                            f"Found image by ID: {img.get('tags', ['<none>'])[0]}"
                        )
                        break
            elif image_name_in_config:
                # Fallback: use explicitly saved image name from config
                logger.info(
                    f"No image_id in config, using saved image name: {image_name_in_config}"
                )
                images = self.docker_manager.list_images()
                for img in images:
                    tags = img.get("tags", [])
                    if image_name_in_config in tags or any(
                        tag.startswith(image_name_in_config) for tag in tags
                    ):
                        image_exists = True
                        image_info = img
                        actual_image_id = img.get("id", "").replace("sha256:", "")
                        logger.info(
                            f"Found image by name: {tags[0] if tags else '<none>'}"
                        )
                        break
            else:
                # No image_id or image_name in config means image not built
                logger.info("No image_id or image_name in config, image not built")

            container_exists = False
            container_running = False
            container_info = None

            # Prefer using container_id from config for precise lookup
            if docker_config.container_id:
                logger.info(
                    f"Checking container by ID: {docker_config.container_id[:12]}"
                )
                containers = self.docker_manager.list_containers(all_containers=True)
                for container in containers:
                    if container["id"].startswith(
                        docker_config.container_id
                    ) or docker_config.container_id.startswith(container["id"]):
                        container_exists = True
                        container_running = container["status"] == "running"
                        container_info = container
                        logger.info(
                            f"Found container by ID: {container['name']} ({container['status']})"
                        )
                        break
            elif container_name_in_config:
                # Fallback: use explicitly saved container name from config
                logger.info(
                    f"No container_id in config, using saved container name: {container_name_in_config}"
                )
                containers = self.docker_manager.list_containers(all_containers=True)
                for container in containers:
                    if container["name"] == container_name_in_config:
                        container_exists = True
                        container_running = container["status"] == "running"
                        container_info = container
                        logger.info(
                            f"Found container by name: {container['name']} ({container['status']})"
                        )
                        break
            else:
                # No container_id or container_name in config means container not deployed
                logger.info(
                    "No container_id or container_name in config, container not deployed"
                )

            # Map container status to standard status
            if container_running:
                status = "running"
            elif container_exists:
                status = "stopped"
            else:
                status = "not_deployed"

            # Build endpoint URL (only when running)
            endpoint_url = None
            if container_running and container_info:
                ports = container_info.get("ports", {})
                if ports:
                    # Extract first port mapping
                    for container_port, host_bindings in ports.items():
                        if (
                            host_bindings
                            and isinstance(host_bindings, list)
                            and len(host_bindings) > 0
                        ):
                            host_port = host_bindings[0].get("HostPort", "")
                            if host_port:
                                endpoint_url = f"http://localhost:{host_port}"
                                break

            # Prepare detailed metadata for CLI display
            metadata = {
                "container_name": container_name_in_config,
                "image_name": image_name_in_config,
                # Container information for CLI display
                "container": {
                    "name": container_info.get("name", "") if container_info else None,
                    "id": container_info.get("id", "") if container_info else None,
                    "status": container_info.get("status", "")
                    if container_info
                    else None,
                    "ports": container_info.get("ports", {}) if container_info else {},
                    "created": container_info.get("created", "")
                    if container_info
                    else None,
                },
                # Image information for CLI display
                "image": {
                    "name": image_info.get("tags", [""])[0]
                    if image_info and image_info.get("tags")
                    else None,
                    "id": actual_image_id[:12] if actual_image_id else None,
                    "size": image_info.get("size", 0) if image_info else 0,
                    "created": image_info.get("created", "") if image_info else None,
                },
                # Build/Deploy status for internal use
                "build": {
                    "exists": image_exists,
                    "image_id": actual_image_id[:12] if actual_image_id else None,
                    "tags": image_info.get("tags", []) if image_info else [],
                },
                "deploy": {
                    "exists": container_exists,
                },
            }

            status_result = StatusResult(
                success=True,
                status=status,
                endpoint_url=endpoint_url,
                container_id=container_info.get("id", "") if container_info else None,
                metadata=metadata,
            )

            if image_exists:
                logger.info(
                    f"Image status: Built ({actual_image_id[:12] if actual_image_id else 'unknown'})"
                )
            else:
                logger.info("Image status: Not built")

            if container_running:
                logger.info("Container status: Running")
            elif container_exists:
                logger.info("Container status: Created but not running")
            else:
                logger.info("Container status: Not deployed")

            return status_result

        except Exception as e:
            error_msg = f"Failed to get status: {str(e)}"
            logger.exception("Status query failed with exception")
            return StatusResult(
                success=False,
                error=error_msg,
                error_code=ErrorCode.UNKNOWN_ERROR,
                status="unknown",
            )

    def invoke(
        self,
        config: LocalDockerRunnerConfig,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
        stream: Optional[bool] = None,
    ) -> InvokeResult:
        """Invoke service in Docker container.

        Args:
            config: Configuration object (strongly typed)
            payload: Request payload
            headers: HTTP request headers (optional)
            stream: Stream mode (optional)

        Returns:
            InvokeResult: Unified invocation result object

        Note:
            - If stream=True: result.response is a generator, result.is_streaming=True
        """
        try:
            docker_config = config
            common_config = docker_config.common_config

            if common_config is None:
                error_msg = "Missing common configuration"
                logger.error(error_msg)
                return InvokeResult(
                    success=False, error=error_msg, error_code=ErrorCode.CONFIG_MISSING
                )

            if not docker_config.container_id:
                error_msg = "Container not deployed, please run deploy command first"
                logger.error(error_msg)
                self.reporter.error("Container not deployed")
                return InvokeResult(
                    success=False,
                    error=error_msg,
                    error_code=ErrorCode.SERVICE_NOT_RUNNING,
                )

            if payload is None:
                error_msg = "Please provide payload parameter"
                logger.error(error_msg)
                return InvokeResult(
                    success=False, error=error_msg, error_code=ErrorCode.CONFIG_INVALID
                )

            # Build invocation endpoint
            # Auto-detect invoke path based on agent_type: A2A agents use '/', others use '/invoke'
            port = docker_config.invoke_port or 8000
            endpoint = f"http://127.0.0.1:{port}/"

            is_a2a = self._is_a2a(common_config)
            invoke_path = "/" if is_a2a else "/invoke"
            invoke_endpoint = (
                urljoin(endpoint, invoke_path.lstrip("/"))
                if invoke_path != "/"
                else endpoint
            )

            # Prepare default request headers
            if headers is None:
                headers = {
                    "Authorization": "Bearer xxx",
                    "user_id": "agentkit_user",
                    "session_id": "agentkit_sample_session",
                }

            # Unified ADK-compatible invocation flow using base class
            ctx = Runner.InvokeContext(
                base_endpoint=endpoint,
                invoke_endpoint=invoke_endpoint,
                headers=headers,
                is_a2a=is_a2a,
                preferred_app_name=getattr(common_config, "agent_name", None),
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
            error_msg = f"Invocation error: {str(e)}"
            logger.exception("Invocation failed with exception")
            self.reporter.error(f"Invocation error: {e}")
            return InvokeResult(
                success=False, error=error_msg, error_code=ErrorCode.INVOKE_FAILED
            )
