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

"""
VeAgentkit constants definition module.

This module defines common constants used throughout the VeAgentkit project,
ensuring consistency across all modules.
"""

from pathlib import Path

# Auto-creation resource identifier
AUTO_CREATE_VE = "Auto"
DEFAULT_WORKSPACE_NAME = "agentkit-cli-workspace"
DEFAULT_CR_NAMESPACE = "agentkit"
DEFAULT_CR_INSTANCE_TEMPLATE_NAME = "agentkit-platform-{{account_id}}"
DEFAULT_TOS_BUCKET_TEMPLATE_NAME = "agentkit-platform-{{account_id}}"

# Default image tag placeholder for timestamped builds
DEFAULT_IMAGE_TAG = "{{timestamp}}"
DEFAULT_IMAGE_TAG_TEMPLATE = "{{timestamp}}"

# Global configuration constants
GLOBAL_CONFIG_DIR = Path.home() / ".agentkit"
GLOBAL_CONFIG_FILE = GLOBAL_CONFIG_DIR / "config.yaml"
GLOBAL_CONFIG_FILE_PERMISSIONS = 0o600  # Owner read/write only

AUTH_TYPE_KEY_AUTH = "key_auth"
AUTH_TYPE_CUSTOM_JWT = "custom_jwt"
