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
Executor 层 - 统一的配置管理和错误处理

Executor 层职责：
- 配置加载和验证
- Strategy 选择和实例化  
- Reporter 注入
- 统一错误处理
- 日志记录

不做：
- 结果转换（Strategy 直接返回标准 Result）
- 进度报告（由 Strategy → Builder/Runner 处理）
"""

from .base_executor import BaseExecutor
from .build_executor import BuildExecutor, BuildOptions
from .deploy_executor import DeployExecutor
from .invoke_executor import InvokeExecutor
from .status_executor import StatusExecutor
from .lifecycle_executor import LifecycleExecutor
from .init_executor import InitExecutor

__all__ = [
    'BaseExecutor',
    'BuildExecutor',
    'BuildOptions',  # 导出 BuildOptions 供 CLI 使用
    'DeployExecutor',
    'InvokeExecutor',
    'StatusExecutor',
    'LifecycleExecutor',
    'InitExecutor'
]
