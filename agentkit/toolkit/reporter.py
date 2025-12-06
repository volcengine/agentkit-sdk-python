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

"""
Reporter interface - UI abstraction layer.

Reporter decouples Builder/Runner from UI implementation details.

Design Problem Solved:
- Previously: Builder/Runner had hardcoded console.print() calls
- Issue: Could not be used in SDK without unwanted console output
- Issue: Difficult to test

Current Solution:
- Builder/Runner depends on abstract Reporter interface
- CLI uses ConsoleReporter (Rich output)
- SDK uses SilentReporter (silent mode)
- Tests use MockReporter
"""

from abc import ABC, abstractmethod
from typing import Optional, List
from contextlib import contextmanager
import logging


class TaskHandle(ABC):
    """
    Abstract interface for long-running task progress tracking.

    Returned by Reporter.long_task() to allow callers to update progress
    and status information during long operations (e.g., build, deployment).
    """

    @abstractmethod
    def update(
        self, description: Optional[str] = None, completed: Optional[float] = None
    ):
        """
        Update task progress and description.

        Args:
            description: Updated task description (optional)
            completed: Completed progress value (optional)
        """
        pass


class Reporter(ABC):
    """
    Abstract interface for progress and message reporting.

    Builder/Runner components report through this interface:
    - Informational messages
    - Progress updates
    - User interactions

    Different implementations serve different contexts:
    - ConsoleReporter: Output to console (CLI)
    - SilentReporter: Silent mode (SDK)
    - LoggingReporter: Output to Python logging
    - MockReporter: For testing
    """

    @abstractmethod
    def info(self, message: str, **kwargs):
        """
        Report an informational message.

        Args:
            message: Message content
            **kwargs: Additional parameters (implementation-specific)
        """
        pass

    @abstractmethod
    def success(self, message: str, **kwargs):
        """
        Report a success message.

        Args:
            message: Message content
            **kwargs: Additional parameters
        """
        pass

    @abstractmethod
    def warning(self, message: str, **kwargs):
        """
        Report a warning message.

        Args:
            message: Message content
            **kwargs: Additional parameters
        """
        pass

    @abstractmethod
    def error(self, message: str, **kwargs):
        """
        Report an error message.

        Args:
            message: Message content
            **kwargs: Additional parameters
        """
        pass

    @abstractmethod
    def progress(self, message: str, current: int, total: int = 100, **kwargs):
        """
        Report progress with percentage calculation.

        Args:
            message: Progress description
            current: Current progress value
            total: Total progress value (default: 100)
            **kwargs: Additional parameters

        Example:
            reporter.progress("Downloading", 50, 100)  # 50%
            reporter.progress("Waiting", 30, 100)  # 30%
        """
        pass

    @abstractmethod
    def confirm(self, message: str, default: bool = False, **kwargs) -> bool:
        """
        Request user confirmation.

        Args:
            message: Confirmation prompt
            default: Default value if user presses Enter without input
            **kwargs: Additional parameters

        Returns:
            User's choice (True/False)

        Example:
            if reporter.confirm("Continue?", default=True):
                # User confirmed

        Note:
            - CLI implementations wait for user input
            - Silent implementations return default immediately
        """
        pass

    @contextmanager
    @abstractmethod
    def long_task(self, description: str, total: float = 100):
        """
        Context manager for long-running task progress tracking.

        Displays progress for operations that take significant time
        (e.g., build, deployment, download).

        Args:
            description: Task description
            total: Total progress value (used for percentage calculation)

        Yields:
            TaskHandle: Handle to update progress during execution

        Example:
            with reporter.long_task("Building image", total=600) as task:
                while not_finished:
                    status = check_status()
                    task.update(description=f"Status: {status}", completed=elapsed_time)
                    time.sleep(1)

        Note:
            - CLI implementations display progress bar
            - Silent implementations produce no output
        """
        pass

    @abstractmethod
    def show_logs(self, title: str, lines: List[str], max_lines: int = 100):
        """
        Display multi-line log content.

        Used to show build logs, error logs, and other multi-line text output.

        Args:
            title: Log section title
            lines: List of log lines
            max_lines: Maximum lines to display (excess lines are truncated with notice)

        Example:
            with open("build.log") as f:
                lines = f.readlines()
            reporter.show_logs("Build Log", lines, max_lines=100)

        Note:
            - CLI implementations format output to console
            - Silent implementations produce no output
        """
        pass


