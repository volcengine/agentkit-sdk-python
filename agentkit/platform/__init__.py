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

from __future__ import annotations

from typing import Optional

from agentkit.platform.configuration import VolcConfiguration, Endpoint, Credentials
from agentkit.platform.constants import DEFAULT_REGION_RULES

__all__ = [
    "VolcConfiguration",
    "Endpoint",
    "Credentials",
    "resolve_endpoint",
    "resolve_credentials",
    "DEFAULT_REGION_RULES",
]

# Backward compatibility wrappers


def resolve_endpoint(
    service: str,
    *,
    region: Optional[str] = None,
    platform_config: Optional[VolcConfiguration] = None,
) -> Endpoint:
    """
    Resolves the endpoint for a service.

    Args:
        service: Service identifier (e.g. 'agentkit', 'cr')
        region: Explicit region override
        platform_config: Optional configuration object. If provided, 'region' arg overrides config.
    """
    # If region is provided explicitly, it should override the config's region.
    # We can achieve this by creating a new ephemeral config or just letting VolcConfiguration handle it?
    # Since VolcConfiguration is immutable-ish, we can just instantiate one if needed.

    if platform_config:
        # If explicit region is passed, it overrides the config's region for this call
        if region and region != platform_config.region:
            # Create a temporary lightweight clone with new region, keeping creds
            # Or more simply, VolcConfiguration handles service-specific region overrides internally
            # but here 'region' is a global override for this call.
            # Let's create a new config merging both.
            cfg = VolcConfiguration(
                region=region,
                access_key=platform_config._ak,
                secret_key=platform_config._sk,
            )
        else:
            cfg = platform_config
    else:
        cfg = VolcConfiguration(region=region)

    return cfg.get_service_endpoint(service)


def resolve_credentials(
    service: str,
    *,
    explicit_access_key: Optional[str] = None,
    explicit_secret_key: Optional[str] = None,
    platform_config: Optional[VolcConfiguration] = None,
) -> Credentials:
    """
    Resolves credentials for a service.
    """
    # 1. Explicit args take absolute precedence
    if explicit_access_key and explicit_secret_key:
        return Credentials(
            access_key=explicit_access_key, secret_key=explicit_secret_key
        )

    cfg = platform_config or VolcConfiguration()
    return cfg.get_service_credentials(service)
