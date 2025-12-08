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

import readline
from typing import Any, Dict, Optional, List, Union, get_type_hints, get_origin, get_args
from dataclasses import fields, is_dataclass, MISSING
from rich.console import Console
from rich.prompt import Confirm
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.align import Align
from rich import box

console = Console()

# Modern icons and style configuration
ICONS = {
    "agent": "🤖",
    "app": "📱",
    "file": "📄",
    "deploy": "🚀",
    "language": "✏️",
    "language_version": "🐍",
    "dependencies_file": "📦",
    "package": "📦",
    "port": "🔌",
    "config": "⚙️",
    "success": "✅",
    "error": "❌",
    "warning": "⚠️",
    "info": "ℹ️",
    "input": "🔤",
    "select": "🔘",
    "description": "✨",
    "list": "📝",
    "dict": "📋",
    "number": "🔢",
    "boolean": "🔲",
    "string": "🔤",
    "rocket": "🚀",
}

# Color configuration
COLORS = {
    "primary": "#2196F3",      # Tech blue
    "success": "#4CAF50",      # Vibrant green
    "warning": "#FF9800",      # Orange
    "error": "#F44336",        # Red
    "border": "#37474F",       # Border gray
    "muted": "#78909C",        # Soft gray
    "label": "#64B5F6",        # Light blue
    "description": "#90A4AE"   # Description gray
}

# Style configuration
STYLES = {
    "title": "bold #2196F3",
    "subtitle": "bold #64B5F6",
    "success": "bold #4CAF50",
    "warning": "bold #FF9800",
    "error": "bold #F44336",
    "label": "bold #64B5F6",
    "value": "#4CAF50",
    "description": "#78909C",
    "muted": "#78909C"
}

