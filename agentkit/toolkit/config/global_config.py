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

"""Global configuration module.

Defines and manages the shared config file (~/.agentkit/config.yaml).
Used to store cross-project settings such as Volcengine credentials and CR/TOS defaults.

Priority:
- Environment variables > project config > global config > class defaults
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import logging

from agentkit.utils.global_config_io import (
    read_global_config_dict,
    write_global_config_dict,
)

from .utils import is_valid_config

logger = logging.getLogger(__name__)


@dataclass
class VolcengineCredentials:
    """Volcengine credentials configuration.

    Stores Volcengine API credentials as a fallback to environment variables.
    Has lower priority than environment variables.
    """

    access_key: str = ""
    secret_key: str = ""

    def to_dict(self):
        return {
            "access_key": self.access_key,
            "secret_key": self.secret_key,
        }

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            access_key=data.get("access_key", ""),
            secret_key=data.get("secret_key", ""),
        )


@dataclass
class CRGlobalConfig:
    """Container Registry (CR) global configuration.

    Used when project config `cr_instance_name` or `cr_namespace_name` is empty or "Auto".
    """

    instance_name: str = ""
    namespace_name: str = ""
    auto_create_instance_type: str = (
        "Micro"  # Instance type when auto-creating: "Micro" or "Enterprise"
    )

    def to_dict(self):
        return {
            "instance_name": self.instance_name,
            "namespace_name": self.namespace_name,
            "auto_create_instance_type": self.auto_create_instance_type,
        }

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            instance_name=data.get("instance_name", ""),
            namespace_name=data.get("namespace_name", ""),
            auto_create_instance_type=data.get("auto_create_instance_type", "Micro"),
        )


@dataclass
class TOSGlobalConfig:
    """TOS (object storage) global configuration.

    Used when project config `tos_bucket` or `tos_prefix` is empty or "Auto".
    """

    bucket: str = ""
    prefix: str = ""

    def to_dict(self):
        return {
            "bucket": self.bucket,
            "prefix": self.prefix,
        }

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            bucket=data.get("bucket", ""),
            prefix=data.get("prefix", ""),
        )


@dataclass
class GlobalConfig:
    """Top-level global configuration.

    Stored in ``~/.agentkit/config.yaml`` and shared across projects.
    """

    region: str = ""

    volcengine: VolcengineCredentials = field(default_factory=VolcengineCredentials)
    cr: CRGlobalConfig = field(default_factory=CRGlobalConfig)
    tos: TOSGlobalConfig = field(default_factory=TOSGlobalConfig)
    region_policy: dict = field(default_factory=dict)

    @dataclass
    class Defaults:
        launch_type: Optional[str] = None
        preflight_mode: Optional[str] = None
        cr_public_endpoint_check: Optional[bool] = None
        iam_role_policies: Optional[list] = None

        def to_dict(self):
            data = {}
            if self.launch_type:
                data["launch_type"] = self.launch_type
            if self.preflight_mode:
                data["preflight_mode"] = self.preflight_mode
            if self.cr_public_endpoint_check is not None:
                data["cr_public_endpoint_check"] = self.cr_public_endpoint_check
            if self.iam_role_policies is not None:
                data["iam_role_policies"] = self.iam_role_policies
            return data

        @classmethod
        def from_dict(cls, data: dict):
            return cls(
                launch_type=data.get("launch_type"),
                preflight_mode=data.get("preflight_mode"),
                cr_public_endpoint_check=data.get("cr_public_endpoint_check"),
                iam_role_policies=data.get("iam_role_policies"),
            )

    defaults: "GlobalConfig.Defaults" = field(
        default_factory=lambda: GlobalConfig.Defaults()
    )

    def to_dict(self):
        base = {
            "region": self.region,
            "volcengine": self.volcengine.to_dict(),
            "cr": self.cr.to_dict(),
            "tos": self.tos.to_dict(),
            "region_policy": self.region_policy,
        }
        defaults_dict = self.defaults.to_dict()
        if defaults_dict:
            base["defaults"] = defaults_dict
        return base

    @classmethod
    def from_dict(cls, data: dict):
        # Fallback: check nested volcengine.region if top-level region is missing
        region = data.get("region", "")
        if not region:
            region = data.get("volcengine", {}).get("region", "")

        return cls(
            region=region,
            volcengine=VolcengineCredentials.from_dict(data.get("volcengine", {})),
            cr=CRGlobalConfig.from_dict(data.get("cr", {})),
            tos=TOSGlobalConfig.from_dict(data.get("tos", {})),
            region_policy=data.get("region_policy", {}),
            defaults=GlobalConfig.Defaults.from_dict(data.get("defaults", {}) or {}),
        )


class GlobalConfigManager:
    """Global configuration manager.

    Responsible for loading, saving and managing the global config file.
    Default path: ``~/.agentkit/config.yaml``.
    """

    DEFAULT_PATH = Path.home() / ".agentkit" / "config.yaml"

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize global configuration manager.

        Args:
            config_path: Optional config file path, defaults to ``~/.agentkit/config.yaml``.
        """
        self.config_path = config_path or self.DEFAULT_PATH
        self._config: Optional[GlobalConfig] = None

    def load(self) -> GlobalConfig:
        """Load global configuration.

        If the config file does not exist or loading fails, returns an empty
        :class:`GlobalConfig` instance without raising.

        Returns:
            GlobalConfig instance
        """
        data = read_global_config_dict(self.config_path)
        if not data:
            logger.debug(
                f"Global config file does not exist or empty: {self.config_path}"
            )
            return GlobalConfig()
        try:
            logger.debug(f"Loaded global config from: {self.config_path}")
            return GlobalConfig.from_dict(data)
        except Exception as e:
            logger.debug(
                f"Failed to parse global config, using empty config: {e}", exc_info=True
            )
            return GlobalConfig()

    def save(self, config: GlobalConfig):
        """Save global configuration to disk.

        Args:
            config: Configuration object to persist
        """
        write_global_config_dict(config.to_dict(), self.config_path)
        logger.info(f"Global config saved: {self.config_path}")

    def get_config(self, force_reload: bool = False) -> GlobalConfig:
        """Get cached global configuration.

        Args:
            force_reload: Whether to force reload from disk.

        Returns:
            GlobalConfig instance
        """
        if self._config is None or force_reload:
            self._config = self.load()
        return self._config

    def exists(self) -> bool:
        """Check whether the global config file exists.

        Returns:
            True if the config file exists.
        """
        return self.config_path.exists()


