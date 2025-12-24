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


import os
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


def create_dockerignore_file(
    target_dir: str, additional_entries: Optional[List[str]] = None
) -> bool:
    """
    Create .dockerignore file with default and additional entries.

    Args:
        target_dir: Directory where .dockerignore should be created
        additional_entries: Additional entries to add to .dockerignore

    Returns:
        bool: True if file was created, False if it already existed

    Raises:
        IOError: When file write fails
    """
    dockerignore_path = os.path.join(target_dir, ".dockerignore")

    try:
        # Check if .dockerignore already exists
        if os.path.exists(dockerignore_path):
            logger.info(
                f".dockerignore already exists at: {dockerignore_path}, skipping creation"
            )
            return False

        # Default entries to exclude
        default_entries = [
            "# AgentKit configuration",
            "agentkit.yaml",
            "agentkit*.yaml",
            ".agentkit/",
            "",
            "# Python cache",
            "__pycache__/",
            "*.py[cod]",
            "*$py.class",
            "",
            "# Virtual environments",
            ".venv/",
            "venv/",
            "ENV/",
            "env/",
            "",
            "# IDE",
            ".vscode/",
            ".idea/",
            ".windsurf/",
            "",
            "# Git",
            ".git/",
            ".gitignore",
            "",
            "# Docker",
            "Dockerfile*",
            ".dockerignore",
        ]

        # Combine default and additional entries
        all_entries = default_entries.copy()
        if additional_entries:
            all_entries.append("")
            all_entries.append("# Additional entries")
            all_entries.extend(additional_entries)

        # Write .dockerignore file
        with open(dockerignore_path, "w", encoding="utf-8") as f:
            f.write("\n".join(all_entries))
            f.write("\n")  # End with newline

        logger.info(f"Successfully created .dockerignore at: {dockerignore_path}")
        return True

    except Exception as e:
        logger.error(f"Error creating .dockerignore: {str(e)}")
        raise
