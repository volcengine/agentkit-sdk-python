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

"""Init API - SDK interface for initializing agent projects."""

from typing import Optional, Dict, Any

from ..executors import InitExecutor
from ..reporter import SilentReporter, Reporter
from ..models import InitResult


def init_project(
    project_name: str,
    template: str = "basic",
    project_root: str = ".",
    agent_name: Optional[str] = None,
    description: Optional[str] = None,
    system_prompt: Optional[str] = None,
    model_name: Optional[str] = None,
    tools: Optional[str] = None,
    reporter: Optional[Reporter] = None,
) -> InitResult:
    """
    Initialize a new agent project from template.

    This function creates a new AgentKit project with the specified template,
    including project files, configuration, and dependencies.

    Args:
        project_name: Name of the project. Must contain only letters, numbers,
            hyphens, and underscores.
        template: Project template to use. Options:
            - "basic": Simple agent application (default)
            - "basic_stream": Agent with streaming support
            - "eino_a2a": Eino framework A2A application
        project_root: Project root directory where agent files and agentkit.yaml
            will be created (default: current directory). This is the final
            directory; AgentKit will **not** automatically append project_name
            as a subdirectory.
        agent_name: Custom agent name (optional).
        description: Agent description (optional).
        system_prompt: System prompt for the agent (optional).
        model_name: Model name to use (optional, default: doubao-seed-1-6-250615).
        tools: Comma-separated list of tools to include (optional).
        reporter: Optional Reporter for progress/log output. If None, uses
            SilentReporter (no console output). Advanced users can pass
            LoggingReporter or a custom Reporter implementation.

    Returns:
        InitResult: Initialization result containing:
            - success: Whether initialization succeeded
            - project_name: Name of the created project
            - project_path: Path to the project directory
            - created_files: List of created files
            - error: Error message if failed

    Example:
        >>> from agentkit.toolkit import sdk
        >>>
        >>> # Simple initialization
        >>> result = sdk.init_project("my-agent")
        >>> if result.success:
        ...     print(f"Created project at: {result.project_path}")
        ...     print(f"Files: {', '.join(result.created_files)}")
        >>>
        >>> # With custom configuration
        >>> result = sdk.init_project(
        ...     project_name="smart-assistant",
        ...     template="basic_stream",
        ...     project_root="./projects",
        ...     agent_name="SmartAssistant",
        ...     description="An intelligent assistant",
        ...     model_name="doubao-1.5-pro",
        ...     tools="web_search,run_code"
        ... )
        >>>
        >>> # Check available templates
        >>> from agentkit.toolkit.sdk import get_available_templates
        >>> templates = get_available_templates()
        >>> for key, info in templates.items():
        ...     print(f"{key}: {info['name']}")

    Raises:
        No exceptions are raised. All errors are captured in InitResult.error.
    """
    if reporter is None:
        reporter = SilentReporter()

    executor = InitExecutor(reporter=reporter)
    return executor.init_project(
        project_name=project_name,
        template=template,
        directory=project_root,
        agent_name=agent_name,
        description=description,
        system_prompt=system_prompt,
        model_name=model_name,
        tools=tools,
    )


def get_available_templates(
    reporter: Optional[Reporter] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Get available project templates.

    Returns a dictionary of template configurations, where each template
    includes name, language, description, and type information.

    Returns:
        Dictionary mapping template keys to template information.

    Example:
        >>> from agentkit.toolkit import sdk
        >>>
        >>> templates = sdk.get_available_templates()
        >>>
        >>> # List all templates
        >>> for key, info in templates.items():
        ...     print(f"{key}:")
        ...     print(f"  Name: {info['name']}")
        ...     print(f"  Language: {info['language']}")
        ...     print(f"  Description: {info['description']}")
        >>>
        >>> # Check if template exists
        >>> if "basic" in templates:
        ...     print("Basic template available")
    """
    if reporter is None:
        reporter = SilentReporter()
    executor = InitExecutor(reporter=reporter)
    return executor.get_available_templates()
