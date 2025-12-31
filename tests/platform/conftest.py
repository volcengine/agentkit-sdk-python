# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
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
import pytest
from unittest.mock import MagicMock


@pytest.fixture
def clean_env(monkeypatch):
    """Clean up all VOLC related environment variables."""
    for key in list(os.environ.keys()):
        if key.startswith("VOLC"):
            monkeypatch.delenv(key)


@pytest.fixture
def mock_global_config(mocker):
    """Mock global config reader."""
    mock_data = {}

    def _get_value(*keys):
        cur = mock_data
        for k in keys:
            if isinstance(cur, dict):
                cur = cur.get(k)
            else:
                return None
        return cur

    def _read_dict(*args, **kwargs):
        return mock_data

    mocker.patch(
        "agentkit.platform.configuration.read_global_config_dict",
        side_effect=_read_dict,
    )
    mocker.patch(
        "agentkit.platform.configuration.get_global_config_value",
        side_effect=_get_value,
    )

    # We also need to patch get_global_config_str because it's used in some places
    def _get_str(*keys):
        val = _get_value(*keys)
        return str(val) if val is not None else None

    mocker.patch(
        "agentkit.platform.configuration.get_global_config_str", side_effect=_get_str
    )

    return mock_data


@pytest.fixture
def mock_vefaas_file(mocker):
    """Mock VeFaaS credential file."""
    mock_open = mocker.mock_open(
        read_data='{"access_key_id": "vefaas_ak", "secret_access_key": "vefaas_sk", "session_token": "vefaas_token"}'
    )
    mocker.patch("builtins.open", mock_open)
    mocker.patch("pathlib.Path.exists", return_value=True)
    return mock_open
