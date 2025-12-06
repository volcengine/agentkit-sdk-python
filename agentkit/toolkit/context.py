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
Execution context - provides thread-safe global state access.

Implemented using contextvars to support multi-threaded and async environments.
Primary purpose is to simplify Reporter passing throughout the call stack,
avoiding explicit parameter passing at every layer.

Design rationale:
- Avoids "reporter" parameter threading through dozens of function signatures
- Maintains clean separation between business logic and reporting concerns
- Enables flexible reporter implementations (console, silent, custom) without code changes

Usage example:
    # Set reporter at CLI entry point
    ExecutionContext.set_reporter(ConsoleReporter())

    # Use directly in low-level code without parameter passing
    ExecutionContext.info("Processing...")
    ExecutionContext.success("Done!")

    # Or retrieve reporter instance for custom handling
    reporter = ExecutionContext.get_reporter()
    reporter.info("Processing...")
"""

from contextvars import ContextVar
from typing import Optional, Dict, Any

from .reporter import Reporter, SilentReporter


class ExecutionContext:
    """
    Execution context manager providing thread/coroutine-safe state management.

    Primary responsibilities:
    1. Global Reporter access - eliminates parameter threading through call stack
    2. Extensible context data storage - supports arbitrary execution state

    Key features:
    - Thread-safe: Uses contextvars.ContextVar for proper isolation
    - Async-safe: Works correctly with asyncio and other async frameworks
    - Graceful defaults: Returns SilentReporter when none is set
    - Convenience methods: Provides info/success/error/warning shortcuts

    Design principle: Each execution context (thread/coroutine) has its own
    isolated state, preventing cross-contamination in concurrent scenarios.
    """

    # ContextVar ensures each thread/coroutine has isolated reporter state
    _reporter: ContextVar[Optional[Reporter]] = ContextVar("reporter", default=None)

    # Extensible context data storage for arbitrary execution state
    _data: ContextVar[Dict[str, Any]] = ContextVar("context_data", default=None)

    @classmethod
    def set_reporter(cls, reporter: Reporter) -> None:
        """
        Set the Reporter for the current execution context.

        Args:
            reporter: Reporter instance to use for all output in this context

        Example:
            ExecutionContext.set_reporter(ConsoleReporter())
        """
        cls._reporter.set(reporter)

    @classmethod
    def get_reporter(cls) -> Reporter:
        """
        Get the Reporter for the current execution context.

        Returns:
            Reporter instance. If none is set, returns SilentReporter to prevent
            AttributeError in code that doesn't explicitly set a reporter.

        Example:
            reporter = ExecutionContext.get_reporter()
            reporter.info("Processing...")
        """
        reporter = cls._reporter.get()
        return reporter if reporter is not None else SilentReporter()

    @classmethod
    def has_reporter(cls) -> bool:
        """
        Check if a Reporter has been explicitly set for this context.

        Returns:
            True if a Reporter is set, False if using default SilentReporter.
        """
        return cls._reporter.get() is not None

    @classmethod
    def info(cls, message: str, **kwargs) -> None:
        """
        Output an informational message using the current Reporter.

        Args:
            message: Message content
            **kwargs: Additional parameters passed to reporter

        Example:
            ExecutionContext.info("Building image...")
        """
        cls.get_reporter().info(message, **kwargs)

    @classmethod
    def success(cls, message: str, **kwargs) -> None:
        """
        Output a success message using the current Reporter.

        Args:
            message: Message content
            **kwargs: Additional parameters passed to reporter

        Example:
            ExecutionContext.success("Build completed!")
        """
        cls.get_reporter().success(message, **kwargs)

    @classmethod
    def error(cls, message: str, **kwargs) -> None:
        """
        Output an error message using the current Reporter.

        Args:
            message: Message content
            **kwargs: Additional parameters passed to reporter

        Example:
            ExecutionContext.error("Build failed!")
        """
        cls.get_reporter().error(message, **kwargs)

    @classmethod
    def warning(cls, message: str, **kwargs) -> None:
        """
        Output a warning message using the current Reporter.

        Args:
            message: Message content
            **kwargs: Additional parameters passed to reporter

        Example:
            ExecutionContext.warning("Deprecated feature used")
        """
        cls.get_reporter().warning(message, **kwargs)

    @classmethod
    def set_data(cls, key: str, value: Any) -> None:
        """
        Set context data for the current execution context.

        Lazily initializes the data dictionary on first use to avoid unnecessary
        allocations when only Reporter functionality is needed.

        Args:
            key: Data key
            value: Data value

        Example:
            ExecutionContext.set_data("build_id", "12345")
        """
        data = cls._data.get()
        if data is None:
            # Lazy initialization: only create dict when data is actually stored
            data = {}
            cls._data.set(data)
        data[key] = value

    @classmethod
    def get_data(cls, key: str, default: Any = None) -> Any:
        """
        Get context data from the current execution context.

        Args:
            key: Data key
            default: Default value if key is not found

        Returns:
            The value associated with the key, or default if not found.

        Example:
            build_id = ExecutionContext.get_data("build_id")
        """
        data = cls._data.get()
        if data is None:
            return default
        return data.get(key, default)

    @classmethod
    def clear_data(cls) -> None:
        """
        Clear all context data for the current execution context.

        Example:
            ExecutionContext.clear_data()
        """
        cls._data.set(None)

    @classmethod
    def reset(cls) -> None:
        """
        Reset the entire execution context.

        Primarily used in test teardown to ensure clean state between test cases.
        Important: Each test should have isolated context to prevent state leakage.

        Example:
            def tearDown(self):
                ExecutionContext.reset()
        """
        cls._reporter.set(None)
        cls._data.set(None)


# Convenience alias for shorter usage: context.info() instead of ExecutionContext.info()
context = ExecutionContext
