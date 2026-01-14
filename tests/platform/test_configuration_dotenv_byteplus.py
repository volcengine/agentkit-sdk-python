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
