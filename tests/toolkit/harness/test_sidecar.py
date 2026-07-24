from __future__ import annotations

import json
import os
import stat
import sys
import textwrap
from pathlib import Path

import pytest

from agentkit.toolkit.harness.sidecar import (
    HarnessSidecarError,
    HarnessSidecarRuntimeUnavailable,
    doctor_harness_sidecar,
    run_with_harness_sidecar,
    start_harness_sidecar,
)
from agentkit.toolkit.harness.sidecar_config import (
    HarnessSidecarConfig,
    SidecarBindingSpec,
)


@pytest.fixture
def fake_runtime(tmp_path: Path) -> Path:
    path = tmp_path / "fake_runtime.py"
    path.write_text(
        textwrap.dedent(
            """
            import json
            import signal
            import sys
            import time

            if sys.argv[1] == "doctor":
                print(json.dumps({"status": "ok", "internal_kernel": True}))
                raise SystemExit(0)

            config_path = sys.argv[sys.argv.index("--config") + 1]
            config = json.load(open(config_path, encoding="utf-8"))
            capture = __import__("os").environ.get("FAKE_RUNTIME_CAPTURE")
            if capture:
                open(capture, "w", encoding="utf-8").write(json.dumps(config))
            discovery = {
                "schema_version": "1",
                "status": "ok",
                "profile": config["profile"],
                "model_proxy": {"url": "http://127.0.0.1:18787/api/v3"},
                "mcp_gateway": {"urls": ["http://127.0.0.1:18899/metrics"]},
                "env": {
                    "MODEL_AGENT_API_BASE": "http://127.0.0.1:18787/api/v3",
                    "MCP_URLS": "http://127.0.0.1:18899/metrics",
                    "HARNESS_SIDECAR_ENABLED": "true",
                    "HARNESS_PROFILE": config["profile"],
                },
                "diagnostics": [],
            }
            print(json.dumps(discovery), flush=True)
            running = True
            def stop(*_args):
                global running
                running = False
            signal.signal(signal.SIGTERM, stop)
            signal.signal(signal.SIGINT, stop)
            while running:
                time.sleep(0.05)
            """
        ),
        encoding="utf-8",
    )
    return path


def _config(fake_runtime: Path) -> HarnessSidecarConfig:
    return HarnessSidecarConfig(
        profile="ops", runtime_command=[sys.executable, str(fake_runtime)]
    )


def test_start_applies_and_restores_binding_env(
    fake_runtime: Path, tmp_path: Path
) -> None:
    capture = tmp_path / "runtime-config.json"
    environ = {
        "MODEL_AGENT_API_BASE": "https://real-model/api/v3",
        "MCP_URLS": "https://real-mcp/metrics",
        "FAKE_RUNTIME_CAPTURE": str(capture),
    }
    binding = start_harness_sidecar(
        _config(fake_runtime), apply_env=True, environ=environ
    )
    try:
        assert binding.process is not None and binding.process.poll() is None
        assert environ["MODEL_AGENT_API_BASE"].startswith("http://127.0.0.1")
        assert environ["MCP_URLS"].endswith("/metrics")
        assert stat.S_IMODE(binding.config_path.stat().st_mode) == 0o600
        runtime_config = json.loads(capture.read_text(encoding="utf-8"))
        assert runtime_config["profile"] == "ops"
        assert "runtime_command" not in runtime_config
    finally:
        binding.stop()
    assert environ["MODEL_AGENT_API_BASE"] == "https://real-model/api/v3"
    assert environ["MCP_URLS"] == "https://real-mcp/metrics"
    assert binding.config_path.exists() is False


def test_runtime_process_env_is_separate_from_binding_target(
    fake_runtime: Path,
) -> None:
    target_env = {"ORIGINAL": "target"}
    runtime_env = {"ORIGINAL": "runtime"}

    binding = start_harness_sidecar(
        _config(fake_runtime),
        apply_env=True,
        environ=target_env,
        process_env=runtime_env,
    )
    try:
        assert target_env["ORIGINAL"] == "target"
        assert target_env["MODEL_AGENT_API_BASE"].startswith("http://127.0.0.1")
    finally:
        binding.stop()


