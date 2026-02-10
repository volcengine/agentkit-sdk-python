# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
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
