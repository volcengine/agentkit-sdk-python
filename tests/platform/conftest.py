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


@pytest.fixture
def clean_env(monkeypatch):
    """Clean up environment variables that may affect platform resolution.

    Snapshots the full environment and restores it on teardown, so tests that
    set variables via raw ``os.environ[...]`` (instead of monkeypatch.setenv)
    cannot leak into later tests and create order-dependent failures.
    """
    snapshot = os.environ.copy()
    for key in list(os.environ.keys()):
        if (
            key.startswith("VOLC")
            or key.startswith("BYTEPLUS")
            or key
            in {
                "AGENTKIT_CLOUD_PROVIDER",
                "CLOUD_PROVIDER",
            }
        ):
            monkeypatch.delenv(key)
    yield
    os.environ.clear()
    os.environ.update(snapshot)


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

    class _Stat:
        st_mtime_ns = 1

    mock_open = mocker.mock_open(
        read_data='{"access_key_id": "vefaas_ak", "secret_access_key": "vefaas_sk", "session_token": "vefaas_token", "expired_time": "2999-01-01T00:00:00+00:00"}'
    )
    mocker.patch("builtins.open", mock_open)
    mocker.patch("pathlib.Path.exists", return_value=True)
    mocker.patch(
        "pathlib.Path.stat",
        return_value=_Stat(),
    )
    return mock_open
