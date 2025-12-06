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

"""Unified logging configuration with multiple formats, outputs, and env-based control."""

import logging
import os
import sys
import json
from typing import Optional, Dict
from datetime import datetime
from pathlib import Path
import contextvars

# Context for request/session/user tracing
request_id_var = contextvars.ContextVar("request_id", default=None)
session_id_var = contextvars.ContextVar("session_id", default=None)
user_id_var = contextvars.ContextVar("user_id", default=None)

# Log format constants
LOG_FORMAT_SIMPLE = "simple"
LOG_FORMAT_DETAILED = "detailed"
LOG_FORMAT_JSON = "json"

# Defaults
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FORMAT = LOG_FORMAT_SIMPLE
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# CLI defaults
DEFAULT_CLI_CONSOLE_ENABLED = False  # Console logging disabled by default
DEFAULT_CLI_FILE_ENABLED = False  # File logging disabled by default
DEFAULT_CLI_CONSOLE_LEVEL = "INFO"  # Default console level
DEFAULT_CLI_FILE_LEVEL = "INFO"  # Default file level

# Environment variables
ENV_LOG_LEVEL = "AGENTKIT_LOG_LEVEL"  # Applies to both console and file
ENV_LOG_FORMAT = "AGENTKIT_LOG_FORMAT"
ENV_LOG_FILE = "AGENTKIT_LOG_FILE"  # Log file path
ENV_LOG_CONSOLE = "AGENTKIT_LOG_CONSOLE"  # Enable console output
ENV_LOG_JSON_INDENT = "AGENTKIT_LOG_JSON_INDENT"
# Additional variables to control console and file separately
ENV_CONSOLE_LOG_LEVEL = "AGENTKIT_CONSOLE_LOG_LEVEL"  # Console log level
ENV_FILE_LOG_LEVEL = "AGENTKIT_FILE_LOG_LEVEL"  # File log level
ENV_FILE_ENABLED = "AGENTKIT_FILE_ENABLED"  # Enable file logging


class ContextFilter(logging.Filter):
    """Inject context fields into records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Attach context to record."""
        record.request_id = request_id_var.get()
        record.session_id = session_id_var.get()
        record.user_id = user_id_var.get()
        return True


class JSONFormatter(logging.Formatter):
    """JSON formatter."""

    def __init__(self, indent: Optional[int] = None):
        super().__init__()
        self.indent = indent

    def format(self, record: logging.LogRecord) -> str:
        """Format record as JSON string."""
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Context
        if hasattr(record, "request_id") and record.request_id:
            log_data["request_id"] = record.request_id
        if hasattr(record, "session_id") and record.session_id:
            log_data["session_id"] = record.session_id
        if hasattr(record, "user_id") and record.user_id:
            log_data["user_id"] = record.user_id

        # Extra fields
        if hasattr(record, "extra") and record.extra:
            log_data.update(record.extra)

        # Exception
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False, indent=self.indent)


def get_log_level_from_env() -> str:
    """Get log level from env."""
    return os.getenv(ENV_LOG_LEVEL, DEFAULT_LOG_LEVEL).upper()


def get_log_format_from_env() -> str:
    """Get log format from env."""
    return os.getenv(ENV_LOG_FORMAT, DEFAULT_LOG_FORMAT).lower()


def get_log_file_from_env() -> Optional[str]:
    """Get log file path from env."""
    return os.getenv(ENV_LOG_FILE)


def get_console_enabled_from_env() -> bool:
    """Get console toggle from env."""
    console_enabled = os.getenv(ENV_LOG_CONSOLE, "true").lower()
    return console_enabled in ("true", "1", "yes", "on")


def create_formatter(format_type: str = DEFAULT_LOG_FORMAT) -> logging.Formatter:
    """Create formatter (simple/detailed/json)."""
    if format_type == LOG_FORMAT_JSON:
        indent = None
        if os.getenv(ENV_LOG_JSON_INDENT):
            try:
                indent = int(os.getenv(ENV_LOG_JSON_INDENT))
            except ValueError:
                pass
        return JSONFormatter(indent=indent)

    elif format_type == LOG_FORMAT_DETAILED:
        fmt = (
            "[%(asctime)s] [%(levelname)s] [%(name)s:%(funcName)s:%(lineno)d] "
            "%(message)s"
        )
        if request_id_var.get():
            fmt = f"[%(request_id)s] {fmt}"
        return logging.Formatter(fmt, datefmt=DEFAULT_DATE_FORMAT)

    else:  # simple format
        fmt = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
        return logging.Formatter(fmt, datefmt=DEFAULT_DATE_FORMAT)


