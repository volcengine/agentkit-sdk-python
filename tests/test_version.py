from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 compatibility
    import tomli as tomllib

from agentkit.version import VERSION


def test_package_and_project_versions_match():
    project = tomllib.loads(
        (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf8")
    )

    # 发布版本会随上游前进，约束两处声明一致，而不是将后续版本锁回旧发布号。
    assert project["project"]["version"] == VERSION
