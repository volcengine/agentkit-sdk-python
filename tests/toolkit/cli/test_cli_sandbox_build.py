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

from typer.testing import CliRunner

from agentkit.toolkit.cli.sandbox.cli import sandbox_app
from agentkit.toolkit.models import BuildResult, ImageInfo

runner = CliRunner()


class _FakeSandboxConfig:
    created = []

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.image_url = None
        type(self).created.append(self)


class _FakeSandboxBuilder:
    created = []
    result = BuildResult(
        success=True,
        image=ImageInfo(repository="registry.example.com/agentkit/demo", tag="v1"),
    )

    def __init__(self, project_dir=None, reporter=None):
        self.project_dir = project_dir
        self.reporter = reporter
        type(self).created.append(self)

    def build(self, config):
        self.config = config
        config.image_url = "registry.example.com/agentkit/demo:v1"
        return type(self).result


def test_sandbox_build_maps_cli_options_to_builder_config(monkeypatch, tmp_path):
    import agentkit.toolkit.builders.ve_sandbox_pipeline as sandbox_pipeline

    _FakeSandboxBuilder.created = []
    _FakeSandboxBuilder.result = BuildResult(
        success=True,
        image=ImageInfo(repository="registry.example.com/ns/custom-image", tag="v2"),
    )
    _FakeSandboxConfig.created = []
    monkeypatch.setattr(
        sandbox_pipeline, "VeSandboxCPCRBuilder", _FakeSandboxBuilder
    )
    monkeypatch.setattr(
        sandbox_pipeline, "VeSandboxCPCRBuilderConfig", _FakeSandboxConfig
    )

    result = runner.invoke(
        sandbox_app,
        [
            "build",
            "--project-dir",
            str(tmp_path),
            "--dockerfile",
            "docker/Sandboxfile",
            "--image-name",
            "custom-image",
            "--tag",
            "v2",
            "--namespace",
            "ns",
        ],
    )

    assert result.exit_code == 0
    assert "Sandbox image build completed successfully" in result.output
    assert _FakeSandboxBuilder.created[0].project_dir == tmp_path
    config = _FakeSandboxConfig.created[0]
    assert config.dockerfile == "docker/Sandboxfile"
    assert config.cr_repo_name == "custom-image"
    assert config.cr_namespace_name == "ns"
    assert config.image_tag == "v2"


def test_sandbox_build_exits_nonzero_on_failed_build(monkeypatch, tmp_path):
    import agentkit.toolkit.builders.ve_sandbox_pipeline as sandbox_pipeline

    _FakeSandboxBuilder.created = []
    _FakeSandboxBuilder.result = BuildResult(success=False, error="pipeline failed")
    _FakeSandboxConfig.created = []
    monkeypatch.setattr(
        sandbox_pipeline, "VeSandboxCPCRBuilder", _FakeSandboxBuilder
    )
    monkeypatch.setattr(
        sandbox_pipeline, "VeSandboxCPCRBuilderConfig", _FakeSandboxConfig
    )

    result = runner.invoke(
        sandbox_app,
        ["build", "--project-dir", str(tmp_path)],
    )

    assert result.exit_code == 1
    assert "Sandbox image build failed: pipeline failed" in result.output
