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
import logging
import tempfile
import uuid
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from agentkit.toolkit.config import (
    CommonConfig,
    AUTO_CREATE_VE,
    DEFAULT_WORKSPACE_NAME,
    DockerBuildConfig,
    DEFAULT_IMAGE_TAG,
)
from agentkit.toolkit.config.dataclass_utils import AutoSerializableMixin
from agentkit.toolkit.models import BuildResult, ImageInfo
from agentkit.toolkit.reporter import Reporter
from agentkit.toolkit.errors import ErrorCode
from agentkit.utils.misc import (
    generate_random_id,
    calculate_nonlinear_progress,
    retry,
)
from agentkit.toolkit.volcengine.services import CRServiceConfig
from .base import Builder

logger = logging.getLogger(__name__)


@dataclass
class VeCPCRBuilderConfig(AutoSerializableMixin):
    """Volcano Engine Code Pipeline + Container Registry builder configuration.

    Manages cloud-based build orchestration across three services:
    - TOS (Object Storage): Source code archive storage
    - CR (Container Registry): Docker image repository
    - Code Pipeline: Build execution environment

    Supports template rendering for dynamic resource naming and auto-creation
    of missing resources when configured with AUTO_CREATE_VE.
    """

    common_config: Optional[CommonConfig] = field(
        default=None, metadata={"system": True, "description": "Common configuration"}
    )

    tos_bucket: str = field(
        default=AUTO_CREATE_VE,
        metadata={"description": "TOS bucket name", "render_template": True},
    )
    tos_region: str = field(
        default="cn-beijing", metadata={"description": "TOS region"}
    )
    tos_prefix: str = field(
        default="agentkit-builds", metadata={"description": "TOS path prefix"}
    )

    cr_instance_name: str = field(
        default=AUTO_CREATE_VE,
        metadata={"description": "CR instance name", "render_template": True},
    )
    cr_namespace_name: str = field(
        default=AUTO_CREATE_VE,
        metadata={"description": "CR namespace", "render_template": True},
    )
    cr_repo_name: str = field(
        default=AUTO_CREATE_VE, metadata={"description": "CR repository name"}
    )
    cr_auto_create_instance_type: str = field(
        default="Micro",
        metadata={
            "description": "CR instance type when auto-creating (Micro or Enterprise)"
        },
    )
    cr_region: str = field(default="cn-beijing", metadata={"description": "CR region"})

    cp_workspace_name: str = field(
        default=DEFAULT_WORKSPACE_NAME,
        metadata={"description": "Code Pipeline workspace name"},
    )
    cp_pipeline_name: str = field(
        default=AUTO_CREATE_VE, metadata={"description": "Code Pipeline name"}
    )
    cp_pipeline_id: str = field(
        default="", metadata={"description": "Code Pipeline ID"}
    )

    cp_region: str = field(
        default="cn-beijing",
        metadata={"description": "Code Pipeline region"},
    )

    image_tag: str = field(
        default=DEFAULT_IMAGE_TAG, metadata={"description": "Image tag"}
    )
    dockerfile_template: str = field(
        default="Dockerfile.j2", metadata={"description": "Dockerfile template"}
    )
    build_timeout: int = field(
        default=3600, metadata={"description": "Build timeout in seconds"}
    )

    image_url: str = field(default=None, metadata={"system": True})
    build_timestamp: str = field(default=None, metadata={"system": True})
    tos_object_key: str = field(default=None, metadata={"system": True})

    docker_build_config: Optional[DockerBuildConfig] = field(
        default=None,
        metadata={
            "system": True,
            "description": "Docker build customization (base_image, build_script, etc.)",
        },
    )

    def __post_init__(self):
        """Auto-render template fields after object creation.

        Processes fields marked with render_template=True metadata to resolve
        template variables like {{agent_name}} using environment context.
        """
        self._render_template_fields()


