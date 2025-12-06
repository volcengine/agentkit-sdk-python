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

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging
from pathlib import Path

from agentkit.toolkit.models import BuildResult
from agentkit.toolkit.reporter import Reporter, SilentReporter

logger = logging.getLogger(__name__)


class Builder(ABC):
    """
    Abstract base class for builders.

    Responsibilities:
    - Accept project directory and reporter
    - Provide build interface
    - Manage working directory

    Design principles:
    - project_dir is a constructor parameter (execution environment), not a configuration parameter
    - workdir is immutable during the instance lifecycle
    """

    def __init__(
        self, project_dir: Optional[Path] = None, reporter: Optional[Reporter] = None
    ):
        """
        Initialize Builder.

        Args:
            project_dir: Project root directory (where config files are located).
                        If None, uses current working directory.
            reporter: Progress reporter for UI feedback.
                     If None, uses SilentReporter.

        Design notes:
            - project_dir is execution environment information, not configuration
            - workdir is immutable during the instance lifecycle
            - Multiple build() calls use the same workdir
        """
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.reporter = reporter or SilentReporter()

        self.workdir = self._resolve_workdir(project_dir)

        self.logger.debug(f"Builder initialized, workdir: {self.workdir}")

    def _resolve_workdir(self, project_dir: Optional[Path]) -> Path:
        """
        Resolve the working directory.

        Args:
            project_dir: Project directory provided by user.

        Returns:
            Path: Resolved working directory (absolute path).

        Warning:
            If project_dir is None, falls back to current working directory (Path.cwd()).
            This may not be the expected project directory. It's recommended to always
            explicitly pass project_dir.
        """
        if project_dir:
            resolved = Path(project_dir).resolve()
            if not resolved.exists():
                self.logger.warning(
                    f"Project directory does not exist: {resolved}, falling back to current directory: {Path.cwd()}"
                )
                return Path.cwd()
            return resolved
        else:
            cwd = Path.cwd()
            self.logger.warning(
                f"project_dir not provided, using current working directory: {cwd}\n"
                f"This may not be the correct project directory! If build fails, check Dockerfile and source file locations."
            )
            return cwd

    @abstractmethod
    def build(self, config: Dict[str, Any]) -> BuildResult:
        """Execute build process.

        Args:
            config: Build configuration.

        Returns:
            BuildResult: Unified build result object.
        """
        pass

    @abstractmethod
    def check_artifact_exists(self, config: Dict[str, Any]) -> bool:
        pass

    @abstractmethod
    def remove_artifact(self, config: Dict[str, Any]) -> bool:
        pass
