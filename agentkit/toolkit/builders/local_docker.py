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
Docker builder implementation
Provides local Docker environment build functionality
"""

import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from agentkit.toolkit.config import CommonConfig
from agentkit.toolkit.config.dataclass_utils import AutoSerializableMixin
from agentkit.toolkit.docker.utils import create_dockerignore_file
from agentkit.toolkit.models import BuildResult, ImageInfo
from agentkit.toolkit.reporter import Reporter
from agentkit.toolkit.errors import ErrorCode
from .base import Builder

from agentkit.toolkit.config import DockerBuildConfig
import shutil

logger = logging.getLogger(__name__)


@dataclass
class LocalDockerBuilderConfig(AutoSerializableMixin):
    """Docker builder configuration"""

    common_config: Optional[CommonConfig] = field(
        default=None, metadata={"system": True, "description": "Common configuration"}
    )
    image_name: str = field(default="", metadata={"description": "Image name"})
    image_tag: str = field(default="latest", metadata={"description": "Image tag"})
    dockerfile_path: str = field(
        default=".", metadata={"description": "Dockerfile directory path"}
    )
    dockerfile_name: str = field(
        default="Dockerfile", metadata={"description": "Dockerfile filename"}
    )
    template_dir: Optional[str] = field(
        default=None, metadata={"description": "Dockerfile template directory"}
    )
    template_name: str = field(
        default="Dockerfile.j2",
        metadata={"description": "Dockerfile template filename"},
    )
    docker_build_config: Optional[DockerBuildConfig] = field(
        default=None,
        metadata={
            "system": True,
            "description": "Docker build customization (base_image, build_script, etc.)",
        },
    )


class LocalDockerBuilder(Builder):
    """Docker builder implementation"""

    def __init__(
        self, project_dir: Optional[Path] = None, reporter: Optional[Reporter] = None
    ):
        """Initialize LocalDockerBuilder.

        Args:
            project_dir: Project root directory.
            reporter: Progress reporter for build progress. Defaults to SilentReporter (no output).
        """
        super().__init__(project_dir, reporter)
        try:
            from agentkit.toolkit.docker.container import DockerManager
        except ImportError:
            raise ImportError(
                "Missing Docker dependencies, please install agentkit[docker] extras"
            )
        self.docker_manager = DockerManager()
        self.dockerfile_renderer = None

    def build(self, config: LocalDockerBuilderConfig) -> BuildResult:
        """Build Docker image.

        Args:
            config: Build configuration object (strongly typed).

        Returns:
            BuildResult: Unified build result object.
        """
        docker_config = config
        common_config = docker_config.common_config

        docker_build_config = docker_config.docker_build_config
        force_regenerate = (
            docker_build_config.regenerate_dockerfile if docker_build_config else False
        )

        if common_config is None:
            error_msg = "Missing common configuration"
            logger.error(error_msg)
            return BuildResult(
                success=False,
                error=error_msg,
                error_code=ErrorCode.CONFIG_MISSING,
                build_logs=[error_msg],
            )

        docker_available, docker_message = self.docker_manager.is_docker_available()
        if not docker_available:
            logger.error("Docker availability check failed")
            error_lines = docker_message.split("\n")
            return BuildResult(
                success=False,
                error=docker_message,
                error_code=ErrorCode.DOCKER_NOT_AVAILABLE,
                build_logs=error_lines,
            )

        try:
            if common_config.language == "Python":
                template_dir = os.path.abspath(
                    os.path.join(
                        os.path.dirname(__file__),
                        "..",
                        "resources",
                        "templates",
                        "python",
                    )
                )
            elif common_config.language == "Golang":
                template_dir = os.path.abspath(
                    os.path.join(
                        os.path.dirname(__file__),
                        "..",
                        "resources",
                        "templates",
                        "golang",
                    )
                )
            else:
                error_msg = f"Unsupported language: {common_config.language}"
                logger.error(error_msg)
                return BuildResult(
                    success=False,
                    error=error_msg,
                    error_code=ErrorCode.CONFIG_INVALID,
                    build_logs=[error_msg],
                )

            try:
                from agentkit.toolkit.docker.container import (
                    DockerfileRenderer,
                )
            except ImportError:
                error_msg = "Missing Docker dependencies"
                logger.error(error_msg)
                return BuildResult(
                    success=False,
                    error=error_msg,
                    error_code=ErrorCode.DEPENDENCY_MISSING,
                    build_logs=[error_msg],
                )

            try:
                renderer = DockerfileRenderer(template_dir)
            except Exception:
                error_msg = "Missing Dockerfile renderer"
                logger.error(error_msg)
                return BuildResult(
                    success=False,
                    error=error_msg,
                    error_code=ErrorCode.BUILD_FAILED,
                    build_logs=[error_msg],
                )

            context = {
                "language_version": common_config.language_version,
            }

            if docker_build_config:
                if docker_build_config.base_image:
                    if common_config.language == "Golang" and isinstance(
                        docker_build_config.base_image, dict
                    ):
                        context["base_image_builder"] = (
                            docker_build_config.base_image.get("builder")
                        )
                        context["base_image_runtime"] = (
                            docker_build_config.base_image.get("runtime")
                        )
                    else:
                        context["base_image"] = docker_build_config.base_image

                if docker_build_config.build_script:
                    build_script_path = self.workdir / docker_build_config.build_script
                    if build_script_path.exists():
                        context["build_script"] = docker_build_config.build_script
                    else:
                        logger.warning(
                            f"Build script not found: {docker_build_config.build_script}"
                        )

            if common_config.language == "Python":
                context["agent_module_path"] = os.path.splitext(
                    common_config.entry_point
                )[0]
                if common_config.dependencies_file:
                    dependencies_file_path = (
                        self.workdir / common_config.dependencies_file
                    )
                    if not dependencies_file_path.exists():
                        dependencies_file_path.write_text("")
                    context["dependencies_file"] = common_config.dependencies_file

            if common_config.language == "Golang":
                entry_path = (self.workdir / common_config.entry_point).resolve()
                if not entry_path.exists():
                    candidate = self.workdir / common_config.entry_point
                    candidate = candidate if candidate.exists() else self.workdir
                    found = None
                    for p in [candidate] + list(candidate.parents):
                        if (Path(p) / "go.mod").exists():
                            found = Path(p)
                            break
                    if found:
                        entry_path = found.resolve()
                    else:
                        error_msg = (
                            f"Project path not found: {common_config.entry_point}"
                        )
                        logger.error(error_msg)
                        return BuildResult(
                            success=False,
                            error=error_msg,
                            error_code=ErrorCode.CONFIG_INVALID,
                            build_logs=[error_msg],
                        )

                src_dest = self.workdir / "src"
                src_dest.mkdir(parents=True, exist_ok=True)

                if entry_path.is_file() and entry_path.suffix == ".sh":
                    project_root = entry_path.parent
                    entry_relative_path = str(
                        (Path("src") / project_root.name / entry_path.name).as_posix()
                    )
                elif entry_path.is_dir():
                    project_root = entry_path
                    entry_relative_path = str(
                        (Path("src") / project_root.name).as_posix()
                    )
                else:
                    error_msg = "Unsupported Go entry: single-file compilation is not supported. Provide project directory or build.sh"
                    logger.error(error_msg)
                    return BuildResult(
                        success=False,
                        error=error_msg,
                        error_code=ErrorCode.CONFIG_INVALID,
                        build_logs=[error_msg],
                    )

                binary_name = common_config.agent_name or project_root.name

                try:
                    project_root.resolve()
                    src_res = src_dest.resolve()
                except Exception:
                    src_res = src_dest

                target_subdir = src_dest / project_root.name
                target_subdir.mkdir(parents=True, exist_ok=True)
                for child in project_root.iterdir():
                    try:
                        if child.resolve() == src_res:
                            continue
                    except Exception:
                        if child == src_dest:
                            continue
                    dest = target_subdir / child.name
                    if child.is_dir():
                        shutil.copytree(child, dest, dirs_exist_ok=True, symlinks=True)
                    else:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(child, dest)

                context.update(
                    {
                        "entry_relative_path": entry_relative_path,
                        "binary_name": binary_name,
                        "agent_module_path": f"/usr/local/bin/{binary_name}",
                    }
                )

            from agentkit.toolkit.docker.dockerfile import DockerfileManager

            config_hash_dict = {
                "language": common_config.language,
                "language_version": common_config.language_version,
                "entry_point": common_config.entry_point,
                "dependencies_file": common_config.dependencies_file,
            }
            if docker_build_config:
                config_hash_dict["docker_build"] = {
                    "base_image": docker_build_config.base_image,
                    "build_script": docker_build_config.build_script,
                }

            def generate_dockerfile_content() -> str:
                """Generate Dockerfile content."""
                from io import StringIO

                StringIO()

                # Use renderer to render to string
                template = renderer.env.get_template(docker_config.template_name)
                rendered = template.render(**context)
                return rendered

            dockerfile_manager = DockerfileManager(self.workdir, self.logger)
            generated, dockerfile_path = dockerfile_manager.prepare_dockerfile(
                config_hash_dict=config_hash_dict,
                content_generator=generate_dockerfile_content,
                force_regenerate=force_regenerate,
            )

            create_dockerignore_file(str(self.workdir))
            image_name = f"{docker_config.image_name or 'agentkit-app'}"
            image_tag = f"{docker_config.image_tag or 'latest'}"

            self.reporter.info(f"Building Docker image: {image_name}:{image_tag}")

            build_kwargs = {
                "dockerfile_path": str(self.workdir),
                "image_name": image_name,
                "image_tag": image_tag,
                "build_args": {},
            }

            if docker_build_config and docker_build_config.platform:
                if docker_build_config.platform.lower() != "auto":
                    build_kwargs["platform"] = docker_build_config.platform
                    self.reporter.info(
                        f"Target platform: {docker_build_config.platform}"
                    )
                else:
                    self.reporter.info("Target platform: auto-detect")

            self.reporter.info("Executing Docker build...")
            success, build_logs, image_id = self.docker_manager.build_image(
                **build_kwargs
            )

            if success:
                self.reporter.success(
                    f"Image built successfully: {image_name}:{image_tag}"
                )
                return BuildResult(
                    success=True,
                    image=ImageInfo(
                        repository=image_name,
                        tag=image_tag,
                        digest=image_id,  # Docker image ID as digest
                    ),
                    build_timestamp=datetime.now(),
                    build_logs=build_logs,
                )
            else:
                error_msg = "Docker build failed"
                return BuildResult(
                    success=False,
                    error=error_msg,
                    error_code=ErrorCode.BUILD_FAILED,
                    build_logs=build_logs,
                    build_timestamp=datetime.now(),
                )

        except Exception as e:
            error_msg = f"Build error: {str(e)}"
            logger.exception("Build failed with exception")
            return BuildResult(
                success=False,
                error=error_msg,
                error_code=ErrorCode.BUILD_FAILED,
                build_logs=[str(e)],
                build_timestamp=datetime.now(),
            )

    def check_artifact_exists(self, config: Dict[str, Any]) -> bool:
        """Check if build artifact exists"""
        try:
            exists, image_info, actual_image_id = (
                self.docker_manager.check_image_exists(config["full_image_name"], None)
            )
            return exists
        except Exception as e:
            self.logger.error(f"Error checking image existence: {str(e)}")
            return False

    def remove_artifact(self, config: Dict[str, Any]) -> bool:
        """Remove Docker image"""
        try:
            return self.docker_manager.remove_image(
                config["full_image_name"], force=True
            )
        except Exception as e:
            self.logger.error(f"Error removing image: {str(e)}")
            return False
