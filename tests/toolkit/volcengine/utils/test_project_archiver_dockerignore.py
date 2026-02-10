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

import tarfile
from pathlib import Path

from agentkit.toolkit.volcengine.utils.project_archiver import create_project_archive


def _tar_members(archive_path: str) -> set[str]:
    with tarfile.open(archive_path, "r:gz") as tar:
        return {m.name for m in tar.getmembers() if m.isfile()}


def test_project_archive_respects_dockerignore_excludes(tmp_path: Path):
    src = tmp_path / "src"
    out = tmp_path / "out"
    src.mkdir()
    out.mkdir()

    (src / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (src / "notes.log").write_text("log\n", encoding="utf-8")

    (src / "dist").mkdir()
    (src / "dist" / "bundle.js").write_text("bundle\n", encoding="utf-8")

    (src / ".venv").mkdir()
    (src / ".venv" / "pyvenv.cfg").write_text("cfg\n", encoding="utf-8")

    (src / ".dockerignore").write_text(
        "dist/\n*.log\n.venv/\n",
        encoding="utf-8",
    )

    archive_path = create_project_archive(
        source_dir=str(src),
        output_dir=str(out),
        archive_name="proj",
    )

    members = _tar_members(archive_path)
    assert "app.py" in members
    assert "notes.log" not in members
    assert "dist/bundle.js" not in members
    assert ".venv/pyvenv.cfg" not in members


def test_project_archive_dockerignore_negation(tmp_path: Path):
    src = tmp_path / "src"
    out = tmp_path / "out"
    src.mkdir()
    out.mkdir()

    (src / "data").mkdir()
    (src / "data" / "keep.json").write_text("{}\n", encoding="utf-8")
    (src / "data" / "drop.json").write_text("{}\n", encoding="utf-8")
    (src / "data" / "keep.txt").write_text("ok\n", encoding="utf-8")

    (src / ".dockerignore").write_text(
        "data/*.json\n!data/keep.json\n",
        encoding="utf-8",
    )

    archive_path = create_project_archive(
        source_dir=str(src),
        output_dir=str(out),
        archive_name="proj",
    )

    members = _tar_members(archive_path)
    assert "data/keep.json" in members
    assert "data/drop.json" not in members
    assert "data/keep.txt" in members


def test_project_archive_dockerignore_anchored_directory(tmp_path: Path):
    src = tmp_path / "src"
    out = tmp_path / "out"
    src.mkdir()
    out.mkdir()

    (src / "dist").mkdir()
    (src / "dist" / "root.txt").write_text("x\n", encoding="utf-8")

    (src / "nested").mkdir()
    (src / "nested" / "dist").mkdir()
    (src / "nested" / "dist" / "nested.txt").write_text("y\n", encoding="utf-8")

    # Anchored: only ignore ./dist, keep nested/dist
    (src / ".dockerignore").write_text("/dist/\n", encoding="utf-8")

    archive_path = create_project_archive(
        source_dir=str(src),
        output_dir=str(out),
        archive_name="proj",
    )

    members = _tar_members(archive_path)
    assert "dist/root.txt" not in members
    assert "nested/dist/nested.txt" in members


def test_project_archive_dockerignore_segment_glob_does_not_cross_directories(
    tmp_path: Path,
):
    src = tmp_path / "src"
    out = tmp_path / "out"
    src.mkdir()
    out.mkdir()

    (src / "dist").mkdir()
    (src / "dist" / "root.txt").write_text("x\n", encoding="utf-8")
    (src / "dist" / "root.md").write_text("m\n", encoding="utf-8")

    (src / "dist" / "nested").mkdir(parents=True)
    (src / "dist" / "nested" / "deep.txt").write_text("y\n", encoding="utf-8")

    # Segment glob: dist/*.txt excludes dist/root.txt, but does not match dist/nested/deep.txt.
    (src / ".dockerignore").write_text("dist/*.txt\n", encoding="utf-8")

    archive_path = create_project_archive(
        source_dir=str(src),
        output_dir=str(out),
        archive_name="proj",
    )

    members = _tar_members(archive_path)
    assert "dist/root.txt" not in members
    assert "dist/root.md" in members
    assert "dist/nested/deep.txt" in members


def test_project_archive_no_dockerignore_includes_all(tmp_path: Path):
    src = tmp_path / "src"
    out = tmp_path / "out"
    src.mkdir()
    out.mkdir()

    (src / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (src / ".hidden").mkdir()
    (src / ".hidden" / "secret.txt").write_text("secret\n", encoding="utf-8")

    archive_path = create_project_archive(
        source_dir=str(src),
        output_dir=str(out),
        archive_name="proj",
    )

    members = _tar_members(archive_path)
    assert "app.py" in members
    assert ".hidden/secret.txt" in members


def test_project_archive_force_includes_dockerfile_even_if_ignored(tmp_path: Path):
    src = tmp_path / "src"
    out = tmp_path / "out"
    src.mkdir()
    out.mkdir()

    (src / "Dockerfile").write_text("FROM python:3.12-slim\n", encoding="utf-8")
    (src / "app.py").write_text("print('ok')\n", encoding="utf-8")

    # This would normally exclude Dockerfile from the archive.
    (src / ".dockerignore").write_text("Dockerfile*\n", encoding="utf-8")

    archive_path = create_project_archive(
        source_dir=str(src),
        output_dir=str(out),
        archive_name="proj",
    )

    members = _tar_members(archive_path)
    assert "Dockerfile" in members
    assert "app.py" in members


def test_project_archive_force_includes_dockerignore_even_if_ignored(tmp_path: Path):
    src = tmp_path / "src"
    out = tmp_path / "out"
    src.mkdir()
    out.mkdir()

    (src / "Dockerfile").write_text("FROM python:3.12-slim\n", encoding="utf-8")
    (src / "app.py").write_text("print('ok')\n", encoding="utf-8")

    # Self-ignore: this would normally exclude .dockerignore from the archive.
    (src / ".dockerignore").write_text(".dockerignore\n", encoding="utf-8")

    archive_path = create_project_archive(
        source_dir=str(src),
        output_dir=str(out),
        archive_name="proj",
    )

    members = _tar_members(archive_path)
    assert ".dockerignore" in members
    assert "Dockerfile" in members
    assert "app.py" in members
