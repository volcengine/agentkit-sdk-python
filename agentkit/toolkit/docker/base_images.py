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

from dataclasses import dataclass
from typing import Dict

from agentkit.platform.provider import CloudProvider


@dataclass(frozen=True)
class DockerfileBaseImageDefaults:
    context: Dict[str, str]


_PYTHON_BASE_IMAGE_VOLCENGINE_TEMPLATE = (
    "agentkit-prod-public-cn-beijing.cr.volces.com/base/py-simple:"
    "python{language_version}-bookworm-slim-latest"
)
_PYTHON_BASE_IMAGE_BYTEPLUS_TEMPLATE = (
    "agentkit-prod-public-ap-southeast-1.cr.bytepluses.com/base/py-simple:"
    "python{language_version}-bookworm-slim-latest"
)

_GOLANG_BUILDER_BASE_IMAGE_DEFAULT = (
    "agentkit-cn-beijing.cr.volces.com/base/compile_basego:1.24"
)
_GOLANG_RUNTIME_BASE_IMAGE_DEFAULT = (
    "agentkit-cn-beijing.cr.volces.com/base/runtime_basego:latest"
)


def resolve_dockerfile_base_image_defaults(
    *, language: str, language_version: str, provider: CloudProvider
) -> DockerfileBaseImageDefaults:
    lang = (language or "Python").strip().lower()
    if lang in ("python", "py"):
        template = (
            _PYTHON_BASE_IMAGE_BYTEPLUS_TEMPLATE
            if provider == CloudProvider.BYTEPLUS
            else _PYTHON_BASE_IMAGE_VOLCENGINE_TEMPLATE
        )
        return DockerfileBaseImageDefaults(
            context={
                "base_image_default": template.format(language_version=language_version)
            }
        )

    if lang in ("golang", "go"):
        return DockerfileBaseImageDefaults(
            context={
                "base_image_default_builder": _GOLANG_BUILDER_BASE_IMAGE_DEFAULT,
                "base_image_default_runtime": _GOLANG_RUNTIME_BASE_IMAGE_DEFAULT,
            }
        )

    return DockerfileBaseImageDefaults(context={})
