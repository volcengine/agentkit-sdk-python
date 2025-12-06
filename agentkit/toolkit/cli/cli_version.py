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

"""AgentKit CLI - Version command implementation."""

from pathlib import Path
from importlib.metadata import version as get_version, PackageNotFoundError
import sys
from rich.panel import Panel
from rich.console import Console

# Note: Avoid importing heavy packages at the top to keep CLI startup fast

# Python 3.11+ has tomllib, older versions need tomli
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None

console = Console()


def get_package_version() -> str:
    """Get package version from installed package or pyproject.toml."""
    # Try to get version from installed package
    try:
        return get_version("agentkit-sdk-python")
    except PackageNotFoundError:
        pass

    # Fallback: read from pyproject.toml using toml parser
    if tomllib is not None:
        try:
            # Find pyproject.toml in the package directory
            current_file = Path(__file__)
            # Go up from agentkit/toolkit/cli/cli.py to workspace root
            pyproject_path = current_file.parent.parent.parent.parent / "pyproject.toml"

            if pyproject_path.exists():
                with open(pyproject_path, "rb") as f:
                    data = tomllib.load(f)
                    return data.get("project", {}).get("version", "unknown")
        except Exception:
            pass

    # Last resort: parse pyproject.toml manually for version line
    try:
        current_file = Path(__file__)
        pyproject_path = current_file.parent.parent.parent.parent / "pyproject.toml"

        if pyproject_path.exists():
            with open(pyproject_path, "r") as f:
                for line in f:
                    if line.strip().startswith("version"):
                        # Parse line like: version = "0.0.7.34"
                        parts = line.split("=")
                        if len(parts) == 2:
                            version_str = parts[1].strip().strip('"').strip("'")
                            return version_str
    except Exception:
        pass

    return "unknown"


def version_command():
    """Show AgentKit version information."""
    pkg_version = get_package_version()
    console.print(
        Panel(
            f"[bold cyan]AgentKit SDK[/bold cyan]\n[green]Version: {pkg_version}[/green]",
            title="📦 Version Info",
            border_style="cyan",
        )
    )
