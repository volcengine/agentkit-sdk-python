from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 compatibility
    import tomli as tomllib

from agentkit.version import VERSION


def test_package_and_project_versions_match_next_header_capable_release():
    project = tomllib.loads(
        (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf8")
    )

    assert VERSION == "0.8.8"
    assert project["project"]["version"] == VERSION
