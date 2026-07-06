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
import os
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Optional

from agentkit.toolkit.builders.ve_pipeline import VeCPCRBuilder
from agentkit.toolkit.config import (
    AUTO_CREATE_VE,
    DEFAULT_CR_NAMESPACE,
    DEFAULT_IMAGE_TAG,
)
from agentkit.toolkit.config.dataclass_utils import AutoSerializableMixin
from agentkit.toolkit.errors import ErrorCode
from agentkit.toolkit.models import BuildResult, ImageInfo
from agentkit.utils.misc import calculate_nonlinear_progress, retry

logger = logging.getLogger(__name__)

# Sandbox builds use a fixed default repo/workspace so repeated builds reuse the
# same CR repository while timestamp tags create distinct image versions.
DEFAULT_SANDBOX_REPO_NAME = "agentkit-custom-sandbox-image"
DEFAULT_SANDBOX_PIPELINE_NAME_PREFIX = "arkclaw_custom_sandbox_image_pipeline"
DEFAULT_SANDBOX_PROJECT_ROOT = "/workspace/sandbox"
DEFAULT_SANDBOX_TOS_PREFIX = "agentkit-sandbox-builds"
DEFAULT_SANDBOX_WORKSPACE_NAME = "agentkit-custom-sandbox-image"


@dataclass
class VeSandboxCPCRBuilderConfig(AutoSerializableMixin):
    """Cloud builder configuration for custom Sandbox images."""

    dockerfile: str = field(
        default="Dockerfile",
        metadata={"description": "Dockerfile path relative to project directory"},
    )
    image_tag: str = field(
        default=DEFAULT_IMAGE_TAG,
        metadata={"description": "Image tag", "render_template": True},
    )

    tos_bucket: str = field(
        default=AUTO_CREATE_VE,
        metadata={"description": "TOS bucket name", "render_template": True},
    )
    tos_region: str = field(default="cn-beijing", metadata={"description": "TOS region"})
    tos_prefix: str = field(
        default=DEFAULT_SANDBOX_TOS_PREFIX,
        metadata={"description": "TOS path prefix"},
    )

    cr_instance_name: str = field(
        default=AUTO_CREATE_VE,
        metadata={"description": "CR instance name", "render_template": True},
    )
    cr_namespace_name: str = field(
        default=DEFAULT_CR_NAMESPACE,
        metadata={"description": "CR namespace", "render_template": True},
    )
    cr_repo_name: str = field(
        default=DEFAULT_SANDBOX_REPO_NAME,
        metadata={"description": "CR repository name"},
    )
    cr_auto_create_instance_type: str = field(
        default="Micro",
        metadata={"description": "CR instance type when auto-creating"},
    )
    cr_region: str = field(default="cn-beijing", metadata={"description": "CR region"})

    cp_workspace_name: str = field(
        default=DEFAULT_SANDBOX_WORKSPACE_NAME,
        metadata={"description": "Code Pipeline workspace name"},
    )
    cp_pipeline_name: str = field(
        default="",
        metadata={"description": "Code Pipeline name"},
    )
    cp_pipeline_id: str = field(default="", metadata={"description": "Code Pipeline ID"})
    cp_region: str = field(default="cn-beijing", metadata={"description": "CP region"})

    cloud_provider: Optional[str] = field(default=None, metadata={"system": True})
    tos_object_key: Optional[str] = field(default=None, metadata={"system": True})
    image_url: Optional[str] = field(default=None, metadata={"system": True})
    build_timestamp: Optional[str] = field(default=None, metadata={"system": True})

    def __post_init__(self):
        self.common_config = SimpleNamespace(
            agent_name="sandbox",
            cloud_provider=self.cloud_provider,
        )
        if not self.cp_pipeline_name:
            # Pipeline is a CP resource, so its default name follows cp_region.
            self.cp_pipeline_name = self.default_pipeline_name()
        self._render_template_fields()

    def default_pipeline_name(self) -> str:
        return f"{DEFAULT_SANDBOX_PIPELINE_NAME_PREFIX}-{self.cp_region}"


