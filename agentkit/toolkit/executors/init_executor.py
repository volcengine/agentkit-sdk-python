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

"""Init Executor - Handles agent project initialization and scaffolding.

This executor provides two initialization modes:
1. Template-based: Create new projects from predefined templates (basic, basic_stream, a2a)
2. Wrapper-based: Wrap existing agent files into deployable projects

Key responsibilities:
- Project structure scaffolding
- Configuration file generation (agentkit.yaml)
- Template rendering with Jinja2
- Global config fallback for cloud resources (CR, TOS)
"""

import random
import re
import shutil
import os
from pathlib import Path
from typing import Optional, Dict, Any, List

from agentkit.toolkit.models import InitResult
from agentkit.toolkit.models import AgentFileInfo
from .base_executor import BaseExecutor
from ..utils import AgentParser
from agentkit.toolkit.config import (
    get_config,
    DEFAULT_IMAGE_TAG,
    DEFAULT_CR_NAMESPACE,
    LocalStrategyConfig,
    CloudStrategyConfig,
    HybridStrategyConfig,
    global_config_exists,
    get_global_config,
)
from agentkit.toolkit.config.constants import (
    DEFAULT_CR_INSTANCE_TEMPLATE_NAME,
    DEFAULT_TOS_BUCKET_TEMPLATE_NAME,
)
from agentkit.toolkit.docker.utils import create_dockerignore_file


TEMPLATES = {
    "basic": {
        "file": "basic.py",
        "name": "Basic Agent App",
        "language": "Python",
        "language_version": "3.12",
        "description": "Minimal agent app for quick start",
        "type": "Basic App",
    },
    "basic_stream": {
        "file": "basic_stream.py",
        "name": "Basic Stream Agent App",
        "language": "Python",
        "language_version": "3.12",
        "description": "Agent app with streaming output support",
        "type": "Stream App",
        "extra_requirements": ["# google-adk"],
    },
    "a2a": {
        "file": "a2a.py",
        "name": "A2A Agent App",
        "language": "Python",
        "language_version": "3.12",
        "description": "Agent app with A2A protocol support",
        "type": "A2A App",
        "extra_requirements": ["# google-adk"],
    },
    "eino_a2a": {
        "filepath": "eino_a2a",
        "name": "Eino A2A Agent App",
        "language": "Golang",
        "language_version": "1.24",
        "description": "A2A Application Based on the Eino Framework",
        "type": "A2A App",
    },
}


