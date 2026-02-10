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


def default_region_for_current_provider() -> str:
    from agentkit.platform.constants import DEFAULT_REGION, DEFAULT_REGION_BY_PROVIDER
    from agentkit.platform.context import get_default_cloud_provider
    from agentkit.platform.provider import (
        normalize_cloud_provider,
        read_cloud_provider_from_env,
    )

    provider = get_default_cloud_provider()
    if provider is None:
        provider = normalize_cloud_provider(read_cloud_provider_from_env())

    if provider is None:
        try:
            from agentkit.toolkit.config.global_config import (
                get_global_config,
                global_config_exists,
            )

            if global_config_exists():
                provider = normalize_cloud_provider(
                    getattr(get_global_config().defaults, "cloud_provider", None)
                )
        except Exception:
            provider = None

    return DEFAULT_REGION_BY_PROVIDER.get(provider, DEFAULT_REGION)
