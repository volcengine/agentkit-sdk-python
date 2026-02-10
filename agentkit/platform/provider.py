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

from enum import Enum
from typing import Optional


class CloudProvider(str, Enum):
    """Cloud provider identifier.

    This is used to isolate region defaults, endpoint registry, and credential
    resolution between Volcano Engine (CN) and BytePlus (Overseas).
    """

    VOLCENGINE = "volcengine"
    BYTEPLUS = "byteplus"


ENV_CLOUD_PROVIDER = "AGENTKIT_CLOUD_PROVIDER"
ENV_CLOUD_PROVIDER_ALIAS = "CLOUD_PROVIDER"


def read_cloud_provider_from_env() -> Optional[str]:
    """Read provider setting from environment variables.

    Precedence:
    1) AGENTKIT_CLOUD_PROVIDER (preferred)
    2) CLOUD_PROVIDER (compat alias)
    """

    import os

    return os.getenv(ENV_CLOUD_PROVIDER) or os.getenv(ENV_CLOUD_PROVIDER_ALIAS)


def normalize_cloud_provider(value: Optional[str]) -> Optional[CloudProvider]:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    v = value.strip().lower()
    if not v:
        return None
    try:
        return CloudProvider(v)
    except Exception:
        return None


def resolve_cloud_provider(
    *,
    explicit_provider: Optional[str] = None,
    env_provider: Optional[str] = None,
    config_provider: Optional[str] = None,
    default: CloudProvider = CloudProvider.VOLCENGINE,
) -> CloudProvider:
    """Resolve provider with precedence: explicit > env > config > default."""
    return (
        normalize_cloud_provider(explicit_provider)
        or normalize_cloud_provider(env_provider)
        or normalize_cloud_provider(config_provider)
        or default
    )
