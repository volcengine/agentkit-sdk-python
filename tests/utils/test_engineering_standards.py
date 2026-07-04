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

"""Offline unit tests for the engineering-standards refactor.

Covers the three foundations applied to the inner HTTP/credential loop:

* ``ve_sign._signed_request`` transient-retry + transport-error wrapping
  (connection errors retried to the budget then wrapped as ``NetworkError``
  with the original cause chained; read timeouts surfaced, not retried;
  ``AGENTKIT_HTTP_RETRIES=0`` disables retries).
* ``utils.http_defaults`` env parsing/clamping.
* ``RedactionFilter`` scrubbing of JWT / ak-sk / opaque tokens from a
  ``logging.LogRecord``.

No network is performed: ``requests.request`` and ``time.sleep`` are
monkeypatched.
"""

from __future__ import annotations

import logging

import pytest
import requests

from agentkit.auth.errors import NetworkError
from agentkit.utils import http_defaults, ve_sign
from agentkit.utils.logging_config import RedactionFilter
from agentkit.utils.redact import redact


# --------------------------------------------------------------------------- #
# ve_sign._signed_request
# --------------------------------------------------------------------------- #


@pytest.fixture
def no_sleep(monkeypatch):
    """Make the retry backoff instantaneous."""
    monkeypatch.setattr(ve_sign.time, "sleep", lambda _seconds: None)


def _count_request(monkeypatch, exc_factory):
    """Patch the shared session's ``request`` to always raise; return an
    attempt counter. (``_signed_request`` goes through ``ve_sign._session``
    for connection pooling, so that is the seam to patch.)"""
    counter = {"attempts": 0}

    def _fake_request(**_kwargs):
        counter["attempts"] += 1
        raise exc_factory()

    monkeypatch.setattr(ve_sign._session, "request", _fake_request)
    return counter


def test_signed_request_retries_connection_error_to_budget_then_networkerror(
    monkeypatch, no_sleep
):
    monkeypatch.setenv(http_defaults.ENV_HTTP_RETRIES, "2")
    counter = _count_request(
        monkeypatch, lambda: requests.ConnectionError("connection refused")
    )

    with pytest.raises(NetworkError) as excinfo:
        ve_sign._signed_request("POST", "https://example.invalid", {}, {}, "")

    # retries=2 -> 1 initial attempt + 2 retries = 3 total attempts.
    assert counter["attempts"] == 3
    # Original transport error is chained, not swallowed.
    assert isinstance(excinfo.value.__cause__, requests.ConnectionError)
    # The domain message must not leak the underlying request/secret payload.
    assert "connection refused" not in str(excinfo.value)


def test_signed_request_read_timeout_not_retried(monkeypatch, no_sleep):
    monkeypatch.setenv(http_defaults.ENV_HTTP_RETRIES, "2")
    counter = _count_request(
        monkeypatch, lambda: requests.ReadTimeout("read timed out")
    )

    with pytest.raises(NetworkError) as excinfo:
        ve_sign._signed_request("POST", "https://example.invalid", {}, {}, "")

    # Read timeouts may have been processed by a non-idempotent action, so a
    # single attempt is made and the error is surfaced, never retried.
    assert counter["attempts"] == 1
    assert isinstance(excinfo.value.__cause__, requests.ReadTimeout)


def test_signed_request_retries_zero_means_single_attempt(monkeypatch, no_sleep):
    monkeypatch.setenv(http_defaults.ENV_HTTP_RETRIES, "0")
    counter = _count_request(
        monkeypatch, lambda: requests.ConnectionError("connection refused")
    )

    with pytest.raises(NetworkError):
        ve_sign._signed_request("POST", "https://example.invalid", {}, {}, "")

    assert counter["attempts"] == 1


def test_retry_after_is_capped_and_sanitized():
    """Server-provided Retry-After must be capped (a misconfigured/hostile
    server saying 3600 must not stall the client for an hour) and invalid
    values must be ignored."""

    class _Resp:
        def __init__(self, value):
            self.headers = {} if value is None else {"Retry-After": value}

    assert ve_sign._retry_after_seconds(_Resp("5")) == 5.0
    assert ve_sign._retry_after_seconds(_Resp("3600")) == ve_sign._RETRY_AFTER_CAP
    assert ve_sign._retry_after_seconds(_Resp("-1")) == 0.0
    assert ve_sign._retry_after_seconds(_Resp("not-a-number")) is None
    assert ve_sign._retry_after_seconds(_Resp(None)) is None


