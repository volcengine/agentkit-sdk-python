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

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class RegionConfigResolver:
    """
    Resolves target regions for services based on user configuration.

    It serves as a single source of truth for determining which region a service
    should target, handling the precedence between the user's logical region intent
    and any explicit service-level overrides.

    Note: This class does NOT perform platform-level mapping (e.g. cn-shanghai -> cn-beijing).
    That responsibility lies with the Platform layer (VolcConfiguration).
    This class simply resolves the "intent" to be passed to the Platform layer.
    """

    logical_region: str
    overrides: Dict[str, str]

    def resolve(self, service_name: str) -> str:
        """
        Resolve the target region for a specific service.

        Args:
            service_name: The name of the service (e.g., "cr", "tos", "cp").

        Returns:
            The override region if specified, otherwise the logical region.
        """
        return self.overrides.get(service_name, self.logical_region)

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> RegionConfigResolver:
        """
        Factory method to create a resolver from a configuration dictionary.

        Args:
            config_dict: A dictionary containing 'region' and optional 'region_overrides'.

        Returns:
            RegionConfigResolver instance.

        Raises:
            ValueError: If logical_region (config_dict['region']) is empty.
        """
        logical_region = config_dict.get("region")
        if not logical_region:
            raise ValueError(
                "Logical region cannot be empty. Please specify a valid region."
            )

        logical_region = logical_region.strip().lower()

        raw_overrides = config_dict.get("region_overrides", {})
        overrides = {}
        if raw_overrides:
            overrides = {k: v for k, v in raw_overrides.items() if v}

        return cls(logical_region=logical_region, overrides=overrides)

    @classmethod
    def from_strategy_config(cls, strategy_config: Any) -> RegionConfigResolver:
        """
        Factory method to create a resolver from a strategy configuration object.

        Args:
            strategy_config: A configuration object containing 'region' and optional 'region_overrides'.

        Returns:
            RegionConfigResolver instance.

        Raises:
            ValueError: If logical_region (strategy_config.region) is empty.
        """
        logical_region = getattr(strategy_config, "region", None)
        if not logical_region:
            raise ValueError(
                "Logical region cannot be empty. Please specify a valid region."
            )

        logical_region = logical_region.strip().lower()

        raw_overrides = getattr(strategy_config, "region_overrides", None)
        overrides = {}
        if raw_overrides:
            overrides = {k: v for k, v in raw_overrides.items() if v}

        return cls(logical_region=logical_region, overrides=overrides)
