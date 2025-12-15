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

from typing import Literal, get_args, get_origin
import json
import time

from pydantic import BaseModel

# Optional imports - only when needed
try:
    from InquirerPy import resolver

    INQUIRERPY_AVAILABLE = True
except ImportError:
    INQUIRERPY_AVAILABLE = False

try:
    from rich.table import Table
    from rich.panel import Panel

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


def prompt_base_model(model: type[BaseModel]) -> dict:
    """Generate interactive prompts for a Pydantic BaseModel.

    Args:
        model: A Pydantic BaseModel class

    Returns:
        Dictionary of user responses mapped to field names
    """
    if not INQUIRERPY_AVAILABLE:
        raise ImportError("InquirerPy is required for interactive prompts")

    prompts = []

    for field_name, model_field in model.model_fields.items():
        if get_origin(model_field.annotation) == Literal:
            prompts.append(
                {
                    "type": "list",
                    "name": field_name,
                    "default": model_field.default if model_field.default else "",
                    "message": model_field.description
                    if model_field.description
                    else field_name,
                    "choices": list(get_args(model_field.annotation)),
                }
            )
        elif model_field.annotation is bool:
            prompts.append(
                {
                    "type": "confirm",
                    "name": field_name,
                    "default": model_field.default if model_field.default else False,
                    "message": model_field.description
                    if model_field.description
                    else field_name,
                }
            )
        else:
            prompts.append(
                {
                    "type": "input",
                    "name": field_name,
                    "default": str(model_field.default) if model_field.default else "",
                    "message": model_field.description
                    if model_field.description
                    else field_name,
                }
            )

    responses = resolver.prompt(prompts)
    return responses


# ==================== SDK-to-CLI Common Helpers ====================


class PaginationHelper:
    """Unified pagination logic for all CLI list commands"""

    @staticmethod
    def fetch_all_pages(
        request_func,
        request_builder,
        max_results,
        next_token,
        fetch_all,
        max_batches,
        sleep_ms,
    ):
        """
        Unified pagination logic for SDK-to-CLI modules
        Returns: (items, last_next_token, batch_count)
        """
        collected = []
        token = next_token
        batch_count = 0
        last_next_token = ""

        while True:
            request = request_builder(token)
            response = request_func(request)

            # Extract items (adapts to different SDK response structures)
            items = (
                getattr(response, "items", None)
                or getattr(response, "knowledge_bases", None)
                or getattr(response, "memories", None)
                or getattr(response, "tools", None)
                or getattr(response, "agent_kit_runtimes", None)
                or []
            )

            if fetch_all:
                collected.extend(items)
            else:
                # In non-fetch-all mode, only collect current batch
                collected = items
                last_next_token = getattr(response, "next_token", None) or ""
                break

            batch_count += 1
            last_next_token = getattr(response, "next_token", None) or ""

            # Termination conditions
            if not fetch_all:
                break
            if max_batches and batch_count >= max_batches:
                break
            if not last_next_token:
                break

            token = last_next_token
            if sleep_ms > 0:
                time.sleep(sleep_ms / 1000.0)

        return collected, last_next_token, batch_count


class OutputFormatter:
    """Unified output formatting for tables, JSON, YAML"""

    @staticmethod
    def create_table(items, columns, title, fields=None):
        """Create standardized table format"""
        if not RICH_AVAILABLE:
            raise ImportError("rich library is required for table formatting")

        table = Table(title=title, show_lines=False)

        # Select columns to display
        selected_cols = columns
        if fields:
            selected_fields = [f.strip() for f in fields.split(",") if f.strip()]
            selected_cols = [
                (field, name, color)
                for field, name, color in columns
                if field in selected_fields
            ]

        # Add columns
        for field, name, color in selected_cols:
            table.add_column(name, style=color)

        # Add rows
        for item in items:
            row_data = []
            for field, _, _ in selected_cols:
                value = getattr(item, field, None)
                if value is None and hasattr(item, "model_dump"):
                    value = item.model_dump(by_alias=True, exclude_none=True).get(
                        field, ""
                    )
                row_data.append(str(value))
            table.add_row(*row_data)

        return table

    @staticmethod
    def format_quiet_output(items, id_field):
        """Quiet mode output - only return ID list"""
        return [str(getattr(item, id_field, "")) for item in items]

    @staticmethod
    def format_json_output(items, include_meta, meta):
        """JSON format output"""
        data = [item.model_dump(by_alias=True, exclude_none=True) for item in items]
        if include_meta:
            return json.dumps(
                {"meta": meta, "items": data}, indent=2, ensure_ascii=False
            )
        return json.dumps(data, indent=2, ensure_ascii=False)

    @staticmethod
    def format_yaml_output(items, include_meta, meta):
        """YAML format output"""
        import yaml

        data = [item.model_dump(by_alias=True, exclude_none=True) for item in items]
        if include_meta:
            return yaml.safe_dump(
                {"meta": meta, "items": data}, sort_keys=False, allow_unicode=True
            )
        return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


class ParameterHelper:
    """Unified parameter parsing and validation"""

    @staticmethod
    def parse_comma_separated(value):
        """Parse comma or semicolon separated values"""
        if not value:
            return None
        separator = "," if "," in value else ";"
        return [p.strip() for p in value.split(separator) if p.strip()]

    @staticmethod
    def validate_values(values, allowed_set, param_name):
        """Validate values against allowed set"""
        if not values:
            return
        invalid = [v for v in values if v not in allowed_set]
        if invalid:
            raise ValueError(
                f"Invalid {param_name}: {invalid}. Allowed: {'|'.join(allowed_set)}"
            )


class PaginationDisplayHelper:
    """Unified pagination display logic"""

    @staticmethod
    def show_pagination_info(
        has_next, next_token, print_next_token, print_next_token_only, quiet, console
    ):
        """Show consistent pagination information"""
        if not RICH_AVAILABLE:
            return

        if quiet or print_next_token_only or not has_next:
            return

        if print_next_token:
            console.print(
                Panel.fit(
                    f"NextToken: {next_token}", title="Cursor", border_style="cyan"
                )
            )
        else:
            # Concise hint - only show command example
            console.print(f"[dim]Next page:[/dim] --next-token '{next_token}'")