def setup_logging(
    level: Optional[str] = None,
    format_type: Optional[str] = None,
    log_file: Optional[str] = None,
    console_enabled: Optional[bool] = None,
    force: bool = False,
) -> None:
    """Configure global logging."""
    # Resolve config (args override env)
    log_level = (level or get_log_level_from_env()).upper()
    log_format = (format_type or get_log_format_from_env()).lower()
    log_file_path = log_file or get_log_file_from_env()
    console_out = (
        console_enabled
        if console_enabled is not None
        else get_console_enabled_from_env()
    )

    # Validate level
    numeric_level = getattr(logging, log_level, None)
    if not isinstance(numeric_level, int):
        print(f"Warning: Invalid log level '{log_level}', using INFO", file=sys.stderr)
        numeric_level = logging.INFO

    # Root logger
    root_logger = logging.getLogger()

    # Skip if already configured and not forcing
    if root_logger.handlers and not force:
        return

    # Clear existing handlers if forcing
    if force:
        root_logger.handlers.clear()

    # Set level
    root_logger.setLevel(numeric_level)

    # Formatter
    formatter = create_formatter(log_format)

    # Context filter
    context_filter = ContextFilter()

    # Console handler
    if console_out:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(formatter)
        console_handler.addFilter(context_filter)
        root_logger.addHandler(console_handler)

    # File handler
    if log_file_path:
        try:
            # Ensure log directory exists
            log_dir = Path(log_file_path).parent
            log_dir.mkdir(parents=True, exist_ok=True)

            file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
            file_handler.setLevel(numeric_level)
            file_handler.setFormatter(formatter)
            file_handler.addFilter(context_filter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            print(f"Warning: Failed to create log file handler: {e}", file=sys.stderr)


def get_logger(name: str) -> logging.Logger:
    """Get a logger namespaced under 'agentkit'."""
    # Ensure namespaced under 'agentkit'
    if not name.startswith("agentkit"):
        name = f"agentkit.{name}"

    return logging.getLogger(name)


def set_context(
    request_id: Optional[str] = None,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> None:
    """Set request/session/user context."""
    if request_id is not None:
        request_id_var.set(request_id)
    if session_id is not None:
        session_id_var.set(session_id)
    if user_id is not None:
        user_id_var.set(user_id)


def clear_context() -> None:
    """Clear logging context."""
    request_id_var.set(None)
    session_id_var.set(None)
    user_id_var.set(None)


def get_context() -> Dict[str, Optional[str]]:
    """Return current logging context as dict."""
    return {
        "request_id": request_id_var.get(),
        "session_id": session_id_var.get(),
        "user_id": user_id_var.get(),
    }


# SDK usage
def setup_sdk_logging(level: str = "INFO") -> None:
    """Configure logging for SDK/library usage."""
    setup_logging(level=level, format_type=LOG_FORMAT_SIMPLE, console_enabled=False)


def _setup_dual_level_logging(
    console_enabled: bool = False,
    console_level: str = "INFO",
    file_enabled: bool = True,
    file_level: str = "INFO",
    log_file_path: Optional[str] = None,
    format_type: str = LOG_FORMAT_SIMPLE,
    force: bool = False,
) -> None:
    """Configure logging with independent console/file levels."""
    # Root logger
    root_logger = logging.getLogger()

    # Skip if already configured and not forcing
    if root_logger.handlers and not force:
        return

    # Clear existing handlers if forcing
    if force:
        root_logger.handlers.clear()

    if not console_enabled and not file_enabled:
        root_logger.addHandler(logging.NullHandler())
        root_logger.setLevel(logging.CRITICAL)
        return

    # Root level = min(handler levels)
    levels = []
    if console_enabled:
        levels.append(getattr(logging, console_level, logging.INFO))
    if file_enabled:
        levels.append(getattr(logging, file_level, logging.INFO))

    if levels:
        root_logger.setLevel(min(levels))
    else:
        root_logger.setLevel(logging.INFO)

    # Create formatter
    formatter = create_formatter(format_type)

    # Context filter
    context_filter = ContextFilter()

    # Console handler
    if console_enabled:
        console_handler = logging.StreamHandler(sys.stderr)
        console_numeric_level = getattr(logging, console_level, None)
        if not isinstance(console_numeric_level, int):
            print(
                f"Warning: Invalid console log level '{console_level}', using INFO",
                file=sys.stderr,
            )
            console_numeric_level = logging.INFO
        console_handler.setLevel(console_numeric_level)
        console_handler.setFormatter(formatter)
        console_handler.addFilter(context_filter)
        root_logger.addHandler(console_handler)

    # File handler
    if file_enabled and log_file_path:
        try:
            # Ensure log directory exists
            log_dir = Path(log_file_path).parent
            log_dir.mkdir(parents=True, exist_ok=True)

            file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
            file_numeric_level = getattr(logging, file_level, None)
            if not isinstance(file_numeric_level, int):
                print(
                    f"Warning: Invalid file log level '{file_level}', using INFO",
                    file=sys.stderr,
                )
                file_numeric_level = logging.INFO
            file_handler.setLevel(file_numeric_level)
            file_handler.setFormatter(formatter)
            file_handler.addFilter(context_filter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            print(f"Warning: Failed to create log file handler: {e}", file=sys.stderr)


def setup_cli_logging(
    verbose: bool = False,
    quiet: bool = False,
    console_enabled: Optional[bool] = None,
    file_enabled: Optional[bool] = None,
    console_level: Optional[str] = None,
    file_level: Optional[str] = None,
    log_file_path: Optional[str] = None,
    force: bool = False,
) -> None:
    """Configure logging for CLI.

    Default (no args/env): console off, file off. If file on: INFO to .agentkit/logs/agentkit-YYYYMMDD.log.
    """
    # Shortcut flags
    if quiet:
        # Silent mode: console off; enable file, level ERROR
        console_enabled = False if console_enabled is None else console_enabled
        file_enabled = True if file_enabled is None else file_enabled
        file_level = file_level or "ERROR"
        console_level = console_level or "ERROR"
    elif verbose:
        # Verbose mode: enable console and file, level DEBUG
        console_enabled = True if console_enabled is None else console_enabled
        file_enabled = True if file_enabled is None else file_enabled
        console_level = console_level or "DEBUG"
        file_level = file_level or "DEBUG"

    # Env overrides
    def get_bool_env(env_name: str, default: bool) -> bool:
        """Read boolean env var."""
        value = os.getenv(env_name)
        if value is None:
            return default
        return value.lower() in ("true", "1", "yes", "on")

    # Console toggle (args > env > default)
    if console_enabled is None:
        console_enabled = get_bool_env(ENV_LOG_CONSOLE, DEFAULT_CLI_CONSOLE_ENABLED)

    # File toggle (args > env > default)
    if file_enabled is None:
        file_enabled = get_bool_env(ENV_FILE_ENABLED, DEFAULT_CLI_FILE_ENABLED)

    # Console level (args > CONSOLE_LOG_LEVEL > LOG_LEVEL > default)
    if console_level is None:
        console_level = (
            os.getenv(ENV_CONSOLE_LOG_LEVEL)
            or os.getenv(ENV_LOG_LEVEL)
            or DEFAULT_CLI_CONSOLE_LEVEL
        )

    # File level (args > FILE_LOG_LEVEL > LOG_LEVEL > default)
    if file_level is None:
        file_level = (
            os.getenv(ENV_FILE_LOG_LEVEL)
            or os.getenv(ENV_LOG_LEVEL)
            or DEFAULT_CLI_FILE_LEVEL
        )

    # Log file path
    if log_file_path is None:
        log_file_path = os.getenv(ENV_LOG_FILE)

    # Default log file path
    if file_enabled and log_file_path is None:
        # .agentkit/logs under current working directory
        log_dir = os.path.join(os.getcwd(), ".agentkit", "logs")
        # Date-based name
        date_str = datetime.now().strftime("%Y%m%d")
        log_file_path = os.path.join(log_dir, f"agentkit-{date_str}.log")

    # Apply
    _setup_dual_level_logging(
        console_enabled=console_enabled,
        console_level=console_level.upper(),
        file_enabled=file_enabled,
        file_level=file_level.upper(),
        log_file_path=log_file_path,
        format_type=LOG_FORMAT_SIMPLE,
        force=force,
    )


def setup_server_logging(
    level: str = "INFO", log_file: Optional[str] = None, json_format: bool = False
) -> None:
    """Configure logging for server apps."""
    format_type = LOG_FORMAT_JSON if json_format else LOG_FORMAT_DETAILED

    setup_logging(
        level=level, format_type=format_type, log_file=log_file, console_enabled=True
    )
