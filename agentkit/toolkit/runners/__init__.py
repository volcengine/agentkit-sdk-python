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
Runners - Runner implementations for deploying and managing agent services.

Implementations:
- LocalDockerRunner: Deploy and manage containers locally using Docker
- VeAgentkitRuntimeRunner: Deploy and manage runtimes on Volcano Engine cloud platform
"""


# Use lazy imports to avoid dependency issues at import time
def __getattr__(name):
    if name == "Runner":
        from .base import Runner

        return Runner
    elif name == "LocalDockerRunner":
        from .local_docker import LocalDockerRunner

        return LocalDockerRunner
    elif name == "LocalDockerRunnerConfig":
        from .local_docker import LocalDockerRunnerConfig

        return LocalDockerRunnerConfig
    elif name == "VeAgentkitRuntimeRunner":
        from .ve_agentkit import VeAgentkitRuntimeRunner

        return VeAgentkitRuntimeRunner
    elif name == "VeAgentkitRunnerConfig":
        from .ve_agentkit import VeAgentkitRunnerConfig

        return VeAgentkitRunnerConfig
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Runner",
    "LocalDockerRunner",
    "LocalDockerRunnerConfig",
    "VeAgentkitRuntimeRunner",
    "VeAgentkitRunnerConfig",
]
