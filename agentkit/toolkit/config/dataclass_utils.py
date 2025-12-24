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


from dataclasses import asdict, fields
import logging
from typing import Any, Dict, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

SENSITIVE_FIELDS = {
    "runtime_envs",
    "runtime_apikey_name",
    "runtime_apikey",
    "runtime_jwt_discovery_url",
    "runtime_jwt_allowed_clients",
}


def _get_safe_value(field_name: str, value: Any) -> Any:
    if field_name in SENSITIVE_FIELDS:
        return "******"
    return value


def _sanitize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize sensitive fields in a dictionary."""
    if not isinstance(data, dict):
        return data
    return {k: _get_safe_value(k, v) for k, v in data.items()}


def _sanitize_diff(diff: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize sensitive fields in a diff dictionary."""
    if not isinstance(diff, dict):
        return diff
    sanitized = {}
    for k, v in diff.items():
        if k in SENSITIVE_FIELDS:
            sanitized[k] = ("******", "******")
        else:
            sanitized[k] = v
    return sanitized


class DataclassSerializer:
    @staticmethod
    def to_dict(obj: Any) -> Dict[str, Any]:
        return asdict(obj)

    @staticmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        from dataclasses import MISSING

        if not hasattr(cls, "__dataclass_fields__"):
            raise ValueError(f"{cls} must be a dataclass")

        # Temporary map to track field value sources
        _sources: Dict[str, str] = {}

        field_info = {}
        for field in fields(cls):
            field_info[field.name] = field

        kwargs = {}
        for field_name, field in field_info.items():
            # Prefer direct field in data
            if field_name in data:
                kwargs[field_name] = data[field_name]
                _sources[field_name] = "local"
                logger.debug(
                    "[DataclassSerializer] source=local field=%s value=%r",
                    field_name,
                    _get_safe_value(field_name, kwargs[field_name]),
                )
            else:
                # Try aliases (backward compatibility)
                found_in_alias = False
                aliases = field.metadata.get("aliases", [])
                for alias in aliases:
                    if alias in data:
                        kwargs[field_name] = data[alias]
                        found_in_alias = True
                        _sources[field_name] = "local"
                        logger.debug(
                            "[DataclassSerializer] source=alias(%s) -> local field=%s value=%r",
                            alias,
                            field_name,
                            _get_safe_value(field_name, kwargs[field_name]),
                        )
                        break

                # Fallback to default values when not provided in data or aliases
                if not found_in_alias:
                    if field.default_factory is not MISSING:
                        kwargs[field_name] = field.default_factory()
                        _sources[field_name] = "default"
                        logger.debug(
                            "[DataclassSerializer] source=default_factory field=%s value=%r",
                            field_name,
                            _get_safe_value(field_name, kwargs[field_name]),
                        )
                    elif field.default is not MISSING:
                        kwargs[field_name] = field.default
                        _sources[field_name] = "default"
                        logger.debug(
                            "[DataclassSerializer] source=default field=%s value=%r",
                            field_name,
                            _get_safe_value(field_name, kwargs[field_name]),
                        )
                    else:
                        kwargs[field_name] = None
                        # No source
                        logger.debug(
                            "[DataclassSerializer] source=none field=%s value=None",
                            field_name,
                        )

        # Create instance (no class-level render skipping is used anymore)
        instance = cls(**kwargs)

        # Attach sources to the instance for later writeback decisions
        try:
            if not hasattr(instance, "_value_sources"):
                instance._value_sources = {}
            instance._value_sources.update(_sources)
        except Exception:
            pass

        return instance


