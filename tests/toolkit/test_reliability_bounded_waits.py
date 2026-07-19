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

"""Regression tests for the three unbounded-wait reliability fixes.

Each of these sites could previously hang the CLI forever:

- ``VeCR.create_instance``: ``while True`` status poll with no deadline.
- ``VeAgentkitRuntimeRunner._wait_for_runtime_status_multiple``: ``timeout=None``
  made the deadline check dead code, so the poll could run forever.
- ``agentkit.utils.http_defaults``: new env-tunable bounds shared by the above
  and by the interactive websocket keepalive.

The tests stub ``time`` and the network layer so they run offline and fast.
"""

from __future__ import annotations

import pytest

from agentkit.utils import http_defaults


# --------------------------------------------------------------------------- #
# http_defaults: new bounded-wait knobs
# --------------------------------------------------------------------------- #
class TestHttpDefaults:
    def test_poll_timeout_default(self, monkeypatch):
        monkeypatch.delenv(http_defaults.ENV_POLL_TIMEOUT, raising=False)
        assert http_defaults.poll_timeout() == http_defaults.DEFAULT_POLL_TIMEOUT

    def test_poll_timeout_env_override(self, monkeypatch):
        monkeypatch.setenv(http_defaults.ENV_POLL_TIMEOUT, "42")
        assert http_defaults.poll_timeout() == 42.0

    def test_poll_timeout_clamps_floor_and_ignores_garbage(self, monkeypatch):
        monkeypatch.setenv(http_defaults.ENV_POLL_TIMEOUT, "0")
        assert http_defaults.poll_timeout() == 1.0
        monkeypatch.setenv(http_defaults.ENV_POLL_TIMEOUT, "not-a-number")
        assert http_defaults.poll_timeout() == http_defaults.DEFAULT_POLL_TIMEOUT

    def test_ws_ping_timeout_forced_below_interval(self, monkeypatch):
        # A pong-wait >= ping interval is illegal for websocket-client; it must
        # be clamped strictly below the interval.
        monkeypatch.setenv(http_defaults.ENV_WS_PING_INTERVAL, "20")
        monkeypatch.setenv(http_defaults.ENV_WS_PING_TIMEOUT, "30")
        interval = http_defaults.ws_ping_interval()
        timeout = http_defaults.ws_ping_timeout()
        assert timeout < interval
        assert timeout == 19.0

    def test_ws_ping_defaults(self, monkeypatch):
        monkeypatch.delenv(http_defaults.ENV_WS_PING_INTERVAL, raising=False)
        monkeypatch.delenv(http_defaults.ENV_WS_PING_TIMEOUT, raising=False)
        assert (
            http_defaults.ws_ping_interval() == http_defaults.DEFAULT_WS_PING_INTERVAL
        )
        assert http_defaults.ws_ping_timeout() == http_defaults.DEFAULT_WS_PING_TIMEOUT
        assert http_defaults.ws_ping_timeout() < http_defaults.ws_ping_interval()


# --------------------------------------------------------------------------- #
# cr.py: create_instance polling is now deadline-bounded
# --------------------------------------------------------------------------- #
class TestCrCreateInstanceDeadline:
    def _make_cr(self, monkeypatch):
        from agentkit.toolkit.volcengine import cr as cr_mod

        monkeypatch.setattr(
            cr_mod, "resolve_endpoint", lambda *a, **k: "https://cr.example"
        )
        instance = cr_mod.VeCR.__new__(cr_mod.VeCR)
        instance.config = object()
        instance.region = "cn-beijing"
        instance._endpoint = "https://cr.example"
        return cr_mod, instance

    def test_create_instance_times_out_instead_of_hanging(self, monkeypatch):
        cr_mod, cr = self._make_cr(monkeypatch)

        # Fresh instance path: _check_instance says NONEXIST first, create
        # succeeds, then status is stuck at "Creating" forever.
        checks = ["NONEXIST"]

        def fake_check(_name):
            return checks.pop(0) if checks else "Creating"

        monkeypatch.setattr(cr, "_check_instance", fake_check)
        monkeypatch.setattr(
            cr,
            "_ve_request",
            lambda **kw: {"ResponseMetadata": {}},
        )

        # Deterministic clock: each monotonic() call advances 60s so the
        # deadline is crossed quickly; sleep is a no-op.
        clock = {"t": 0.0}

        def fake_monotonic():
            clock["t"] += 60.0
            return clock["t"]

        monkeypatch.setattr(cr_mod.time, "monotonic", fake_monotonic)
        monkeypatch.setattr(cr_mod.time, "sleep", lambda *_a: None)
        monkeypatch.setenv(http_defaults.ENV_POLL_TIMEOUT, "120")

        with pytest.raises(TimeoutError) as exc:
            cr._create_instance("stuck-instance", instance_type="Micro")
        assert "did not reach Running" in str(exc.value)

    def test_create_instance_returns_on_running(self, monkeypatch):
        cr_mod, cr = self._make_cr(monkeypatch)
        statuses = iter(["NONEXIST", "Creating", "Running"])
        monkeypatch.setattr(cr, "_check_instance", lambda _n: next(statuses))
        monkeypatch.setattr(cr, "_ve_request", lambda **kw: {"ResponseMetadata": {}})
        monkeypatch.setattr(cr_mod.time, "sleep", lambda *_a: None)
        assert (
            cr._create_instance("ok-instance", instance_type="Micro") == "ok-instance"
        )


# --------------------------------------------------------------------------- #
# ve_agentkit.py: wait loop is bounded even when timeout=None
# --------------------------------------------------------------------------- #
class TestRuntimeWaitBounded:
    def test_none_timeout_falls_back_to_poll_bound(self, monkeypatch):
        from agentkit.toolkit.runners import ve_agentkit as va

        runner = va.VeAgentkitRuntimeRunner.__new__(va.VeAgentkitRuntimeRunner)

        # Runtime never reaches target; with the old code (timeout=None) this
        # loop would spin forever. Now it must exit via the poll-timeout bound.
        class _Runtime:
            status = "Creating"

        monkeypatch.setattr(va, "retry", lambda fn: _Runtime())
        monkeypatch.setattr(runner, "_get_runtime_client", lambda region: object())

        # Progress reporter context manager stub.
        class _Task:
            def update(self, *a, **k):
                pass

        class _LongTask:
            def __enter__(self):
                return _Task()

            def __exit__(self, *a):
                return False

        class _Reporter:
            def long_task(self, *a, **k):
                return _LongTask()

            def success(self, *a, **k):
                pass

        runner.reporter = _Reporter()

        # Deterministic clock advancing 500s per reading; sleep no-op.
        ticks = iter([0.0] + [500.0 * i for i in range(1, 100)])
        monkeypatch.setattr(va.time, "time", lambda: next(ticks))
        monkeypatch.setattr(va.time, "sleep", lambda *_a: None)
        monkeypatch.setenv(http_defaults.ENV_POLL_TIMEOUT, "300")

        ok, runtime, err = runner._wait_for_runtime_status_multiple(
            runtime_id="rt-1",
            target_statuses=["Running"],
            task_description="waiting",
            timeout=None,
        )
        assert ok is False
        assert err is not None and "timeout" in err.lower()