# Singleton instance
_global_config_manager: Optional[GlobalConfigManager] = None


def get_global_config_manager() -> GlobalConfigManager:
    """Get the singleton :class:`GlobalConfigManager` instance."""
    global _global_config_manager
    if _global_config_manager is None:
        _global_config_manager = GlobalConfigManager()
    return _global_config_manager


def get_global_config(force_reload: bool = False) -> GlobalConfig:
    """Get global configuration via the singleton manager.

    This is the primary API for reading global configuration.

    Args:
        force_reload: Whether to force reload from disk.

    Returns:
        GlobalConfig instance

    Example:
        >>> global_config = get_global_config()
        >>> print(global_config.volcengine.access_key)
        >>> print(global_config.cr.instance_name)
    """
    return get_global_config_manager().get_config(force_reload=force_reload)


def save_global_config(config: GlobalConfig):
    """Persist global configuration via the singleton manager.

    Args:
        config: Configuration object to save.

    Example:
        >>> global_config = get_global_config()
        >>> global_config.cr.instance_name = "my-cr-instance"
        >>> save_global_config(global_config)
    """
    get_global_config_manager().save(config)


def global_config_exists() -> bool:
    """Convenience wrapper to check whether global config file exists.

    Returns:
        True if the config file exists.
    """
    return get_global_config_manager().exists()


def apply_global_config_defaults(
    config_obj,
    project_data: dict,
):
    """Apply global configuration defaults when project config is empty/"Auto".

    This function is called after ``from_dict()`` has constructed the config
    object. It fills project-level fields from global config only when the
    project config did not provide a valid value.

    Priority:
        1. Explicit project config (valid value) - highest, never overridden
        2. Global config (valid value) - used to fill missing project values
        3. Dataclass default - lowest, used when neither project nor global set

    Args:
        config_obj: Config object instance (already created via ``from_dict``)
        project_data: Original project config dict used to build the object

    Returns:
        The same config object with possible fields filled from global config.

    Example:
        >>> # project config has empty cr_instance_name
        >>> config = HybridStrategyConfig.from_dict({"cr_instance_name": ""})
        >>> # apply_global_config_defaults will fill from global config if set
        >>> # config.cr_instance_name = "my-team-cr-instance" (from global config)
    """
    # Lazy imports to avoid circular dependencies
    try:
        from .strategy_configs import HybridStrategyConfig, CloudStrategyConfig
    except ImportError as e:
        logger.debug(
            f"Failed to import strategy config classes, skip applying global config defaults: {e}"
        )
        return config_obj

    # Only handle strategy config classes
    if not isinstance(config_obj, (HybridStrategyConfig, CloudStrategyConfig)):
        return config_obj

    try:
        # Load global config
        global_config = get_global_config()

        # Map project field -> (global config section, attribute)
        field_mappings = {
            "cr_instance_name": ("cr", "instance_name"),
            "cr_namespace_name": ("cr", "namespace_name"),
            "cr_auto_create_instance_type": ("cr", "auto_create_instance_type"),
        }

        # For VeAgentkitConfig, also apply TOS-related settings
        if isinstance(config_obj, CloudStrategyConfig):
            field_mappings.update(
                {
                    "tos_bucket": ("tos", "bucket"),
                    "tos_prefix": ("tos", "prefix"),
                }
            )

        # Apply global config values
        for field_name, (section, attr) in field_mappings.items():
            # Skip if the target field does not exist on the config object
            if not hasattr(config_obj, field_name):
                continue

            # Use original project_data value to decide if user explicitly set it.
            # Note: from_dict may have already replaced empty/"Auto" with
            # template defaults, so we rely on raw project_data instead.
            original_project_value = (
                project_data.get(field_name) if isinstance(project_data, dict) else None
            )
            if is_valid_config(original_project_value):
                logger.debug(
                    f"Keep explicit project value for field {field_name}: {original_project_value}"
                )
                continue  # user explicitly provided value; do not override

            # Read value from global config
            section_obj = getattr(global_config, section, None)
            if section_obj is None:
                continue

            global_value = getattr(section_obj, attr, None)

            # If global config provides a valid value, apply it
            if global_value and is_valid_config(global_value):
                logger.info(
                    f"Apply global config: {field_name} = {global_value} (source: ~/.agentkit/config.yaml)"
                )
                setattr(config_obj, field_name, global_value)
                # Mark source as 'global' so persistence can keep local field empty
                try:
                    if not hasattr(config_obj, "_value_sources"):
                        config_obj._value_sources = {}
                    config_obj._value_sources[field_name] = "global"
                except Exception:
                    pass
            else:
                logger.debug(
                    f"Global config does not provide a valid value for field: {field_name}"
                )

    except Exception as e:
        # Errors while applying global config should not break the main flow
        logger.debug(
            f"Error while applying global config defaults (ignored): {e}", exc_info=True
        )

    return config_obj
