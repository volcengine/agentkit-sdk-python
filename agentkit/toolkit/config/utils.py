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

"""Configuration utility functions."""

from pathlib import Path
from typing import Dict, Any, Optional
import logging

from dotenv import load_dotenv, dotenv_values
from yaml import safe_load, YAMLError

from .constants import AUTO_CREATE_VE
from .config import CommonConfig

logger = logging.getLogger(__name__)


def is_invalid_config(s: str) -> bool:
    return s is None or s == "" or s == AUTO_CREATE_VE


def is_valid_config(s: str) -> bool:
    return not is_invalid_config(s)


def load_dotenv_file(project_dir: Path) -> Dict[str, str]:
    """Load environment variables from .env file (standard dotenv format).

    Args:
        project_dir: Project directory containing .env file

    Returns:
        Dictionary of environment variables from .env file
    """
    env_file_path = project_dir / ".env"
    if not env_file_path.exists():
        return {}

    # Load .env into environment temporarily to get the values
    load_dotenv(env_file_path)
    env_values = dotenv_values(env_file_path)
    return {k: str(v) for k, v in env_values.items() if v is not None}


def load_veadk_yaml_file(project_dir: Path) -> Dict[str, str]:
    """Load and flatten veADK's config.yaml file.

    Args:
        project_dir: Project directory containing config.yaml file

    Returns:
        Dictionary of flattened environment variables from config.yaml
    """
    config_yaml_path = project_dir / "config.yaml"
    if not config_yaml_path.exists():
        return {}

    try:
        with open(config_yaml_path, "r", encoding="utf-8") as yaml_file:
            config_dict = safe_load(yaml_file) or {}

        # Flatten nested dictionary structure like veADK does
        flattened_config = flatten_dict(config_dict)
        # Convert to uppercase keys like veADK does
        return {k.upper(): str(v) for k, v in flattened_config.items() if v is not None}
    except (FileNotFoundError, PermissionError) as e:
        logger.warning(f"Cannot read config.yaml: {e}")
        return {}
    except (YAMLError, ValueError) as e:
        logger.warning(f"Invalid YAML format in config.yaml: {e}")
        return {}


def load_compat_config_files(project_dir: Optional[Path] = None) -> Dict[str, str]:
    """Load compatibility configuration files (.env and veADK config.yaml).

    This function loads external configuration files for veADK compatibility:
    1. Load standard .env file if exists (higher priority)
    2. Load veADK config.yaml file if exists and flatten nested structure (lower priority)

    Args:
        project_dir: Project directory to search for files. If None, uses current working directory.

    Returns:
        Dictionary of environment variables from .env file and veADK config.yaml
    """
    if project_dir is None:
        project_dir = Path.cwd()

    veadk_envs = {}
    veadk_envs.update(load_veadk_yaml_file(project_dir))
    veadk_envs.update(load_dotenv_file(project_dir))

    return veadk_envs


def flatten_dict(
    d: Dict[str, Any], parent_key: str = "", sep: str = "_"
) -> Dict[str, str]:
    """Flatten a nested dictionary like veADK does.

    Input:  {"model": {"name": "doubao"}}
    Output: {"MODEL_NAME": "doubao"}

    Args:
        d: Dictionary to flatten
        parent_key: Parent key prefix
        sep: Separator to use

    Returns:
        Flattened dictionary with string values
    """
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key.upper(), str(v)))
    return dict(items)


def merge_runtime_envs(
    common_config: CommonConfig,
    strategy_config: Dict[str, Any],
    project_dir: Optional[Path] = None,
) -> Dict[str, str]:
    """Merge environment variables from multiple sources with veADK compatibility.

    Priority order (highest to lowest):
    1. Strategy-level runtime_envs (from agentkit.yaml launch_types.*.runtime_envs)
    2. Common-level runtime_envs (from agentkit.yaml common.runtime_envs)
    3. .env file environment variables (standard dotenv format)
    4. config.yaml file environment variables (veADK style, flattened)

    Args:
        common_config: CommonConfig instance
        strategy_config: Strategy configuration dict
        project_dir: Project directory for loading veADK files and .env file

    Returns:
        Merged environment variables dict
    """
    merged_envs = {}

    # Load veADK environment files first (lowest priority)
    veadk_envs = load_compat_config_files(project_dir)
    if veadk_envs:
        merged_envs.update(veadk_envs)

    # Add common-level runtime_envs (medium priority)
    app_level_envs = getattr(common_config, "runtime_envs", {})
    if isinstance(app_level_envs, dict):
        merged_envs.update(app_level_envs)

    # Add strategy-level runtime_envs (highest priority)
    strategy_level_envs = strategy_config.get("runtime_envs", {})
    if isinstance(strategy_level_envs, dict):
        merged_envs.update(strategy_level_envs)

    return merged_envs
