# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
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

from __future__ import annotations

import types
from types import SimpleNamespace

import pytest

from agentkit.toolkit.builders.ve_sandbox_pipeline import (
    DEFAULT_SANDBOX_PROJECT_ROOT,
    VeSandboxCPCRBuilder,
    VeSandboxCPCRBuilderConfig,
)
from agentkit.toolkit.errors import ErrorCode
from agentkit.toolkit.reporter import Reporter


class _SpyReporter(Reporter):
    def __init__(self):
        self.infos = []
        self.successes = []
        self.warnings = []
        self.errors = []

    def info(self, message: str, **kwargs):
        self.infos.append(message)

    def success(self, message: str, **kwargs):
        self.successes.append(message)

    def warning(self, message: str, **kwargs):
        self.warnings.append(message)

    def error(self, message: str, **kwargs):
        self.errors.append(message)

    def progress(self, message: str, current: int, total: int = 100, **kwargs):
        pass

    def confirm(self, message: str, default: bool = False, **kwargs) -> bool:
        return default

    def long_task(self, description: str, total: float = 100):
        from contextlib import contextmanager

        @contextmanager
        def _cm():
            class _Task:
                def update(self, description=None, completed=None):
                    pass

            yield _Task()

        return _cm()

    def show_logs(self, title: str, lines, max_lines: int = 100):
        pass


def test_validate_dockerfile_path_accepts_relative_paths_inside_project(tmp_path):
    nested = tmp_path / "docker"
    nested.mkdir()
    (nested / "Sandboxfile").write_text("FROM scratch\n", encoding="utf-8")

    builder = VeSandboxCPCRBuilder(project_dir=tmp_path, reporter=_SpyReporter())

    assert builder._validate_dockerfile_path("docker/Sandboxfile") == (
        "docker/Sandboxfile"
    )


def test_validate_dockerfile_path_rejects_absolute_or_missing_paths(tmp_path):
    builder = VeSandboxCPCRBuilder(project_dir=tmp_path, reporter=_SpyReporter())
    outside = tmp_path.parent / "Dockerfile"

    with pytest.raises(ValueError, match="relative to the project directory"):
        builder._validate_dockerfile_path(str(outside))

    with pytest.raises(FileNotFoundError, match="Dockerfile not found"):
        builder._validate_dockerfile_path("Dockerfile")