# --------------------------------------------------------------------------- #
# http_defaults env clamping
# --------------------------------------------------------------------------- #


def test_http_timeout_default(monkeypatch):
    monkeypatch.delenv(http_defaults.ENV_HTTP_TIMEOUT, raising=False)
    assert http_defaults.http_timeout() == 30.0


def test_http_timeout_clamped_to_floor(monkeypatch):
    monkeypatch.setenv(http_defaults.ENV_HTTP_TIMEOUT, "0")
    assert http_defaults.http_timeout() == 1.0


def test_http_timeout_invalid_falls_back_to_default(monkeypatch):
    monkeypatch.setenv(http_defaults.ENV_HTTP_TIMEOUT, "not-a-number")
    assert http_defaults.http_timeout() == http_defaults.DEFAULT_HTTP_TIMEOUT


def test_http_retries_clamped_non_negative(monkeypatch):
    monkeypatch.setenv(http_defaults.ENV_HTTP_RETRIES, "-5")
    assert http_defaults.http_retries() == 0


def test_http_retries_invalid_falls_back_to_default(monkeypatch):
    monkeypatch.setenv(http_defaults.ENV_HTTP_RETRIES, "abc")
    assert http_defaults.http_retries() == http_defaults.DEFAULT_HTTP_RETRIES


def test_http_retries_honors_valid_value(monkeypatch):
    monkeypatch.setenv(http_defaults.ENV_HTTP_RETRIES, "4")
    assert http_defaults.http_retries() == 4


def test_stream_timeout_default_and_clamp(monkeypatch):
    monkeypatch.delenv(http_defaults.ENV_STREAM_TIMEOUT, raising=False)
    assert http_defaults.stream_timeout() == 300.0
    monkeypatch.setenv(http_defaults.ENV_STREAM_TIMEOUT, "0.1")
    assert http_defaults.stream_timeout() == 1.0


# --------------------------------------------------------------------------- #
# RedactionFilter
# --------------------------------------------------------------------------- #


def _record(msg, *args):
    return logging.LogRecord(
        name="agentkit.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=args,
        exc_info=None,
    )


def test_redaction_filter_scrubs_jwt():
    secret = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.s1gn4tur3_padding_xyz"
    record = _record("auth header token=%s end", secret)

    assert RedactionFilter().filter(record) is True
    out = record.getMessage()
    assert secret not in out
    assert "***" in out
    # Lazy %-args must be cleared so a downstream formatter cannot re-expand them.
    assert record.args == ()


def test_redaction_filter_scrubs_ak_sk_field():
    record = _record('{"secret_access_key": "AKLTabcdefgh1234567890ZZ"}')

    RedactionFilter().filter(record)
    out = record.getMessage()
    assert "AKLTabcdefgh1234567890ZZ" not in out
    assert "***" in out


def test_redaction_filter_scrubs_opaque_token():
    opaque = "abcdefghijklmnopqrstuvwxyz0123456789"
    record = _record("bearer %s", opaque)

    RedactionFilter().filter(record)
    out = record.getMessage()
    assert opaque not in out
    assert "***" in out


def test_redaction_preserves_identifier_shapes():
    # UUIDs, OTel trace ids, git shas, paths, long words and long numbers are
    # what error logs are made of — scrubbing them makes logs undebuggable.
    line = (
        "request_id=550e8400-e29b-41d4-a716-446655440000 "
        "trace_id=4bf92f3577b34da6a3ce929d0e0e4736 "
        "commit=3f785ee19b9a44f2a2b1e2f4c0deadbeefcafe12 "
        "path=/var/log/agentkit/agent-server-2026.log "
        "word=internationalization_configuration id=123456789012345678901234"
    )
    assert redact(line) == line


def test_redaction_still_scrubs_unlabeled_token_material():
    # Mixed alpha+digit, 20+ chars, no identifier shape — and deliberately not
    # in any real vendor key format (GitHub push protection scans fixtures).
    token = "b64secretQWxhZGRpbjpvcGVuc2VzYW1lMjAyNg"
    out = redact(f"request failed with {token}")
    assert token not in out
    assert "***" in out
