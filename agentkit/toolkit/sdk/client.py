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

"""AgentKit SDK Client - Configuration management and simplified API."""

from typing import Optional, Dict, Any, Union

from .builder import build as _build
from .deployer import deploy as _deploy
from .invoker import invoke as _invoke
from .status import status as _status
from .lifecycle import launch as _launch, destroy as _destroy
from .initializer import (
    init_project as _init_project,
    get_available_templates as _get_available_templates,
)

from ..models import (
    BuildResult,
    DeployResult,
    InvokeResult,
    StatusResult,
    LifecycleResult,
    InitResult,
    PreflightMode,
)
from ..reporter import Reporter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import AgentConfig


class AgentKitClient:
    """
    AgentKit SDK Client with configuration management.

    This client wraps the functional SDK APIs and provides configuration
    reuse across multiple operations. It's recommended for applications
    that need to perform multiple operations on the same agent.

    Example:
        >>> from agentkit.toolkit.sdk import AgentKitClient
        >>>
        >>> # Create client with configuration
        >>> client = AgentKitClient("agentkit.yaml")
        >>>
        >>> # Perform operations without repeating config
        >>> build_result = client.build()
        >>> deploy_result = client.deploy()
        >>> invoke_result = client.invoke({"prompt": "Hello"})
        >>>
        >>> # Or use as context manager
        >>> with AgentKitClient("agentkit.yaml") as client:
        ...     client.build()
        ...     client.deploy()

    Attributes:
        config_file: Path to configuration file.
        config_dict: Configuration dictionary (overrides config_file).
    """

    def __init__(
        self,
        config: Optional[Union[str, "AgentConfig"]] = None,
        config_file: Optional[str] = None,
        config_dict: Optional[Dict[str, Any]] = None,
        reporter: Optional[Reporter] = None,
    ):
        """
        Initialize AgentKit client.

        Args:
            config: Configuration source (recommended parameter):
                - AgentConfig object: Use SDK config manager
                - str: Path to config file (e.g., "agentkit.yaml")
                - None: Use default "agentkit.yaml" in current directory
            config_file: Path to configuration file (legacy parameter).
                Ignored if 'config' is provided.
            config_dict: Configuration as dictionary (highest priority).
                Overrides config/config_file if provided.
            reporter: Optional Reporter for progress/log output. If None,
                the underlying SDK APIs use SilentReporter (no console output).

        Example:
            >>> # Recommended: With AgentConfig object
            >>> from agentkit.toolkit.sdk import AgentConfig
            >>> config = AgentConfig.load("./my_agent")
            >>> client = AgentKitClient(config)
            >>>
            >>> # With config file path (string)
            >>> client = AgentKitClient("my-config.yaml")
            >>>
            >>> # With config dict
            >>> client = AgentKitClient(config_dict={
            ...     "common": {"agent_name": "my-agent"}
            ... })
            >>>
            >>> # With both (dict takes priority)
            >>> client = AgentKitClient(
            ...     config="base-config.yaml",
            ...     config_dict={"common": {"agent_name": "override"}}
            ... )
        """
        # Import AgentConfig here to avoid circular import
        from .config import AgentConfig

        # Store reporter for all subsequent operations
        self.reporter: Optional[Reporter] = reporter

        # Handle the new 'config' parameter
        if isinstance(config, AgentConfig):
            # AgentConfig object provided
            self.config_file = str(config.file_path)
            self.config_dict = config_dict  # Still allow dict overrides
            self._agent_config = config
        elif isinstance(config, str):
            # String path provided
            self.config_file = config
            self.config_dict = config_dict
            self._agent_config = None
        elif config is None:
            # Use legacy parameters or defaults
            self.config_file = config_file
            self.config_dict = config_dict
            self._agent_config = None
        else:
            raise TypeError(
                f"config must be AgentConfig, str, or None, got {type(config).__name__}"
            )

    @property
    def config(self) -> "AgentConfig":
        """Get AgentConfig instance (lazy load).

        Returns:
            AgentConfig instance for this client.

        Example:
            >>> client = AgentKitClient("agentkit.yaml")
            >>> config = client.config  # Lazy load
            >>> print(config.launch_type)
        """
        if self._agent_config is None and self.config_file:
            from .config import AgentConfig

            self._agent_config = AgentConfig.load(self.config_file)
        return self._agent_config

    def _merge_config(
        self, overrides: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Merge client configuration with operation-specific overrides.

        Args:
            overrides: Operation-specific configuration overrides.

        Returns:
            Merged configuration dictionary.
        """
        if overrides is None:
            return self.config_dict

        if self.config_dict is None:
            return overrides

        # Deep merge: overrides take priority
        merged = self.config_dict.copy()
        for key, value in overrides.items():
            if (
                key in merged
                and isinstance(merged[key], dict)
                and isinstance(value, dict)
            ):
                # Merge nested dicts
                merged[key] = {**merged[key], **value}
            else:
                merged[key] = value

        return merged

    def build(
        self,
        platform: str = "auto",
        config_overrides: Optional[Dict[str, Any]] = None,
        preflight_mode: PreflightMode = PreflightMode.WARN,
    ) -> BuildResult:
        """
        Build agent image using client configuration.

        Args:
            platform: Docker build platform/architecture string
                (e.g., "linux/amd64", "linux/arm64", or "auto"). This controls
                the Docker build target platform and is independent from the
                launch_type (local/cloud/hybrid) configured in agentkit.yaml.
            config_overrides: Optional configuration overrides for this operation.
                These will be merged with the client's base configuration.
            preflight_mode: Preflight check behavior for required cloud services when
                using cloud or hybrid launch types. Options are the same as
                agentkit.toolkit.models.PreflightMode. SDK default is WARN.

        Returns:
            BuildResult: Build operation result.

        Example:
            >>> client = AgentKitClient("agentkit.yaml")
            >>>
            >>> # Simple build
            >>> result = client.build()
            >>>
            >>> # Build with platform override
            >>> result = client.build(platform="local")
            >>>
            >>> # Build with config overrides
            >>> result = client.build(
            ...     config_overrides={"local": {"image_tag": "dev"}}
            ... )
        """
        merged_config = self._merge_config(config_overrides)
        return _build(
            config_file=self.config_file,
            config_dict=merged_config,
            platform=platform,
            preflight_mode=preflight_mode,
            reporter=self.reporter,
        )

    def deploy(
        self,
        config_overrides: Optional[Dict[str, Any]] = None,
        preflight_mode: PreflightMode = PreflightMode.WARN,
    ) -> DeployResult:
        """
        Deploy agent using client configuration.

        Args:
            config_overrides: Optional configuration overrides for this operation.
                These will be merged with the client's base configuration.
            preflight_mode: Preflight check behavior for required cloud services when
                using cloud or hybrid launch types. Options are the same as
                agentkit.toolkit.models.PreflightMode. SDK default is WARN.

        Returns:
            DeployResult: Deploy operation result.

        Example:
            >>> client = AgentKitClient("agentkit.yaml")
            >>>
            >>> # Simple deploy
            >>> result = client.deploy()
            >>>
            >>> # Deploy with config overrides
            >>> result = client.deploy(
            ...     config_overrides={"cloud": {"runtime_name": "prod-v2"}}
            ... )
        """
        merged_config = self._merge_config(config_overrides)
        return _deploy(
            config_file=self.config_file,
            config_dict=merged_config,
            preflight_mode=preflight_mode,
            reporter=self.reporter,
        )

    def invoke(
        self,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]],
        config_overrides: Optional[Dict[str, Any]] = None,
    ) -> InvokeResult:
        """
        Invoke deployed agent using client configuration.

        Args:
            payload: Request payload dictionary to send to agent.
                Typically contains fields like "prompt", "messages", etc.
            headers: Optional HTTP headers dictionary.
                Common headers: {"user_id": "...", "session_id": "..."}
            config_overrides: Optional configuration overrides for this operation.

        Returns:
            InvokeResult: Invocation result.

        Example:
            >>> client = AgentKitClient("agentkit.yaml")
            >>>
            >>> # Simple invocation
            >>> result = client.invoke({"prompt": "Hello, agent!"})
            >>>
            >>> # With headers
            >>> result = client.invoke(
            ...     payload={"prompt": "What's the weather?"},
            ...     headers={"user_id": "user123"},
            ... )
            >>>
            >>> # Handle streaming response
            >>> result = client.invoke({"prompt": "Tell me a story"})
            >>> if result.is_streaming:
            ...     for event in result.stream():
            ...         print(event)
            ... else:
            ...     print(result.response)
        """
        merged_config = self._merge_config(config_overrides)
        return _invoke(
            payload=payload,
            config_file=self.config_file,
            config_dict=merged_config,
            headers=headers,
            reporter=self.reporter,
        )

    def status(self, config_overrides: Optional[Dict[str, Any]] = None) -> StatusResult:
        """
        Query agent status using client configuration.

        Args:
            config_overrides: Optional configuration overrides for this operation.

        Returns:
            StatusResult: Status query result.

        Example:
            >>> client = AgentKitClient("agentkit.yaml")
            >>>
            >>> # Query status
            >>> result = client.status()
            >>>
            >>> # Check status
            >>> if result.is_running():
            ...     print(f"Agent running at: {result.endpoint_url}")
            ... else:
            ...     print(f"Agent status: {result.status}")
        """
        merged_config = self._merge_config(config_overrides)
        return _status(
            config_file=self.config_file,
            config_dict=merged_config,
            reporter=self.reporter,
        )

    def launch(
        self,
        platform: str = "auto",
        config_overrides: Optional[Dict[str, Any]] = None,
        preflight_mode: PreflightMode = PreflightMode.WARN,
    ) -> LifecycleResult:
        """
        Launch agent (build + deploy) using client configuration.

        Args:
            platform: Docker build platform/architecture string
                (e.g., "linux/amd64", "linux/arm64", or "auto"). This controls
                the Docker build target platform and is independent from the
                launch_type (local/cloud/hybrid) configured in agentkit.yaml.
            config_overrides: Optional configuration overrides for this operation.
            preflight_mode: Preflight check behavior for required cloud services when
                using cloud or hybrid launch types. Options are the same as
                agentkit.toolkit.models.PreflightMode. SDK default is WARN.

        Returns:
            LifecycleResult: Launch operation result.

        Example:
            >>> client = AgentKitClient("agentkit.yaml")
            >>>
            >>> # Launch agent
            >>> result = client.launch()
            >>> if result.success:
            ...     print(f"Agent launched successfully")
        """
        merged_config = self._merge_config(config_overrides)
        return _launch(
            config_file=self.config_file,
            config_dict=merged_config,
            platform=platform,
            preflight_mode=preflight_mode,
            reporter=self.reporter,
        )

    def destroy(
        self, config_overrides: Optional[Dict[str, Any]] = None
    ) -> LifecycleResult:
        """
        Destroy agent runtime using client configuration.

        Args:
            config_overrides: Optional configuration overrides for this operation.

        Returns:
            LifecycleResult: Destroy operation result.

        Example:
            >>> client = AgentKitClient("agentkit.yaml")
            >>>
            >>> # Destroy agent
            >>> result = client.destroy()
        """
        merged_config = self._merge_config(config_overrides)
        return _destroy(
            config_file=self.config_file,
            config_dict=merged_config,
            reporter=self.reporter,
        )

    def __enter__(self):
        """Context manager entry - returns self."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Context manager exit - cleanup if needed.

        Currently no cleanup is needed, but this allows for
        future resource management (e.g., connection pooling).
        """
        pass

    @staticmethod
    def init_project(
        project_name: str,
        template: str = "basic",
        project_root: str = ".",
        agent_name: Optional[str] = None,
        description: Optional[str] = None,
        system_prompt: Optional[str] = None,
        model_name: Optional[str] = None,
        tools: Optional[str] = None,
    ) -> InitResult:
        """
        Initialize a new agent project from template (static method).

        This is a static method because project initialization doesn't require
        an existing configuration (it creates the configuration).

        Args:
            project_name: Name of the project.
            template: Project template (basic, basic_stream, eino_a2a).
            project_root: Project root directory where agent files and
                agentkit.yaml will be created.
            agent_name: Custom agent name (optional).
            description: Agent description (optional).
            system_prompt: System prompt (optional).
            model_name: Model name (optional).
            tools: Comma-separated tools list (optional).

        Returns:
            InitResult: Initialization result.

        Example:
            >>> from agentkit.toolkit.sdk import AgentKitClient
            >>>
            >>> # Initialize a new project
            >>> result = AgentKitClient.init_project(
            ...     project_name="my-agent",
            ...     template="basic",
            ...     project_root="./projects"
            ... )
            >>>
            >>> if result.success:
            ...     print(f"Created: {', '.join(result.created_files)}")
            ...
            ...     # Now create client for the new project
            ...     client = AgentKitClient(
            ...         f"{result.project_path}/agentkit.yaml"
            ...     )
            ...     client.build()
        """
        return _init_project(
            project_name=project_name,
            template=template,
            project_root=project_root,
            agent_name=agent_name,
            description=description,
            system_prompt=system_prompt,
            model_name=model_name,
            tools=tools,
        )

    @staticmethod
    def get_available_templates() -> Dict[str, Dict[str, Any]]:
        """
        Get available project templates (static method).

        Returns:
            Dictionary of template configurations.

        Example:
            >>> from agentkit.toolkit.sdk import AgentKitClient
            >>>
            >>> templates = AgentKitClient.get_available_templates()
            >>> for key, info in templates.items():
            ...     print(f"{key}: {info['name']}")
        """
        return _get_available_templates()

    def __repr__(self) -> str:
        """String representation of client."""
        config_source = "dict" if self.config_dict else f"file({self.config_file})"
        return f"AgentKitClient(config={config_source})"