class AutoPromptGenerator:
    def __init__(self):
        self.type_handlers = {
            str: self._handle_string,
            int: self._handle_int,
            float: self._handle_float,
            bool: self._handle_bool,
            list: self._handle_list,
            List: self._handle_list,
            dict: self._handle_dict,
            Dict: self._handle_dict,
        }

    def _safe_input(self, prompt_text, default: str = "") -> str:
        """Safe input method that protects prompt text from being deleted by Backspace.

        Args:
            prompt_text: Prompt text (Rich Text object or string)
            default: Default value

        Returns:
            User input string
        """
        # Convert Rich Text to string with ANSI escape codes
        # Use Console's internal method to render styles as ANSI codes
        from io import StringIO
        string_io = StringIO()
        # Use global console's is_terminal property to determine if terminal features should be enabled
        # This allows automatic adaptation to the actual terminal environment, avoiding garbled output
        temp_console = Console(file=string_io, force_terminal=console.is_terminal, width=200)
        temp_console.print(prompt_text, end="")
        rendered_prompt = string_io.getvalue()

        # If there's a default value, try to use readline's pre_input_hook to prefill
        # Add compatibility handling as some systems (e.g., macOS libedit) may not support these features
        if default:
            def prefill():
                try:
                    readline.insert_text(default)
                    readline.redisplay()
                except (AttributeError, OSError):
                    # Some readline implementations (e.g., libedit) may not support insert_text or redisplay
                    # In this case, we'll display the default value in the prompt as a fallback
                    pass
            try:
                readline.set_pre_input_hook(prefill)
            except (AttributeError, OSError):
                # If set_pre_input_hook is unavailable, display default value in prompt
                if console.is_terminal:
                    rendered_prompt += f" \033[2m[Default: {default}]\033[0m"
                else:
                    rendered_prompt += f" [Default: {default}]"

        try:
            # Use input()'s prompt parameter; Python automatically protects this prompt from Backspace deletion
            # The prompt contains ANSI escape codes, so Rich styles are displayed
            user_input = input(rendered_prompt)

            # If user didn't input anything and there's a default value, return the default
            if not user_input and default:
                return default

            return user_input
        finally:
            # Clean up hook; use try-except to prevent errors on unsupported systems
            try:
                readline.set_pre_input_hook()
            except (AttributeError, OSError):
                pass

    def generate_config(self, dataclass_type: type, existing_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not is_dataclass(dataclass_type):
            raise ValueError(f"{dataclass_type} must be a dataclass")

        config = {}
        existing_config = existing_config or {}

        # Get dataclass metadata
        # Try to get from class attributes; if not found, create instance to get field values
        config_metadata = {}
        if hasattr(dataclass_type, '_config_metadata'):
            # If it's a class attribute
            config_metadata = getattr(dataclass_type, '_config_metadata', {})
        else:
            # If it's a field, need to create instance to get default value
            try:
                # Get field's default value factory or default value
                for field in fields(dataclass_type):
                    if field.name == '_config_metadata':
                        if field.default_factory is not None and field.default_factory != MISSING:
                            config_metadata = field.default_factory()
                        elif field.default != MISSING:
                            config_metadata = field.default
                        break
            except Exception:
                pass

        config_name = config_metadata.get('name', dataclass_type.__name__)

        # Get custom messages
        welcome_message = config_metadata.get('welcome_message')
        next_step_hint = config_metadata.get('next_step_hint')
        completion_message = config_metadata.get('completion_message')
        next_action_hint = config_metadata.get('next_action_hint')

        # Display modern welcome panel
        self._show_welcome_panel(config_name, welcome_message, next_step_hint)

        # Get field list and display progress
        visible_fields = [f for f in fields(dataclass_type)
                         if not f.metadata.get("hidden", False) and not f.metadata.get("system", False) and f.name != "_config_metadata"]
        total_fields = len(visible_fields)

        for idx, field in enumerate(visible_fields, 1):
            field_name = field.name
            field_type = get_type_hints(dataclass_type).get(field_name, str)
            existing_value = existing_config.get(field_name)
            default_value = existing_value if existing_value is not None else field.default
            description = field.metadata.get("description") or field.name.replace("_", " ").title()

            # Pass progress info and current config to field handler
            value = self._prompt_for_field(field_name, field_type, description, default_value, field.metadata, idx, total_fields, config)

            if value is not None:
                config[field_name] = value

        # Display completion panel
        self._show_completion_panel(config, completion_message, next_action_hint)

        # Handle hidden and system fields
        for field in fields(dataclass_type):
            field_name = field.name
            if field.metadata.get("hidden", False) or field.metadata.get("system", False):
                if field_name in existing_config:
                    config[field_name] = existing_config[field_name]

        # Filter out MISSING values
        filtered_config = {}
        for key, value in config.items():
            if not isinstance(value, type(MISSING)):
                filtered_config[key] = value

        return filtered_config

    def _prompt_for_field(self, name: str, field_type: type, description: str, default: Any, metadata: Dict[str, Any] = None, current: int = 1, total: int = 1, current_config: Dict[str, Any] = None) -> Any:
        """Field input coordinator - handles advanced validation logic.
        
        Args:
            name: Field name
            field_type: Field type
            description: Field description
            default: Default value
            metadata: Field metadata
            current: Current progress
            total: Total fields
            current_config: Currently configured fields (for conditional validation)
            
        Returns:
            User input value
        """
        metadata = metadata or {}
        current_config = current_config or {}

        if get_origin(field_type) is not None:
            if get_origin(field_type) is Union:
                args = get_args(field_type)
                if len(args) == 2 and type(None) in args:
                    field_type = args[0]

        if get_origin(field_type) is list or field_type is List:
            return self._handle_list(description, default, metadata, current, total)

        if get_origin(field_type) is dict or field_type is Dict:
            return self._handle_dict(description, default, metadata, current, total)

        if default is MISSING or isinstance(default, type(MISSING)):
            default = None

        choices = metadata.get("choices")
        if choices:
            return self._handle_choice_selection(description, default, choices, metadata, current, total)

        # Enhance description with conditional hints
        enhanced_description = self._enhance_description_with_hints(
            description, metadata, current_config
        )
        
        # Conditional validation loop
        validation = metadata.get('validation', {})
        while True:
            # Call specific input handler (basic validation)
            handler = self.type_handlers.get(field_type)
            if handler:
                value = handler(enhanced_description, default, metadata, current, total)
            else:
                value = self._handle_string(enhanced_description, default, metadata, current, total)
            
            # If conditional validation type, perform conditional validation
            if validation.get('type') == 'conditional' and value:
                errors = self._validate_conditional_value(
                    name, value, validation, current_config
                )
                
                if errors:
                    # Display errors and continue loop for re-input
                    for error in errors:
                        console.print(f"{ICONS['error']} {error}")
                    continue  # Re-input
            
            # Validation passed, return value
            return value
    
    def _enhance_description_with_hints(self, description: str, metadata: dict, current_config: dict) -> str:
        """Enhance description with hints based on conditional validation rules.
        
        Args:
            description: Original description
            metadata: Field metadata
            current_config: Currently configured fields
            
        Returns:
            Enhanced description (with hint information)
        """
        validation = metadata.get('validation', {})
        
        # Not conditional validation, return original description directly
        if validation.get('type') != 'conditional':
            return description
        
        depends_on = validation.get('depends_on')
        rules = validation.get('rules', {})
        
        if not depends_on or not rules:
            return description
        
        # Get current value of dependent field
        depend_value = current_config.get(depends_on)
        
        # If dependent field has value and has corresponding rule
        if depend_value and depend_value in rules:
            rule = rules[depend_value]
            
            # Add hints based on rule type
            if 'choices' in rule:
                # choices rule: display available options
                hint = f" [Options: {', '.join(rule['choices'])}]"
                return f"{description}{hint}"
            
            elif 'pattern' in rule and 'hint' in rule:
                # pattern rule: display format hint
                hint = rule['hint']
                return f"{description} {hint}"
        
        return description
    
    def _validate_conditional_value(self, field_name: str, value: Any, validation: dict, current_config: dict) -> List[str]:
        """Validate conditional field value.
        
        Args:
            field_name: Field name
            value: Input value
            validation: Validation rules (metadata['validation'])
            current_config: Currently configured fields
        
        Returns:
            List of errors; empty list means validation passed
        """
        errors = []
        
        depends_on = validation.get('depends_on')
        rules = validation.get('rules', {})
        
        if not depends_on or not rules:
            return errors
        
        # Get value of dependent field
        depend_value = current_config.get(depends_on)
        
        # If dependent field has value and has corresponding rule
        if depend_value and depend_value in rules:
            rule = rules[depend_value]
            
            # choices validation
            if 'choices' in rule and value not in rule['choices']:
                msg = rule.get('message', f"Must be one of: {', '.join(rule['choices'])}")
                errors.append(msg)
            
            # pattern validation
            if 'pattern' in rule:
                import re
                if not re.match(rule['pattern'], value):
                    msg = rule.get('message', 'Format is incorrect')
                    errors.append(msg)
        
        return errors

    def _handle_choice_selection(self, description: str, default: Any, choices: List[Any], field_metadata: Dict[str, Any] = None, current: int = 1, total: int = 1) -> str:
        # Handle different types of choice data
        if isinstance(choices, list) and len(choices) > 0 and isinstance(choices[0], dict):
            # Handle dictionary format choice items
            if not default or (default and default not in [choice['value'] for choice in choices]):
                default = choices[0]['value'] if choices else None
        else:
            # Handle simple list format choice items
            if not default or (default and default not in choices):
                default = choices[0] if choices else None

        # Get field icon (supports metadata specification)
        icon = self._get_field_icon(description, field_metadata) if field_metadata else ICONS['select']

        # Create choice panel title with integrated progress information
        console.print(f"\n[{current}/{total}] {icon} {description}")

        # Process choice data
        choice_descriptions = {}
        if isinstance(choices, dict):
            choice_descriptions = choices
            choices = list(choices.keys())
        elif isinstance(choices, list) and len(choices) > 0 and isinstance(choices[0], dict):
            choice_descriptions = {item["value"]: item.get("description", "") for item in choices}
            choices = [item["value"] for item in choices]

        # Create modern choice menu
        table = Table(show_header=False, box=box.ROUNDED, padding=(0, 1))

        for i, choice in enumerate(choices, 1):
            desc = choice_descriptions.get(choice, "")

            # Mark default option
            is_default = choice == default
            default_marker = " (current)" if is_default else ""

            # Format choice item
            choice_text = Text()
            choice_text.append(f"{i}. ")
            choice_text.append(f"{choice}")
            if desc:
                choice_text.append(f" - {desc}")
            choice_text.append(default_marker)

            table.add_row(choice_text)

        # Display choice table
        console.print(table)
        console.print()

        while True:
            # Create input prompt
            prompt_str = "Please select (enter number or name): "

            # Use input()'s prompt parameter
            try:
                user_input = input(prompt_str)
            except KeyboardInterrupt:
                raise
            except EOFError:
                console.print(f"\n{ICONS['warning']} Selection cancelled, using default value")
                return str(default) if default else str(choices[0]) if choices else ""

            if user_input.isdigit():
                choice_num = int(user_input)
                if 1 <= choice_num <= len(choices):
                    selected = choices[choice_num - 1]
                    # Display selection confirmation
                    console.print(f"\n[{COLORS['success']}]»[/] Selected: {selected}\n")
                    return selected
                else:
                    console.print(f"{ICONS['error']} Please enter a number between 1-{len(choices)}")
                    continue

            if user_input in choices:
                # Display selection confirmation
                console.print(f"\n[{COLORS['success']}]»[/] Selected: {user_input}\n")
                return user_input
            elif user_input == "":
                console.print(f"\n[{COLORS['success']}]»[/] Using default: {default}\n")
                return default
            else:
                valid_choices = ", ".join(choices)
                console.print(f"{ICONS['error']} Invalid choice, please select: {valid_choices}")

    def _handle_string(self, description: str, default: Any, field_metadata: Dict[str, Any] = None, current: int = 1, total: int = 1) -> str:
        # Get field icon (supports metadata specification)
        icon = self._get_field_icon(description, field_metadata) if field_metadata else ICONS['input']

        # Get validation rules
        validation_rules = field_metadata.get('validation', {}) if field_metadata else {}

        while True:
            # Build complete prompt information
            if default:
                prompt_str = f"\n[{current}/{total}] {icon} {description} (current: {default}{'' if not ('{' in default and '}' in default) else ', content in curly braces is a dynamic placeholder, no need to fill manually'}): "
            else:
                prompt_str = f"\n[{current}/{total}] {icon} {description}: "

            # Use input()'s prompt parameter; Python protects this prompt from Backspace deletion
            try:
                result = input(prompt_str)
            except KeyboardInterrupt:
                raise
            except EOFError:
                result = ""

            # If no input and there's a default value, use the default
            if not result and default:
                result = str(default)

            # Apply validation rules
            if validation_rules:
                # Check required
                if validation_rules.get('required') and (not result or result.strip() == ''):
                    console.print(f"{ICONS['error']} This field cannot be empty")
                    continue

                # Check regex pattern
                pattern = validation_rules.get('pattern')
                if pattern and result:
                    import re
                    if not re.match(pattern, result):
                        error_msg = validation_rules.get('message', 'Input format does not meet requirements')
                        console.print(f"{ICONS['error']} {error_msg}")
                        continue

            console.print(f"[{COLORS['success']}]»[/] {result}\n")
            return result

    def _handle_int(self, description: str, default: Any, field_metadata: Dict[str, Any] = None, current: int = 1, total: int = 1) -> int:
        while True:
            try:
                # Get field icon (supports metadata specification)
                icon = self._get_field_icon(description, field_metadata) if field_metadata else ICONS['input']

                # Build complete prompt information
                if default is not None:
                    prompt_str = f"\n[{current}/{total}] {icon} {description} (current: {default}) (number): "
                else:
                    prompt_str = f"\n[{current}/{total}] {icon} {description} (number): "

                # Use input()'s prompt parameter
                try:
                    value = input(prompt_str)
                except KeyboardInterrupt:
                    raise
                except EOFError:
                    value = ""

                # If no input and there's a default value, use the default
                if not value and default is not None:
                    value = str(default)
                elif not value:
                    value = "0"

                result = int(value)
                console.print(f"[{COLORS['success']}]»[/] {result}\n")
                return result
            except ValueError:
                console.print(f"{ICONS['error']} Please enter a valid integer")
            except KeyboardInterrupt:
                raise

    def _handle_float(self, description: str, default: Any, field_metadata: Dict[str, Any] = None, current: int = 1, total: int = 1) -> float:
        while True:
            try:
                # Get field icon (supports metadata specification)
                icon = self._get_field_icon(description, field_metadata) if field_metadata else ICONS['input']

                # Build complete prompt information
                if default is not None:
                    prompt_str = f"\n[{current}/{total}] {icon} {description} (current: {default}) (number): "
                else:
                    prompt_str = f"\n[{current}/{total}] {icon} {description} (number): "

                # Use input()'s prompt parameter
                try:
                    value = input(prompt_str)
                except KeyboardInterrupt:
                    raise
                except EOFError:
                    value = ""

                # If no input and there's a default value, use the default
                if not value and default is not None:
                    value = str(default)
                elif not value:
                    value = "0.0"

                result = float(value)
                console.print(f"[{COLORS['success']}]»[/] {result}\n")
                return result
            except ValueError:
                console.print(f"{ICONS['error']} Please enter a valid number")
            except KeyboardInterrupt:
                raise

    def _handle_bool(self, description: str, default: Any, field_metadata: Dict[str, Any] = None, current: int = 1, total: int = 1) -> bool:
        # Get field icon (supports metadata specification)
        icon = self._get_field_icon(description, field_metadata) if field_metadata else ICONS['select']

        # Display progress information
        console.print(f"\n[{current}/{total}] {icon} {description}")

        result = Confirm.ask("", default=bool(default))
        result_text = "Yes" if result else "No"
        console.print(f"[{COLORS['success']}]»[/] Selected: {result_text}\n")
        return result

    def _handle_list(self, description: str, default: Any, field_metadata: Dict[str, Any] = None, current: int = 1, total: int = 1) -> List[str]:
        # Get field icon (supports metadata specification)
        icon = self._get_field_icon(description, field_metadata) if field_metadata else ICONS['list']

        # Display progress information
        console.print(f"\n[{current}/{total}] {icon} {description}")
        console.print("Enter each item and press Enter; enter an empty line to finish\n")

        items = []
        counter = 1

        while True:
            # Create list item input prompt
            prompt_str = f"  [{current}/{total}] [{counter}] Item: "
            
            try:
                item = input(prompt_str)
            except KeyboardInterrupt:
                raise
            except EOFError:
                item = ""
            if not item.strip():
                break
            items.append(item.strip())
            console.print(f"  [{COLORS['success']}]»[/] Added: {item.strip()}")
            counter += 1

        if items:
            console.print(f"\n{ICONS['list']} Added {len(items)} items\n")
        else:
            console.print(f"\n{ICONS['info']} No items added\n")

        return items if items else (default if default is not None else [])

    def _handle_dict(self, description: str, default: Any, field_metadata: Dict[str, Any] = None, current: int = 1, total: int = 1) -> Dict[str, str]:
        # Get field icon (supports metadata specification)
        icon = self._get_field_icon(description, field_metadata) if field_metadata else ICONS['dict']

        # Display progress information
        console.print(f"\n[{current}/{total}] {icon} {description}")

        # Add environment variable hints (if description contains 'env')
        if "env" in description.lower():
            console.print("Common environment variables:")
            console.print("  - MODEL_AGENT_API_KEY=your_api_key")
            console.print("  - DEBUG=true")
            console.print("  - LOG_LEVEL=info")

        console.print("Input format: KEY=VALUE")
        console.print("Commands: 'del KEY' to delete, 'list' to view, 'clear' to clear all, empty line to finish\n")

        result_dict = {}
        if isinstance(default, dict):
            result_dict.update(default)

        while True:
            # Create dictionary input prompt
            prompt_str = f"\n[{current}/{total}] {icon} Variable: "
            
            try:
                user_input = input(prompt_str)
            except KeyboardInterrupt:
                raise
            except EOFError:
                user_input = ""

            if not user_input.strip():
                break

            if user_input == "list":
                if result_dict:
                    console.print("\nCurrent variables:")
                    for key, value in result_dict.items():
                        console.print(f"  {key}={value}")
                else:
                    console.print("No variables set")
                continue

            if user_input == "clear":
                result_dict.clear()
                console.print("All variables cleared")
                continue

            if user_input.startswith("del "):
                key_to_delete = user_input[4:].strip()
                if key_to_delete in result_dict:
                    del result_dict[key_to_delete]
                    console.print(f"Deleted: {key_to_delete}")
                else:
                    console.print(f"Variable not found: {key_to_delete}")
                continue

            if "=" not in user_input:
                console.print("Invalid format, please use KEY=VALUE")
                continue

            key, value = user_input.split("=", 1)
            key = key.strip()
            value = value.strip()
            
            # Strip surrounding quotes (both single and double quotes)
            if len(value) >= 2:
                if (value[0] == '"' and value[-1] == '"') or (value[0] == "'" and value[-1] == "'"):
                    value = value[1:-1]

            if not key:
                console.print("Key name cannot be empty")
                continue

            if not key.replace("_", "").isalnum():
                console.print("Key name can only contain letters, numbers, and underscores")
                continue

            old_value = result_dict.get(key)
            result_dict[key] = value

            if old_value is not None:
                console.print(f"Updated: {key}={value} (previous: {old_value})")
            else:
                console.print(f"Added: {key}={value}")

        if result_dict:
            console.print(f"\n{ICONS['dict']} Configured {len(result_dict)} variables\n")
        else:
            console.print(f"\n{ICONS['info']} No variables configured\n")

        return result_dict if result_dict else (default if default is not None else {})

    def _show_welcome_panel(self, config_name: str, welcome_message: Optional[str] = None,
                           next_step_hint: Optional[str] = None):
        """Display welcome panel."""
        # Create title text with ASCII-safe decorators
        # Note: Avoid emojis in Panel titles as they cause alignment issues in some terminals
        # (e.g., iTerm2) due to inconsistent emoji width calculation between Rich and terminal
        title_text = Text()
        title_text.append(" ◆ ", style=f"bold {COLORS['primary']}")
        title_text.append(config_name, style=STYLES["title"])
        title_text.append(" ◆ ", style=f"bold {COLORS['primary']}")

        # Create content with visual hierarchy
        # Note: Avoid emojis in Panel content as they cause alignment issues in some terminals
        content = Text()

        # Use custom welcome message or default message
        if welcome_message:
            content.append("► ", style=f"bold {COLORS['success']}")
            content.append(f"{welcome_message}\n", style="bold white")
        else:
            content.append("► ", style=f"bold {COLORS['success']}")
            content.append("Welcome to AgentKit Configuration Wizard\n", style="bold white")
            content.append("\n  This wizard will help you configure your Agent application.\n", style=COLORS["description"])
            content.append("  Follow the prompts or press Enter to use default values.\n", style=COLORS["description"])

        # Add next step hint
        if next_step_hint:
            content.append(f"\n  {next_step_hint}\n", style=f"italic {COLORS['label']}")

        content.append("\n• ", style=f"dim {COLORS['warning']}")
        content.append("Press Ctrl+C at any time to exit configuration.", style="dim")

        # Create panel with enhanced styling
        panel = Panel(
            content,
            title=title_text,
            border_style=COLORS["primary"],
            box=box.ROUNDED,
            padding=(1, 2),
            expand=False
        )

        console.print(panel)
        console.print()

    def _show_progress(self, current: int, total: int, field_name: str, description: str):
        """Display progress indicator."""
        # Get field icon (supports metadata specification)
        icon = self._get_field_icon(field_name)

        # Create progress bar
        progress_width = 30
        filled_width = int((current / total) * progress_width)
        progress_bar = f"[{'█' * filled_width}{'░' * (progress_width - filled_width)}]"

        # Create progress information
        progress_text = Text()
        progress_text.append(f"{icon} ", style=STYLES["label"])
        progress_text.append(f"{description}", style="bold white")
        progress_text.append(f"  [{current}/{total}]\n", style=STYLES["description"])
        progress_text.append(f"    {progress_bar} {current/total*100:.0f}%", style=COLORS["label"])

        console.print(progress_text)
        console.print()

    def _show_progress_clean(self, current: int, total: int, field_name: str, description: str):
        """Display clean progress indicator (no repeated progress bar)."""
        # Get field icon (supports metadata specification)
        icon = self._get_field_icon(field_name)

        # Only show progress bar on first field or when field changes
        if current == 1 or current != getattr(self, '_last_progress', 0):
            # Create progress bar
            progress_width = 30
            filled_width = int((current / total) * progress_width)
            progress_bar = f"[{'█' * filled_width}{'░' * (progress_width - filled_width)}]"

            # Create progress information
            progress_text = Text()
            progress_text.append(f"{icon} ", style=STYLES["label"])
            progress_text.append(f"{description}", style="bold white")
            progress_text.append(f"  [{current}/{total}]\n", style=STYLES["description"])
            progress_text.append(f"    {progress_bar} {current/total*100:.0f}%", style=COLORS["label"])

            console.print(progress_text)
            console.print()

            # Record current progress
            self._last_progress = current

    def _get_field_icon(self, field_name: str, field_metadata: Dict[str, Any] = None) -> str:
        """Get corresponding icon based on field metadata or field name."""
        # Prioritize icon specified in metadata
        if field_metadata and "icon" in field_metadata:
            return field_metadata["icon"]

        # Fall back to hardcoded mapping (maintain backward compatibility)
        icon_map = {
            "agent_name": ICONS["agent"],
            "entry_point": ICONS["file"],
            "launch_type": ICONS["deploy"],
            "description": ICONS["description"],
            "language": ICONS["language"],
            "language_version": ICONS["language_version"],
            "dependencies_file": ICONS["package"],
            "entry_port": ICONS["port"],
        }
        return icon_map.get(field_name, ICONS["config"])

    def _show_completion_panel(self, config: Dict[str, Any], completion_message: Optional[str] = None,
                             next_action_hint: Optional[str] = None):
        """Display configuration completion panel."""
        # Create title text with ASCII-safe decorators (consistent with welcome panel)
        # Note: Avoid emojis in Panel titles as they cause alignment issues in some terminals
        title_text = Text()
        title_text.append(" ◆ ", style=f"bold {COLORS['success']}")
        title_text.append("Configuration Complete", style=STYLES["success"])
        title_text.append(" ◆ ", style=f"bold {COLORS['success']}")

        # Create content with visual hierarchy (consistent with welcome panel style)
        content = Text()

        # Success message
        if completion_message:
            content.append("► ", style=f"bold {COLORS['success']}")
            content.append(f"{completion_message}\n", style="bold white")
        else:
            content.append("► ", style=f"bold {COLORS['success']}")
            content.append("Configuration saved successfully!\n", style="bold white")

        # Configuration summary (compact format, no redundant header)
        content.append("\n")
        for key, value in config.items():
            if not key.startswith('_'):  # Skip internal fields
                formatted_key = self._format_field_name(key)
                if isinstance(value, type(MISSING)) or value is None:
                    formatted_value = "Not set"
                else:
                    # Truncate long values for display
                    formatted_value = str(value)
                    if len(formatted_value) > 50:
                        formatted_value = formatted_value[:47] + "..."
                content.append(f"  • {formatted_key}: ", style=COLORS["label"])
                content.append(f"{formatted_value}\n", style=STYLES["value"])

        # Next steps hint
        content.append("\n• ", style=f"dim {COLORS['primary']}")
        if next_action_hint:
            content.append(next_action_hint, style="dim")
        else:
            content.append("Run 'agentkit build' to build your application.", style="dim")

        # Create panel with consistent styling
        completion_panel = Panel(
            content,
            title=title_text,
            border_style=COLORS["success"],
            box=box.ROUNDED,
            padding=(1, 2),
            expand=False
        )

        console.print("\n")
        console.print(completion_panel)
        console.print()

    def _format_field_name(self, field_name: str) -> str:
        """Format field name for display."""
        name_map = {
            "agent_name": "Application Name",
            "entry_point": "Entry Point",
            "launch_type": "Launch Type",
            "description": "Description",
            "language": "Language",
            "language_version": "Language Version",
            "dependencies_file": "Dependencies File",
            "entry_port": "Port",
            "ve_cr_instance_name": "CR Instance Name",
            "ve_cr_namespace_name": "CR Namespace",
            "ve_cr_repo_name": "CR Repository",
        }
        return name_map.get(field_name, field_name.replace("_", " ").title())

auto_prompt = AutoPromptGenerator()

def generate_config_from_dataclass(dataclass_type: type, existing_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return auto_prompt.generate_config(dataclass_type, existing_config)


def create_common_config_interactively(existing_config: Optional[Dict[str, Any]] = None):
    """Interactively create CommonConfig (CLI layer specific).
    
    This function is responsible for creating CommonConfig objects through interactive prompts.
    It belongs to the CLI layer and should not exist in the core config layer.
    
    Args:
        existing_config: Existing configuration dictionary for prefilling
        
    Returns:
        CommonConfig: Created configuration object
        
    Example:
        >>> config = create_common_config_interactively({"agent_name": "my-agent"})
    """
    from agentkit.toolkit.config import CommonConfig
    
    existing = CommonConfig.from_dict(existing_config or {})
    config_dict = auto_prompt.generate_config(CommonConfig, existing.to_dict())
    return CommonConfig.from_dict(config_dict)