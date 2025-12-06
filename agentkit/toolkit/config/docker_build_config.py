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

from dataclasses import dataclass, field
from typing import Optional, Union, Dict
from .dataclass_utils import AutoSerializableMixin


@dataclass
class DockerBuildConfig(AutoSerializableMixin):
    """Docker build configuration.

    Customizes the Docker image build process with support for:
    - Custom base images (base_image)
    - Custom build scripts (build_script)
    - Platform-specific builds (platform)
    - Dockerfile regeneration (regenerate_dockerfile)

    Examples:
        Python project with custom image:
        >>> docker_build:
        >>>   base_image: "python:3.11-slim"
        >>>   build_script: "scripts/setup.sh"

        Go project with multi-stage build:
        >>> docker_build:
        >>>   base_image:
        >>>     builder: "golang:1.24-alpine"
        >>>     runtime: "alpine:latest"
        >>>   build_script: "scripts/install_certs.sh"
    """

    base_image: Optional[Union[str, Dict[str, str]]] = field(
        default=None,
        metadata={
            "description": "Custom base image for Docker build",
            "detail": (
                "For Python projects, use a string like 'python:3.12-alpine'. "
                "For Go projects, use a dict with 'builder' and 'runtime' keys, "
                "e.g., {'builder': 'golang:1.24-alpine', 'runtime': 'alpine:latest'}"
            ),
        },
    )

    build_script: Optional[str] = field(
        default=None,
        metadata={
            "description": "Path to custom build script (relative to project root)",
            "detail": (
                "Script executed during Docker build for installing system dependencies, "
                "compiling C extensions, or setting up environment. "
                "Path relative to project root, e.g., 'scripts/setup.sh' or 'docker/install_deps.sh'"
            ),
        },
    )

    regenerate_dockerfile: bool = field(
        default=False,
        metadata={
            "description": "Force regenerate Dockerfile even if it exists",
            "detail": (
                "When True, regenerates Dockerfile regardless of existing file. "
                "Typically set via CLI parameter --regenerate-dockerfile."
            ),
        },
    )

    platform: Optional[str] = field(
        default=None,
        metadata={
            "description": "Target CPU architecture platform",
            "detail": (
                "Specifies the target CPU architecture for Docker image, "
                "e.g., 'linux/amd64' or 'linux/arm64'. "
                "Used for cross-platform builds. Typically set via CLI parameter --platform."
            ),
        },
    )
