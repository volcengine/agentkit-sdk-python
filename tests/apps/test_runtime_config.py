import json

import pytest

from agentkit.apps.agent_server_app.diagnostics import runtime_attributes
from agentkit.apps.agent_server_app.runtime_config import runtime_config_attributes


def test_execution_uses_process_config_and_fingerprint(monkeypatch):
    monkeypatch.setenv("MODEL_AGENT_CLIENT_REQ_ID", "agentkit/r-test")
    monkeypatch.setenv("_FAAS_REVISION_NUMBER", "8")
    config = {
        "schema_version": 1,
        "cpu_milli": 2000,
        "memory_mb": 4096,
        "max_concurrency": 8,
        "target_type": "latest",
    }
    monkeypatch.setenv("AGENTKIT_RUNTIME_DIAGNOSTIC_CONFIG", json.dumps(config))
    first = runtime_attributes()
    assert first["agentkit.runtime.config.cpu_milli"] == 2000
    assert first["agentkit.runtime.config.memory_mb"] == 4096
    assert first["agentkit.runtime.config.max_concurrency"] == 8
    assert first["agentkit.runtime.target.type"] == "latest"
    assert first["faas.version"] == "8"
    assert "agentkit.runtime.version.id" not in first
    config["cpu_milli"] = 4000
    config["target_type"] = "formal"
    monkeypatch.setenv("AGENTKIT_RUNTIME_DIAGNOSTIC_CONFIG", json.dumps(config))
    second = runtime_attributes()
    assert (
        second["agentkit.runtime.config.fingerprint"]
        != first["agentkit.runtime.config.fingerprint"]
    )
    assert first["agentkit.runtime.config.cpu_milli"] == 2000
    assert second["agentkit.runtime.target.type"] == "formal"


def test_canonical_fingerprint_and_no_default_values(monkeypatch):
    monkeypatch.setenv(
        "AGENTKIT_RUNTIME_DIAGNOSTIC_CONFIG",
        '{"schema_version":1,"cpu_milli":2000,"memory_mb":4096}',
    )
    first = runtime_config_attributes()
    monkeypatch.setenv(
        "AGENTKIT_RUNTIME_DIAGNOSTIC_CONFIG",
        '{"memory_mb":4096,"cpu_milli":2000,"schema_version":1,"target_type":"formal"}',
    )
    second = runtime_config_attributes()
    assert (
        first["agentkit.runtime.config.fingerprint"]
        == second["agentkit.runtime.config.fingerprint"]
    )
    assert "agentkit.runtime.config.max_concurrency" not in first
    monkeypatch.setenv("AGENTKIT_RUNTIME_DIAGNOSTIC_CONFIG", '{"schema_version":1}')
    assert runtime_config_attributes() == {}


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "{",
        "[]",
        "null",
        "1",
        '"text"',
        '{"schema_version":true}',
        '{"schema_version":2}',
        "{}",
        '{"schema_version":1,"cpu_milli":0}',
        '{"schema_version":1,"cpu_milli":-1}',
        '{"schema_version":1,"cpu_milli":true}',
        '{"schema_version":1,"memory_mb":1.5}',
        '{"schema_version":1,"max_concurrency":"8"}',
        '{"schema_version":1,"cpu_milli":2147483648}',
        '{"schema_version":1,"target_type":"preview"}',
        '{"schema_version":1,"target_type":[]}',
        '{"schema_version":1,"target_type":null}',
        '{"schema_version":1,"cpu_milli":1,"cpu_milli":2}',
        '{"schema_version":1,"API_KEY":"must-not-escape"}',
        '{"schema_version":1,"cpu_milli":NaN}',
        '{"schema_version":1,"cpu_milli":Infinity}',
        '{"schema_version":1,"cpu_milli":{}}',
        "[" * 500 + "]" * 500,
        "x" * 1025,
    ],
)
def test_invalid_metadata_is_not_recorded(monkeypatch, raw):
    monkeypatch.setenv("AGENTKIT_RUNTIME_DIAGNOSTIC_CONFIG", raw)
    assert runtime_config_attributes() == {}


def test_config_cannot_create_runtime_identity(monkeypatch):
    monkeypatch.delenv("MODEL_AGENT_CLIENT_REQ_ID", raising=False)
    monkeypatch.setenv(
        "AGENTKIT_RUNTIME_DIAGNOSTIC_CONFIG", '{"schema_version":1,"cpu_milli":2000}'
    )
    assert runtime_attributes() == {}


@pytest.mark.parametrize(
    "function_id", ["function-a", "vefaas-cn-beijing-test_02", "func.0:1"]
)
def test_native_function_id_is_recorded_with_runtime_identity(monkeypatch, function_id):
    monkeypatch.setenv("MODEL_AGENT_CLIENT_REQ_ID", "agentkit/r-test")
    monkeypatch.setenv("_FAAS_FUNC_ID", function_id)
    assert runtime_attributes()["agentkit.runtime.function.id"] == function_id
    monkeypatch.delenv("MODEL_AGENT_CLIENT_REQ_ID")
    assert runtime_attributes() == {}


@pytest.mark.parametrize(
    "function_id", ["", " bad", "bad ", "bad\n", "a/b", "https://x", "_bad", "a" * 129]
)
def test_invalid_native_function_id_is_omitted(monkeypatch, function_id):
    monkeypatch.setenv("MODEL_AGENT_CLIENT_REQ_ID", "agentkit/r-test")
    monkeypatch.setenv("_FAAS_FUNC_ID", function_id)
    assert "agentkit.runtime.function.id" not in runtime_attributes()