class AutoSerializableMixin:
    """Mixin for configuration dataclasses.

    Responsibilities:
    - Convert to/from dict
    - Apply global defaults (only when local value is invalid)
    - Fill remaining invalid values with default_template/default value
    - Render template fields and validate unresolved placeholders
    - Produce persistable dict based on value sources
    """

    def to_dict(self) -> Dict[str, Any]:
        return DataclassSerializer.to_dict(self)

    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any], skip_render: bool = False) -> T:
        """Create a config instance from a dict.

        Steps:
        1) Construct instance without rendering
        2) Apply global defaults for invalid fields (empty/Auto), keeping user values
        3) Fill remaining invalid fields via default_template or dataclass defaults
        4) Render fields marked with render_template (unless skip_render=True)
        """
        # Construct first, so global defaults can be applied before any rendering
        logger = logging.getLogger(f"{__name__}.{cls.__name__}")
        logger.debug(
            "from_dict: start, skip_render=%s for %s", skip_render, cls.__name__
        )
        data = dict(data)

        # 2) Create instance without rendering
        try:
            instance = DataclassSerializer.from_dict(cls, data)
            logger.debug(
                "from_dict: instance created without rendering for %s", cls.__name__
            )
        except Exception as e:
            logger.debug(
                "from_dict: failed to create instance for %s: %s", cls.__name__, e
            )
            raise

        # Apply global defaults using original project data (pre-render)
        try:
            from .global_config import apply_global_config_defaults

            before = instance.to_dict()
            logger.debug(
                "from_dict: before globals for %s -> %r",
                cls.__name__,
                _sanitize_dict(before),
            )
            instance = apply_global_config_defaults(instance, data)
            after = instance.to_dict()
            if before != after:
                diff = {
                    k: (before.get(k), after.get(k))
                    for k in after.keys()
                    if before.get(k) != after.get(k)
                }
                logger.debug(
                    "from_dict: applied global defaults for %s; changes=%r",
                    cls.__name__,
                    _sanitize_diff(diff),
                )
            else:
                logger.debug(
                    "from_dict: applied global defaults for %s; no changes",
                    cls.__name__,
                )
        except ImportError:
            logger.debug(
                "from_dict: global_config not available; skipped applying globals for %s",
                cls.__name__,
            )
        except Exception:
            logger.debug(
                "from_dict: apply_global_config_defaults raised; ignored for %s",
                cls.__name__,
            )

        # Render template fields after globals/defaults. Skipped if skip_render is True.
        if not skip_render:
            try:
                # Ensure instance-level skip flag is cleared
                if hasattr(instance, "_skip_render"):
                    setattr(instance, "_skip_render", False)
                logger.debug(
                    "from_dict: start rendering template fields for %s", cls.__name__
                )
                instance._render_template_fields()
                logger.debug("from_dict: rendered template fields for %s", cls.__name__)
            except Exception:
                logger.debug(
                    "from_dict: rendering failed for %s; re-raising", cls.__name__
                )
                raise

        return instance

    def _render_template_fields(self):
        """Render fields whose metadata has render_template=True.

        - Saves original template strings in _template_originals
        - Supports default_template for Auto/empty values
        - Validates that no placeholders remain after rendering
        - Honors instance-level _skip_render
        """

        # Only meaningful for dataclasses
        if not hasattr(self, "__dataclass_fields__"):
            logger.debug("_render_template_fields: not a dataclass, skipping")
            return

        # Skip when explicitly requested on the instance (e.g., status-only flows)
        inst_skip = getattr(self, "_skip_render", False)
        if inst_skip:
            logger.debug(
                "_render_template_fields: skip rendering for %s, skip_render=%s",
                self.__class__.__name__,
                inst_skip,
            )
            return

        try:
            from agentkit.utils.template_utils import render_template
            from agentkit.toolkit.config.utils import is_invalid_config

            cfg_name = self.__class__.__name__

            # Initialize original template map
            if not hasattr(self, "_template_originals"):
                self._template_originals = {}

            for field_info in fields(self):
                # Process only fields marked for template rendering
                logger.debug(
                    "[%s] [template] checking field: name=%s, render_template=%s",
                    cfg_name,
                    field_info.name,
                    field_info.metadata.get("render_template"),
                )
                if field_info.metadata.get("render_template"):
                    field_value = getattr(self, field_info.name)
                    logger.debug(
                        "[%s] [template] start field render check: name=%s, value=%r, has_placeholders=%s",
                        cfg_name,
                        field_info.name,
                        _get_safe_value(field_info.name, field_value),
                        (
                            isinstance(field_value, str)
                            and ("{{" in field_value and "}}" in field_value)
                        ),
                    )

                    # Handle invalid values (None/""/Auto) via default_template when available
                    if is_invalid_config(field_value):
                        default_template = field_info.metadata.get("default_template")
                        if default_template:
                            logger.debug(
                                "[%s] [template] field %s is Auto/empty -> using default_template=%r",
                                cfg_name,
                                field_info.name,
                                _get_safe_value(field_info.name, default_template),
                            )
                            field_value = default_template
                            self._template_originals[field_info.name] = default_template
                            try:
                                if not hasattr(self, "_value_sources"):
                                    self._value_sources = {}
                                self._value_sources[field_info.name] = (
                                    "default_template"
                                )
                            except Exception:
                                pass
                            setattr(self, field_info.name, default_template)
                        else:
                            logger.debug(
                                "[%s] [template] field %s is Auto/empty and has no default_template -> skip",
                                cfg_name,
                                field_info.name,
                            )
                            continue

                    # Render non-empty value
                    if field_value:
                        # Save original template string only if placeholders are present
                        if "{{" in str(field_value) and "}}" in str(field_value):
                            if field_info.name not in self._template_originals:
                                self._template_originals[field_info.name] = field_value
                                logger.debug(
                                    "[%s] [template] save original template for %s: %r",
                                    cfg_name,
                                    field_info.name,
                                    _get_safe_value(field_info.name, field_value),
                                )

                        try:
                            is_sensitive = field_info.name in SENSITIVE_FIELDS
                            rendered = render_template(
                                field_value, sensitive=is_sensitive
                            )
                            logger.debug(
                                "[%s] [template] rendered field %s: %r -> %r",
                                cfg_name,
                                field_info.name,
                                _get_safe_value(field_info.name, field_value),
                                _get_safe_value(field_info.name, rendered),
                            )
                            # Fail if unresolved placeholders remain
                            if "{{" in str(rendered) and "}}" in str(rendered):
                                error_msg = (
                                    f"Config field '{field_info.name}' template variables were not fully rendered: "
                                    f"'{field_value}' -> '{rendered}'"
                                )
                                logger.error(f"[{cfg_name}] {error_msg}")
                                raise ValueError(error_msg)

                            if rendered != field_value:
                                logger.debug(
                                    "[%s] [template] apply rendered value for %s",
                                    cfg_name,
                                    field_info.name,
                                )
                                setattr(self, field_info.name, rendered)
                        except Exception as e:
                            # Do not silently fallback on render failures; surface details
                            error_type = type(e).__name__
                            error_detail = str(e)

                            # Build detailed error message
                            error_msg = f"Config field '{field_info.name}' template rendering failed: {field_value}\n"
                            error_msg += f"Error type: {error_type}\n"
                            error_msg += f"Error detail: {error_detail}"

                            if "{{account_id}}" in str(field_value):
                                error_msg += (
                                    "\n\nHint: failed to obtain account_id; please check Volcengine AK/SK "
                                    "configuration and IAM permissions."
                                )

                            logger.error(f"[{cfg_name}] {error_msg}")
                            # Log full stack for debugging
                            logger.debug(
                                f"[{cfg_name}] Full stack trace of config rendering failure:",
                                exc_info=True,
                            )
                            raise ValueError(error_msg) from e
                else:
                    logger.debug(
                        "[%s] [template] field %s is not marked for rendering, value: %r",
                        cfg_name,
                        field_info.name,
                        _get_safe_value(
                            field_info.name, getattr(self, field_info.name)
                        ),
                    )
        except ImportError:
            # If template utils are not available, no-op
            logger.error(
                "Template utils not available; skipping template rendering",
                exc_info=True,
            )

    def to_persist_dict(self) -> Dict[str, Any]:
        """Produce a persistable dict following value-source rules.

        - global: write empty string (keep local unset)
        - default_template: write saved original template
        - default: write current value
        - local: write original template if present, otherwise current value
        - system fields are ignored here (left as runtime values)
        """
        result = self.to_dict()

        sources = getattr(self, "_value_sources", {}) or {}
        originals = getattr(self, "_template_originals", {}) or {}

        # Iterate fields and decide persisted value based on source rules
        for field_info in fields(self):
            name = field_info.name
            source = sources.get(name)
            current_value = getattr(self, name)
            original_tpl = originals.get(name)

            if source == "global":
                # Global source: write empty string so project config remains "unset"
                result[name] = ""
                logger.debug(
                    "[persist] field=%s source=global -> write='' (keep local unset)",
                    name,
                )
            elif source == "default_template":
                # Write back the template instead of rendered value
                chosen = original_tpl if original_tpl is not None else current_value
                result[name] = chosen
                logger.debug(
                    "[persist] field=%s source=default_template original=%r current=%r -> write=%r",
                    name,
                    original_tpl,
                    current_value,
                    chosen,
                )
            elif source == "default" or source == "local":
                if original_tpl is not None:
                    result[name] = original_tpl
                else:
                    result[name] = current_value
                logger.debug(
                    "[persist] field=%s source=%s original=%r current=%r -> write=%r",
                    name,
                    source,
                    original_tpl,
                    current_value,
                    result[name],
                )
            else:
                # Unknown source: keep current value
                result[name] = current_value
                logger.debug(
                    "[persist] field=%s source=unknown -> write current=%r",
                    name,
                    current_value,
                )

        return result