class _SilentTaskHandle(TaskHandle):
    """Silent task handle that produces no output."""

    def update(
        self, description: Optional[str] = None, completed: Optional[float] = None
    ):
        """No-op: silent mode produces no output."""
        pass


class SilentReporter(Reporter):
    """
    Silent reporter implementation for SDK usage.

    All methods are no-ops. This is the default Reporter for Builder/Runner
    components when used in SDK mode (non-interactive). The confirm() method
    automatically returns the default value without user interaction.
    """

    def info(self, message: str, **kwargs):
        """No-op: silent mode produces no output."""
        pass

    def success(self, message: str, **kwargs):
        """No-op: silent mode produces no output."""
        pass

    def warning(self, message: str, **kwargs):
        """No-op: silent mode produces no output."""
        pass

    def error(self, message: str, **kwargs):
        """No-op: silent mode produces no output."""
        pass

    def progress(self, message: str, current: int, total: int = 100, **kwargs):
        """No-op: silent mode produces no output."""
        pass

    def confirm(self, message: str, default: bool = False, **kwargs) -> bool:
        """Return default value without user interaction (non-interactive mode)."""
        return default

    @contextmanager
    def long_task(self, description: str, total: float = 100):
        """Yield a silent task handle that produces no output."""
        yield _SilentTaskHandle()

    def show_logs(self, title: str, lines: List[str], max_lines: int = 100):
        """No-op: silent mode produces no output."""
        pass


class _LoggingTaskHandle(TaskHandle):
    """Task handle that logs progress to Python logging system."""

    def __init__(self, logger: logging.Logger, description: str, total: float):
        self.logger = logger
        self.description = description
        self.total = total

    def update(
        self, description: Optional[str] = None, completed: Optional[float] = None
    ):
        """Log progress update with percentage calculation."""
        if description:
            self.description = description
        if completed is not None:
            percentage = int((completed / self.total) * 100) if self.total > 0 else 0
            self.logger.info(f"{self.description} ({percentage}%)")


class LoggingReporter(Reporter):
    """
    Reporter implementation that outputs to Python logging system.

    All messages are logged using the standard logging module. This is suitable
    for server-side scenarios, debugging, and environments where structured
    logging is preferred over interactive console output.

    Example:
        reporter = LoggingReporter(logger=my_logger)
        reporter.info("Starting build")  # Logs to configured logger
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize logging reporter.

        Args:
            logger: Logger instance. If None, uses the module's default logger.
        """
        self.logger = logger or logging.getLogger(__name__)

    def info(self, message: str, **kwargs):
        """Log message at INFO level."""
        self.logger.info(message)

    def success(self, message: str, **kwargs):
        """Log success message at INFO level with success indicator."""
        self.logger.info(f"✓ {message}")

    def warning(self, message: str, **kwargs):
        """Log message at WARNING level."""
        self.logger.warning(message)

    def error(self, message: str, **kwargs):
        """Log message at ERROR level."""
        self.logger.error(message)

    def progress(self, message: str, current: int, total: int = 100, **kwargs):
        """Log progress with percentage calculation at INFO level."""
        percentage = int((current / total) * 100) if total > 0 else 0
        self.logger.info(f"{message} ({percentage}%)")

    def confirm(self, message: str, default: bool = False, **kwargs) -> bool:
        """
        Log confirmation request and return default value.

        In logging mode, true user interaction is not possible, so the default
        value is returned automatically. The request is logged for audit purposes.
        """
        self.logger.warning(f"Auto-confirm: {message} -> {default}")
        return default

    @contextmanager
    def long_task(self, description: str, total: float = 100):
        """Log long-running task progress."""
        self.logger.info(f"Task started: {description}")
        yield _LoggingTaskHandle(self.logger, description, total)
        self.logger.info(f"Task completed: {description}")

    def show_logs(self, title: str, lines: List[str], max_lines: int = 100):
        """Log multi-line content with line numbers and truncation notice."""
        self.logger.info(f"=== {title} ===")
        for i, line in enumerate(lines[:max_lines], 1):
            self.logger.info(f"{i:3d}: {line.rstrip()}")
        if len(lines) > max_lines:
            self.logger.info(f"... ({len(lines) - max_lines} more lines)")


# Public API
__all__ = [
    "TaskHandle",
    "Reporter",
    "SilentReporter",
    "LoggingReporter",
]
