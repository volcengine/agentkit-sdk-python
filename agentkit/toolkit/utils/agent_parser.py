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

"""Agent parser utility - Parse user's Agent definition files."""

import re
import logging
from pathlib import Path
from typing import Optional, List, Tuple

from agentkit.toolkit.models import AgentFileInfo


logger = logging.getLogger(__name__)


class AgentParser:
    """Utility for parsing user-provided Agent definition files."""

    def parse_agent_file(
        self, file_path: str, agent_var_name: Optional[str] = None
    ) -> AgentFileInfo:
        """
        Parse an Agent definition file and extract key information.

        Args:
            file_path: Path to the Agent definition file.
            agent_var_name: Optional explicit Agent variable name.

        Returns:
            AgentFileInfo: Parsed information about the Agent file.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If no Agent definition is found.
        """
        file_path_obj = Path(file_path).resolve()

        # Validate file exists
        if not file_path_obj.exists():
            raise FileNotFoundError(f"Agent file not found: {file_path}")

        if not file_path_obj.is_file():
            raise ValueError(f"Path is not a file: {file_path}")

        if file_path_obj.suffix != ".py":
            raise ValueError(f"File must be a Python file (.py): {file_path}")

        # Read file content
        try:
            content = file_path_obj.read_text(encoding="utf-8")
        except Exception as e:
            raise ValueError(f"Failed to read file {file_path}: {e}")

        # Parse file content
        module_name = file_path_obj.stem
        file_name = file_path_obj.name

        # Find Agent variable
        if agent_var_name:
            # User specified the variable name
            if not self._validate_agent_var(content, agent_var_name):
                raise ValueError(
                    f"Specified variable '{agent_var_name}' not found or "
                    f"is not an Agent instance in {file_name}"
                )
            detected_var = agent_var_name
        else:
            # Auto-detect Agent variable
            detected_var = self._detect_agent_variable(content)
            if not detected_var:
                raise ValueError(
                    f"Could not find Agent definition in {file_name}.\n"
                    f"Hints:\n"
                    f"  - Make sure your file contains: agent = Agent(...)\n"
                    f"  - Try specifying the variable name with --agent-var"
                )

        # Extract additional information
        imports = self._extract_imports(content)
        has_runner = self._detect_runner(content)
        has_entrypoint = self._detect_entrypoint(content)
        detected_tools = self._detect_tools(content)

        return AgentFileInfo(
            file_path=str(file_path_obj),
            agent_var_name=detected_var,
            module_name=module_name,
            file_name=file_name,
            imports=imports,
            has_runner=has_runner,
            has_entrypoint=has_entrypoint,
            detected_tools=detected_tools,
        )

    def validate_agent_file(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """
        Validate if the file contains a valid Agent definition.

        Args:
            file_path: Path to the file to validate.

        Returns:
            Tuple of (is_valid, error_message).
        """
        try:
            self.parse_agent_file(file_path)
            return True, None
        except FileNotFoundError as e:
            return False, str(e)
        except ValueError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Unexpected error: {e}"

    def _detect_agent_variable(self, content: str) -> Optional[str]:
        """
        Detect Agent variable name using pattern matching.

        Only matches direct instantiation: variable_name = Agent(...)
        For other patterns (e.g., agent = generate_agent_from_config()),
        user should specify --agent-var explicitly.
        """
        # Match: agent = Agent(...) or my_agent = Agent(...)
        pattern = r"(\w+)\s*=\s*Agent\s*\("
        matches = re.findall(pattern, content, re.MULTILINE)

        if matches:
            # If multiple matches, prefer common names or last one
            for preferred in ["agent", "main_agent", "my_agent"]:
                if preferred in matches:
                    logger.info(f"Detected Agent variable: {preferred}")
                    return preferred

            # Return the last match
            detected = matches[-1]
            logger.info(f"Detected Agent variable: {detected}")
            return detected

        return None

    def _validate_agent_var(self, content: str, var_name: str) -> bool:
        """
        Validate that the specified variable exists and is assigned a value.

        When user explicitly specifies --agent-var, we trust them and only check
        that the variable is assigned something. This handles cases like:
        - agent = Agent(...)
        - agent = generate_agent_from_config(config_path)
        - agent = create_custom_agent()
        """
        # Check if variable is assigned to anything: var_name = ...
        pattern = rf"^\s*{re.escape(var_name)}\s*=\s*\S"
        return bool(re.search(pattern, content, re.MULTILINE))

    def _extract_imports(self, content: str) -> List[str]:
        """
        Extract import statements from the file.

        Returns list of import lines for reference.
        """
        import_lines = []

        # Match: from xxx import yyy
        # Match: import xxx
        import_pattern = r"^(?:from\s+[\w.]+\s+import\s+.+|import\s+[\w.,\s]+)"

        for line in content.split("\n"):
            line = line.strip()
            if re.match(import_pattern, line):
                import_lines.append(line)

        return import_lines

    def _detect_runner(self, content: str) -> bool:
        """
        Detect if Runner is already defined in the file.
        """
        # Pattern: xxx = Runner(...)
        pattern = r"\w+\s*=\s*Runner\s*\("
        return bool(re.search(pattern, content))

    def _detect_entrypoint(self, content: str) -> bool:
        """
        Detect if an entrypoint function is already defined.
        """
        # Pattern: @app.entrypoint
        pattern = r"@\w+\.entrypoint"
        return bool(re.search(pattern, content))

    def _detect_tools(self, content: str) -> List[str]:
        """
        Detect which tools are used in the file.

        Common tools: web_search, run_code, get_weather
        """
        tools = []

        tool_patterns = {
            "web_search": r"\bweb_search\b",
            "run_code": r"\brun_code\b",
            "get_weather": r"\bget_weather\b",
        }

        for tool_name, pattern in tool_patterns.items():
            if re.search(pattern, content):
                tools.append(tool_name)

        return tools