class InitExecutor(BaseExecutor):
    """Executor for initializing agent projects."""

    def __init__(self, reporter=None):
        super().__init__(reporter)
        self.created_files: List[str] = []

    def get_available_templates(self) -> Dict[str, Dict[str, Any]]:
        """
        Get available project templates.

        Returns:
            Dictionary of template configurations.
        """
        return TEMPLATES.copy()

    def init_project(
        self,
        project_name: str,
        template: str = "basic",
        directory: str = ".",
        agent_name: Optional[str] = None,
        description: Optional[str] = None,
        system_prompt: Optional[str] = None,
        model_name: Optional[str] = None,
        model_api_base: Optional[str] = None,
        model_api_key: Optional[str] = None,
        tools: Optional[str] = None,
    ) -> InitResult:
        """
        Initialize a new agent project from template.

        Args:
            project_name: Name of the project.
            template: Template to use (basic, basic_stream, a2a).
            directory: Target directory for the project.
            agent_name: Agent name (optional).
            description: Agent description (optional).
            system_prompt: System prompt (optional).
            model_name: Model name (optional).
            tools: Comma-separated list of tools (optional).

        Returns:
            InitResult: Initialization operation result.
        """
        try:
            self.created_files = []

            if not re.match(r"^[a-zA-Z0-9_-]+$", project_name):
                return InitResult(
                    success=False,
                    error=f"Project name '{project_name}' contains invalid characters. Only letters, numbers, hyphens, and underscores are allowed.",
                    error_code="INVALID_CONFIG",
                )

            if template not in TEMPLATES:
                return InitResult(
                    success=False,
                    error=f"Unknown template '{template}'. Available: {', '.join(TEMPLATES.keys())}",
                    error_code="INVALID_CONFIG",
                )

            template_info = TEMPLATES[template]
            language = template_info["language"]
            language_version = template_info["language_version"]

            target_dir = Path(directory).resolve()
            if not target_dir.exists():
                target_dir.mkdir(parents=True, exist_ok=True)
                self.logger.info(f"Created directory: {target_dir}")
            elif not target_dir.is_dir():
                return InitResult(
                    success=False,
                    error=f"'{target_dir}' exists but is not a directory",
                    error_code="INVALID_CONFIG",
                )

            if language == "Python":
                file_name = f"{project_name}.py"
                dependencies_file_path = target_dir / "requirements.txt"
            elif language == "Golang":
                file_name = project_name
                dependencies_file_path = target_dir / "go.mod"
            else:
                return InitResult(
                    success=False,
                    error=f"Unsupported language: {language}",
                    error_code="INVALID_CONFIG",
                )

            agent_file_path = target_dir / file_name
            config_file_path = target_dir / "agentkit.yaml"

            source_key = template_info.get("file") or template_info.get("filepath")
            service_dir = Path(__file__).parent
            source_path = service_dir.parent / "resources" / "samples" / source_key

            if not source_path.exists():
                return InitResult(
                    success=False,
                    error=f"Template resource not found: {source_path}",
                    error_code="FILE_NOT_FOUND",
                )

            render_context = self._build_render_context(
                agent_name,
                description,
                system_prompt,
                model_name,
                tools,
            )

            if source_path.is_dir():
                self._copy_template_directory(
                    source_path, target_dir, language, render_context
                )
            else:
                self._copy_template_file(
                    source_path, agent_file_path, language, render_context
                )

            self._create_dependencies_file(
                dependencies_file_path,
                language,
                language_version,
                template_info,
                project_name,
                target_dir,
            )

            if language == "Golang":
                if (target_dir / "build.sh").exists():
                    entry_point_name = "build.sh"
                else:
                    entry_point_name = "."
            else:
                entry_point_name = file_name

            runtime_envs = None
            if model_api_base or model_api_key:
                runtime_envs = {}
                if model_api_base:
                    runtime_envs["MODEL_AGENT_API_BASE"] = model_api_base
                if model_api_key:
                    runtime_envs["MODEL_AGENT_API_KEY"] = model_api_key

            if not config_file_path.exists():
                self._create_config_file(
                    config_file_path=config_file_path,
                    project_name=project_name,
                    language=language,
                    language_version=language_version,
                    agent_type=template_info.get("type", "Basic App"),
                    description=f"AgentKit project {project_name} - {template_info.get('name', '')}",
                    entry_point_name=entry_point_name,
                    dependencies_file_name=dependencies_file_path.name,
                    runtime_envs=runtime_envs,
                )
                self.created_files.append("agentkit.yaml")
            else:
                self.logger.info("File agentkit.yaml already exists, skipping")

            self._create_dockerignore(target_dir)

            return InitResult(
                success=True,
                project_name=project_name,
                template=template,
                project_path=str(target_dir),
                created_files=self.created_files,
                metadata={
                    "language": language,
                    "language_version": language_version,
                    "entry_point": entry_point_name,
                    "template_name": template_info["name"],
                },
            )

        except Exception as e:
            error_info = self._handle_exception("Project initialization", e)
            return InitResult(
                success=False,
                project_name=project_name,
                template=template,
                error=error_info["error"],
                error_code=error_info["error_code"],
            )

    def _build_render_context(
        self,
        agent_name: Optional[str],
        description: Optional[str],
        system_prompt: Optional[str],
        model_name: Optional[str],
        tools: Optional[str],
    ) -> Dict[str, Any]:
        """Build template rendering context."""
        render_context = {}
        if agent_name is not None:
            render_context["agent_name"] = agent_name
        if description is not None:
            render_context["description"] = description
        if system_prompt is not None:
            render_context["system_prompt"] = system_prompt
        if model_name is not None:
            render_context["model_name"] = model_name
        if tools is not None:
            tools_list = [tool.strip() for tool in tools.split(",") if tool.strip()]
            render_context["tools"] = tools_list
        return render_context

    def _copy_template_directory(
        self,
        source_path: Path,
        target_dir: Path,
        language: str,
        render_context: Dict[str, Any],
    ):
        """Copy template directory contents."""
        for item in source_path.iterdir():
            dest = target_dir / item.name
            if dest.exists():
                self.logger.info(f"Skipped existing: {dest}")
                continue
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
            self.created_files.append(item.name)

        if language.lower() == "golang":
            self._render_go_agent_templates(target_dir, render_context)

    def _copy_template_file(
        self,
        source_path: Path,
        agent_file_path: Path,
        language: str,
        render_context: Dict[str, Any],
    ):
        """Copy and render single template file."""
        if agent_file_path.exists():
            self.logger.info(f"File {agent_file_path.name} already exists, skipping")
            return

        if language.lower() == "python":
            try:
                import jinja2
            except ImportError:
                raise ImportError(
                    "Jinja2 is required. Please install with 'pip install Jinja2'"
                )

            template_content = source_path.read_text(encoding="utf-8")
            template = jinja2.Template(template_content)
            rendered_content = template.render(**render_context)
            agent_file_path.write_text(rendered_content, encoding="utf-8")
            self.created_files.append(agent_file_path.name)

        elif language.lower() == "golang":
            shutil.copy2(source_path, agent_file_path)
            self.created_files.append(agent_file_path.name)
            if agent_file_path.name == "agent.go":
                self._render_go_agent_templates(agent_file_path.parent, render_context)

    def _render_go_agent_templates(
        self, target_dir: Path, render_context: Dict[str, Any]
    ):
        """Render Go template files (agent.go)."""
        try:
            import jinja2
        except ImportError:
            self.logger.warning("Jinja2 not available, skipping Go template rendering")
            return

        for root, _, files in os.walk(target_dir):
            for fname in files:
                if fname == "agent.go":
                    p = Path(root) / fname
                    try:
                        template_content = p.read_text(encoding="utf-8")
                        template = jinja2.Template(template_content)
                        rendered_content = template.render(**render_context)
                        p.write_text(rendered_content, encoding="utf-8")
                        self.logger.info(
                            f"Rendered Go template: {p.relative_to(target_dir)}"
                        )
                    except Exception as e:
                        self.logger.warning(f"Failed to render {p}: {e}")

    def _create_python_requirements(
        self,
        dependencies_file_path: Path,
        extra_requirements: Optional[List[str]] = None,
        include_usage_hints: bool = False,
    ):
        """Create Python requirements.txt file."""
        if dependencies_file_path.exists():
            self.logger.info(
                f"File {dependencies_file_path.name} already exists, skipping"
            )
            return

        with open(dependencies_file_path, "w", encoding="utf-8") as req_file:
            if include_usage_hints:
                req_file.write("# AgentKit dependencies\n")
            req_file.write("# veadk-python\n")
            req_file.write("# veadk-python[extensions]\n")

            if extra_requirements:
                if include_usage_hints:
                    req_file.write("\n# Additional dependencies\n")
                for requirement in extra_requirements:
                    req_file.write(f"{requirement}\n")

            if include_usage_hints:
                req_file.write("\n# Add your Agent's additional dependencies below\n")
                req_file.write("# Example:\n")
                req_file.write("# requests\n")
                req_file.write("# pandas\n")

        self.created_files.append(dependencies_file_path.name)
        self.logger.info(f"Created {dependencies_file_path.name}")

    def _create_dependencies_file(
        self,
        dependencies_file_path: Path,
        language: str,
        language_version: str,
        template_info: Dict[str, Any],
        project_name: str,
        target_dir: Path,
    ):
        """Create dependencies file (requirements.txt or go.mod)."""
        if dependencies_file_path.exists():
            self.logger.info(
                f"File {dependencies_file_path.name} already exists, skipping"
            )
            return

        if language.lower() == "python":
            extra_reqs = template_info.get("extra_requirements", [])
            self._create_python_requirements(
                dependencies_file_path,
                extra_requirements=extra_reqs,
                include_usage_hints=False,
            )

        elif language.lower() == "golang":
            go_ver = language_version or "1.24"
            with open(dependencies_file_path, "w", encoding="utf-8") as gomod:
                gomod.write(f"module {project_name}\n\ngo {go_ver}\n")
            self.created_files.append(dependencies_file_path.name)

    def _setup_config_launch_type(self, config_manager, common_config):
        """
        Setup launch type specific configurations (local, cloud, or hybrid).

        For cloud resources (CR, TOS), if a global config value exists, the project-level
        field is left empty so it inherits from global config at runtime. Otherwise,
        default templates are generated.
        """
        global_config = None
        if global_config_exists():
            try:
                global_config = get_global_config()
            except Exception as e:
                self.logger.debug(f"Failed to load global config: {e}")

        if common_config.launch_type == "local":
            local_config = LocalStrategyConfig.from_dict(
                config_manager.get_strategy_config(common_config.launch_type)
            )
            random_port = random.randint(1024, 49151)
            local_config.invoke_port = random_port
            local_config.ports = [f"{random_port}:8000"]
            config_manager.update_strategy_config(
                common_config.launch_type, local_config.to_dict()
            )

        elif common_config.launch_type == "cloud":
            # Create config directly to avoid auto-injection from global config
            cloud_config = CloudStrategyConfig()

            global_region = None
            if global_config and global_config.region:
                global_region = global_config.region
            cloud_config.region = global_region or "cn-beijing"

            # Empty string means "inherit from global config at runtime"
            if global_config and global_config.cr.instance_name:
                cloud_config.cr_instance_name = ""
                self.logger.debug("Using global CR instance config")
            else:
                cloud_config.cr_instance_name = DEFAULT_CR_INSTANCE_TEMPLATE_NAME

            if global_config and global_config.cr.namespace_name:
                cloud_config.cr_namespace_name = ""
                self.logger.debug("Using global CR namespace config")
            else:
                cloud_config.cr_namespace_name = DEFAULT_CR_NAMESPACE

            if global_config and global_config.tos.bucket:
                cloud_config.tos_bucket = ""
                self.logger.debug("Using global TOS bucket config")
            else:
                cloud_config.tos_bucket = DEFAULT_TOS_BUCKET_TEMPLATE_NAME

            if global_config and global_config.tos.prefix:
                cloud_config.tos_prefix = ""
            else:
                cloud_config.tos_prefix = "agentkit-builds"

            # Project-specific values (always set, not inherited)
            cloud_config.cr_repo_name = common_config.agent_name
            cloud_config.image_tag = DEFAULT_IMAGE_TAG

            config_manager.update_strategy_config(
                common_config.launch_type, cloud_config.to_dict()
            )

        elif common_config.launch_type == "hybrid":
            # Create config directly to avoid auto-injection from global config
            # Hybrid mode only needs CR config (no TOS needed)
            hybrid_config = HybridStrategyConfig()
            # Region: prefer global volcengine.region
            global_region = None
            if global_config and global_config.region:
                global_region = global_config.region
            hybrid_config.region = global_region or "cn-beijing"

            if global_config and global_config.cr.instance_name:
                hybrid_config.cr_instance_name = ""
                self.logger.debug("Using global CR instance config")
            else:
                hybrid_config.cr_instance_name = DEFAULT_CR_INSTANCE_TEMPLATE_NAME

            if global_config and global_config.cr.namespace_name:
                hybrid_config.cr_namespace_name = ""
                self.logger.debug("Using global CR namespace config")
            else:
                hybrid_config.cr_namespace_name = DEFAULT_CR_NAMESPACE

            # Project-specific values (always set, not inherited)
            hybrid_config.cr_repo_name = common_config.agent_name
            hybrid_config.image_tag = DEFAULT_IMAGE_TAG

            config_manager.update_strategy_config(
                common_config.launch_type, hybrid_config.to_dict()
            )

    def _create_config_file(
        self,
        config_file_path: Path,
        project_name: str,
        language: str,
        language_version: str,
        agent_type: str,
        description: str,
        entry_point_name: str,
        dependencies_file_name: str,
        runtime_envs: Optional[dict] = None,
    ):
        """
        Create agentkit.yaml configuration file.

        This is a unified method that works for both template-based and wrapper-based projects.
        """
        config_manager = get_config(config_path=config_file_path)
        common_config = config_manager.get_common_config()

        try:
            global_cfg = get_global_config()
            default_lt = getattr(
                getattr(global_cfg, "defaults", None), "launch_type", None
            )
        except Exception:
            default_lt = None

        common_config.launch_type = default_lt or "cloud"
        common_config.language = language
        common_config.language_version = language_version
        common_config.agent_name = project_name
        common_config.agent_type = agent_type
        common_config.description = description
        common_config.entry_point = entry_point_name
        common_config.dependencies_file = dependencies_file_name
        if runtime_envs:
            common_config.runtime_envs.update(runtime_envs)
        config_manager.update_common_config(common_config)

        self._setup_config_launch_type(config_manager, common_config)

    def _create_dockerignore(self, target_dir: Path):
        """Create .dockerignore file."""
        if create_dockerignore_file(str(target_dir)):
            self.created_files.append(".dockerignore")

    def init_from_agent_file(
        self,
        project_name: str,
        agent_file_path: str,
        agent_var_name: Optional[str] = None,
        wrapper_type: str = "basic",
        directory: str = ".",
    ) -> InitResult:
        """
        Initialize a project by wrapping an existing Agent definition file.

        Args:
            project_name: Name of the project.
            agent_file_path: Path to the existing Agent definition file.
            agent_var_name: Optional explicit Agent variable name.
            wrapper_type: Type of wrapper to generate (basic or stream).
            directory: Target directory for the project.

        Returns:
            InitResult: Initialization operation result.
        """
        try:
            self.created_files = []

            if not re.match(r"^[a-zA-Z0-9_-]+$", project_name):
                return InitResult(
                    success=False,
                    error=f"Project name '{project_name}' contains invalid characters. "
                    f"Only letters, numbers, hyphens, and underscores are allowed.",
                    error_code="INVALID_CONFIG",
                )

            if wrapper_type not in ["basic", "stream"]:
                return InitResult(
                    success=False,
                    error=f"Invalid wrapper type '{wrapper_type}'. Must be 'basic' or 'stream'.",
                    error_code="INVALID_CONFIG",
                )

            parser = AgentParser()
            try:
                agent_info = parser.parse_agent_file(agent_file_path, agent_var_name)
                self.logger.info(f"Parsed Agent file: {agent_info}")
            except (FileNotFoundError, ValueError) as e:
                error_code = (
                    "FILE_NOT_FOUND"
                    if isinstance(e, FileNotFoundError)
                    else "INVALID_CONFIG"
                )
                return InitResult(success=False, error=str(e), error_code=error_code)

            target_dir = Path(directory).resolve()
            if not target_dir.exists():
                target_dir.mkdir(parents=True, exist_ok=True)
                self.logger.info(f"Created directory: {target_dir}")
            elif not target_dir.is_dir():
                return InitResult(
                    success=False,
                    error=f"'{target_dir}' exists but is not a directory",
                    error_code="INVALID_CONFIG",
                )

            self._copy_agent_file(agent_info, target_dir)

            wrapper_file_path = target_dir / f"{project_name}.py"
            self._generate_wrapper_file(
                wrapper_file_path, agent_info, wrapper_type, project_name
            )

            dependencies_file_path = target_dir / "requirements.txt"
            extra_reqs = ["google-adk"] if wrapper_type == "stream" else []
            self._create_python_requirements(
                dependencies_file_path,
                extra_requirements=extra_reqs,
                include_usage_hints=True,
            )

            config_file_path = target_dir / "agentkit.yaml"
            if not config_file_path.exists():
                self._create_config_file(
                    config_file_path=config_file_path,
                    project_name=project_name,
                    language="Python",
                    language_version="3.12",
                    agent_type=f"Wrapped Agent ({wrapper_type.title()})",
                    description=f"AgentKit wrapped project: {project_name}",
                    entry_point_name=wrapper_file_path.name,
                    dependencies_file_name=dependencies_file_path.name,
                )
                self.created_files.append("agentkit.yaml")
            else:
                self.logger.info("File agentkit.yaml already exists, skipping")

            self._create_dockerignore(target_dir)

            return InitResult(
                success=True,
                project_name=project_name,
                template=f"wrapper_{wrapper_type}",
                project_path=str(target_dir),
                created_files=self.created_files,
                metadata={
                    "language": "Python",
                    "language_version": "3.12",
                    "entry_point": wrapper_file_path.name,
                    "template_name": f"Agent Wrapper ({wrapper_type.title()})",
                    "agent_file": agent_info.file_name,
                    "agent_var": agent_info.agent_var_name,
                    "wrapper_type": wrapper_type,
                },
            )

        except Exception as e:
            error_info = self._handle_exception("Agent file wrapping", e)
            return InitResult(
                success=False,
                project_name=project_name,
                template=f"wrapper_{wrapper_type}",
                error=error_info["error"],
                error_code=error_info["error_code"],
            )

    def _copy_agent_file(self, agent_info: AgentFileInfo, target_dir: Path):
        """Copy user's Agent file to target directory."""
        source_path = Path(agent_info.file_path)
        dest_path = target_dir / agent_info.file_name

        if dest_path.exists():
            self.logger.info(
                f"File {agent_info.file_name} already exists in target, skipping copy"
            )
            return

        shutil.copy2(source_path, dest_path)
        self.created_files.append(agent_info.file_name)
        self.logger.info(f"Copied Agent file: {agent_info.file_name}")

    def _generate_wrapper_file(
        self,
        wrapper_file_path: Path,
        agent_info: AgentFileInfo,
        wrapper_type: str,
        project_name: str,
    ):
        """Generate the wrapper file from template."""
        if wrapper_file_path.exists():
            self.logger.info(f"File {wrapper_file_path.name} already exists, skipping")
            return

        try:
            import jinja2
        except ImportError:
            raise ImportError(
                "Jinja2 is required. Please install with 'pip install Jinja2'"
            )

        service_dir = Path(__file__).parent
        template_path = (
            service_dir.parent
            / "resources"
            / "wrappers"
            / f"wrapper_{wrapper_type}.py.jinja2"
        )

        if not template_path.exists():
            raise FileNotFoundError(f"Wrapper template not found: {template_path}")

        template_content = template_path.read_text(encoding="utf-8")
        template = jinja2.Template(template_content)

        render_context = {
            "agent_file_name": agent_info.file_name,
            "agent_module_name": agent_info.module_name,
            "agent_var_name": agent_info.agent_var_name,
            "app_name": project_name,
        }

        rendered_content = template.render(**render_context)
        wrapper_file_path.write_text(rendered_content, encoding="utf-8")
        self.created_files.append(wrapper_file_path.name)
        self.logger.info(f"Generated wrapper file: {wrapper_file_path.name}")