class VeSandboxCPCRBuilder(VeCPCRBuilder):
    """Build custom Sandbox images with TOS + Code Pipeline + Volcano CR."""

    def build(self, config: VeSandboxCPCRBuilderConfig) -> BuildResult:
        resources: Dict[str, Any] = {}
        try:
            dockerfile_rel = self._validate_dockerfile_path(config.dockerfile)
            config.dockerfile = dockerfile_rel

            self.reporter.info("Starting sandbox cloud build process...")
            self.reporter.info("1/5 Creating project archive...")
            resources["archive_path"] = self._create_project_archive(config)

            self.reporter.info("2/5 Uploading to TOS...")
            resources["tos_url"], resources["tos_actual_region"] = self._upload_to_tos(
                resources["archive_path"], config
            )
            resources["tos_object_key"] = config.tos_object_key
            resources["tos_bucket"] = config.tos_bucket

            self.reporter.info("3/5 Preparing CR resources...")
            resources["cr_config"], resources["cr_actual_region"] = (
                self._prepare_cr_resources(config)
            )

            self.reporter.info("4/5 Preparing Code Pipeline resources...")
            resources["pipeline_id"] = self._prepare_pipeline_resources(
                config, resources["tos_url"], resources["cr_config"]
            )
            if hasattr(self, "_build_resources"):
                resources.update(
                    {
                        k: v
                        for k, v in self._build_resources.items()
                        if k in {"pipeline_name", "pipeline_id"}
                    }
                )

            self.reporter.info("5/5 Executing sandbox build...")
            resources["image_url"] = self._execute_build(
                resources["pipeline_id"],
                config,
                runtime_overrides={
                    "tos_region": resources.get("tos_actual_region"),
                    "cr_region": resources.get("cr_actual_region"),
                },
            )
            self.reporter.success(
                f"Sandbox image build completed: {resources['image_url']}"
            )

            config.image_url = resources["image_url"]
            config.cp_pipeline_id = resources["pipeline_id"]
            config.build_timestamp = datetime.now().isoformat()

            repository, tag = resources["image_url"].rsplit(":", 1)
            return BuildResult(
                success=True,
                image=ImageInfo(repository=repository, tag=tag),
                build_timestamp=datetime.fromisoformat(config.build_timestamp),
                metadata={
                    "cr_image_url": resources["image_url"],
                    "cp_pipeline_id": resources["pipeline_id"],
                    "cp_pipeline_name": resources.get("pipeline_name"),
                    "cr_instance_name": config.cr_instance_name,
                    "cr_namespace_name": config.cr_namespace_name,
                    "cr_repo_name": config.cr_repo_name,
                    "tos_object_url": resources["tos_url"],
                    "tos_object_key": config.tos_object_key,
                    "tos_bucket": config.tos_bucket,
                    "dockerfile": config.dockerfile,
                    "resources": resources,
                },
            )
        except Exception as e:
            logger.exception("Sandbox cloud build failed")
            return BuildResult(
                success=False,
                error=str(e),
                error_code=ErrorCode.BUILD_FAILED,
                build_timestamp=datetime.now(),
                metadata={"resources": resources},
            )

    def check_artifact_exists(self, config: VeSandboxCPCRBuilderConfig) -> bool:
        return bool(getattr(config, "image_url", None))

    def remove_artifact(self, config: VeSandboxCPCRBuilderConfig) -> bool:
        return True

    def _validate_dockerfile_path(self, dockerfile: str) -> str:
        """Return a normalized Dockerfile path relative to the build context."""
        dockerfile = (dockerfile or "Dockerfile").strip() or "Dockerfile"
        candidate = Path(dockerfile)
        if candidate.is_absolute():
            raise ValueError(
                "--dockerfile must be a path relative to the project directory"
            )

        resolved = (self.workdir / candidate).resolve()
        try:
            rel = resolved.relative_to(self.workdir.resolve())
        except ValueError:
            raise ValueError("--dockerfile must not point outside the project directory")

        if not resolved.is_file():
            raise FileNotFoundError(f"Dockerfile not found: {rel.as_posix()}")

        return rel.as_posix()

    def _create_project_archive(self, config: VeSandboxCPCRBuilderConfig) -> str:
        try:
            from agentkit.toolkit.volcengine.utils.project_archiver import (
                ArchiveConfig,
                ProjectArchiver,
            )

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_name = f"sandbox_{timestamp}_{uuid.uuid4().hex[:8]}"

            temp_dir = tempfile.mkdtemp()
            source_base_path = self.workdir
            dockerignore_path = source_base_path / ".dockerignore"
            dockerignore_path_str = (
                str(dockerignore_path) if dockerignore_path.is_file() else None
            )

            archive_config = ArchiveConfig(
                source_dir=str(source_base_path),
                output_dir=temp_dir,
                archive_name=archive_name,
                dockerignore_path=dockerignore_path_str,
            )
            archiver = ProjectArchiver(archive_config)
            files_to_include = archiver.collect_files_to_include()

            dockerfile_path = (source_base_path / config.dockerfile).resolve()
            # A custom Dockerfile must always be present in the remote build context,
            # even when a local .dockerignore pattern would otherwise exclude it.
            if dockerfile_path not in files_to_include:
                files_to_include.append(dockerfile_path)

            total_size_bytes = 0
            included_files_with_size: list[tuple[str, int]] = []
            for p in files_to_include:
                try:
                    rel = p.relative_to(source_base_path).as_posix()
                    size = p.stat().st_size
                except Exception:
                    continue
                total_size_bytes += size
                included_files_with_size.append((rel, size))

            size_threshold_bytes = 100 * 1024 * 1024
            if total_size_bytes > size_threshold_bytes:
                self._warn_large_archive(
                    total_size_bytes=total_size_bytes,
                    threshold_bytes=size_threshold_bytes,
                    included_files_with_size=included_files_with_size,
                )
                if sys.stdin.isatty():
                    confirmed = self.reporter.confirm(
                        message=(
                            "The archive to be uploaded is larger than 100 MiB. "
                            "Continue uploading?"
                        ),
                        default=False,
                    )
                    if not confirmed:
                        raise Exception("Build aborted by user")

            archive_path = archiver.create_archive(files_to_include=files_to_include)
            self.reporter.success(f"Project archive created: {archive_path}")
            return archive_path
        except Exception as e:
            raise Exception(f"Failed to create project archive: {str(e)}")

    def _prepare_pipeline_resources(
        self, config: VeSandboxCPCRBuilderConfig, tos_url: str, cr_config: Any
    ) -> str:
        """Create or reuse the CP workspace and pipeline for sandbox image builds."""
        try:
            from agentkit.toolkit.volcengine.code_pipeline import VeCodePipeline

            provider = getattr(config, "cloud_provider", None)
            cp_client = VeCodePipeline(region=config.cp_region, provider=provider)

            workspace_name = config.cp_workspace_name or DEFAULT_SANDBOX_WORKSPACE_NAME
            workspace_id = self._get_or_create_workspace(cp_client, workspace_name)

            pipeline_name = config.cp_pipeline_name or config.default_pipeline_name()
            pipeline_id = self._get_or_create_pipeline(
                cp_client, workspace_id, pipeline_name
            )

            config.cp_pipeline_name = pipeline_name
            config.cp_pipeline_id = pipeline_id
            self._cp_client = cp_client
            self._workspace_id = workspace_id
            self._build_resources = {
                "pipeline_name": pipeline_name,
                "pipeline_id": pipeline_id,
            }
            return pipeline_id
        except Exception as e:
            logger.exception("Failed to prepare sandbox pipeline resources")
            raise Exception(
                f"Failed to prepare sandbox pipeline resources: {str(e)}, "
                "Please check Code Pipeline Service is enabled."
            )

    def _get_or_create_workspace(self, cp_client: Any, workspace_name: str) -> str:
        result = cp_client.get_workspaces_by_name(workspace_name, page_size=100)
        for workspace in result.get("Items", []):
            if workspace.get("Name") == workspace_name:
                self.reporter.success(f"Using workspace: {workspace_name}")
                return workspace["Id"]

        if result.get("Items"):
            fuzzy_names = ", ".join(
                item.get("Name", "<unknown>") for item in result.get("Items", [])
            )
            self.reporter.info(
                f"Ignoring non-exact workspace matches for '{workspace_name}': "
                f"{fuzzy_names}"
            )

        self.reporter.warning(
            f"Workspace '{workspace_name}' exact match not found, creating..."
        )
        workspace_id = cp_client.create_workspace(
            name=workspace_name,
            visibility="Account",
            description="AgentKit sandbox image workspace",
        )
        self.reporter.success(f"Workspace created successfully: {workspace_name}")
        return workspace_id

    def _get_or_create_pipeline(
        self, cp_client: Any, workspace_id: str, pipeline_name: str
    ) -> str:
        existing_pipelines = cp_client.list_pipelines(
            workspace_id=workspace_id, name_filter=pipeline_name
        )
        for pipeline_info in existing_pipelines.get("Items", []):
            found_name = pipeline_info.get("Name", pipeline_name)
            if found_name == pipeline_name:
                self.reporter.success(f"Reusing pipeline by name: {found_name}")
                return pipeline_info["Id"]

        if existing_pipelines.get("Items"):
            fuzzy_names = ", ".join(
                item.get("Name", "<unknown>")
                for item in existing_pipelines.get("Items", [])
            )
            self.reporter.info(
                f"Ignoring non-exact pipeline matches for '{pipeline_name}': "
                f"{fuzzy_names}"
            )

        self.reporter.info(f"Creating new pipeline: {pipeline_name}")
        pipeline_id = cp_client._create_pipeline(
            workspace_id=workspace_id,
            pipeline_name=pipeline_name,
            spec=self._render_pipeline_spec(),
            parameters=self._pipeline_parameter_schema(),
        )
        self.reporter.success(
            f"Pipeline created successfully: {pipeline_name} (ID: {pipeline_id})"
        )
        return pipeline_id

    def _render_pipeline_spec(self) -> str:
        template_path = (
            Path(__file__).resolve().parent.parent
            / "resources"
            / "templates"
            / "code-pipeline-sandbox-tos-cr-step.j2"
        )
        if not template_path.exists():
            raise FileNotFoundError(f"Pipeline template file not found: {template_path}")
        return template_path.read_text(encoding="utf-8")

    def _pipeline_parameter_schema(self) -> list[dict[str, Any]]:
        """Parameters declared on pipeline creation; values are filled per run."""
        return [
            {
                "Key": "DOCKERFILE_PATH",
                "Value": f"{DEFAULT_SANDBOX_PROJECT_ROOT}/Dockerfile",
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
                "Value": DEFAULT_SANDBOX_PROJECT_ROOT,
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
        ]

    def _execute_build(
        self,
        pipeline_id: str,
        config: VeSandboxCPCRBuilderConfig,
        runtime_overrides: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Run the prepared pipeline and return the pushed CR image URL."""
        try:
            if not hasattr(self, "_cp_client") or not hasattr(self, "_workspace_id"):
                raise Exception(
                    "Pipeline client not initialized, please call _prepare_pipeline_resources first"
                )

            cp_client = self._cp_client
            workspace_id = self._workspace_id
            overrides = runtime_overrides or {}
            tos_region = overrides.get("tos_region") or config.tos_region
            cr_region = overrides.get("cr_region") or config.cr_region
            cr_domain = self._resolve_cr_domain(config, cr_region)
            build_parameters = self._build_pipeline_parameters(
                config=config,
                tos_region=tos_region,
                cr_region=cr_region,
                cr_domain=cr_domain,
            )

            run_id = self._start_pipeline_run(
                cp_client=cp_client,
                workspace_id=workspace_id,
                pipeline_id=pipeline_id,
                config=config,
                build_parameters=build_parameters,
            )
            self._wait_pipeline_run(
                cp_client=cp_client,
                workspace_id=workspace_id,
                pipeline_id=pipeline_id,
                run_id=run_id,
            )

            image_url = (
                f"{cr_domain}/{config.cr_namespace_name}/"
                f"{config.cr_repo_name}:{config.image_tag}"
            )
            config.image_url = image_url
            return image_url
        except Exception as e:
            raise Exception(f"Sandbox build execution failed: {str(e)}")

    def _build_pipeline_parameters(
        self,
        config: VeSandboxCPCRBuilderConfig,
        tos_region: str,
        cr_region: str,
        cr_domain: str,
    ) -> list[dict[str, Any]]:
        """Build runtime parameters passed to a single CP pipeline run."""
        # The archive is extracted into DEFAULT_SANDBOX_PROJECT_ROOT in CP, so the
        # user-provided relative Dockerfile path must be rebuilt under that root.
        dockerfile_path = f"{DEFAULT_SANDBOX_PROJECT_ROOT}/{config.dockerfile}"
        return [
            {"Key": "TOS_BUCKET_NAME", "Value": config.tos_bucket},
            {"Key": "TOS_REGION", "Value": tos_region},
            {
                "Key": "TOS_PROJECT_FILE_NAME",
                "Value": os.path.basename(config.tos_object_key),
            },
            {"Key": "TOS_PROJECT_FILE_PATH", "Value": config.tos_object_key},
            {"Key": "PROJECT_ROOT_DIR", "Value": DEFAULT_SANDBOX_PROJECT_ROOT},
            {"Key": "DOWNLOAD_PATH", "Value": "/workspace"},
            {"Key": "DOCKERFILE_PATH", "Value": dockerfile_path},
            {"Key": "CR_INSTANCE", "Value": config.cr_instance_name},
            {"Key": "CR_DOMAIN", "Value": cr_domain},
            {"Key": "CR_NAMESPACE", "Value": config.cr_namespace_name},
            {"Key": "CR_OCI", "Value": config.cr_repo_name},
            {"Key": "CR_TAG", "Value": config.image_tag},
            {"Key": "CR_REGION", "Value": cr_region},
        ]

    def _start_pipeline_run(
        self,
        cp_client: Any,
        workspace_id: str,
        pipeline_id: str,
        config: VeSandboxCPCRBuilderConfig,
        build_parameters: list[dict[str, Any]],
    ) -> str:
        run_id = cp_client.run_pipeline(
            workspace_id=workspace_id,
            pipeline_id=pipeline_id,
            description=f"Build Sandbox Image: {config.cr_repo_name}",
            parameters=build_parameters,
        )
        self.reporter.success(f"Pipeline triggered successfully, run ID: {run_id}")
        self.reporter.info("Waiting for sandbox image build completion...")
        return run_id

    def _wait_pipeline_run(
        self,
        cp_client: Any,
        workspace_id: str,
        pipeline_id: str,
        run_id: str,
    ) -> None:
        max_wait_time = 900
        check_interval = 3
        expected_time = 30
        start_time = time.time()

        with self.reporter.long_task(
            "Waiting for sandbox image build completion...", total=max_wait_time
        ) as task:
            last_status = None
            while True:
                status = retry(
                    lambda: cp_client.get_pipeline_run_status(
                        workspace_id=workspace_id,
                        pipeline_id=pipeline_id,
                        run_id=run_id,
                    )
                )
                if status != last_status:
                    task.update(description=f"Build status: {status}")
                    last_status = status

                if status == "Succeeded":
                    task.update(completed=max_wait_time)
                    return
                if status in ["Failed", "Cancelled", "Timeout"]:
                    task.update(description=f"Build failed: {status}")
                    self._handle_pipeline_failure_logs(
                        cp_client, workspace_id, pipeline_id, run_id
                    )
                    raise Exception(f"Pipeline execution failed, status: {status}")

                elapsed_time = time.time() - start_time
                if elapsed_time >= max_wait_time:
                    task.update(description="Wait timeout")
                    self._handle_pipeline_failure_logs(
                        cp_client, workspace_id, pipeline_id, run_id
                    )
                    raise Exception(
                        f"Wait timeout ({max_wait_time}s), current status: {status}"
                    )
                task.update(
                    completed=calculate_nonlinear_progress(
                        elapsed_time, max_wait_time, expected_time
                    )
                )
                time.sleep(check_interval)

    def _handle_pipeline_failure_logs(
        self, cp_client: Any, workspace_id: str, pipeline_id: str, run_id: str
    ) -> None:
        try:
            self.reporter.info("Downloading sandbox build logs...")
            log_file = cp_client.download_and_merge_pipeline_logs(
                workspace_id=workspace_id,
                pipeline_id=pipeline_id,
                pipeline_run_id=run_id,
                output_file=f"sandbox_pipeline_failed_{run_id}.log",
            )
            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            self.reporter.show_logs(
                title="Sandbox build failure logs (first 100 lines)",
                lines=lines,
                max_lines=100,
            )
            self.reporter.info(f"Complete logs saved to: {log_file}")
        except Exception as log_err:
            self.reporter.warning(f"Log download failed: {log_err}")
