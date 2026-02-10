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

from agentkit.toolkit.config import CommonConfig
from agentkit.toolkit.config.utils import load_dotenv_file, merge_runtime_envs


def test_load_dotenv_file_returns_values(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("FOO=bar\nHELLO=world\n", encoding="utf-8")

    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("HELLO", raising=False)

    values = load_dotenv_file(tmp_path)

    assert values["FOO"] == "bar"
    assert values["HELLO"] == "world"


def test_load_dotenv_file_does_not_mutate_process_environment(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "FOO=bar\nVOLCENGINE_ACCESS_KEY=ak_from_dotenv\n",
        encoding="utf-8",
    )

    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("VOLCENGINE_ACCESS_KEY", raising=False)

    values = load_dotenv_file(tmp_path)
    assert values["FOO"] == "bar"
    assert values["VOLCENGINE_ACCESS_KEY"] == "ak_from_dotenv"

    assert "FOO" not in os.environ
    assert "VOLCENGINE_ACCESS_KEY" not in os.environ


def test_merge_runtime_envs_precedence_includes_dotenv(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "model:\n  api_key: from_config\n",
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text(
        "A=dotenv\nB=dotenv\nMODEL_API_KEY=from_env\n",
        encoding="utf-8",
    )

    common_config = CommonConfig(runtime_envs={"A": "common", "B": "common"})
    strategy_config = {"runtime_envs": {"B": "strategy", "C": "strategy"}}

    merged = merge_runtime_envs(common_config, strategy_config, project_dir=tmp_path)

    assert merged["A"] == "common"
    assert merged["B"] == "strategy"
    assert merged["C"] == "strategy"
    assert merged["MODEL_API_KEY"] == "from_env"
