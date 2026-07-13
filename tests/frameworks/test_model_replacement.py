import os
import sys
import logging
from types import ModuleType

import pytest

from agentkit.frameworks import model_replacement as module
from agentkit.frameworks.model_replacement import (
    ARK_DEFAULT_BASE_URL,
    apply_agentkit_model_replacement,
)


def _install_fake_strands(monkeypatch):
    strands = ModuleType("strands")
    models = ModuleType("strands.models")
    openai = ModuleType("strands.models.openai")
    bedrock = ModuleType("strands.models.bedrock")
    anthropic = ModuleType("strands.models.anthropic")

    class OpenAIModel:
        def __init__(self, client_args=None, **config):
            self.client_args = client_args
            self.config = config

    class BedrockModel:
        pass

    class AnthropicModel:
        pass

    openai.OpenAIModel = OpenAIModel
    models.BedrockModel = BedrockModel
    bedrock.BedrockModel = BedrockModel
    anthropic.AnthropicModel = AnthropicModel
    strands.models = models
    models.openai = openai
    models.bedrock = bedrock
    models.anthropic = anthropic

    for fake_module in (strands, models, openai, bedrock, anthropic):
        monkeypatch.setitem(sys.modules, fake_module.__name__, fake_module)
    return models, bedrock, anthropic


def test_model_replacement_sets_common_alias_envs_without_overwriting(monkeypatch):
    for key in (
        "BEDROCK_MODEL_ID",
        "MODEL_ID",
        "MODEL_NAME",
        "OPENAI_BASE_URL",
        "OPENAI_API_BASE",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ARK_MODEL_ID", "doubao-target")
    monkeypatch.setenv("ARK_API_KEY", "ark-key")
    monkeypatch.setenv("ARK_BASE_URL", "https://ark.example/api/v3")
    monkeypatch.setenv("DEFAULT_MODEL", "existing-default")
    monkeypatch.setenv("OPENAI_API_KEY", "existing-openai-key")
    monkeypatch.setattr(module, "_patch_strands_model_classes", lambda: False)

    assert apply_agentkit_model_replacement() is True

    assert os.environ["BEDROCK_MODEL_ID"] == "doubao-target"
    assert os.environ["MODEL_ID"] == "doubao-target"
    assert os.environ["MODEL_NAME"] == "doubao-target"
    assert os.environ["DEFAULT_MODEL"] == "existing-default"
    assert os.environ["OPENAI_BASE_URL"] == "https://ark.example/api/v3"
    assert os.environ["OPENAI_API_BASE"] == "https://ark.example/api/v3"
    assert os.environ["OPENAI_API_KEY"] == "existing-openai-key"


def test_model_replacement_logs_startup_diagnostics_without_secrets(monkeypatch, caplog):
    monkeypatch.setenv("ARK_MODEL_ID", "doubao-target")
    monkeypatch.setenv("ARK_API_KEY", "secret-key")
    monkeypatch.setattr(module, "_patch_strands_model_classes", lambda: False)

    with caplog.at_level(logging.INFO, logger="agentkit.frameworks.model_replacement"):
        assert apply_agentkit_model_replacement() is True

    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "AgentKit model replacement enabled" in messages
    assert "env_aliases=True" in messages
    assert "strands_model_patch=False" in messages
    assert "secret-key" not in messages


def test_model_replacement_patches_strands_bedrock_and_anthropic(monkeypatch):
    models, bedrock, anthropic = _install_fake_strands(monkeypatch)
    monkeypatch.setenv("ARK_API_KEY", "ark-test-key")
    monkeypatch.setenv("ARK_MODEL_ID", "doubao-test-model")

    assert apply_agentkit_model_replacement() is True

    model = models.BedrockModel(
        model_id="anthropic.claude",
        region_name="us-west-2",
        cache_prompt="default",
        max_tokens=128,
        context_window_limit=2048,
        stream=True,
    )

    assert type(model).__name__ == "AgentKitOpenAIModel"
    assert model.config["model_id"] == "doubao-test-model"
    assert model.config["params"] == {"max_tokens": 128}
    assert model.config["context_window_limit"] == 2048
    assert model.config["stream"] is True
    assert model.client_args == {
        "base_url": ARK_DEFAULT_BASE_URL,
        "api_key": "ark-test-key",
    }
    assert type(bedrock.BedrockModel()).__name__ == "AgentKitOpenAIModel"
    assert anthropic.AnthropicModel().config["model_id"] == "doubao-test-model"


def test_model_replacement_can_be_disabled(monkeypatch, caplog):
    monkeypatch.setenv("ARK_MODEL_REPLACEMENT", "off")
    monkeypatch.setenv("ARK_MODEL_ID", "doubao-target")
    monkeypatch.delenv("BEDROCK_MODEL_ID", raising=False)

    with caplog.at_level(logging.INFO, logger="agentkit.frameworks.model_replacement"):
        assert apply_agentkit_model_replacement() is False

    assert "BEDROCK_MODEL_ID" not in os.environ
    assert "AgentKit model replacement disabled" in "\n".join(
        record.getMessage() for record in caplog.records
    )


def test_model_replacement_requires_ark_model_id_for_patched_strands(monkeypatch):
    models, _, _ = _install_fake_strands(monkeypatch)
    monkeypatch.setenv("ARK_API_KEY", "ark-test-key")
    monkeypatch.delenv("ARK_MODEL_ID", raising=False)

    assert apply_agentkit_model_replacement() is True
    with pytest.raises(RuntimeError, match="ARK_MODEL_ID"):
        models.BedrockModel(model_id="anthropic.claude")


def test_model_replacement_requires_ark_api_key_for_patched_strands(monkeypatch):
    models, _, _ = _install_fake_strands(monkeypatch)
    monkeypatch.setenv("ARK_MODEL_ID", "doubao-test-model")
    monkeypatch.delenv("ARK_API_KEY", raising=False)

    assert apply_agentkit_model_replacement() is True
    with pytest.raises(RuntimeError, match="ARK_API_KEY"):
        models.BedrockModel(model_id="anthropic.claude")


def test_model_replacement_returns_false_when_no_alias_or_supported_model_class(monkeypatch):
    monkeypatch.delenv("ARK_MODEL_ID", raising=False)
    monkeypatch.setattr(
        module,
        "_agentkit_openai_model_cls",
        lambda: (_ for _ in ()).throw(ImportError("missing strands")),
    )

    assert apply_agentkit_model_replacement() is False


def test_model_replacement_patch_attr_reports_missing_targets():
    assert module._patch_model_attr("json", "missing_attr", object) is False
    assert module._patch_model_attr("definitely_missing_module", "x", object) is False
