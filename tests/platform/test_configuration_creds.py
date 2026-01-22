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

import pytest
import os
from pathlib import Path
from agentkit.platform.configuration import VolcConfiguration


class TestConfigurationCredentials:
    def test_creds_explicit_priority(self, clean_env, mock_global_config):
        """Test that explicit credentials take highest priority."""
        # Setup conflicting environment variables
        os.environ["VOLCENGINE_ACCESS_KEY"] = "TEST_ENV_AK"
        os.environ["VOLCENGINE_SECRET_KEY"] = "TEST_ENV_SK"

        config = VolcConfiguration(
            access_key="TEST_EXPLICIT_AK", secret_key="TEST_EXPLICIT_SK"
        )
        creds = config.get_service_credentials("agentkit")

        assert creds.access_key == "TEST_EXPLICIT_AK"
        assert creds.secret_key == "TEST_EXPLICIT_SK"

    def test_creds_service_env_priority(self, clean_env, mock_global_config):
        """Test that service-specific environment variables take priority over global ones."""
        os.environ["VOLCENGINE_AGENTKIT_ACCESS_KEY"] = "TEST_SVC_AK"
        os.environ["VOLCENGINE_AGENTKIT_SECRET_KEY"] = "TEST_SVC_SK"
        os.environ["VOLCENGINE_ACCESS_KEY"] = "TEST_GLOBAL_AK"
        os.environ["VOLCENGINE_SECRET_KEY"] = "TEST_GLOBAL_SK"

        config = VolcConfiguration()
        creds = config.get_service_credentials("agentkit")

        assert creds.access_key == "TEST_SVC_AK"
        assert creds.secret_key == "TEST_SVC_SK"

        # Other services should still use global
        other_creds = config.get_service_credentials("other")
        assert other_creds.access_key == "TEST_GLOBAL_AK"

    def test_creds_global_env_priority(self, clean_env, mock_global_config):
        """Test that global environment variables take priority over config file."""
        os.environ["VOLCENGINE_ACCESS_KEY"] = "TEST_GLOBAL_AK"
        os.environ["VOLCENGINE_SECRET_KEY"] = "TEST_GLOBAL_SK"

        mock_global_config.update(
            {"volcengine": {"access_key": "TEST_CFG_AK", "secret_key": "TEST_CFG_SK"}}
        )

        config = VolcConfiguration()
        creds = config.get_service_credentials("agentkit")

        assert creds.access_key == "TEST_GLOBAL_AK"
        assert creds.secret_key == "TEST_GLOBAL_SK"

    def test_creds_config_file_priority(self, clean_env, mock_global_config, mocker):
        """Test that config file is used when no env vars are present."""
        # Ensure VeFaaS check fails
        mocker.patch("pathlib.Path.exists", return_value=False)

        mock_global_config.update(
            {"volcengine": {"access_key": "TEST_CFG_AK", "secret_key": "TEST_CFG_SK"}}
        )

        config = VolcConfiguration()
        creds = config.get_service_credentials("agentkit")

        assert creds.access_key == "TEST_CFG_AK"
        assert creds.secret_key == "TEST_CFG_SK"

    def test_creds_vefaas_fallback(
        self, clean_env, mock_global_config, mock_vefaas_file
    ):
        """Test fallback to VeFaaS credentials."""
        # No env, no config
        config = VolcConfiguration()
        creds = config.get_service_credentials("agentkit")

        assert creds.access_key == "vefaas_ak"
        assert creds.secret_key == "vefaas_sk"
        assert creds.session_token == "vefaas_token"

    def test_creds_dotenv_fallback_from_cwd(
        self, clean_env, mock_global_config, monkeypatch, tmp_path, mocker
    ):
        """Test fallback to .env in current working directory when other sources are missing."""
        # Ensure VeFaaS IAM check fails
        mocker.patch("pathlib.Path.exists", return_value=False)

        monkeypatch.chdir(tmp_path)
        (tmp_path / ".env").write_text(
            "VOLCENGINE_ACCESS_KEY=AK_FROM_DOTENV\nVOLCENGINE_SECRET_KEY=SK_FROM_DOTENV\n",
            encoding="utf-8",
        )

        config = VolcConfiguration()
        creds = config.get_service_credentials("agentkit")

        assert creds.access_key == "AK_FROM_DOTENV"
        assert creds.secret_key == "SK_FROM_DOTENV"

    def test_creds_dotenv_does_not_override_global_env(
        self, clean_env, mock_global_config, monkeypatch, tmp_path
    ):
        """Test that .env fallback never overrides real process environment variables."""
        os.environ["VOLCENGINE_ACCESS_KEY"] = "AK_FROM_ENV"
        os.environ["VOLCENGINE_SECRET_KEY"] = "SK_FROM_ENV"

        monkeypatch.chdir(tmp_path)
        (tmp_path / ".env").write_text(
            "VOLCENGINE_ACCESS_KEY=AK_FROM_DOTENV\nVOLCENGINE_SECRET_KEY=SK_FROM_DOTENV\n",
            encoding="utf-8",
        )

        config = VolcConfiguration()
        creds = config.get_service_credentials("agentkit")

        assert creds.access_key == "AK_FROM_ENV"
        assert creds.secret_key == "SK_FROM_ENV"

    def test_creds_dotenv_does_not_override_global_config(
        self, clean_env, mock_global_config, monkeypatch, tmp_path, mocker
    ):
        """Test that .env fallback never overrides ~/.agentkit/config.yaml credentials."""
        # Ensure VeFaaS IAM check fails
        mocker.patch("pathlib.Path.exists", return_value=False)

        mock_global_config.update(
            {"volcengine": {"access_key": "AK_FROM_CFG", "secret_key": "SK_FROM_CFG"}}
        )

        monkeypatch.chdir(tmp_path)
        (tmp_path / ".env").write_text(
            "VOLCENGINE_ACCESS_KEY=AK_FROM_DOTENV\nVOLCENGINE_SECRET_KEY=SK_FROM_DOTENV\n",
            encoding="utf-8",
        )

        config = VolcConfiguration()
        creds = config.get_service_credentials("agentkit")

        assert creds.access_key == "AK_FROM_CFG"
        assert creds.secret_key == "SK_FROM_CFG"

    def test_creds_dotenv_partial_is_ignored(
        self, clean_env, mock_global_config, monkeypatch, tmp_path, mocker
    ):
        """Test that partial .env credentials are ignored and lookup continues."""
        # Ensure VeFaaS IAM check fails
        mocker.patch("pathlib.Path.exists", return_value=False)

        monkeypatch.chdir(tmp_path)
        (tmp_path / ".env").write_text(
            "VOLCENGINE_ACCESS_KEY=AK_ONLY\n",
            encoding="utf-8",
        )

        config = VolcConfiguration()
        with pytest.raises(ValueError, match="Volcengine credentials not found"):
            config.get_service_credentials("agentkit")

    def test_creds_vefaas_takes_priority_over_dotenv(
        self, clean_env, mock_global_config, mock_vefaas_file, monkeypatch, tmp_path
    ):
        """Test that VeFaaS IAM credentials take priority over .env fallback."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".env").write_text(
            "VOLCENGINE_ACCESS_KEY=AK_FROM_DOTENV\nVOLCENGINE_SECRET_KEY=SK_FROM_DOTENV\n",
            encoding="utf-8",
        )

        config = VolcConfiguration()
        creds = config.get_service_credentials("agentkit")

        assert creds.access_key == "vefaas_ak"
        assert creds.secret_key == "vefaas_sk"
        assert creds.session_token == "vefaas_token"

    def test_creds_missing_error(self, clean_env, mock_global_config, mocker):
        """Test error raised when no credentials found."""
        mocker.patch("pathlib.Path.exists", return_value=False)

        config = VolcConfiguration()
        with pytest.raises(ValueError, match="Volcengine credentials not found"):
            config.get_service_credentials("agentkit")

    def test_creds_legacy_env_support(self, clean_env, mock_global_config):
        """Test support for legacy VOLC_ prefix."""
        os.environ["VOLC_ACCESSKEY"] = "TEST_LEGACY_AK"
        os.environ["VOLC_SECRETKEY"] = "TEST_LEGACY_SK"

        config = VolcConfiguration()
        creds = config.get_service_credentials("agentkit")

        assert creds.access_key == "TEST_LEGACY_AK"
        assert creds.secret_key == "TEST_LEGACY_SK"

    def test_creds_partial_env(self, clean_env, mock_global_config):
        """Test that partial env vars (AK only) are ignored and lookup continues."""
        os.environ["VOLCENGINE_ACCESS_KEY"] = "TEST_PARTIAL_AK"
        # Missing SECRET_KEY

        mock_global_config.update(
            {"volcengine": {"access_key": "TEST_CFG_AK", "secret_key": "TEST_CFG_SK"}}
        )

        config = VolcConfiguration()
        creds = config.get_service_credentials("agentkit")

        # Should skip partial env and find config
        assert creds.access_key == "TEST_CFG_AK"
        assert creds.secret_key == "TEST_CFG_SK"

    def test_creds_explicit_token(self, clean_env, mock_global_config):
        """Test that session token is correctly passed when provided explicitly."""
        config = VolcConfiguration(
            access_key="TEST_AK", secret_key="TEST_SK", session_token="TEST_TOKEN"
        )

        creds = config.get_service_credentials("agentkit")
        assert creds.access_key == "TEST_AK"
        assert creds.secret_key == "TEST_SK"
        assert creds.session_token == "TEST_TOKEN"

    def test_creds_vefaas_corrupt(self, clean_env, mock_global_config, mocker):
        """Test graceful failure when VeFaaS file is corrupt."""
        # Mock open to return invalid JSON
        mock_open = mocker.mock_open(read_data="{invalid_json}")
        mocker.patch("builtins.open", mock_open)
        mocker.patch("pathlib.Path.exists", return_value=True)

        config = VolcConfiguration()

        # Should raise ValueError because VeFaaS failed and nothing else is available
        with pytest.raises(ValueError, match="Volcengine credentials not found"):
            config.get_service_credentials("agentkit")
