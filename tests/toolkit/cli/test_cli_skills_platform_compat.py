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

import pytest


def test_init_generates_unquoted_frontmatter(tmp_path):
    import typer

    from agentkit.toolkit.cli.cli_skills_workflow import add_workflow_commands

    app = typer.Typer()
    add_workflow_commands(app)

    init_cmd = typer.main.get_command(app).get_command(None, "init")  # type: ignore[attr-defined]
    init_cmd.callback(  # type: ignore[attr-defined]
        skill_name="demo-skill",
        description="desc",
        path=str(tmp_path),
    )
    text = (tmp_path / "demo-skill" / "SKILL.md").read_text(encoding="utf-8")
    assert 'name: "demo-skill"' not in text
    assert 'description: "desc"' not in text
    assert "name: demo-skill" in text
    assert "description: desc" in text


def test_validate_rejects_quoted_frontmatter(tmp_path):
    from agentkit.toolkit.cli.cli_skills_workflow import _load_skill_metadata

    d = tmp_path / "my-skill"
    d.mkdir()
    (d / "SKILL.md").write_text(
        """---
name: "my-skill"
description: "desc"
---
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        _load_skill_metadata(str(d))


def test_fix_frontmatter_quotes():
    from agentkit.toolkit.cli.cli_skills_workflow import (
        _fix_platform_frontmatter_quotes,
    )

    fixed = _fix_platform_frontmatter_quotes(
        """---
name: "my-skill"
description: "desc"
---
"""
    )
    assert 'name: "my-skill"' not in fixed
    assert 'description: "desc"' not in fixed
    assert "name: my-skill" in fixed
    assert "description: desc" in fixed


def test_validate_skill_space_name():
    from agentkit.toolkit.cli.cli_skills import _validate_skill_space_name

    _validate_skill_space_name("abc_123")
    with pytest.raises(Exception):
        _validate_skill_space_name("abc-123")
    with pytest.raises(Exception):
        _validate_skill_space_name("ABC")
    with pytest.raises(Exception):
        _validate_skill_space_name("")


def test_make_content_hashed_zip_copy(tmp_path):
    from agentkit.toolkit.cli.cli_skills_workflow import (
        _make_content_hashed_zip_copy,
        _sha256_file_hex,
    )

    src = tmp_path / "skill.zip"
    src.write_bytes(b"hello")
    out = _make_content_hashed_zip_copy(str(src), "my-skill", str(tmp_path))
    digest = _sha256_file_hex(str(src))[:8]
    assert out.endswith(f"my-skill-{digest}.zip")
    assert (tmp_path / f"my-skill-{digest}.zip").read_bytes() == b"hello"


def test_ensure_bucket_ready_noninteractive_requires_yes(monkeypatch):
    from agentkit.toolkit.cli import cli_skills_workflow as m
    import typer

    class FakeConfig:
        def __init__(self, region, bucket, prefix):
            self.region = region
            self.bucket = bucket
            self.prefix = prefix

    class FakeService:
        def __init__(self, config):
            self.config = config

        def bucket_exists(self):
            return False

        def create_bucket(self):
            return True

        def bucket_is_owned(self, bucket_name=None):
            return True

    import agentkit.toolkit.volcengine.services.tos_service as tos_service

    monkeypatch.setattr(tos_service, "TOSServiceConfig", FakeConfig)
    monkeypatch.setattr(tos_service, "TOSService", FakeService)
    monkeypatch.setattr(m, "_is_interactive", lambda: False)

    with pytest.raises(typer.BadParameter):
        m._ensure_bucket_ready(
            bucket_name="b",
            prefix="p",
            region="cn-beijing",
            auto_bucket=False,
            assume_yes=False,
            assume_no=False,
        )


def test_ensure_bucket_ready_interactive_prompts_and_creates(monkeypatch):
    from agentkit.toolkit.cli import cli_skills_workflow as m

    created = {"ok": False}

    class FakeConfig:
        def __init__(self, region, bucket, prefix):
            self.region = region
            self.bucket = bucket
            self.prefix = prefix

    class FakeService:
        def __init__(self, config):
            self.config = config

        def bucket_exists(self):
            return False

        def create_bucket(self):
            created["ok"] = True
            return True

        def bucket_is_owned(self, bucket_name=None):
            return True

    import agentkit.toolkit.volcengine.services.tos_service as tos_service
    import typer

    monkeypatch.setattr(tos_service, "TOSServiceConfig", FakeConfig)
    monkeypatch.setattr(tos_service, "TOSService", FakeService)
    monkeypatch.setattr(m, "_is_interactive", lambda: True)
    monkeypatch.setattr(typer, "confirm", lambda *args, **kwargs: True)

    m._ensure_bucket_ready(
        bucket_name="b",
        prefix="p",
        region="cn-beijing",
        auto_bucket=False,
        assume_yes=False,
        assume_no=False,
    )
    assert created["ok"] is True


def test_ensure_bucket_ready_assume_yes_creates(monkeypatch):
    from agentkit.toolkit.cli import cli_skills_workflow as m

    created = {"ok": False}

    class FakeConfig:
        def __init__(self, region, bucket, prefix):
            self.region = region
            self.bucket = bucket
            self.prefix = prefix

    class FakeService:
        def __init__(self, config):
            self.config = config

        def bucket_exists(self):
            return False

        def create_bucket(self):
            created["ok"] = True
            return True

        def bucket_is_owned(self, bucket_name=None):
            return True

    import agentkit.toolkit.volcengine.services.tos_service as tos_service

    monkeypatch.setattr(tos_service, "TOSServiceConfig", FakeConfig)
    monkeypatch.setattr(tos_service, "TOSService", FakeService)
    monkeypatch.setattr(m, "_is_interactive", lambda: False)

    m._ensure_bucket_ready(
        bucket_name="b",
        prefix="p",
        region="cn-beijing",
        auto_bucket=False,
        assume_yes=True,
        assume_no=False,
    )
    assert created["ok"] is True


def test_ensure_bucket_ready_assume_no_rejects(monkeypatch):
    from agentkit.toolkit.cli import cli_skills_workflow as m
    import typer

    class FakeConfig:
        def __init__(self, region, bucket, prefix):
            self.region = region
            self.bucket = bucket
            self.prefix = prefix

    class FakeService:
        def __init__(self, config):
            self.config = config

        def bucket_exists(self):
            return False

        def create_bucket(self):
            return True

        def bucket_is_owned(self, bucket_name=None):
            return True

    import agentkit.toolkit.volcengine.services.tos_service as tos_service

    monkeypatch.setattr(tos_service, "TOSServiceConfig", FakeConfig)
    monkeypatch.setattr(tos_service, "TOSService", FakeService)

    with pytest.raises(typer.BadParameter):
        m._ensure_bucket_ready(
            bucket_name="b",
            prefix="p",
            region="cn-beijing",
            auto_bucket=False,
            assume_yes=False,
            assume_no=True,
        )


def test_ensure_bucket_ready_blocks_not_owned(monkeypatch):
    from agentkit.toolkit.cli import cli_skills_workflow as m
    import typer

    class FakeConfig:
        def __init__(self, region, bucket, prefix):
            self.region = region
            self.bucket = bucket
            self.prefix = prefix

    class FakeService:
        def __init__(self, config):
            self.config = config

        def bucket_exists(self):
            return True

        def create_bucket(self):
            return True

        def bucket_is_owned(self, bucket_name=None):
            return False

    import agentkit.toolkit.volcengine.services.tos_service as tos_service

    monkeypatch.setattr(tos_service, "TOSServiceConfig", FakeConfig)
    monkeypatch.setattr(tos_service, "TOSService", FakeService)

    with pytest.raises(typer.BadParameter):
        m._ensure_bucket_ready(
            bucket_name="b",
            prefix="p",
            region="cn-beijing",
            auto_bucket=False,
            assume_yes=False,
            assume_no=False,
        )


def test_tos_upload_skip_verify_bucket(monkeypatch, tmp_path):
    from agentkit.toolkit.cli import cli_skills_workflow as m

    uploaded = {"ok": False}

    class FakeConfig:
        def __init__(self, region, bucket, prefix):
            self.region = region
            self.bucket = bucket
            self.prefix = prefix

    class FakeService:
        def __init__(self, config):
            self.config = config

        def bucket_exists(self):
            raise AssertionError(
                "bucket_exists should not be called when verify_bucket=False"
            )

        def bucket_is_owned(self, bucket_name=None):
            raise AssertionError(
                "bucket_is_owned should not be called when verify_bucket=False"
            )

        def upload_file(self, local_path, object_key):
            uploaded["ok"] = True
            assert object_key.endswith("x.zip")
            return f"https://example.com/{object_key}"

    import agentkit.toolkit.volcengine.services.tos_service as tos_service

    monkeypatch.setattr(tos_service, "TOSServiceConfig", FakeConfig)
    monkeypatch.setattr(tos_service, "TOSService", FakeService)

    p = tmp_path / "x.zip"
    p.write_bytes(b"data")
    url = m._tos_upload(
        str(p), "b", "agentkit/skills", "cn-beijing", verify_bucket=False
    )
    assert uploaded["ok"] is True
    assert url.startswith("https://example.com/")
