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
CLI Reporter Implementation

Console output implementation based on Rich library, providing:
- Colored output
- Progress bar
- User interaction
"""

from typing import Optional, List
from contextlib import contextmanager
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TaskProgressColumn,
    TimeElapsedColumn,
)

from agentkit.toolkit.reporter import Reporter, TaskHandle


class ConsoleReporter(Reporter):
    """
    Console reporter for CLI usage.

    Provides beautiful console output using Rich library:
    - info: Cyan text
    - success: Green text + ✅
    - warning: Yellow text + ⚠️
    - error: Red text + ❌
    - progress: Auto-managed progress bar
    - confirm: Interactive confirmation

    Usage example:
        reporter = ConsoleReporter()
        reporter.info("Starting build...")
        reporter.progress("Building", 50, 100)
        reporter.success("Build successful!")

        if reporter.confirm("Continue?"):
            # User chose yes
    """

    def __init__(self):
        """Initialize console reporter."""
        self.console = Console()
        self._progress: Optional[Progress] = None
        self._task_id: Optional[int] = None

    def info(self, message: str, **kwargs):
        """Output cyan info message."""
        self.console.print(f"[cyan]{message}[/cyan]")

    def success(self, message: str, **kwargs):
        """Output green success message (with ✅)."""
        self.console.print(f"[green]✅ {message}[/green]")

    def warning(self, message: str, **kwargs):
        """Output yellow warning message (with ⚠️)."""
        self.console.print(f"[yellow]⚠️  {message}[/yellow]")

    def error(self, message: str, **kwargs):
        """Output red error message (with ❌)."""
        self.console.print(f"[red]❌ {message}[/red]")

    def progress(self, message: str, current: int, total: int = 100, **kwargs):
        """
        Report progress (auto-managed Rich Progress bar).

        How it works:
        1. Create progress bar on first call
        2. Update progress on subsequent calls
        3. Auto-stop and cleanup when reaching 100%

        This way Builder/Runner doesn't need to manually manage progress bar lifecycle.
        """
        # First call: create progress bar
        if self._progress is None and current < total:
            self._progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=self.console,
            )
            self._progress.start()
            self._task_id = self._progress.add_task(message, total=total)

        # Update progress
        if self._progress and self._task_id is not None:
            self._progress.update(self._task_id, completed=current, description=message)

        # Reach 100%: stop and cleanup
        if current >= total and self._progress:
            self._progress.stop()
            self._progress = None
            self._task_id = None

    def confirm(self, message: str, default: bool = False, **kwargs) -> bool:
        """
        Request user confirmation (interactive).

        Args:
            message: Confirmation message
            default: Default value (when user presses Enter)

        Returns:
            User's choice

        Example:
            Confirm cleanup? (Y/n):   # default=True
            Confirm cleanup? (y/N):   # default=False
        """
        # Display message
        self.console.print(f"\n[yellow]{message}[/yellow]")

        # Prompt
        default_str = "Y/n" if default else "y/N"
        user_input = input(f"Confirm? ({default_str}): ").strip().lower()

        # Parse input
        if not user_input:
            return default

        return user_input in ["y", "yes"]

    @contextmanager
    def long_task(self, description: str, total: float = 100):
        """
        Context manager for long-running tasks.

        Display progress bar using Rich Progress.

        Example:
            with reporter.long_task("Waiting for build to complete", total=600) as task:
                for i in range(600):
                    task.update(description=f"In progress {i}/600", completed=i)
                    time.sleep(1)
        """
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=self.console,
        )

        with progress:
            task_id = progress.add_task(description, total=total)
            yield _RichTaskHandle(progress, task_id)

    def show_logs(self, title: str, lines: List[str], max_lines: int = 100):
        """
        Display log content.

        Format and output logs with line numbers and borders.
        """
        self.console.print("\n" + "=" * 80)
        self.console.print(f"[bold red]{title}[/bold red]")
        self.console.print("=" * 80)

        for i, line in enumerate(lines[:max_lines], 1):
            self.console.print(f"{i:3d}: {line.rstrip()}")

        if len(lines) > max_lines:
            self.console.print(
                f"\n[yellow]... ({len(lines) - max_lines} more lines)[/yellow]"
            )

        self.console.print("=" * 80 + "\n")

    def __del__(self):
        """Ensure progress bar is stopped on destruction."""
        if self._progress:
            try:
                self._progress.stop()
            except Exception:
                pass


class _RichTaskHandle(TaskHandle):
    """Task handle for Rich progress bar."""

    def __init__(self, progress: Progress, task_id):
        self._progress = progress
        self._task_id = task_id

    def update(
        self, description: Optional[str] = None, completed: Optional[float] = None
    ):
        """Update task progress."""
        kwargs = {}
        if description is not None:
            kwargs["description"] = description
        if completed is not None:
            kwargs["completed"] = completed
        self._progress.update(self._task_id, **kwargs)


__all__ = ["ConsoleReporter"]
