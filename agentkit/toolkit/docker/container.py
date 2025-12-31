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

import os
from typing import Dict, Any, Optional, List, Tuple
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
import logging
import docker
from docker.errors import DockerException, ImageNotFound

from agentkit.toolkit.docker.utils import create_dockerignore_file

logger = logging.getLogger(__name__)


class DockerfileRenderer:
    """Dockerfile template renderer for generating Dockerfiles from Jinja2 templates."""

    def __init__(self, template_dir: Optional[str] = None):
        """
        Initialize Dockerfile renderer.

        Args:
            template_dir: Directory containing Dockerfile.j2 template, defaults to current directory
        """
        self.template_dir = template_dir or os.getcwd()
        self.env = Environment(
            loader=FileSystemLoader(self.template_dir),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render_dockerfile(
        self,
        context: Dict[str, Any],
        template_name: str = "Dockerfile.j2",
        output_path: Optional[str] = None,
        create_dockerignore: bool = True,
        dockerignore_entries: Optional[List[str]] = None,
    ) -> str:
        """
        Render Dockerfile from Jinja2 template.

        Args:
            context: Template rendering parameters
            template_name: Template filename, defaults to Dockerfile.j2
            output_path: Output Dockerfile path, defaults to Dockerfile in current directory
            create_dockerignore: Whether to create .dockerignore file, defaults to True
            dockerignore_entries: Additional entries to add to .dockerignore, defaults to None

        Returns:
            Rendered Dockerfile content

        Raises:
            TemplateNotFound: When template file doesn't exist
            IOError: When file write fails
        """
        try:
            template = self.env.get_template(template_name)
            rendered_content = template.render(**context)

            if output_path is None:
                output_path = os.path.join(
                    os.path.dirname(self.template_dir), "Dockerfile"
                )

            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(rendered_content)

            logger.info(f"Successfully rendered Dockerfile to: {output_path}")

            # Create .dockerignore file if requested
            if create_dockerignore:
                target_dir = output_dir or os.path.dirname(output_path)
                create_dockerignore_file(target_dir, dockerignore_entries)

            return rendered_content

        except TemplateNotFound:
            logger.error(
                f"Template file {template_name} not found in {self.template_dir}"
            )
            raise
        except Exception as e:
            logger.error(f"Error rendering Dockerfile: {str(e)}")
            raise

    def create_dockerignore(
        self, dockerignore_path: str, additional_entries: Optional[List[str]] = None
    ) -> None:
        """
        Create .dockerignore file with default and additional entries.

        Deprecated: Use agentkit.toolkit.docker.utils.create_dockerignore_file instead.

        Args:
            dockerignore_path: Path to .dockerignore file
            additional_entries: Additional entries to add to .dockerignore

        Raises:
            IOError: When file write fails
        """
        target_dir = os.path.dirname(dockerignore_path)
        create_dockerignore_file(target_dir, additional_entries)


class DockerManager:
    """Docker image builder and container manager."""

    def __init__(self):
        """Initialize Docker manager."""
        self.client = None
        self._docker_available = False
        self._docker_error = None

        try:
            self.client = docker.from_env()
            self._docker_available = True
            logger.info("Successfully connected to Docker daemon")
        except DockerException as e:
            self._docker_error = str(e)
            logger.warning(f"Docker daemon not available: {str(e)}")
        except Exception as e:
            self._docker_error = str(e)
            logger.warning(f"Unexpected error connecting to Docker: {str(e)}")

    def is_docker_available(self) -> Tuple[bool, str]:
        """
        Check if Docker is available and working properly.

        Returns:
            Tuple[bool, str]: (is_available, message)
                - is_available: Whether Docker is available and working
                - message: Friendly message describing the status or error

        Examples:
            >>> docker_manager = DockerManager()
            >>> available, message = docker_manager.is_docker_available()
            >>> if not available:
            ...     print(f"Docker is not available: {message}")
        """
        # Check if Docker client was initialized successfully
        if self.client is None or not self._docker_available:
            import platform

            system = platform.system()

            # Provide platform-specific help messages
            if system == "Darwin":  # macOS
                help_msg = (
                    "Please ensure:\n"
                    "1. Docker Desktop is installed (download from https://www.docker.com/products/docker-desktop)\n"
                    "2. Docker Desktop is running (check menu bar for Docker icon)\n"
                    "3. Docker daemon has finished starting (may take a minute after launching Docker Desktop)"
                )
            elif system == "Linux":
                help_msg = (
                    "Please ensure:\n"
                    "1. Docker is installed on your system\n"
                    "2. Docker daemon is running (try 'sudo systemctl start docker' or 'sudo service docker start')\n"
                    "3. You have permission to access Docker (try adding your user to the 'docker' group: 'sudo usermod -aG docker $USER')\n"
                    "4. Docker socket is accessible (usually at /var/run/docker.sock)"
                )
            else:  # Windows or other
                help_msg = (
                    "Please ensure:\n"
                    "1. Docker Desktop is installed and running\n"
                    "2. Docker daemon has finished starting"
                )

            error_msg = f"Docker is not available: {self._docker_error}\n\n{help_msg}"
            return False, error_msg

        try:
            # Try to ping the Docker daemon to verify it's still working
            self.client.ping()

            # Get Docker version information to verify functionality
            version_info = self.client.version()
            docker_version = version_info.get("Version", "Unknown")
            api_version = version_info.get("ApiVersion", "Unknown")

            success_msg = (
                f"Docker is available (Version: {docker_version}, API: {api_version})"
            )
            logger.info(success_msg)
            return True, success_msg

        except DockerException as e:
            error_msg = (
                f"Docker daemon stopped responding: {str(e)}\n"
                "Please check if Docker is still running."
            )
            logger.error(error_msg)
            return False, error_msg

        except Exception as e:
            error_msg = f"Unexpected error checking Docker availability: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def build_image(
        self,
        dockerfile_path: str,
        image_name: str,
        image_tag: str = "latest",
        build_args: Optional[Dict[str, str]] = None,
        no_cache: bool = False,
        platform: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Build Docker image.

        Args:
            dockerfile_path: Path to Dockerfile directory
            image_name: Image name
            image_tag: Image tag, defaults to latest
            build_args: Build arguments
            no_cache: Whether to disable cache
            platform: Target platform

        Returns:
            (build_success, build_logs, image_id)
        """
        # Check if Docker is available before attempting to build
        if not self._docker_available or self.client is None:
            is_available, error_msg = self.is_docker_available()
            if not is_available:
                logger.error(f"Cannot build image: {error_msg}")
                return False, error_msg, None

        try:
            full_image_name = f"{image_name}:{image_tag}"
            build_logs = []

            logger.info(f"Starting image build: {full_image_name}")

            build_kwargs = {
                "path": dockerfile_path,
                "tag": full_image_name,
                "nocache": no_cache,
                "decode": True,
                "rm": True,
                "forcerm": True,
            }

            if build_args:
                build_kwargs["buildargs"] = build_args

            if platform:
                build_kwargs["platform"] = platform

            build_output = self.client.api.build(**build_kwargs)

            for chunk in build_output:
                if "stream" in chunk:
                    log_line = chunk["stream"].strip()
                    if log_line:
                        build_logs.append(log_line)
                        logger.debug(log_line)
                elif "errorDetail" in chunk:
                    error_msg = chunk["errorDetail"].get(
                        "message", "Unknown build error"
                    )
                    build_logs.append(f"ERROR: {error_msg}")
                    logger.error(error_msg)
                    return False, build_logs, None

            try:
                image = self.client.images.get(full_image_name)
                image_id = image.id
                logger.info(
                    f"Image build successful: {full_image_name} (ID: {image_id})"
                )
                return True, build_logs, image_id
            except Exception as e:
                logger.warning(f"Build successful but couldn't get image ID: {str(e)}")
                return True, build_logs, None

        except Exception as e:
            error_msg = f"Image build failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, None

    def list_images(self, name_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List local images.

        Args:
            name_filter: Image name filter

        Returns:
            List of image information
        """
        try:
            images = self.client.images.list(name=name_filter)
            image_list = []

            for image in images:
                image_info = {
                    "id": image.id,
                    "tags": image.tags or [],
                    "created": image.attrs.get("Created", ""),
                    "size": image.attrs.get("Size", 0),
                    "virtual_size": image.attrs.get(
                        "VirtualSize", image.attrs.get("Size", 0)
                    ),
                }
                image_list.append(image_info)

            return image_list

        except Exception as e:
            logger.error(f"Failed to get image list: {str(e)}")
            return []

    def remove_image(self, image_name: str, force: bool = False) -> bool:
        """
        Remove image.

        Args:
            image_name: Image name
            force: Whether to force removal

        Returns:
            Whether removal was successful
        """
        try:
            self.client.images.remove(image_name, force=force)
            logger.info(f"Successfully removed image: {image_name}")
            return True
        except Exception as e:
            if "No such image" in str(e):
                return True
            logger.error(f"Failed to remove image: {str(e)}")
            return False

    def list_containers(
        self,
        all_containers: bool = True,
        name_filter: Optional[str] = None,
        status_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List containers.

        Args:
            all_containers: Whether to show all containers including stopped ones
            name_filter: Container name filter
            status_filter: Status filter (running, exited, paused, etc.)

        Returns:
            List of container information
        """
        try:
            containers = self.client.containers.list(all=all_containers)
            container_list = []

            for container in containers:
                try:
                    if name_filter and name_filter not in container.name:
                        continue
                    if status_filter and container.status != status_filter:
                        continue

                    network_settings = container.attrs.get("NetworkSettings", {})
                    ports = network_settings.get("Ports", {})

                    state = container.attrs.get("State", {})

                    container_info = {
                        "id": container.id[:12],
                        "name": container.name,
                        "status": container.status,
                        "image": container.image.tags[0]
                        if container.image.tags
                        else container.image.id,
                        "created": container.attrs.get("Created", ""),
                        "ports": ports,
                        "state": {
                            "running": state.get("Running", False),
                            "started_at": state.get("StartedAt", ""),
                            "finished_at": state.get("FinishedAt", ""),
                        },
                    }
                    container_list.append(container_info)
                except Exception as e:
                    logger.warning(f"Error processing container info: {str(e)}")
                    continue

            return container_list

        except Exception as e:
            logger.error(f"Failed to get container list: {str(e)}")
            return []

    def create_container(
        self,
        image_name: str,
        container_name: Optional[str] = None,
        ports: Optional[Dict[str, str]] = None,
        volumes: Optional[Dict[str, Dict[str, str]]] = None,
        environment: Optional[Dict[str, str]] = None,
        command: Optional[str] = None,
        detach: bool = True,
        restart_policy: Optional[Dict[str, str]] = None,
        mem_limit: Optional[str] = None,
        cpu_quota: Optional[int] = None,
        **kwargs,
    ) -> Tuple[bool, str]:
        """
        Create and start container.

        Args:
            image_name: Image name
            container_name: Container name
            ports: Port mapping {'host_port': 'container_port'}
            volumes: Volume mapping {'host_path': {'bind': 'container_path', 'mode': 'rw/ro'}}
            environment: Environment variables
            command: Startup command
            detach: Whether to run in background
            restart_policy: Restart policy {'Name': 'always/no/unless-stopped', 'MaximumRetryCount': 0}
            mem_limit: Memory limit (e.g., '1g', '512m')
            cpu_quota: CPU quota (microseconds, 100000 = 1 CPU core)
            **kwargs: Other Docker container parameters

        Returns:
            (success, container_id or error_message)
        """
        # Check if Docker is available before attempting to create container
        if not self._docker_available or self.client is None:
            is_available, error_msg = self.is_docker_available()
            if not is_available:
                logger.error(f"Cannot create container: {error_msg}")
                return False, error_msg

        try:
            try:
                self.client.images.get(image_name)
            except ImageNotFound:
                logger.info(f"Image {image_name} not found, attempting to pull...")
                self.client.images.pull(image_name)

            container_kwargs = {"image": image_name, "detach": detach, "remove": False}

            if container_name:
                container_kwargs["name"] = container_name

            if ports:
                container_kwargs["ports"] = {k: v for k, v in ports.items()}

            if volumes:
                container_kwargs["volumes"] = volumes

            if environment:
                container_kwargs["environment"] = environment

            if command:
                container_kwargs["command"] = command

            if restart_policy:
                container_kwargs["restart_policy"] = restart_policy

            if mem_limit or cpu_quota:
                container_kwargs["mem_limit"] = mem_limit
                if cpu_quota:
                    container_kwargs["cpu_quota"] = cpu_quota

            container = self.client.containers.run(**container_kwargs)

            logger.info(
                f"Container created successfully: {container.name} ({container.id[:12]})"
            )
            return True, container.id

        except Exception as e:
            error_msg = f"Container creation failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def start_container(self, container_id_or_name: str) -> bool:
        """
        Start container.

        Args:
            container_id_or_name: Container ID or name

        Returns:
            Whether start was successful
        """
        try:
            container = self.client.containers.get(container_id_or_name)
            container.start()
            logger.info(
                f"Container started successfully: {container.name} ({container.id[:12]})"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to start container: {str(e)}")
            return False

    def stop_container(self, container_id_or_name: str, timeout: int = 10) -> bool:
        """
        Stop container.

        Args:
            container_id_or_name: Container ID or name
            timeout: Timeout in seconds

        Returns:
            Whether stop was successful
        """
        try:
            container = self.client.containers.get(container_id_or_name)
            container.stop(timeout=timeout)
            logger.info(
                f"Container stopped successfully: {container.name} ({container.id[:12]})"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to stop container: {str(e)}")
            return False

    def remove_container(self, container_id_or_name: str, force: bool = False) -> bool:
        """
        Remove container.

        Args:
            container_id_or_name: Container ID or name
            force: Whether to force removal

        Returns:
            Whether removal was successful
        """
        try:
            container = self.client.containers.get(container_id_or_name)
            container.remove(force=force)
            logger.info(f"Container removed successfully: {container_id_or_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove container: {str(e)}")
            return False

    def get_container(self, container_id_or_name: str) -> Dict[str, Any]:
        """
        Get detailed information for a single container.

        Args:
            container_id_or_name: Container ID or name

        Returns:
            Container details dictionary with status, config, network info
        """
        try:
            container = self.client.containers.get(container_id_or_name)

            container_info = {
                "id": container.id[:12],
                "name": container.name,
                "status": container.status,
                "image": container.image.tags[0]
                if container.image.tags
                else container.image.id,
                "created": container.attrs.get("Created", ""),
                "started_at": container.attrs.get("State", {}).get("StartedAt", ""),
                "finished_at": container.attrs.get("State", {}).get("FinishedAt", ""),
                "restart_count": container.attrs.get("RestartCount", 0),
                "command": container.attrs.get("Config", {}).get("Cmd", []),
                "environment": container.attrs.get("Config", {}).get("Env", []),
                "working_dir": container.attrs.get("Config", {}).get("WorkingDir", ""),
                "labels": container.attrs.get("Config", {}).get("Labels", {}),
            }

            network_settings = container.attrs.get("NetworkSettings", {})
            container_info["network"] = {
                "ip_address": network_settings.get("IPAddress", ""),
                "gateway": network_settings.get("Gateway", ""),
                "mac_address": network_settings.get("MacAddress", ""),
                "ports": network_settings.get("Ports", {}),
                "networks": list(network_settings.get("Networks", {}).keys()),
            }

            mounts = container.attrs.get("Mounts", [])
            container_info["mounts"] = [
                {
                    "type": mount.get("Type", ""),
                    "source": mount.get("Source", ""),
                    "destination": mount.get("Destination", ""),
                    "mode": mount.get("Mode", ""),
                    "read_only": mount.get("RW", True) is False,
                }
                for mount in mounts
            ]

            host_config = container.attrs.get("HostConfig", {})
            container_info["resources"] = {
                "memory_limit": host_config.get("Memory", 0),
                "cpu_limit": host_config.get("CpuQuota", 0),
                "cpu_shares": host_config.get("CpuShares", 0),
                "restart_policy": host_config.get("RestartPolicy", {}),
            }

            return container_info

        except Exception as e:
            if "No such container" in str(e):
                return {}
            logger.error(f"Failed to get container info: {str(e)}")
            return {}

    def login_to_registry(
        self, registry_url: str, username: str, password: str, **kwargs
    ) -> Tuple[bool, str]:
        """
        Login to remote Docker registry.

        Args:
            registry_url: Registry URL (e.g: registry.hub.docker.com, registry.cn-hangzhou.aliyuncs.com)
            username: Username
            password: Password or access token
            **kwargs: Other authentication parameters like email

        Returns:
            (Login success, result message)
        """
        try:
            logger.info(f"Logging in to Docker registry: {registry_url}")

            login_config = {
                "username": username,
                "password": password,
                "registry": registry_url,
                "reauth": True,  # Force re-authentication
            }

            if "email" in kwargs:
                login_config["email"] = kwargs["email"]

            result = self.client.login(**login_config)

            if result.get("Status") == "Login Succeeded":
                logger.info(f"Successfully logged in to registry: {registry_url}")
                return True, f"Successfully logged in to registry: {registry_url}"
            else:
                status = result.get("Status", "Unknown status")
                logger.warning(f"Login result: {status}")
                return True, f"Login result: {status}"

        except Exception as e:
            error_msg = f"Failed to login to registry: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def push_image(
        self,
        local_image: str,
        registry_url: str,
        namespace: str = None,
        remote_image_name: str = None,
        remote_tag: str = None,
    ) -> Tuple[bool, str]:
        """
        Push image to remote registry.

        Args:
            local_image: Local image name (format: name:tag) or image ID
            registry_url: Registry URL
            namespace: Namespace/organization name (optional)
            remote_image_name: Remote image name (optional, defaults to local image name)
            remote_tag: Remote image tag (optional, defaults to local tag)

        Returns:
            (Push success, result message)
        """
        try:
            is_image_id = len(local_image) >= 12 and not (
                ":" in local_image and len(local_image.split(":")) == 2
            )

            if is_image_id:
                image_id = local_image
                logger.info(f"Using image ID for push: {image_id}")

                try:
                    image = self.client.images.get(image_id)
                except ImageNotFound:
                    error_msg = f"Local image ID does not exist: {image_id}"
                    logger.error(error_msg)
                    return False, error_msg

                image_tags = image.tags
                if image_tags:
                    first_tag = image_tags[0]
                    local_name = (
                        first_tag.split(":")[0] if ":" in first_tag else first_tag
                    )
                else:
                    local_name = image_id[:12]

                local_tag = "latest"

            else:
                if ":" in local_image:
                    local_name, local_tag = local_image.rsplit(":", 1)
                else:
                    local_name = local_image
                    local_tag = "latest"

                try:
                    image = self.client.images.get(f"{local_name}:{local_tag}")
                except ImageNotFound:
                    error_msg = f"Local image does not exist: {local_name}:{local_tag}"
                    logger.error(error_msg)
                    return False, error_msg

            remote_name = remote_image_name or local_name
            remote_tag_value = remote_tag or local_tag

            if namespace:
                full_remote_image = (
                    f"{registry_url}/{namespace}/{remote_name}:{remote_tag_value}"
                )
            else:
                full_remote_image = f"{registry_url}/{remote_name}:{remote_tag_value}"

            logger.info(
                f"Preparing to push image: {local_image} -> {full_remote_image}"
            )

            image.tag(full_remote_image)
            logger.info(f"Tagged image: {full_remote_image}")

            push_logs = []
            for line in self.client.images.push(
                full_remote_image, stream=True, decode=True
            ):
                if "error" in line:
                    error_msg = line.get("error", "Unknown push error")
                    push_logs.append(f"ERROR: {error_msg}")
                    logger.error(error_msg)
                    return False, "\n".join(push_logs)
                elif "status" in line:
                    status = line.get("status", "")
                    progress = line.get("progress", "")
                    if progress:
                        log_line = f"{status}: {progress}"
                    else:
                        log_line = status
                    push_logs.append(log_line)
                    logger.debug(log_line)

            logger.info(f"Image pushed successfully: {full_remote_image}")
            return True, full_remote_image

        except Exception as e:
            error_msg = f"Failed to push image: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def check_image_exists(
        self, image_name: str, image_id: str = None
    ) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        Unified check if image exists.

        This function provides unified image existence check logic, supporting both image ID and image name checks.
        When image ID check fails, it automatically falls back to image name check.

        Args:
            image_name: Image name (format: name:tag)
            image_id: Optional image ID, will be used first if provided

        Returns:
            Tuple[bool, Optional[Dict[str, Any]], str]:
            - Whether image exists
            - Image info dictionary (if exists)
            - Actual image ID found (if exists)
        """
        try:
            if image_id:
                try:
                    image = self.client.images.get(image_id)
                    tags = image.tags
                    actual_image_id = image.id.replace("sha256:", "")

                    return (
                        True,
                        {
                            "id": actual_image_id,
                            "tags": tags,
                            "created": image.attrs.get("Created", ""),
                            "size": image.attrs.get("Size", 0),
                        },
                        actual_image_id,
                    )

                except ImageNotFound:
                    logger.info(
                        f"Image not found by ID: {image_id[:12]}, trying by name"
                    )

            images = self.list_images()
            for img in images:
                tags = img.get("tags", [])

                if image_name in tags:
                    actual_image_id = img.get("id", "").replace("sha256:", "")
                    return True, img, actual_image_id

                if ":" not in image_name:
                    repo_name = image_name
                    if any(tag.startswith(repo_name + ":") for tag in tags):
                        actual_image_id = img.get("id", "").replace("sha256:", "")
                        return True, img, actual_image_id

            return False, None, ""

        except Exception as e:
            logger.error(f"Error checking image existence: {str(e)}")
            return False, None, ""