def test_build_runs_sandbox_pipeline_steps_and_returns_image_info(tmp_path):
    (tmp_path / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    builder = VeSandboxCPCRBuilder(project_dir=tmp_path, reporter=_SpyReporter())
    config = VeSandboxCPCRBuilderConfig(
        cr_instance_name="instance",
        cr_namespace_name="agentkit",
        cr_repo_name="sandbox-image",
        image_tag="v1",
        tos_bucket="bucket",
        tos_region="cn-beijing",
        cr_region="cn-beijing",
        cp_region="cn-beijing",
    )
    calls = []

    def fake_archive(self, cfg):
        calls.append(("_create_project_archive", cfg.dockerfile))
        return "/tmp/archive.tar.gz"

    def fake_upload(self, archive_path, cfg):
        calls.append(("_upload_to_tos", archive_path))
        cfg.tos_object_key = "agentkit-sandbox-builds/archive.tar.gz"
        return "tos://bucket/agentkit-sandbox-builds/archive.tar.gz", "tos-actual"

    def fake_prepare_cr(self, cfg):
        calls.append(("_prepare_cr_resources", cfg.cr_repo_name))
        return SimpleNamespace(instance_name=cfg.cr_instance_name), "cr-actual"

    def fake_prepare_pipeline(self, cfg, tos_url, cr_config):
        calls.append(("_prepare_pipeline_resources", tos_url, cr_config.instance_name))
        self._build_resources = {
            "pipeline_name": "sandbox-pipeline",
            "pipeline_id": "pipeline-id",
        }
        return "pipeline-id"

    def fake_execute(self, pipeline_id, cfg, runtime_overrides=None):
        calls.append(("_execute_build", pipeline_id, runtime_overrides))
        return "instance-cn-beijing.cr.volces.com/agentkit/sandbox-image:v1"

    builder._create_project_archive = types.MethodType(fake_archive, builder)
    builder._upload_to_tos = types.MethodType(fake_upload, builder)
    builder._prepare_cr_resources = types.MethodType(fake_prepare_cr, builder)
    builder._prepare_pipeline_resources = types.MethodType(
        fake_prepare_pipeline, builder
    )
    builder._execute_build = types.MethodType(fake_execute, builder)

    result = builder.build(config)

    assert result.success is True
    assert result.image.repository == (
        "instance-cn-beijing.cr.volces.com/agentkit/sandbox-image"
    )
    assert result.image.tag == "v1"
    assert result.metadata["dockerfile"] == "Dockerfile"
    assert result.metadata["cp_pipeline_id"] == "pipeline-id"
    assert result.metadata["cp_pipeline_name"] == "sandbox-pipeline"
    assert calls == [
        ("_create_project_archive", "Dockerfile"),
        ("_upload_to_tos", "/tmp/archive.tar.gz"),
        (
            "_prepare_cr_resources",
            "sandbox-image",
        ),
        (
            "_prepare_pipeline_resources",
            "tos://bucket/agentkit-sandbox-builds/archive.tar.gz",
            "instance",
        ),
        (
            "_execute_build",
            "pipeline-id",
            {"tos_region": "tos-actual", "cr_region": "cr-actual"},
        ),
    ]


def test_build_returns_failed_result_when_dockerfile_is_missing(tmp_path):
    builder = VeSandboxCPCRBuilder(project_dir=tmp_path, reporter=_SpyReporter())

    result = builder.build(VeSandboxCPCRBuilderConfig())

    assert result.success is False
    assert result.error_code == ErrorCode.BUILD_FAILED
    assert "Dockerfile not found" in result.error


def test_build_pipeline_parameters_resolve_custom_dockerfile_path():
    config = VeSandboxCPCRBuilderConfig(
        dockerfile="docker/Sandboxfile",
        tos_bucket="bucket",
        tos_object_key="prefix/archive.tar.gz",
        cr_instance_name="instance",
        cr_namespace_name="ns",
        cr_repo_name="repo",
        image_tag="v2",
    )
    builder = VeSandboxCPCRBuilder(reporter=_SpyReporter())

    params = builder._build_pipeline_parameters(
        config=config,
        tos_region="tos-actual",
        cr_region="cr-actual",
        cr_domain="instance-cr-actual.cr.volces.com",
    )
    by_key = {param["Key"]: param["Value"] for param in params}

    assert by_key["DOCKERFILE_PATH"] == (
        f"{DEFAULT_SANDBOX_PROJECT_ROOT}/docker/Sandboxfile"
    )
    assert by_key["TOS_PROJECT_FILE_NAME"] == "archive.tar.gz"
    assert by_key["TOS_PROJECT_FILE_PATH"] == "prefix/archive.tar.gz"
    assert by_key["TOS_REGION"] == "tos-actual"
    assert by_key["CR_REGION"] == "cr-actual"
    assert by_key["CR_DOMAIN"] == "instance-cr-actual.cr.volces.com"
    assert by_key["CR_NAMESPACE"] == "ns"
    assert by_key["CR_OCI"] == "repo"
    assert by_key["CR_TAG"] == "v2"


def test_get_or_create_workspace_reuses_exact_name_match(tmp_path):
    class _FakeCPClient:
        def __init__(self):
            self.created = []

        def get_workspaces_by_name(self, name, page_size=10):
            return {
                "Items": [
                    {
                        "Id": "workspace-exact",
                        "Name": "agentkit-custom-sandbox-image",
                    },
                    {
                        "Id": "workspace-kch",
                        "Name": "agentkit-custom-sandbox-image_kch",
                    },
                ],
                "TotalCount": 2,
            }

        def create_workspace(self, name, visibility, description=""):
            self.created.append(name)
            return "workspace-created"

    cp_client = _FakeCPClient()
    builder = VeSandboxCPCRBuilder(project_dir=tmp_path, reporter=_SpyReporter())

    workspace_id = builder._get_or_create_workspace(
        cp_client, "agentkit-custom-sandbox-image"
    )

    assert workspace_id == "workspace-exact"
    assert cp_client.created == []


def test_get_or_create_workspace_ignores_fuzzy_name_match(tmp_path):
    class _FakeCPClient:
        def __init__(self):
            self.created = []

        def get_workspaces_by_name(self, name, page_size=10):
            return {
                "Items": [
                    {
                        "Id": "workspace-kch",
                        "Name": "agentkit-custom-sandbox-image_kch",
                    }
                ],
                "TotalCount": 1,
            }

        def create_workspace(self, name, visibility, description=""):
            self.created.append(
                {
                    "name": name,
                    "visibility": visibility,
                    "description": description,
                }
            )
            return "workspace-exact"

    cp_client = _FakeCPClient()
    builder = VeSandboxCPCRBuilder(project_dir=tmp_path, reporter=_SpyReporter())

    workspace_id = builder._get_or_create_workspace(
        cp_client, "agentkit-custom-sandbox-image"
    )

    assert workspace_id == "workspace-exact"
    assert cp_client.created == [
        {
            "name": "agentkit-custom-sandbox-image",
            "visibility": "Account",
            "description": "AgentKit sandbox image workspace",
        }
    ]


def test_get_or_create_pipeline_ignores_fuzzy_name_match(tmp_path):
    class _FakeCPClient:
        def __init__(self):
            self.created = []

        def list_pipelines(self, workspace_id, name_filter):
            return {
                "Items": [
                    {
                        "Id": "pipeline-kch",
                        "Name": "arkclaw_custom_sandbox_image_pipeline-cn-beijing_kch",
                    }
                ]
            }

        def _create_pipeline(self, workspace_id, pipeline_name, spec, parameters):
            self.created.append(
                {
                    "workspace_id": workspace_id,
                    "pipeline_name": pipeline_name,
                    "spec": spec,
                    "parameters": parameters,
                }
            )
            return "pipeline-exact"

    cp_client = _FakeCPClient()
    builder = VeSandboxCPCRBuilder(project_dir=tmp_path, reporter=_SpyReporter())
    builder._render_pipeline_spec = lambda: "pipeline-spec"
    builder._pipeline_parameter_schema = lambda: [{"Key": "A", "Value": "B"}]

    pipeline_id = builder._get_or_create_pipeline(
        cp_client,
        "workspace-exact",
        "arkclaw_custom_sandbox_image_pipeline-cn-beijing",
    )

    assert pipeline_id == "pipeline-exact"
    assert cp_client.created == [
        {
            "workspace_id": "workspace-exact",
            "pipeline_name": "arkclaw_custom_sandbox_image_pipeline-cn-beijing",
            "spec": "pipeline-spec",
            "parameters": [{"Key": "A", "Value": "B"}],
        }
    ]
