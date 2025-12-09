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
AgentKit Toolkit SDK - Python API for building and deploying agents.

This SDK provides a programmatic interface to all toolkit functionality,
allowing you to build, deploy, invoke, and manage agents from Python code.

Two API styles are available:

1. Client API (Recommended for multiple operations):
    >>> from agentkit.toolkit.sdk import AgentKitClient
    >>>
    >>> # Create client with configuration
    >>> client = AgentKitClient("agentkit.yaml")
    >>>
    >>> # Perform operations without repeating config
    >>> client.build()
    >>> client.deploy()
    >>> client.invoke({"prompt": "Hello, agent!"})

2. Functional API (Good for simple scripts):
    >>> from agentkit.toolkit import sdk
    >>>
    >>> # Each operation specifies config
    >>> sdk.build(config_file="agentkit.yaml")
    >>> sdk.deploy(config_file="agentkit.yaml")
    >>> sdk.invoke(
    ...     payload={"prompt": "Hello, agent!"},
    ...     config_file="agentkit.yaml"
    ... )
"""

# Import main API functions
from .builder import build
from .deployer import deploy
from .invoker import invoke
from .lifecycle import launch, destroy
from .status import status
from .initializer import init_project, get_available_templates

# Import client, config and helpers
from .client import AgentKitClient
from .config import AgentConfig
from .bindings import bind_memory_env_to_config_for_veadk

# Import result types from unified models
from ..models import (
    BuildResult,
    DeployResult,
    InvokeResult,
    StatusResult,
    LifecycleResult,
    InitResult,
)

__all__ = [
    # Main operations
    "build",
    "deploy",
    "invoke",
    "launch",
    "destroy",
    "status",
    "init_project",
    "get_available_templates",
    # Client and Config
    "AgentKitClient",
    "AgentConfig",
    # Helpers
    "bind_memory_env_to_config_for_veadk",
    # Result types
    "BuildResult",
    "DeployResult",
    "InvokeResult",
    "StatusResult",
    "LifecycleResult",
    "InitResult",
]
