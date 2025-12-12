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


from .config import (
    AgentkitConfigManager,
    CommonConfig,
    get_config,
)

from .strategy_configs import (
    LocalStrategyConfig,
    HybridStrategyConfig,
    CloudStrategyConfig,
)

from .docker_build_config import (
    DockerBuildConfig,
)

from .global_config import (
    GlobalConfig,
    GlobalConfigManager,
    get_global_config,
    get_global_config_manager,
    save_global_config,
    global_config_exists,
    VolcengineCredentials,
    CRGlobalConfig,
    TOSGlobalConfig,
)

from .utils import is_valid_config, is_invalid_config, merge_runtime_envs
from .constants import (
    AUTO_CREATE_VE,
    AUTH_TYPE_KEY_AUTH,
    AUTH_TYPE_CUSTOM_JWT,
    GLOBAL_CONFIG_FILE_PERMISSIONS,
    GLOBAL_CONFIG_FILE,
    GLOBAL_CONFIG_DIR,
    DEFAULT_IMAGE_TAG,
    DEFAULT_TOS_BUCKET_TEMPLATE_NAME,
    DEFAULT_CR_INSTANCE_TEMPLATE_NAME,
    DEFAULT_CR_NAMESPACE,
    DEFAULT_WORKSPACE_NAME,
)

__all__ = [
    "AgentkitConfigManager",
    "CommonConfig",
    "ConfigUpdateResult",
    "get_config",
    "create_config_update_result",
    "GlobalConfig",
    "GlobalConfigManager",
    "get_global_config",
    "get_global_config_manager",
    "save_global_config",
    "global_config_exists",
    "VolcengineCredentials",
    "CRGlobalConfig",
    "TOSGlobalConfig",
    "AUTO_CREATE_VE",
    "AUTH_TYPE_KEY_AUTH",
    "AUTH_TYPE_CUSTOM_JWT",
    "DEFAULT_WORKSPACE_NAME",
    "DEFAULT_CR_NAMESPACE",
    "DEFAULT_CR_INSTANCE_TEMPLATE_NAME",
    "DEFAULT_TOS_BUCKET_TEMPLATE_NAME",
    "DEFAULT_IMAGE_TAG",
    "GLOBAL_CONFIG_DIR",
    "GLOBAL_CONFIG_FILE",
    "GLOBAL_CONFIG_FILE_PERMISSIONS",
    "is_valid_config",
    "is_invalid_config",
    "merge_runtime_envs",
    "LocalStrategyConfig",
    "HybridStrategyConfig",
    "CloudStrategyConfig",
    "DockerBuildConfig",
]
