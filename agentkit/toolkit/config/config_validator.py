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

"""Configuration validation utilities."""

import re
from typing import List, Any
from dataclasses import fields, is_dataclass

from agentkit.toolkit.config.config import CommonConfig


class ConfigValidator:
    """Configuration validator."""

    @staticmethod
    def validate_common_config(config: CommonConfig) -> List[str]:
        """Validate common configuration.

        Args:
            config: CommonConfig instance

        Returns:
            List of error messages, empty if validation passes
        """
        errors = []

        for field in fields(CommonConfig):
            if field.name.startswith("_"):
                continue

            validation = field.metadata.get("validation", {})

            if validation.get("type") == "conditional":
                continue

            value = getattr(config, field.name)

            if validation.get("required") and (
                not value or (isinstance(value, str) and not value.strip())
            ):
                desc = field.metadata.get("description", field.name)
                errors.append(f"{desc} is required")
                continue

            pattern = validation.get("pattern")
            if pattern and value and isinstance(value, str):
                if not re.match(pattern, value):
                    desc = field.metadata.get("description", field.name)
                    msg = validation.get("message", "Invalid format")
                    errors.append(f"{desc}: {msg}")

            choices = field.metadata.get("choices")
            if choices and value:
                valid_values = []
                if isinstance(choices, list):
                    if choices and isinstance(choices[0], dict):
                        valid_values = [c["value"] for c in choices]
                    else:
                        valid_values = choices

                if valid_values and value not in valid_values:
                    desc = field.metadata.get("description", field.name)
                    errors.append(
                        f"{desc} must be one of: {', '.join(map(str, valid_values))}"
                    )

        conditional_errors = ConfigValidator._validate_conditional_fields(config)
        errors.extend(conditional_errors)

        return errors

    @staticmethod
    def validate_dataclass(config: Any) -> List[str]:
        if not is_dataclass(config):
            return []

        errors: List[str] = []

        for field in fields(config):
            if field.name.startswith("_"):
                continue

            validation = field.metadata.get("validation", {})

            if validation.get("type") == "conditional":
                continue

            value = getattr(config, field.name)

            if validation.get("required") and (
                not value or (isinstance(value, str) and not value.strip())
            ):
                desc = field.metadata.get("description", field.name)
                errors.append(f"{desc} is required")
                continue

            pattern = validation.get("pattern")
            if pattern and value and isinstance(value, str):
                if not re.match(pattern, value):
                    desc = field.metadata.get("description", field.name)
                    msg = validation.get("message", "Invalid format")
                    errors.append(f"{desc}: {msg}")

            choices = field.metadata.get("choices")
            if choices and value:
                valid_values = []
                if isinstance(choices, list):
                    if choices and isinstance(choices[0], dict):
                        valid_values = [c["value"] for c in choices]
                    else:
                        valid_values = choices

                if valid_values and value not in valid_values:
                    desc = field.metadata.get("description", field.name)
                    errors.append(
                        f"{desc} must be one of: {', '.join(map(str, valid_values))}"
                    )

        conditional_errors = ConfigValidator._validate_conditional_fields(config)
        errors.extend(conditional_errors)

        return errors

    @staticmethod
    def _validate_conditional_fields(config: Any) -> List[str]:
        """Execute conditional validation (cross-field dependencies).

        Args:
            config: CommonConfig instance

        Returns:
            List of error messages
        """
        errors = []

        for field in fields(config):
            if field.name.startswith("_"):
                continue

            validation = field.metadata.get("validation", {})

            if validation.get("type") != "conditional":
                continue

            depends_on = validation.get("depends_on")
            rules = validation.get("rules", {})

            if not depends_on or not rules:
                continue

            depend_value = getattr(config, depends_on, None)
            current_value = getattr(config, field.name, None)

            if depend_value in rules:
                rule = rules[depend_value]
                field_errors = ConfigValidator._apply_conditional_rule(
                    field.name, current_value, rule, field.metadata
                )
                errors.extend(field_errors)

        return errors

    @staticmethod
    def _apply_conditional_rule(
        field_name: str, value: Any, rule: dict, metadata: dict
    ) -> List[str]:
        """Apply single conditional rule.

        Args:
            field_name: Field name
            value: Field value
            rule: Conditional rule from validation.rules
            metadata: Field metadata

        Returns:
            List of error messages
        """
        errors = []
        desc = metadata.get("description", field_name)

        if rule.get("required") and (
            value is None or (isinstance(value, str) and not value.strip())
        ):
            errors.append(f"{desc} is required")
            return errors

        if "choices" in rule:
            if value not in rule["choices"]:
                msg = rule.get(
                    "message", f"Must be one of: {', '.join(rule['choices'])}"
                )
                errors.append(f"{desc}: {msg}")

        if "pattern" in rule:
            if not re.match(rule["pattern"], value):
                msg = rule.get("message", "Invalid format")
                errors.append(f"{desc}: {msg}")

        return errors

    @staticmethod
    def validate_field_value(
        field_name: str, value: Any, field_metadata: dict
    ) -> List[str]:
        """Validate a single field value.

        Args:
            field_name: Field name
            value: Field value
            field_metadata: Field metadata

        Returns:
            List of error messages
        """
        errors = []
        validation = field_metadata.get("validation", {})

        if validation.get("required") and (
            not value or (isinstance(value, str) and not value.strip())
        ):
            desc = field_metadata.get("description", field_name)
            errors.append(f"{desc} is required")
            return errors

        pattern = validation.get("pattern")
        if pattern and value and isinstance(value, str):
            if not re.match(pattern, value):
                desc = field_metadata.get("description", field_name)
                msg = validation.get("message", "Invalid format")
                errors.append(f"{desc}: {msg}")

        choices = field_metadata.get("choices")
        if choices and value:
            valid_values = []
            if isinstance(choices, list):
                if choices and isinstance(choices[0], dict):
                    valid_values = [c["value"] for c in choices]
                else:
                    valid_values = choices

            if valid_values and value not in valid_values:
                desc = field_metadata.get("description", field_name)
                errors.append(
                    f"{desc} must be one of: {', '.join(map(str, valid_values))}"
                )

        return errors
