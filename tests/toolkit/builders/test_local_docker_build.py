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

"""Behavioral coverage for ``LocalDockerBuilder.build``.

This module exercises the real Docker image build *orchestration* branch by
branch, replacing only the Docker daemon boundary (``DockerManager``) with a
hand-rolled fake. The Jinja2 render, cloud-provider resolution, base-image
defaults, template hashing, ``DockerfileManager`` decision/write, and
``.dockerignore`` creation all run for real against ``tmp_path`` and the
packaged templates -- so the assertions below prove the actual control flow,
error-code mapping, and result shapes, not merely that the function imports.

The seam: the constructor does ``self.docker_manager = DockerManager()`` (with
``DockerManager`` lazily imported from ``agentkit.toolkit.docker.container``).
We patch that name at its source module *before* construction so the ctor
never touches ``docker.from_env()``; the sibling ``DockerfileRenderer`` import
in ``build`` stays real.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

import pytest

import agentkit.toolkit.docker.container as container_mod
from agentkit.toolkit.builders.local_docker import (
    LocalDockerBuilder,
    LocalDockerBuilderConfig,
)
from agentkit.toolkit.config import CommonConfig, DockerBuildConfig
from agentkit.toolkit.errors import ErrorCode


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeDockerManager:
    """Stand-in for ``agentkit.toolkit.docker.container.DockerManager``.

    Matches the real method names and return shapes:
      - ``is_docker_available() -> Tuple[bool, str]``
      - ``build_image(**kwargs) -> Tuple[bool, str, Optional[str]]``
    Class-level attributes configure per-test behavior and record calls; they
    are reset by the autouse fixture below so tests never leak into each other.
    """

    # --- configurable behavior (class-level) ---
    available: Tuple[bool, str] = (True, "Docker is available (Version: test)")
    build_return: Tuple[bool, str, Optional[str]] = (
        True,
        "Step 1/5 : FROM base\nSuccessfully built abc123",
        "sha256:deadbeefimageid",
    )

    # --- recorded calls (class-level) ---
    build_calls: List[dict] = []
    availability_checks: int = 0

    def __init__(self, *args, **kwargs):
        # The real ctor calls docker.from_env(); we intentionally do nothing.
        pass

    def is_docker_available(self) -> Tuple[bool, str]:
        type(self).availability_checks += 1
        return type(self).available

    def build_image(self, **kwargs) -> Tuple[bool, str, Optional[str]]:
        type(self).build_calls.append(dict(kwargs))
        return type(self).build_return


@pytest.fixture(autouse=True)
def _reset_fake_state(monkeypatch):
    """Reset mutable fake state and pin env for deterministic provider resolution."""
    _FakeDockerManager.available = (True, "Docker is available (Version: test)")
    _FakeDockerManager.build_return = (
        True,
        "Step 1/5 : FROM base\nSuccessfully built abc123",
        "sha256:deadbeefimageid",
    )
    _FakeDockerManager.build_calls = []
    _FakeDockerManager.availability_checks = 0

    # read_cloud_provider_from_env reads these; keep them absent so provider
    # resolution is driven by config only (deterministic -> volcengine).
    monkeypatch.delenv("AGENTKIT_CLOUD_PROVIDER", raising=False)
    monkeypatch.delenv("CLOUD_PROVIDER", raising=False)

    # Swap the DockerManager name at its source module so the ctor builds the
    # fake instead of connecting to a Docker daemon.
    monkeypatch.setattr(container_mod, "DockerManager", _FakeDockerManager)
    yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_builder(project_dir: Path) -> LocalDockerBuilder:
    """Construct the builder; ctor picks up the patched fake DockerManager."""
    builder = LocalDockerBuilder(project_dir=project_dir)
    assert isinstance(builder.docker_manager, _FakeDockerManager)
    return builder


def _python_common(**overrides) -> CommonConfig:
    base = dict(
        agent_name="myagent",
        entry_point="agent.py",
        language="Python",
        language_version="3.12",
        dependencies_file="requirements.txt",
    )
    base.update(overrides)
    return CommonConfig(**base)


def _golang_common(entry_point: str, **overrides) -> CommonConfig:
    base = dict(
        agent_name="mygoagent",
        entry_point=entry_point,
        language="Golang",
        language_version="1.24",
    )
    base.update(overrides)
    return CommonConfig(**base)


# ---------------------------------------------------------------------------
# Happy path (Python)
# ---------------------------------------------------------------------------


def test_python_happy_path_returns_image_info_and_calls_build_image(tmp_path):
    builder = _make_builder(tmp_path)
    config = LocalDockerBuilderConfig(
        common_config=_python_common(),
        image_name="my-repo",
        image_tag="v1.2",
    )

    result = builder.build(config)

    assert result.success is True
    assert result.error is None
    assert result.error_code is None
    # ImageInfo is assembled from image_name/image_tag and the image_id digest.
    assert result.image is not None
    assert result.image.repository == "my-repo"
    assert result.image.tag == "v1.2"
    assert result.image.digest == "sha256:deadbeefimageid"
    assert result.image.full_name == "my-repo:v1.2"
    # build_logs is normalized to a list of lines (split from build_image's
    # single log string) for a consistent BuildResult.build_logs contract.
    assert isinstance(result.build_logs, list)
    assert "Successfully built abc123" in result.build_logs
    assert result.build_timestamp is not None

    # A real Dockerfile was rendered + written to the workdir, and .dockerignore too.
    assert (tmp_path / "Dockerfile").exists()
    dockerfile_text = (tmp_path / "Dockerfile").read_text()
    assert "CMD [\"python\", \"-m\", \"agent\"]" in dockerfile_text
    assert (tmp_path / ".dockerignore").exists()

    # build_image was invoked exactly once with the resolved name/tag/context dir.
    assert len(_FakeDockerManager.build_calls) == 1
    call = _FakeDockerManager.build_calls[0]
    assert call["image_name"] == "my-repo"
    assert call["image_tag"] == "v1.2"
    assert call["dockerfile_path"] == str(tmp_path)
    assert call["build_args"] == {}
    # platform not supplied -> not forwarded
    assert "platform" not in call


def test_python_default_image_name_and_tag_when_blank(tmp_path):
    builder = _make_builder(tmp_path)
    # image_name blank, image_tag blank -> defaults agentkit-app / latest
    config = LocalDockerBuilderConfig(
        common_config=_python_common(),
        image_name="",
        image_tag="",
    )

    result = builder.build(config)

    assert result.success is True
    assert result.image.repository == "agentkit-app"
    assert result.image.tag == "latest"
    call = _FakeDockerManager.build_calls[0]
    assert call["image_name"] == "agentkit-app"
    assert call["image_tag"] == "latest"


def test_python_missing_dependencies_file_is_created_empty(tmp_path):
    # dependencies_file is referenced in context; if absent it is written empty.
    builder = _make_builder(tmp_path)
    config = LocalDockerBuilderConfig(common_config=_python_common())

    assert not (tmp_path / "requirements.txt").exists()
    result = builder.build(config)

    assert result.success is True
    dep_file = tmp_path / "requirements.txt"
    assert dep_file.exists()
    assert dep_file.read_text() == ""


def test_platform_forwarded_when_specified_and_not_auto(tmp_path):
    builder = _make_builder(tmp_path)
    config = LocalDockerBuilderConfig(
        common_config=_python_common(),
        docker_build_config=DockerBuildConfig(platform="linux/arm64"),
    )

    result = builder.build(config)

    assert result.success is True
    call = _FakeDockerManager.build_calls[0]
    assert call["platform"] == "linux/arm64"


def test_platform_auto_is_not_forwarded(tmp_path):
    builder = _make_builder(tmp_path)
    config = LocalDockerBuilderConfig(
        common_config=_python_common(),
        docker_build_config=DockerBuildConfig(platform="auto"),
    )

    result = builder.build(config)

    assert result.success is True
    call = _FakeDockerManager.build_calls[0]
    assert "platform" not in call


def test_python_custom_base_image_is_rendered_into_dockerfile(tmp_path):
    builder = _make_builder(tmp_path)
    config = LocalDockerBuilderConfig(
        common_config=_python_common(),
        docker_build_config=DockerBuildConfig(base_image="python:3.12-slim"),
    )

    result = builder.build(config)

    assert result.success is True
    dockerfile_text = (tmp_path / "Dockerfile").read_text()
    # base_image override wins over the provider default template line.
    assert "FROM python:3.12-slim" in dockerfile_text


# ---------------------------------------------------------------------------
# Early error branches
# ---------------------------------------------------------------------------


def test_missing_common_config_returns_config_missing(tmp_path):
    builder = _make_builder(tmp_path)
    config = LocalDockerBuilderConfig(common_config=None)

    result = builder.build(config)

    assert result.success is False
    assert result.error_code == ErrorCode.CONFIG_MISSING
    assert result.error == "Missing common configuration"
    assert result.build_logs == ["Missing common configuration"]
    # Short-circuits before ever checking docker availability or building.
    assert _FakeDockerManager.availability_checks == 0
    assert _FakeDockerManager.build_calls == []


def test_docker_unavailable_returns_docker_not_available_with_split_logs(tmp_path):
    _FakeDockerManager.available = (False, "Docker is not available: boom\nline two")
    builder = _make_builder(tmp_path)
    config = LocalDockerBuilderConfig(common_config=_python_common())

    result = builder.build(config)

    assert result.success is False
    assert result.error_code == ErrorCode.DOCKER_NOT_AVAILABLE
    assert result.error == "Docker is not available: boom\nline two"
    # The message is split on newlines into build_logs lines.
    assert result.build_logs == ["Docker is not available: boom", "line two"]
    # Never proceeds to build_image.
    assert _FakeDockerManager.build_calls == []


def test_unsupported_language_returns_config_invalid(tmp_path):
    builder = _make_builder(tmp_path)
    # Rust is not a supported language -> CONFIG_INVALID before template selection.
    common = _python_common()
    common.language = "Rust"
    config = LocalDockerBuilderConfig(common_config=common)

    result = builder.build(config)

    assert result.success is False
    assert result.error_code == ErrorCode.CONFIG_INVALID
    assert result.error == "Unsupported language: Rust"
    assert result.build_logs == ["Unsupported language: Rust"]
    assert _FakeDockerManager.build_calls == []


# ---------------------------------------------------------------------------
# build_image failure branch
# ---------------------------------------------------------------------------


def test_build_image_failure_returns_build_failed_with_logs(tmp_path):
    _FakeDockerManager.build_return = (
        False,
        "Step 3/5 : RUN bad\nERROR: build step failed",
        None,
    )
    builder = _make_builder(tmp_path)
    config = LocalDockerBuilderConfig(common_config=_python_common())

    result = builder.build(config)

    assert result.success is False
    assert result.error_code == ErrorCode.BUILD_FAILED
    assert result.error == "Docker build failed"
    assert result.image is None
    # The failing build logs are surfaced on the result.
    assert "ERROR: build step failed" in result.build_logs
    assert result.build_timestamp is not None
    # build_image was actually reached and invoked once.
    assert len(_FakeDockerManager.build_calls) == 1


# ---------------------------------------------------------------------------
# Golang entry-point resolution branches
# ---------------------------------------------------------------------------


def test_golang_build_script_entry_happy_path(tmp_path):
    # entry_point points at an existing .sh file inside a project dir.
    project = tmp_path / "svc"
    project.mkdir()
    (project / "build.sh").write_text("#!/bin/sh\necho build\n")
    (project / "main.go").write_text("package main\nfunc main() {}\n")

    builder = _make_builder(tmp_path)
    config = LocalDockerBuilderConfig(
        common_config=_golang_common(entry_point="svc/build.sh"),
        image_name="go-repo",
        image_tag="v1",
    )

    result = builder.build(config)

    assert result.success is True
    assert result.image.repository == "go-repo"
    assert result.image.digest == "sha256:deadbeefimageid"
    # Sources were copied under workdir/src/<project>/ for the Docker context.
    copied = tmp_path / "src" / "svc" / "build.sh"
    assert copied.exists()
    # The rendered Dockerfile references the .sh entry via the golang template
    # (build script branch runs `sh <entry_relative_path>`).
    dockerfile_text = (tmp_path / "Dockerfile").read_text()
    assert "src/svc/build.sh" in dockerfile_text


def test_golang_directory_entry_happy_path(tmp_path):
    # entry_point points at an existing directory (a Go package).
    pkg = tmp_path / "cmd"
    pkg.mkdir()
    (pkg / "main.go").write_text("package main\nfunc main() {}\n")

    builder = _make_builder(tmp_path)
    # CommonConfig entry_point validation requires .py/.go/.sh; use a .go file
    # path whose resolution falls back to the go.mod project dir. Instead, to
    # exercise the is_dir() branch we give an entry that resolves to a dir via
    # the go.mod discovery fallback below.
    (tmp_path / "go.mod").write_text("module example.com/m\n")
    config = LocalDockerBuilderConfig(
        common_config=_golang_common(entry_point="cmd/app.go"),
    )

    result = builder.build(config)

    # cmd/app.go does not exist -> discovery walks up to tmp_path (has go.mod)
    # -> entry_path becomes the directory tmp_path -> is_dir() branch.
    assert result.success is True
    dockerfile_text = (tmp_path / "Dockerfile").read_text()
    # entry_relative_path is src/<workdir-name> (a directory) -> go build branch.
    assert "src/" + tmp_path.name in dockerfile_text
    assert "go build" in dockerfile_text


def test_golang_single_go_file_entry_returns_config_invalid(tmp_path):
    # An existing single .go file (not .sh, not a dir) -> unsupported entry.
    (tmp_path / "main.go").write_text("package main\nfunc main() {}\n")

    builder = _make_builder(tmp_path)
    config = LocalDockerBuilderConfig(
        common_config=_golang_common(entry_point="main.go"),
    )

    result = builder.build(config)

    assert result.success is False
    assert result.error_code == ErrorCode.CONFIG_INVALID
    assert "single-file compilation is not supported" in result.error
    assert _FakeDockerManager.build_calls == []


def test_golang_missing_entry_and_no_go_mod_returns_config_invalid(tmp_path):
    # entry_point does not exist and no go.mod anywhere -> project-not-found.
    builder = _make_builder(tmp_path)
    config = LocalDockerBuilderConfig(
        common_config=_golang_common(entry_point="missing/app.go"),
    )

    result = builder.build(config)

    assert result.success is False
    assert result.error_code == ErrorCode.CONFIG_INVALID
    assert "Project path not found" in result.error
    assert _FakeDockerManager.build_calls == []
