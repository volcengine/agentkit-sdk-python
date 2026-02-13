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

import os
import zipfile

import pytest


def test_parse_skill_md_frontmatter_ok():
    from agentkit.toolkit.cli.cli_skills_workflow import _parse_skill_md_frontmatter

    meta = _parse_skill_md_frontmatter(
        """---
name: "my-skill"
description: "hello"
---

# Title
"""
    )
    assert meta["name"] == "my-skill"
    assert meta["description"] == "hello"


def test_validate_skill_name_rejects_uppercase():
    from agentkit.toolkit.cli.cli_skills_workflow import _validate_skill_name

    with pytest.raises(ValueError):
        _validate_skill_name("MySkill")


def test_validate_skill_name_rejects_reserved_word():
    from agentkit.toolkit.cli.cli_skills_workflow import _validate_skill_name

    with pytest.raises(ValueError):
        _validate_skill_name("agentkit-skill")


def test_validate_skill_description_rejects_xml_tags():
    from agentkit.toolkit.cli.cli_skills_workflow import _validate_skill_description

    with pytest.raises(ValueError):
        _validate_skill_description("hello <tag> world")


def test_load_skill_metadata_reads_skill_md(tmp_path):
    from agentkit.toolkit.cli.cli_skills_workflow import _load_skill_metadata

    d = tmp_path / "my-skill"
    d.mkdir()
    (d / "SKILL.md").write_text(
        """---
name: my-skill
description: desc
---
""",
        encoding="utf-8",
    )
    meta = _load_skill_metadata(str(d))
    assert meta == {"name": "my-skill", "description": "desc"}


def test_zip_skill_dir_has_single_root(tmp_path):
    from agentkit.toolkit.cli.cli_skills_workflow import _zip_skill_dir

    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """---
name: my-skill
description: desc
---
""",
        encoding="utf-8",
    )
    (skill_dir / "data.txt").write_text("x", encoding="utf-8")

    out_zip = tmp_path / "out.zip"
    _zip_skill_dir(str(skill_dir), "my-skill", str(out_zip))

    with zipfile.ZipFile(str(out_zip), "r") as zf:
        names = zf.namelist()

    assert any(n == "my-skill/SKILL.md" for n in names)
    assert all(n.startswith("my-skill/") for n in names)
    assert all(not n.startswith("my-skill/../") for n in names)
    assert all(os.path.isabs(n) is False for n in names)
