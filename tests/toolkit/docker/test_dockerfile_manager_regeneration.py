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

from pathlib import Path

from agentkit.toolkit.docker.dockerfile.manager import DockerfileManager
from agentkit.toolkit.docker.dockerfile.metadata import MetadataExtractor


def test_python_template_default_base_image_domain() -> None:
    template_path = (
        Path(__file__).resolve().parents[3]
        / "agentkit"
        / "toolkit"
        / "resources"
        / "templates"
        / "python"
        / "Dockerfile.j2"
    )
    content = template_path.read_text(encoding="utf-8")
    assert (
        "FROM agentkit-prod-public-cn-beijing.cr.volces.com/base/py-simple:python{{ language_version }}-bookworm-slim-latest"
        in content
    )


def test_managed_dockerfile_regenerates_when_template_hash_changes(
    tmp_path: Path,
) -> None:
    manager = DockerfileManager(tmp_path)

    config_hash_dict_v1 = {
        "language": "Python",
        "language_version": "3.12",
        "entry_point": "agent.py",
        "dependencies_file": "requirements.txt",
        "dockerfile_template": "Dockerfile.j2",
        "dockerfile_template_hash": "hash_v1",
        "docker_build": {"base_image": None, "build_script": None},
    }

    def content_generator() -> str:
        return "FROM python:3.12-slim\n"

    generated_1, dockerfile_path_1 = manager.prepare_dockerfile(
        config_hash_dict=config_hash_dict_v1,
        content_generator=content_generator,
        force_regenerate=False,
    )
    assert generated_1 is True
    assert dockerfile_path_1 == str(tmp_path / "Dockerfile")

    dockerfile_content_1 = (tmp_path / "Dockerfile").read_text(encoding="utf-8")
    metadata_1 = MetadataExtractor.extract(dockerfile_content_1)
    assert metadata_1.is_managed is True
    assert metadata_1.config_hash == MetadataExtractor.calculate_config_hash(
        config_hash_dict_v1
    )

    config_hash_dict_v2 = dict(config_hash_dict_v1)
    config_hash_dict_v2["dockerfile_template_hash"] = "hash_v2"

    generated_2, dockerfile_path_2 = manager.prepare_dockerfile(
        config_hash_dict=config_hash_dict_v2,
        content_generator=content_generator,
        force_regenerate=False,
    )
    assert generated_2 is True
    assert dockerfile_path_2 == str(tmp_path / "Dockerfile")

    backup_dir = tmp_path / ".agentkit" / "dockerfile_backups"
    backups = list(backup_dir.glob("Dockerfile.backup.*"))
    assert len(backups) == 1

    dockerfile_content_2 = (tmp_path / "Dockerfile").read_text(encoding="utf-8")
    metadata_2 = MetadataExtractor.extract(dockerfile_content_2)
    assert metadata_2.is_managed is True
    assert metadata_2.config_hash == MetadataExtractor.calculate_config_hash(
        config_hash_dict_v2
    )


def test_managed_dockerfile_not_regenerated_when_config_hash_unchanged(
    tmp_path: Path,
) -> None:
    manager = DockerfileManager(tmp_path)

    config_hash_dict_v1 = {
        "language": "Python",
        "language_version": "3.12",
        "entry_point": "agent.py",
        "dependencies_file": "requirements.txt",
        "dockerfile_template": "Dockerfile.j2",
        "dockerfile_template_hash": "hash_v1",
        "docker_build": {"base_image": None, "build_script": None},
    }

    def content_generator() -> str:
        return "FROM python:3.12-slim\n"

    generated_1, _ = manager.prepare_dockerfile(
        config_hash_dict=config_hash_dict_v1,
        content_generator=content_generator,
        force_regenerate=False,
    )
    assert generated_1 is True

    generated_2, _ = manager.prepare_dockerfile(
        config_hash_dict=config_hash_dict_v1,
        content_generator=content_generator,
        force_regenerate=False,
    )
    assert generated_2 is False

    backup_dir = tmp_path / ".agentkit" / "dockerfile_backups"
    assert list(backup_dir.glob("Dockerfile.backup.*")) == []


def test_managed_dockerfile_not_overwritten_when_user_modified_and_config_changes(
    tmp_path: Path,
) -> None:
    manager = DockerfileManager(tmp_path)

    config_hash_dict_v1 = {
        "language": "Python",
        "language_version": "3.12",
        "entry_point": "agent.py",
        "dependencies_file": "requirements.txt",
        "dockerfile_template": "Dockerfile.j2",
        "dockerfile_template_hash": "hash_v1",
        "docker_build": {"base_image": None, "build_script": None},
    }

    def content_generator() -> str:
        return "FROM python:3.12-slim\n"

    manager.prepare_dockerfile(
        config_hash_dict=config_hash_dict_v1,
        content_generator=content_generator,
        force_regenerate=False,
    )

    dockerfile_path = tmp_path / "Dockerfile"
    dockerfile_path.write_text(
        dockerfile_path.read_text(encoding="utf-8") + "\nRUN echo user-modified\n",
        encoding="utf-8",
    )

    config_hash_dict_v2 = dict(config_hash_dict_v1)
    config_hash_dict_v2["dockerfile_template_hash"] = "hash_v2"

    generated, _ = manager.prepare_dockerfile(
        config_hash_dict=config_hash_dict_v2,
        content_generator=content_generator,
        force_regenerate=False,
    )
    assert generated is False
    assert "RUN echo user-modified" in dockerfile_path.read_text(encoding="utf-8")
