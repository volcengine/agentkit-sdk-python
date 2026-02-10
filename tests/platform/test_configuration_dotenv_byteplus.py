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
from pathlib import Path

from agentkit.platform.configuration import VolcConfiguration
from agentkit.platform.provider import ENV_CLOUD_PROVIDER


def test_byteplus_creds_from_dotenv(
    clean_env, mock_global_config, monkeypatch, tmp_path: Path
) -> None:
    os.environ[ENV_CLOUD_PROVIDER] = "byteplus"

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "BYTEPLUS_ACCESS_KEY=BP_DOTENV_AK\nBYTEPLUS_SECRET_KEY=BP_DOTENV_SK\n",
        encoding="utf-8",
    )

    cfg = VolcConfiguration()
    creds = cfg.get_service_credentials("agentkit")

    assert creds.access_key == "BP_DOTENV_AK"
    assert creds.secret_key == "BP_DOTENV_SK"