class VeCPCRBuilder(Builder):
    """Volcano Engine Code Pipeline + Container Registry cloud builder.

    Orchestrates cloud-based Docker image builds using Volcano Engine services:
    1. Packages source code and uploads to TOS
    2. Ensures CR resources (instance, namespace, repository) exist
    3. Creates/reuses Code Pipeline for build execution
    4. Monitors build progress and returns image URL

    Supports both Python and Golang projects with multi-stage builds.
    """

    def __init__(
        self, project_dir: Optional[Path] = None, reporter: Optional[Reporter] = None
    ):
        """Initialize VeCPCRBuilder.

        Args:
            project_dir: Project root directory for source code packaging.
            reporter: Progress reporter for build status. Defaults to SilentReporter.
        """
        super().__init__(project_dir, reporter)
        # Service instances are lazily initialized when needed
        self._tos_service = None
        self._cr_service = None
        self._pipeline_service = None

    def build(self, config: VeCPCRBuilderConfig) -> BuildResult:
        """Execute cloud build process.

        Orchestrates the complete build workflow:
        1. Validates configuration and renders Dockerfile
        2. Creates project archive and uploads to TOS
        3. Ensures CR resources exist with public access
        4. Creates/reuses Code Pipeline for build execution
        5. Monitors build progress and returns image metadata

        Args:
            config: Strongly-typed build configuration with auto-creation support.

        Returns:
            BuildResult: Contains image info, metadata, and build status.

        Raises:
            Exception: For configuration validation, resource creation, or build failures.
        """
        builder_config = config
        resources = {}  # Track created resources for cleanup on failure

        docker_build_config = builder_config.docker_build_config

        try:
            if not self._validate_config(builder_config):
                return BuildResult(
                    success=False,
                    error="Configuration validation failed",
                    error_code=ErrorCode.CONFIG_INVALID,
                )

            self.reporter.info("Starting cloud build process...")

            self.reporter.info("1/6 Rendering Dockerfile...")
            resources["dockerfile_path"] = self._render_dockerfile(
                builder_config, docker_build_config
            )

            self.reporter.info("2/6 Creating project archive...")
            resources["archive_path"] = self._create_project_archive(builder_config)

            self.reporter.info("3/6 Uploading to TOS...")
            resources["tos_url"], resources["tos_actual_region"] = self._upload_to_tos(
                resources["archive_path"], builder_config
            )
            resources["tos_object_key"] = builder_config.tos_object_key
            resources["tos_bucket"] = builder_config.tos_bucket
            self.reporter.info(
                f"Uploaded to TOS: {resources['tos_url']}, bucket: {resources['tos_bucket']}"
            )

            self.reporter.info("4/6 Preparing CR resources...")
            resources["cr_config"], resources["cr_actual_region"] = (
                self._prepare_cr_resources(builder_config)
            )

            self.reporter.info("5/6 Preparing Code Pipeline resources...")
            resources["pipeline_id"] = self._prepare_pipeline_resources(
                builder_config, resources["tos_url"], resources["cr_config"]
            )
            # Capture pipeline metadata from resource preparation
            if hasattr(self, "_build_resources"):
                if "pipeline_name" in self._build_resources:
                    resources["pipeline_name"] = self._build_resources["pipeline_name"]
                if "pipeline_id" in self._build_resources:
                    resources["pipeline_id"] = self._build_resources["pipeline_id"]

            self.reporter.info("6/6 Executing build...")

            # Aggregate all runtime overrides
            runtime_overrides = {
                "tos_region": resources.get("tos_actual_region"),
                "cr_region": resources.get("cr_actual_region"),
            }

            resources["image_url"] = self._execute_build(
                resources["pipeline_id"],
                builder_config,
                runtime_overrides=runtime_overrides,
            )
            self.reporter.success(f"Build completed: {resources['image_url']}")

            # Update config with build results for persistence
            builder_config.image_url = resources["image_url"]
            builder_config.cp_pipeline_id = resources["pipeline_id"]
            builder_config.build_timestamp = datetime.now().isoformat()
            builder_config.tos_object_key = resources["tos_object_key"]

            # Parse image URL to extract repository and tag components
            image_url = resources["image_url"]
            if ":" in image_url:
                repository, tag = image_url.rsplit(":", 1)
            else:
                repository = image_url
                tag = builder_config.image_tag

            image_info = ImageInfo(repository=repository, tag=tag, digest=None)

            return BuildResult(
                success=True,
                image=image_info,
                build_timestamp=datetime.fromisoformat(builder_config.build_timestamp),
                build_logs=[],
                metadata={
                    "cr_image_url": resources["image_url"],
                    "cp_pipeline_id": resources["pipeline_id"],
                    "cp_pipeline_name": resources.get("pipeline_name"),
                    "cr_instance_name": builder_config.cr_instance_name,
                    "cr_namespace_name": builder_config.cr_namespace_name,
                    "cr_repo_name": builder_config.cr_repo_name,
                    "tos_object_url": resources["tos_url"],
                    "tos_object_key": builder_config.tos_object_key,
                    "tos_bucket": builder_config.tos_bucket,
                    "resources": resources,
                },
            )

        except Exception as e:
            logger.error(f"Build failed: {str(e)}")
            logger.exception("Cloud build failed with exception")

            # Preserve partial build state for debugging and cleanup
            if resources:
                builder_config.build_timestamp = datetime.now().isoformat()
                if "tos_object_key" in resources:
                    builder_config.tos_object_key = resources["tos_object_key"]
                if "pipeline_id" in resources:
                    builder_config.cp_pipeline_id = resources["pipeline_id"]

            error_msg = str(e)

            return BuildResult(
                success=False,
                error=error_msg,
                error_code=ErrorCode.BUILD_FAILED,
                build_timestamp=datetime.now(),
                metadata={
                    "resources": resources,
                    "tos_object_key": builder_config.tos_object_key
                    if resources
                    else None,
                    "cp_pipeline_id": resources.get("pipeline_id")
                    if resources
                    else None,
                },
            )

    def check_artifact_exists(self, config: VeCPCRBuilderConfig) -> bool:
        """Check if the built image exists in Container Registry.

        Args:
            config: Build configuration with image URL to verify.

        Returns:
            True if image exists and is accessible, False otherwise.

        Note:
            Currently simplified to check config.image_url presence.
            TODO: Implement actual CR API verification.
        """
        try:
            builder_config = config
            if not builder_config.image_url:
                return False

            # Use CR service to verify image existence
            try:
                # TODO: Implement actual CR API image verification
                # Currently simplified - assumes image exists if URL is configured
                self.reporter.info(
                    f"Checking image existence: {builder_config.image_url}"
                )
                return True

            except Exception as e:
                logger.warning(f"Image existence check failed: {str(e)}")
                return False

        except Exception:
            return False

    def remove_artifact(self, config: VeCPCRBuilderConfig) -> bool:
        """Remove build artifacts from cloud resources.

        Cleans up:
        - TOS source archive (if tos_object_key exists)
        - CR image (TODO: not implemented - images may be shared)
        - Pipeline resources (TODO: not implemented - may affect other builds)

        Args:
            config: Build configuration with artifact locations.

        Returns:
            True if cleanup completed without critical errors.

        Note:
            Partial cleanup failures are logged as warnings but don't fail the operation.
        """
        try:
            builder_config = config

            # Clean up TOS source archive
            if builder_config.tos_object_key:
                try:
                    from agentkit.toolkit.volcengine.services.tos_service import (
                        TOSService,
                        TOSServiceConfig,
                    )

                    tos_config = TOSServiceConfig(
                        bucket=builder_config.tos_bucket,
                        region=builder_config.tos_region,
                        prefix=builder_config.tos_prefix,
                    )

                    tos_service = TOSService(tos_config)
                    tos_service.delete_file(builder_config.tos_object_key)
                    logger.info(f"Deleted TOS archive: {builder_config.tos_object_key}")

                except Exception as e:
                    logger.warning(f"Failed to delete TOS archive: {str(e)}")

            # CR image cleanup (not implemented - images may be shared)
            if builder_config.image_url:
                try:
                    self.reporter.warning(
                        f"Note: CR image deletion not implemented, image preserved: {builder_config.image_url}"
                    )
                    # TODO: Implement CR image deletion via API
                    # Consider: Images may be used by running services
                    # Requires careful lifecycle management

                except Exception as e:
                    logger.warning(f"CR image cleanup failed: {str(e)}")

            # Pipeline resource cleanup (not implemented)
            if builder_config.cp_pipeline_id:
                try:
                    self.reporter.warning(
                        f"Note: Pipeline cleanup not implemented, Pipeline ID: {builder_config.cp_pipeline_id}"
                    )
                    # TODO: Implement pipeline resource cleanup
                    # Consider: Pipeline may be reused for future builds
                    # Could clean up build history/logs instead of pipeline itself

                except Exception as e:
                    logger.warning(f"Pipeline cleanup failed: {str(e)}")

            return True

        except Exception as e:
            logger.error(f"Artifact cleanup failed: {str(e)}")
            return False

    def _validate_config(self, config: VeCPCRBuilderConfig) -> bool:
        """Validate build configuration.

        Checks required fields that cannot be auto-created or have no sensible defaults.
        """
        if not config.tos_bucket:
            self.reporter.error("Error: TOS bucket not configured")
            return False
        if not config.cr_region:
            self.reporter.error("Error: CR region not configured")
            return False
        if not config.tos_region:
            self.reporter.error("Error: TOS region not configured")
            return False
        return True

    def _render_dockerfile(
        self,
        config: VeCPCRBuilderConfig,
        docker_build_config: Optional[DockerBuildConfig] = None,
    ) -> str:
        """Render Dockerfile with language-specific templates.

        Supports Python and Golang projects with customizable base images and build scripts.
        For Golang, handles both script-based builds (.sh files) and directory-based builds
        with multi-stage Docker support.

        Returns:
            Path to the generated Dockerfile in the working directory.
        """
        try:
            from agentkit.toolkit.docker.container import DockerfileRenderer
            import shutil

            common_config = config.common_config
            language = getattr(common_config, "language", "Python")
            context = {
                "language_version": common_config.language_version,
            }

            # Inject Docker build configuration parameters
            if docker_build_config:
                # Handle base image configuration
                if docker_build_config.base_image:
                    if language == "Golang" and isinstance(
                        docker_build_config.base_image, dict
                    ):
                        # Golang multi-stage build: separate builder and runtime images
                        context["base_image_builder"] = (
                            docker_build_config.base_image.get("builder")
                        )
                        context["base_image_runtime"] = (
                            docker_build_config.base_image.get("runtime")
                        )
                    else:
                        # Python or single-stage Golang build
                        context["base_image"] = docker_build_config.base_image

                # Handle custom build script
                if docker_build_config.build_script:
                    build_script_path = self.workdir / docker_build_config.build_script
                    if build_script_path.exists():
                        context["build_script"] = docker_build_config.build_script
                    else:
                        logger.warning(
                            f"Build script not found: {docker_build_config.build_script}"
                        )

            # Select language-specific template directory
            if language == "Python":
                template_dir = os.path.abspath(
                    os.path.join(
                        os.path.dirname(__file__),
                        "..",
                        "resources",
                        "templates",
                        "python",
                    )
                )
                context["agent_module_path"] = os.path.splitext(
                    common_config.entry_point
                )[0]
                if common_config.dependencies_file:
                    dependencies_file_path = (
                        self.workdir / common_config.dependencies_file
                    )
                    if not dependencies_file_path.exists():
                        # Create empty dependencies file if missing
                        dependencies_file_path.write_text("")
                    context["dependencies_file"] = common_config.dependencies_file

            elif language == "Golang":
                template_dir = os.path.abspath(
                    os.path.join(
                        os.path.dirname(__file__),
                        "..",
                        "resources",
                        "templates",
                        "golang",
                    )
                )
                entry_on_disk = (self.workdir / common_config.entry_point).resolve()
                if not entry_on_disk.exists():
                    raise Exception(
                        f"Project path not found: {common_config.entry_point}"
                    )

                src_dest = self.workdir / "src"
                src_dest.mkdir(parents=True, exist_ok=True)

                # Script-based build: copy entire project and place script in src/<project>/
                if entry_on_disk.is_file() and entry_on_disk.suffix == ".sh":
                    project_root = entry_on_disk.parent
                    target_subdir = src_dest / project_root.name
                    proj_res = project_root.resolve()
                    src_res = src_dest.resolve()

                    # Check if src directory is inside project to avoid infinite recursion
                    try:
                        src_res.relative_to(proj_res) == src_res.relative_to(proj_res)
                    except Exception:
                        pass

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
                            shutil.copytree(
                                child, dest, dirs_exist_ok=True, symlinks=True
                            )
                        else:
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(child, dest)

                    entry_relative_path = str(
                        (
                            Path("src") / project_root.name / entry_on_disk.name
                        ).as_posix()
                    )
                    binary_name = common_config.agent_name or project_root.name
                else:
                    # Directory-based build: copy project directory to src/<project>
                    project_root = (
                        entry_on_disk
                        if entry_on_disk.is_dir()
                        else entry_on_disk.parent
                    )
                    target_subdir = src_dest / project_root.name
                    proj_res = project_root.resolve()
                    src_res = src_dest.resolve()

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
                            shutil.copytree(
                                child, dest, dirs_exist_ok=True, symlinks=True
                            )
                        else:
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(child, dest)

                    entry_relative_path = str(
                        (Path("src") / project_root.name).as_posix()
                    )
                    binary_name = common_config.agent_name or project_root.name

                context.update(
                    {
                        "entry_relative_path": entry_relative_path,
                        "binary_name": binary_name,
                        "agent_module_path": f"/usr/local/bin/{binary_name}",
                    }
                )
            else:
                raise Exception(f"Unsupported language: {language}")

            # Use DockerfileManager for intelligent Dockerfile generation
            from agentkit.toolkit.docker.dockerfile import DockerfileManager

            # Prepare config hash for change detection (avoids unnecessary regeneration)
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

            renderer = DockerfileRenderer(template_dir)

            # Content generator function (captures context via closure)
            def generate_dockerfile_content() -> str:
                """Generate Dockerfile content without metadata header."""
                template = renderer.env.get_template(config.dockerfile_template)
                rendered = template.render(**context)
                return rendered

            # Check if forced regeneration is requested
            force_regenerate = False
            if docker_build_config:
                force_regenerate = docker_build_config.regenerate_dockerfile

            dockerfile_manager = DockerfileManager(self.workdir, logger)
            generated, dockerfile_path = dockerfile_manager.prepare_dockerfile(
                config_hash_dict=config_hash_dict,
                content_generator=generate_dockerfile_content,
                force_regenerate=force_regenerate,
            )

            # Ensure .dockerignore exists for optimal build context
            dockerignore_path = self.workdir / ".dockerignore"
            if not dockerignore_path.exists():
                renderer.create_dockerignore(str(dockerignore_path))

            return dockerfile_path

        except ImportError:
            raise Exception("Missing Docker-related dependencies")

    def _create_project_archive(self, config: VeCPCRBuilderConfig) -> str:
        """Create project archive for TOS upload.

        Generates a uniquely named archive containing the entire project directory.
        Uses timestamp and random ID to ensure uniqueness across builds.

        Returns:
            Path to the created archive file.
        """
        try:
            from agentkit.toolkit.volcengine.utils.project_archiver import (
                create_project_archive,
            )

            common_config = config.common_config
            # Generate unique archive name with timestamp and random ID
            agent_name = common_config.agent_name or "agentkit-app"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_name = f"{agent_name}_{timestamp}_{uuid.uuid4().hex[:8]}"

            temp_dir = tempfile.mkdtemp()
            source_base_path = self.workdir

            # Create archive using project archiver utility
            archive_path = create_project_archive(
                source_dir=str(source_base_path),
                output_dir=temp_dir,
                archive_name=archive_name,
            )

            logger.info(f"Project archive created: {archive_path}")
            self.reporter.success(f"Project archive created: {archive_path}")
            return archive_path

        except Exception as e:
            raise Exception(f"Failed to create project archive: {str(e)}")

    def _upload_to_tos(
        self, archive_path: str, config: VeCPCRBuilderConfig
    ) -> tuple[str, str]:
        """Upload project archive to TOS (Object Storage).

        Handles bucket auto-creation, template variable validation, and upload verification.
        Supports both user-specified and auto-generated bucket names.

        Args:
            archive_path: Local path to the project archive.
            config: Build configuration with TOS settings.

        Returns:
            Tuple[str, str]: (TOS URL of the uploaded archive, Actual TOS Region used)

        Raises:
            ValueError: For unrendered template variables in bucket name.
            Exception: For bucket creation or upload failures.
        """
        try:
            from agentkit.toolkit.volcengine.services.tos_service import (
                TOSService,
                TOSServiceConfig,
            )

            # Handle bucket configuration with auto-creation support
            bucket_name = config.tos_bucket
            auto_created_bucket = False

            # Case 1: Auto-generate bucket name if not configured or set to AUTO_CREATE_VE
            if not bucket_name or bucket_name == AUTO_CREATE_VE:
                bucket_name = TOSService.generate_bucket_name()
                self.reporter.info("TOS bucket name not configured, auto-generating...")
                self.reporter.info(f"Auto-generated TOS bucket name: {bucket_name}")
                auto_created_bucket = True
            else:
                # Validate bucket name for unrendered template variables
                if "{{" in bucket_name and "}}" in bucket_name:
                    error_msg = f"TOS bucket name contains unrendered template variables: {bucket_name}. Please check configuration or environment variables."
                    self.reporter.error(error_msg)
                    raise ValueError(error_msg)
            if config.tos_prefix == "" or config.tos_prefix == AUTO_CREATE_VE:
                config.tos_prefix = "agentkit-builds"

            tos_config = TOSServiceConfig(
                bucket=bucket_name, region=config.tos_region, prefix=config.tos_prefix
            )

            tos_service = TOSService(tos_config)

            # Check if bucket exists and create if necessary
            self.reporter.info(f"Checking TOS bucket existence: {bucket_name}")
            if not tos_service.bucket_exists():
                # Case 2: Bucket doesn't exist, create it
                self.reporter.warning(
                    f"TOS bucket does not exist, creating: {bucket_name}"
                )

                if not tos_service.create_bucket():
                    error_msg = f"Failed to create TOS bucket: {bucket_name}"
                    self.reporter.error(error_msg)
                    logger.error(error_msg)
                    raise Exception(error_msg)

                self.reporter.success(f"TOS bucket created successfully: {bucket_name}")

                # Verify bucket creation with retry logic (eventual consistency)
                self.reporter.info(f"Verifying TOS bucket creation: {bucket_name}")
                import time

                start_time = time.time()
                timeout = 30  # 30 second timeout
                check_interval = 2  # Check every 2 seconds

                while time.time() - start_time < timeout:
                    if tos_service.bucket_exists():
                        self.reporter.success(
                            f"TOS bucket verification successful: {bucket_name}"
                        )
                        break
                    else:
                        self.reporter.info(
                            f"Waiting for TOS bucket to be ready... ({time.time() - start_time:.1f}s)"
                        )
                        time.sleep(check_interval)
                else:
                    # Timeout occurred
                    error_msg = f"TOS bucket creation verification timeout ({timeout}s): {bucket_name}"
                    self.reporter.error(error_msg)
                    logger.error(error_msg)
                    raise Exception(error_msg)

                # Notify user if their configured bucket didn't exist and was auto-created
                if config.tos_bucket and config.tos_bucket != AUTO_CREATE_VE:
                    self.reporter.info(
                        f"Note: Your configured bucket '{config.tos_bucket}' did not exist, auto-created new bucket '{bucket_name}'"
                    )
            else:
                self.reporter.success(f"TOS bucket exists: {bucket_name}")

            # Update config with auto-generated bucket name if applicable
            if auto_created_bucket:
                config.tos_bucket = bucket_name

            # Generate object key for the archive
            archive_name = os.path.basename(archive_path)
            object_key = f"{config.tos_prefix}/{archive_name}"

            # Upload file to TOS
            tos_url = tos_service.upload_file(archive_path, object_key)

            # Get the actual region resolved by the service, or fallback to config
            actual_region = getattr(tos_service, "actual_region", config.tos_region)

            # Save object key to config for later reference
            config.tos_object_key = object_key

            logger.info(f"File uploaded to TOS: {tos_url} (Region: {actual_region})")
            return tos_url, actual_region

        except Exception as e:
            if "AccountDisable" in str(e):
                raise Exception(
                    "Tos Service is not enabled, please enable it in the console. Enable services at: https://console.volcengine.com/agentkit/region:agentkit+cn-beijing/auth"
                )
            if "TooManyBuckets" in str(e):
                raise Exception(
                    "You have reached the maximum number of buckets allowed. Please delete some buckets and try again."
                )
            raise Exception(f"Failed to upload to TOS: {str(e)}")

    def _prepare_cr_resources(
        self, config: VeCPCRBuilderConfig
    ) -> tuple[CRServiceConfig, str]:
        """Prepare Container Registry resources.

        Ensures CR instance, namespace, and repository exist with public access.
        Auto-creates missing resources when configured with AUTO_CREATE_VE.

        Returns:
            Tuple[CRServiceConfig, str]: (Validated resource info, Actual CR Region used)

        Raises:
            Exception: For CR resource creation or configuration failures.
        """
        try:
            cr_config = CRServiceConfig(
                instance_name=config.cr_instance_name,
                namespace_name=config.cr_namespace_name,
                repo_name=config.cr_repo_name,
                auto_create_instance_type=config.cr_auto_create_instance_type,
                region=config.cr_region,
            )

            # Config update callback to sync CR resource names back to builder config
            def config_updater(service: str, cr_config_dict: Dict[str, Any]) -> None:
                """Callback to update builder config with auto-created CR resource names."""
                if "instance_name" in cr_config_dict:
                    config.cr_instance_name = cr_config_dict["instance_name"]
                if "namespace_name" in cr_config_dict:
                    config.cr_namespace_name = cr_config_dict["namespace_name"]
                if "repo_name" in cr_config_dict:
                    config.cr_repo_name = cr_config_dict["repo_name"]
                if "image_full_url" in cr_config_dict:
                    config.image_url = cr_config_dict["image_full_url"]

            from agentkit.toolkit.volcengine.services import (
                CRService,
                DefaultCRConfigCallback,
            )

            cr_service = CRService(
                config_callback=DefaultCRConfigCallback(config_updater=config_updater),
                reporter=self.reporter,
            )

            common_config = config.common_config

            # Ensure CR resources exist (instance, namespace, repository)
            self.reporter.info("Ensuring CR resources exist...")
            cr_result = cr_service.ensure_cr_resources(cr_config, common_config)

            if not cr_result.success:
                raise Exception(cr_result.error)

            # Ensure public endpoint access for image pulls (controlled by global config)
            try:
                from agentkit.toolkit.config.global_config import get_global_config

                gc = get_global_config()
                do_check = getattr(
                    getattr(gc, "defaults", None), "cr_public_endpoint_check", None
                )
            except Exception:
                do_check = None
            if do_check is False:
                self.reporter.info(
                    "Skipping CR public endpoint check per global config"
                )
            else:
                self.reporter.info("Ensuring CR public endpoint access...")
                public_result = cr_service.ensure_public_endpoint(cr_config)

                if not public_result.success:
                    error_msg = (
                        f"Public endpoint configuration failed: {public_result.error}"
                    )
                    raise Exception(error_msg)

            self.reporter.success("CR resource preparation completed")
            self.reporter.info(f"   Instance: {cr_result.instance_name}")
            self.reporter.info(f"   Namespace: {cr_result.namespace_name}")
            self.reporter.info(f"   Repository: {cr_result.repo_name}")

            actual_region = getattr(cr_service, "actual_region", config.cr_region)

            return cr_config, actual_region

        except Exception as e:
            raise Exception(f"Failed to prepare CR resources: {str(e)}")

    def _prepare_pipeline_resources(
        self, config: VeCPCRBuilderConfig, tos_url: str, cr_config: CRServiceConfig
    ) -> str:
        """Prepare Code Pipeline resources.

        Creates or reuses Code Pipeline for build execution. Supports pipeline lookup
        by both ID and name, with intelligent fallback to creation when not found.

        Args:
            config: Build configuration with pipeline settings.
            tos_url: TOS URL of the source archive.
            cr_config: CR configuration for image repository.

        Returns:
            Pipeline ID for build execution.

        Raises:
            Exception: For pipeline creation or configuration failures.
        """
        try:
            from agentkit.toolkit.volcengine.code_pipeline import VeCodePipeline

            cp_client = VeCodePipeline(region=config.cp_region)

            # Get or create agentkit-cli-workspace
            workspace_name = "agentkit-cli-workspace"
            if not cp_client.workspace_exists_by_name(workspace_name):
                logger.info(f"Workspace '{workspace_name}' does not exist, creating...")
                self.reporter.warning(
                    f"Workspace '{workspace_name}' does not exist, creating..."
                )
                workspace_id = cp_client.create_workspace(
                    name=workspace_name,
                    visibility="Account",
                    description="AgentKit CLI dedicated workspace",
                )
                logger.info(f"Workspace created successfully: {workspace_id}")
                self.reporter.success(
                    f"Workspace created successfully: {workspace_name}"
                )
            else:
                # Workspace exists, get its ID
                result = cp_client.get_workspaces_by_name(workspace_name, page_size=1)
                if result.get("Items") and len(result["Items"]) > 0:
                    workspace_id = result["Items"][0]["Id"]
                    logger.info(
                        f"Using existing workspace: {workspace_name} (ID: {workspace_id})"
                    )
                    self.reporter.success(f"Using workspace: {workspace_name}")
                else:
                    raise Exception(f"Unable to get workspace '{workspace_name}' ID")

            logger.info(f"Using workspace: {workspace_name} (ID: {workspace_id})")

            common_config = config.common_config
            agent_name = common_config.agent_name or "agentkit-app"

            # Check if pipeline already exists - try multiple lookup strategies
            # Case 1: If Pipeline ID is configured, use ID for exact lookup

            # tmp: temp fix for pipeline id issue, cp_pipeline_id should be empty string for fix cp name
            config.cp_pipeline_id = ""
            if config.cp_pipeline_id and config.cp_pipeline_id != AUTO_CREATE_VE:
                try:
                    # Get pipeline details by ID
                    result = cp_client.list_pipelines(
                        workspace_id=workspace_id, pipeline_ids=[config.cp_pipeline_id]
                    )

                    if result.get("Items") and len(result["Items"]) > 0:
                        pipeline_info = result["Items"][0]
                        found_pipeline_name = pipeline_info.get("Name", "")

                        # If name is also configured, validate name-ID consistency
                        if (
                            config.cp_pipeline_name
                            and config.cp_pipeline_name != AUTO_CREATE_VE
                        ):
                            if found_pipeline_name != config.cp_pipeline_name:
                                error_msg = f"Pipeline name '{config.cp_pipeline_name}' does not match ID '{config.cp_pipeline_id}' corresponding name '{found_pipeline_name}'. Please verify configuration. If you haven't modified Code Pipeline, remove the current Pipeline ID from yaml config."
                                logger.error(error_msg)
                                self.reporter.error(error_msg)
                                raise Exception(error_msg)

                        # Validation passed, reuse found pipeline
                        logger.info(
                            f"Reusing pipeline by ID: {found_pipeline_name} (ID: {config.cp_pipeline_id})"
                        )
                        self.reporter.success(
                            f"Reusing pipeline by ID: {found_pipeline_name}"
                        )

                        # Update config with pipeline name
                        config.cp_pipeline_name = found_pipeline_name

                        # Save pipeline client for later use
                        self._cp_client = cp_client
                        self._workspace_id = workspace_id

                        # Record resource information
                        if not hasattr(self, "_build_resources"):
                            self._build_resources = {}
                        self._build_resources["pipeline_name"] = found_pipeline_name
                        self._build_resources["pipeline_id"] = config.cp_pipeline_id

                        return config.cp_pipeline_id
                    else:
                        logger.warning(
                            f"Configured Pipeline ID '{config.cp_pipeline_id}' does not exist, will create new pipeline"
                        )
                        self.reporter.warning(
                            "Configured Pipeline ID does not exist, will create new pipeline"
                        )

                except Exception as e:
                    if "does not match" in str(e):
                        raise  # Name-ID mismatch, propagate exception
                    logger.warning(
                        f"Pipeline lookup by ID failed: {str(e)}, will create new pipeline"
                    )

            # Case 2: If only pipeline name is configured (not AUTO_CREATE_VE), lookup by name
            elif config.cp_pipeline_name and config.cp_pipeline_name != AUTO_CREATE_VE:
                try:
                    existing_pipelines = cp_client.list_pipelines(
                        workspace_id=workspace_id, name_filter=config.cp_pipeline_name
                    )

                    if (
                        existing_pipelines.get("Items")
                        and len(existing_pipelines["Items"]) > 0
                    ):
                        # Found existing pipeline
                        pipeline_info = existing_pipelines["Items"][0]
                        pipeline_id = pipeline_info["Id"]
                        found_name = pipeline_info.get("Name", "")

                        logger.info(
                            f"Reusing pipeline by name: {found_name} (ID: {pipeline_id})"
                        )
                        self.reporter.success(f"Reusing pipeline by name: {found_name}")

                        # Update config with pipeline ID
                        config.cp_pipeline_id = pipeline_id

                        # Save pipeline client for later use
                        self._cp_client = cp_client
                        self._workspace_id = workspace_id

                        # Record resource information
                        if not hasattr(self, "_build_resources"):
                            self._build_resources = {}
                        self._build_resources["pipeline_name"] = found_name
                        self._build_resources["pipeline_id"] = pipeline_id

                        return pipeline_id
                    else:
                        logger.warning(
                            f"Configured pipeline name '{config.cp_pipeline_name}' does not exist, will create new pipeline"
                        )
                        self.reporter.warning(
                            "Configured pipeline name does not exist, will create new pipeline"
                        )
                except Exception as e:
                    logger.warning(
                        f"Pipeline lookup by name failed: {str(e)}, will create new pipeline"
                    )

            # If no config or lookup failed, create new pipeline
            pipeline_name = (
                config.cp_pipeline_name
                if config.cp_pipeline_name and config.cp_pipeline_name != AUTO_CREATE_VE
                else f"agentkit-cli-{agent_name}-{generate_random_id(4)}"
            )
            self.reporter.info(f"Creating new pipeline: {pipeline_name}")

            # Load pipeline template
            import jinja2

            # Navigate from current file to project root for template path
            current_file_dir = os.path.dirname(os.path.abspath(__file__))
            # Navigate up: agentkit/toolkit/builders -> agentkit/toolkit -> agentkit -> project_root
            project_root = os.path.dirname(
                os.path.dirname(os.path.dirname(current_file_dir))
            )
            template_path = os.path.join(
                project_root,
                "agentkit",
                "toolkit",
                "resources",
                "templates",
                "code-pipeline-tos-cr-step.j2",
            )

            # Validate template file exists
            if not os.path.exists(template_path):
                error_msg = f"Pipeline template file not found: {template_path}"
                logger.error(error_msg)
                raise FileNotFoundError(error_msg)

            with open(template_path, "r", encoding="utf-8") as f:
                template_content = f.read()

            # Render template with Jinja2
            template = jinja2.Template(template_content)
            spec_template = template.render(
                bucket_name=config.tos_bucket,
                bucket_region=config.tos_region or "cn-beijing",
            )

            # Create pipeline
            logger.info(f"Creating pipeline: {pipeline_name}")
            pipeline_id = cp_client._create_pipeline(
                workspace_id=workspace_id,
                pipeline_name=pipeline_name,
                spec=spec_template,
                parameters=[
                    {
                        "Key": "DOCKERFILE_PATH",
                        "Value": "/workspace/agentkit-app/Dockerfile",
                        "Dynamic": True,
                        "Env": True,
                    },
                    {
                        "Key": "DOWNLOAD_PATH",
                        "Value": "/workspace",
                        "Dynamic": True,
                        "Env": True,
                    },
                    {
                        "Key": "PROJECT_ROOT_DIR",
                        "Value": "/workspace/agentkit-app",
                        "Dynamic": True,
                        "Env": True,
                    },
                    {"Key": "TOS_BUCKET_NAME", "Value": "", "Dynamic": True},
                    {"Key": "TOS_REGION", "Value": "", "Dynamic": True},
                    {
                        "Key": "TOS_PROJECT_FILE_NAME",
                        "Value": "",
                        "Dynamic": True,
                        "Env": True,
                    },
                    {
                        "Key": "TOS_PROJECT_FILE_PATH",
                        "Value": "",
                        "Dynamic": True,
                        "Env": True,
                    },
                    {"Key": "CR_NAMESPACE", "Value": "", "Dynamic": True, "Env": True},
                    {"Key": "CR_INSTANCE", "Value": "", "Dynamic": True, "Env": True},
                    {"Key": "CR_DOMAIN", "Value": "", "Dynamic": True, "Env": True},
                    {"Key": "CR_OCI", "Value": "", "Dynamic": True, "Env": True},
                    {"Key": "CR_TAG", "Value": "", "Dynamic": True, "Env": True},
                    {"Key": "CR_REGION", "Value": "", "Dynamic": True, "Env": True},
                ],
            )

            logger.info(f"Pipeline created successfully: {pipeline_id}")
            self.reporter.success(
                f"Pipeline created successfully: {pipeline_name} (ID: {pipeline_id})"
            )

            # Update config with pipeline information
            config.cp_pipeline_name = pipeline_name
            config.cp_pipeline_id = pipeline_id

            # Save pipeline client for later use
            self._cp_client = cp_client
            self._workspace_id = workspace_id

            # Add pipeline info to build results for upper-level workflow
            if not hasattr(self, "_build_resources"):
                self._build_resources = {}
            self._build_resources["pipeline_name"] = pipeline_name
            self._build_resources["pipeline_id"] = pipeline_id

            return pipeline_id

        except Exception as e:
            raise Exception(f"Failed to prepare pipeline resources: {str(e)}")

    def _execute_build(
        self,
        pipeline_id: str,
        config: VeCPCRBuilderConfig,
        runtime_overrides: Dict[str, Any] = None,
    ) -> str:
        """Execute build using Code Pipeline.

        Triggers pipeline execution with build parameters and monitors progress
        until completion. Downloads and displays logs on failure.

        Args:
            pipeline_id: Code Pipeline ID for build execution.
            config: Build configuration with CR and TOS settings.
            runtime_overrides: Optional dictionary of runtime overrides (e.g. resolved physical regions).
                             Keys: "tos_region", "cr_region", etc.

        Returns:
            Full image URL in Container Registry.

        Raises:
            Exception: For pipeline execution or build failures.
        """
        try:
            # Get saved Code Pipeline client and workspace ID
            if not hasattr(self, "_cp_client") or not hasattr(self, "_workspace_id"):
                raise Exception(
                    "Pipeline client not initialized, please call _prepare_pipeline_resources first"
                )

            cp_client = self._cp_client
            workspace_id = self._workspace_id

            common_config = config.common_config
            agent_name = common_config.agent_name or "agentkit-app"

            # Helper function for log download and display on build failure
            def download_and_show_logs(run_id: str):
                """Download and display build logs helper function."""
                try:
                    self.reporter.info("Downloading build logs...")
                    log_file = cp_client.download_and_merge_pipeline_logs(
                        workspace_id=workspace_id,
                        pipeline_id=pipeline_id,
                        pipeline_run_id=run_id,
                        output_file=f"pipeline_failed_{run_id}.log",
                    )

                    # Read log content
                    with open(log_file, "r", encoding="utf-8") as f:
                        lines = f.readlines()

                    # Display logs through reporter
                    self.reporter.show_logs(
                        title="Build failure logs (first 100 lines)",
                        lines=lines,
                        max_lines=100,
                    )
                    self.reporter.info(f"Complete logs saved to: {log_file}")

                except Exception as log_err:
                    self.reporter.warning(f"Log download failed: {log_err}")

            # Prepare build parameters for pipeline execution
            overrides = runtime_overrides or {}
            tos_region = overrides.get("tos_region") or config.tos_region
            cr_region = overrides.get("cr_region") or config.cr_region

            build_parameters = [
                {"Key": "TOS_BUCKET_NAME", "Value": config.tos_bucket},
                {"Key": "TOS_REGION", "Value": tos_region},
                {
                    "Key": "TOS_PROJECT_FILE_NAME",
                    "Value": os.path.basename(config.tos_object_key),
                },
                {"Key": "TOS_PROJECT_FILE_PATH", "Value": config.tos_object_key},
                {"Key": "PROJECT_ROOT_DIR", "Value": f"/workspace/{agent_name}"},
                {"Key": "DOWNLOAD_PATH", "Value": "/workspace"},
                {
                    "Key": "DOCKERFILE_PATH",
                    "Value": f"/workspace/{agent_name}/Dockerfile",
                },
                {"Key": "CR_INSTANCE", "Value": config.cr_instance_name},
                {
                    "Key": "CR_DOMAIN",
                    "Value": f"{config.cr_instance_name}-{cr_region}.cr.volces.com",
                },
                {"Key": "CR_NAMESPACE", "Value": config.cr_namespace_name},
                {"Key": "CR_OCI", "Value": config.cr_repo_name},
                {"Key": "CR_TAG", "Value": config.image_tag},
                {"Key": "CR_REGION", "Value": cr_region},
            ]

            # Execute pipeline
            run_id = cp_client.run_pipeline(
                workspace_id=workspace_id,
                pipeline_id=pipeline_id,
                description=f"Build Agent: {agent_name}",
                parameters=build_parameters,
            )

            self.reporter.success(f"Pipeline triggered successfully, run ID: {run_id}")
            self.reporter.info("Waiting for build completion...")

            # Wait for build completion using reporter's long task interface
            max_wait_time = 900  # 15 minutes
            check_interval = 3  # Check every 3 seconds
            expected_time = (
                30  # Controls progress curve speed (smaller = faster initial progress)
            )
            import time

            start_time = time.time()

            with self.reporter.long_task(
                "Waiting for build completion...", total=max_wait_time
            ) as task:
                last_status = None

                while True:
                    try:
                        status = retry(
                            lambda: cp_client.get_pipeline_run_status(
                                workspace_id=workspace_id,
                                pipeline_id=pipeline_id,
                                run_id=run_id,
                            )
                        )

                        # Update progress description
                        if status != last_status:
                            task.update(description=f"Build status: {status}")
                            last_status = status

                        # Check if completed
                        if status == "Succeeded":
                            task.update(completed=max_wait_time)  # 100%
                            break
                        elif status in ["Failed", "Cancelled", "Timeout"]:
                            task.update(description=f"Build failed: {status}")
                            error_msg = f"Pipeline execution failed, status: {status}"
                            self.reporter.error(error_msg)
                            download_and_show_logs(run_id)
                            raise Exception(error_msg)
                        elif status in [
                            "InProgress",
                            "Enqueued",
                            "Dequeued",
                            "Initializing",
                        ]:
                            # Continue waiting, update progress
                            elapsed_time = time.time() - start_time
                            if elapsed_time >= max_wait_time:
                                task.update(description="Wait timeout")
                                error_msg = f"Wait timeout ({max_wait_time}s), current status: {status}"
                                self.reporter.error(error_msg)
                                download_and_show_logs(run_id)
                                raise Exception(error_msg)

                            task.update(
                                completed=calculate_nonlinear_progress(
                                    elapsed_time, max_wait_time, expected_time
                                )
                            )
                            time.sleep(check_interval)
                        else:
                            # Unknown status
                            elapsed_time = time.time() - start_time
                            if elapsed_time >= max_wait_time:
                                task.update(description="Wait timeout")
                                error_msg = f"Wait timeout ({max_wait_time}s), final status: {status}"
                                self.reporter.error(error_msg)
                                download_and_show_logs(run_id)
                                raise Exception(error_msg)

                            task.update(
                                completed=calculate_nonlinear_progress(
                                    elapsed_time, max_wait_time, expected_time
                                )
                            )
                            time.sleep(check_interval)

                    except Exception:
                        # Exception will auto-propagate, task context will auto-cleanup
                        raise

            # Build completed successfully
            self.reporter.success("Pipeline execution completed!")

            # Construct image URL: [instance-name]-[region].cr.volces.com
            image_url = f"{config.cr_instance_name}-{cr_region}.cr.volces.com/{config.cr_namespace_name}/{config.cr_repo_name}:{config.image_tag}"
            config.image_url = image_url

            return image_url

        except Exception as e:
            raise Exception(f"Build execution failed: {str(e)}")
