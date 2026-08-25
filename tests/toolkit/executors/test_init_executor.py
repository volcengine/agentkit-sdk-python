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

"""Offline unit tests for ``InitExecutor`` scaffolding behavior.

These tests exercise the pure, filesystem-only surface of
``agentkit.toolkit.executors.init_executor.InitExecutor`` -- the render-context
builder, the template registry accessor, ``init_project`` validation gates and
its Python happy path, and the harness scaffold. ``_setup_config_launch_type`` /
cloud-provider region defaults are intentionally NOT re-covered here; that lives
in ``test_init_cloud_provider_defaults.py``.

All filesystem writes go to ``tmp_path``. No network, docker, or ``.run()`` is
touched: ``init_project`` only renders a Jinja template to text and writes
config/dockerignore files, none of which import the agent's runtime deps.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from agentkit.toolkit.executors.init_executor import InitExecutor, TEMPLATES
from agentkit.toolkit.models import InitResult


def _read_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    assert isinstance(data, dict)
    return data


# ---------------------------------------------------------------------------
# _build_render_context
# ---------------------------------------------------------------------------


def test_build_render_context_omits_all_none_arguments() -> None:
    executor = InitExecutor()
    ctx = executor._build_render_context(None, None, None, None, None)
    assert ctx == {}


def test_build_render_context_includes_only_non_none_keys() -> None:
    executor = InitExecutor()
    ctx = executor._build_render_context(
        agent_name="MyAgent",
        description=None,
        system_prompt="be helpful",
        model_name=None,
        tools=None,
    )
    assert ctx == {"agent_name": "MyAgent", "system_prompt": "be helpful"}
    assert "description" not in ctx
    assert "model_name" not in ctx
    assert "tools" not in ctx


def test_build_render_context_splits_and_trims_tools_into_list() -> None:
    executor = InitExecutor()
    ctx = executor._build_render_context(
        None, None, None, None, tools=" web_search , run_code ,,  calculator "
    )
    # Comma-split, each entry stripped, blank entries dropped.
    assert ctx["tools"] == ["web_search", "run_code", "calculator"]


def test_build_render_context_empty_tools_string_yields_empty_list_but_key_present() -> None:
    executor = InitExecutor()
    # tools is not None, so the key is added even though every entry is blank.
    ctx = executor._build_render_context(None, None, None, None, tools="  , ,")
    assert ctx["tools"] == []
    assert "tools" in ctx


# ---------------------------------------------------------------------------
# get_available_templates
# ---------------------------------------------------------------------------


def test_get_available_templates_returns_the_registered_template_keys() -> None:
    executor = InitExecutor()
    templates = executor.get_available_templates()
    # Pin the shape: at least the "basic" Python template is present and typed.
    assert "basic" in templates
    assert templates["basic"]["language"] == "Python"
    assert templates["basic"]["name"] == "Basic Agent App"


def test_get_available_templates_returns_a_copy_that_does_not_mutate_source() -> None:
    executor = InitExecutor()
    templates = executor.get_available_templates()

    original_keys = set(TEMPLATES.keys())
    templates["__injected__"] = {"name": "bogus"}
    del templates["basic"]

    # The returned dict is a shallow copy: top-level mutation must not leak.
    assert "__injected__" not in TEMPLATES
    assert "basic" in TEMPLATES
    assert set(TEMPLATES.keys()) == original_keys


# ---------------------------------------------------------------------------
# init_project validation early-returns
# ---------------------------------------------------------------------------


def test_init_project_rejects_invalid_project_name(tmp_path: Path) -> None:
    executor = InitExecutor()
    result = executor.init_project(
        project_name="bad name!",
        template="basic",
        directory=str(tmp_path),
    )
    assert isinstance(result, InitResult)
    assert result.success is False
    assert result.error_code == "INVALID_CONFIG"
    assert "invalid characters" in result.error
    # Early return: no scaffolding happened.
    assert not (tmp_path / "agentkit.yaml").exists()


def test_init_project_rejects_unknown_template_and_lists_available(
    tmp_path: Path,
) -> None:
    executor = InitExecutor()
    result = executor.init_project(
        project_name="demo",
        template="does_not_exist",
        directory=str(tmp_path),
    )
    assert result.success is False
    assert result.error_code == "INVALID_CONFIG"
    assert "Unknown template 'does_not_exist'" in result.error
    assert "Available:" in result.error
    # The available list must name a real registered template.
    assert "basic" in result.error


def test_init_project_rejects_unsupported_language_template(
    tmp_path: Path, monkeypatch
) -> None:
    # Inject a fake template whose language is neither Python nor Golang so the
    # language branch falls through to the "Unsupported language" early return.
    import agentkit.toolkit.executors.init_executor as init_mod

    fake_templates = dict(TEMPLATES)
    fake_templates["_ruby_"] = {
        "file": "nope.rb",
        "name": "Ruby App",
        "language": "Ruby",
        "language_version": "3.3",
        "description": "unsupported",
        "type": "Basic App",
    }
    monkeypatch.setattr(init_mod, "TEMPLATES", fake_templates)

    executor = InitExecutor()
    result = executor.init_project(
        project_name="demo",
        template="_ruby_",
        directory=str(tmp_path),
    )
    assert result.success is False
    assert result.error_code == "INVALID_CONFIG"
    assert "Unsupported language: Ruby" in result.error


# ---------------------------------------------------------------------------
# init_project happy path (Python "basic")
# ---------------------------------------------------------------------------


def test_init_project_python_basic_scaffolds_expected_files_and_metadata(
    tmp_path: Path,
) -> None:
    executor = InitExecutor()
    result = executor.init_project(
        project_name="demo_agent",
        template="basic",
        directory=str(tmp_path),
    )

    assert result.success is True
    assert result.template == "basic"
    assert result.project_name == "demo_agent"
    assert Path(result.project_path) == tmp_path.resolve()

    # Entry file is named after the project, ends in .py, and was rendered from
    # the Jinja template (license header survives the render).
    entry_file = tmp_path / "demo_agent.py"
    assert entry_file.exists()
    assert "Apache License" in entry_file.read_text(encoding="utf-8")

    requirements = tmp_path / "requirements.txt"
    assert requirements.exists()
    assert "veadk-python" in requirements.read_text(encoding="utf-8")

    config_file = tmp_path / "agentkit.yaml"
    assert config_file.exists()

    dockerignore = tmp_path / ".dockerignore"
    assert dockerignore.exists()

    # created_files tracks the files produced this run.
    assert "demo_agent.py" in result.created_files
    assert "requirements.txt" in result.created_files
    assert "agentkit.yaml" in result.created_files
    assert ".dockerignore" in result.created_files

    # Metadata reflects the resolved template.
    assert result.metadata["language"] == "Python"
    assert result.metadata["entry_point"] == "demo_agent.py"
    assert result.metadata["template_name"] == "Basic Agent App"


def test_init_project_python_basic_writes_project_name_into_config(
    tmp_path: Path,
) -> None:
    executor = InitExecutor()
    result = executor.init_project(
        project_name="demo_agent",
        template="basic",
        directory=str(tmp_path),
    )
    assert result.success is True

    data = _read_yaml(tmp_path / "agentkit.yaml")
    common = data.get("common") or {}
    assert common.get("agent_name") == "demo_agent"
    assert common.get("language") == "Python"
    assert common.get("entry_point") == "demo_agent.py"


# ---------------------------------------------------------------------------
# init_harness
# ---------------------------------------------------------------------------


def test_init_harness_writes_env_example_and_dockerfile(tmp_path: Path) -> None:
    executor = InitExecutor()
    result = executor.init_harness(project_name="myharness", directory=str(tmp_path))

    assert result.success is True
    assert result.template == "harness"
    assert result.metadata["template_name"] == "Harness"

    harness_dir = tmp_path / "myharness"
    env_example = harness_dir / ".env.example"
    dockerfile = harness_dir / "Dockerfile"

    assert env_example.exists()
    assert dockerfile.exists()
    assert ".env.example" in result.created_files
    assert "Dockerfile" in result.created_files

    dockerfile_text = dockerfile.read_text(encoding="utf-8")
    assert dockerfile_text.startswith("FROM ")
    assert 'CMD ["python"' in dockerfile_text


def test_init_harness_env_example_ships_empty_credential_placeholders(
    tmp_path: Path,
) -> None:
    executor = InitExecutor()
    executor.init_harness(project_name="myharness", directory=str(tmp_path))

    env_text = (tmp_path / "myharness" / ".env.example").read_text(encoding="utf-8")

    # Secret-hygiene pin: credential keys are present but carry NO value. The
    # AK/SK placeholders must be empty (key= with nothing after the '=').
    lines = {
        line.split("=", 1)[0]: line.split("=", 1)[1]
        for line in env_text.splitlines()
        if "=" in line and not line.lstrip().startswith("#")
    }
    assert lines["VOLCENGINE_ACCESS_KEY"] == ""
    assert lines["VOLCENGINE_SECRET_KEY"] == ""
    assert "# CLOUD_PROVIDER=byteplus" in env_text
    assert "# BYTEPLUS_ACCESS_KEY=" in env_text
    assert "# BYTEPLUS_SECRET_KEY=" in env_text


def test_init_harness_is_idempotent_and_skips_existing_files(tmp_path: Path) -> None:
    executor = InitExecutor()

    first = executor.init_harness(project_name="myharness", directory=str(tmp_path))
    assert first.success is True
    assert set(first.created_files) == {".env.example", "Dockerfile"}

    harness_dir = tmp_path / "myharness"
    # User customizes .env.example after the first init.
    sentinel = "VOLCENGINE_ACCESS_KEY=preserved\n"
    (harness_dir / ".env.example").write_text(sentinel, encoding="utf-8")

    second = executor.init_harness(project_name="myharness", directory=str(tmp_path))
    assert second.success is True
    # Both files already exist: nothing is re-created and edits are preserved.
    assert second.created_files == []
    assert (harness_dir / ".env.example").read_text(encoding="utf-8") == sentinel


def test_init_harness_rejects_invalid_project_name(tmp_path: Path) -> None:
    executor = InitExecutor()
    result = executor.init_harness(project_name="bad name!", directory=str(tmp_path))
    assert result.success is False
    assert result.error_code == "INVALID_CONFIG"
    assert "invalid characters" in result.error
