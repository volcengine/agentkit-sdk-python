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
from typing import Optional

from agentkit.platform.provider import (
    CloudProvider,
    normalize_cloud_provider,
    read_cloud_provider_from_env,
)


@dataclass(frozen=True)
class ResolvedCloudProvider:
    provider: CloudProvider
    source: str


def resolve_cloud_provider_for_project(
    *,
    project_provider: Optional[str],
    global_provider: Optional[str],
    env_provider: Optional[str],
    default: CloudProvider = CloudProvider.VOLCENGINE,
) -> ResolvedCloudProvider:
    if normalize_cloud_provider(env_provider) is not None:
        return ResolvedCloudProvider(
            provider=normalize_cloud_provider(env_provider) or default, source="env"
        )

    if normalize_cloud_provider(project_provider) is not None:
        return ResolvedCloudProvider(
            provider=normalize_cloud_provider(project_provider) or default,
            source="project",
        )

    if normalize_cloud_provider(global_provider) is not None:
        return ResolvedCloudProvider(
            provider=normalize_cloud_provider(global_provider) or default,
            source="global",
        )

    return ResolvedCloudProvider(provider=default, source="default")


def resolve_cloud_provider_for_config_manager(cfg) -> ResolvedCloudProvider:
    try:
        project_provider = cfg.get_raw_value("common.cloud_provider", default=None)
    except Exception:
        project_provider = None

    env_provider = read_cloud_provider_from_env()

    try:
        from agentkit.toolkit.config.global_config import (
            get_global_config,
            global_config_exists,
        )

        if global_config_exists():
            global_provider = getattr(
                get_global_config().defaults, "cloud_provider", None
            )
        else:
            global_provider = None
    except Exception:
        global_provider = None

    return resolve_cloud_provider_for_project(
        project_provider=project_provider,
        global_provider=global_provider,
        env_provider=env_provider,
    )