def test_run_wraps_child_with_sidecar_environment(
    fake_runtime: Path, tmp_path: Path
) -> None:
    output = tmp_path / "child-env.json"
    child = tmp_path / "child.py"
    child.write_text(
        "import json, os, sys; "
        "json.dump({'model': os.getenv('MODEL_AGENT_API_BASE'), "
        "'mcp': os.getenv('MCP_URLS')}, open(sys.argv[1], 'w'))",
        encoding="utf-8",
    )

    exit_code = run_with_harness_sidecar(
        _config(fake_runtime), [sys.executable, str(child), str(output)]
    )

    assert exit_code == 0
    values = json.loads(output.read_text(encoding="utf-8"))
    assert values["model"] == "http://127.0.0.1:18787/api/v3"
    assert values["mcp"] == "http://127.0.0.1:18899/metrics"


def test_doctor_uses_product_runtime_entrypoint(fake_runtime: Path) -> None:
    report = doctor_harness_sidecar(_config(fake_runtime))

    assert report == {"status": "ok", "internal_kernel": True}


def test_missing_runtime_has_customer_facing_install_hint(monkeypatch) -> None:
    monkeypatch.delenv("AGENTKIT_HARNESS_RUNTIME_COMMAND", raising=False)
    monkeypatch.setattr("shutil.which", lambda _name: None)

    with pytest.raises(
        HarnessSidecarRuntimeUnavailable,
        match=r"agentkit-sdk-python\[harness-sidecar\]",
    ):
        start_harness_sidecar({"profile": "ops"})


def test_run_fails_open_to_direct_child(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output = tmp_path / "direct.txt"
    monkeypatch.delenv("AGENTKIT_HARNESS_RUNTIME_COMMAND", raising=False)
    monkeypatch.setattr("shutil.which", lambda _name: None)

    with pytest.warns(RuntimeWarning, match="running command directly"):
        exit_code = run_with_harness_sidecar(
            {"profile": "ops", "fail_open": True},
            [sys.executable, "-c", f"open({str(output)!r}, 'w').write('ok')"],
        )

    assert exit_code == 0
    assert output.read_text(encoding="utf-8") == "ok"


def test_run_fails_open_when_runtime_discovery_is_invalid(tmp_path: Path) -> None:
    runtime = tmp_path / "invalid-runtime.py"
    runtime.write_text("print('not-json', flush=True)", encoding="utf-8")
    output = tmp_path / "direct-after-invalid-runtime.txt"

    with pytest.warns(RuntimeWarning, match="running command directly"):
        exit_code = run_with_harness_sidecar(
            {
                "profile": "ops",
                "fail_open": True,
                "runtime_command": [sys.executable, str(runtime)],
            },
            [sys.executable, "-c", f"open({str(output)!r}, 'w').write('ok')"],
        )

    assert exit_code == 0
    assert output.read_text(encoding="utf-8") == "ok"


def test_doctor_has_a_bounded_timeout(tmp_path: Path) -> None:
    runtime = tmp_path / "slow-runtime.py"
    runtime.write_text("import time; time.sleep(30)", encoding="utf-8")

    with pytest.raises(HarnessSidecarError, match="doctor timed out"):
        doctor_harness_sidecar(
            {
                "runtime_command": [sys.executable, str(runtime)],
                "startup_timeout_seconds": 0.1,
            }
        )


def test_discovery_v2_reports_product_activation_state() -> None:
    spec = SidecarBindingSpec.from_discovery(
        {
            "schema_version": "agentkit.harness-sidecar.discovery/v2",
            "status": "degraded",
            "profile": "ops",
            "requested_components": ["context_engine", "verifier"],
            "effective_components": ["context_engine", "verifier"],
            "active_components": ["context_engine"],
            "failed_components": ["verifier"],
            "endpoints": {"model_proxy_url": "http://127.0.0.1:18787/api/v3"},
            "runtime": {
                "installed_internal_components": [
                    "runtime_core",
                    "ops",
                    "goal_runtime",
                    "model_proxy",
                ]
            },
            "plan_hash": "sha256:test",
        }
    )

    assert spec.model_proxy_url == "http://127.0.0.1:18787/api/v3"
    assert spec.requested_components == ["context_engine", "verifier"]
    assert spec.effective_components == ["context_engine", "verifier"]
    assert spec.active_components == ["context_engine"]
    assert spec.failed_components == ["verifier"]
    assert spec.runtime_components == [
        "runtime_core",
        "ops",
        "goal_runtime",
        "model_proxy",
    ]
    assert spec.plan_hash == "sha256:test"
