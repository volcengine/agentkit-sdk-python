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

"""Configuration utility functions."""

from typing import Dict, Any

from .constants import AUTO_CREATE_VE


def is_invalid_config(s: str) -> bool:
    return s is None or s == "" or s == AUTO_CREATE_VE


def is_valid_config(s: str) -> bool:
    return not is_invalid_config(s)


def merge_runtime_envs(
    common_config: Any, strategy_config: Dict[str, Any]
) -> Dict[str, str]:
    """Merge application-level and strategy-level environment variables.

    Strategy-level variables override application-level ones with the same name.

    Args:
        common_config: CommonConfig instance
        strategy_config: Strategy configuration dict

    Returns:
        Merged environment variables dict
    """
    merged_envs = {}

    app_level_envs = getattr(common_config, "runtime_envs", {})
    if isinstance(app_level_envs, dict):
        merged_envs.update(app_level_envs)

    strategy_level_envs = strategy_config.get("runtime_envs", {})
    if isinstance(strategy_level_envs, dict):
        merged_envs.update(strategy_level_envs)

    return merged_envs
