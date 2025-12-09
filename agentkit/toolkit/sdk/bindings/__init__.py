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

"""Framework-specific bindings for AgentKit services.

This module provides framework-specific bindings for various AgentKit services,
such as memory, knowledge, and tools. Each binding module is responsible
for translating AgentKit service configurations into framework-specific
environment variables or configuration formats.

"""

from .memory import bind_memory_env_to_config_for_veadk

__all__ = [
    "bind_memory_env_to_config_for_veadk",
]
