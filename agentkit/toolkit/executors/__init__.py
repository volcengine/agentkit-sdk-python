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
Executor layer - Unified configuration management and error handling.

Responsibilities:
- Configuration loading and validation
- Strategy selection and instantiation
- Reporter injection for progress reporting
- Unified error handling and logging

Design principle: Executors are thin orchestration layers. They delegate actual
work to Strategies and return results directly without transformation.
"""

from .base_executor import BaseExecutor, ServiceNotEnabledException
from .build_executor import BuildExecutor, BuildOptions
from .deploy_executor import DeployExecutor
from .invoke_executor import InvokeExecutor
from .status_executor import StatusExecutor
from .lifecycle_executor import LifecycleExecutor
from .init_executor import InitExecutor

# Re-export PreflightMode from models for convenience
from agentkit.toolkit.models import PreflightMode

__all__ = [
    "BaseExecutor",
    "BuildExecutor",
    "BuildOptions",
    "DeployExecutor",
    "InvokeExecutor",
    "StatusExecutor",
    "LifecycleExecutor",
    "InitExecutor",
    "PreflightMode",
    "ServiceNotEnabledException",
]
