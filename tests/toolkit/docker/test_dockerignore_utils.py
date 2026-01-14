from pathlib import Path


def test_create_dockerignore_file_includes_common_defaults(tmp_path: Path):
    from agentkit.toolkit.docker.utils import create_dockerignore_file

    created = create_dockerignore_file(str(tmp_path))
    assert created is True

    content = (tmp_path / ".dockerignore").read_text(encoding="utf-8")

    expected_entries = [
        ".pytest_cache/",
        ".mypy_cache/",
        ".ruff_cache/",
        ".tox/",
        ".nox/",
        ".coverage",
        "coverage.xml",
        "htmlcov/",
        "*.log",
        "*.tmp",
        "*.swp",
        "*.swo",
        "dist/",
        "build/",
        "*.egg-info/",
        ".eggs/",
        ".DS_Store",
        "Thumbs.db",
        ".env",
        ".env.*",
    ]

    for entry in expected_entries:
        assert f"\n{entry}\n" in f"\n{content}\n"
