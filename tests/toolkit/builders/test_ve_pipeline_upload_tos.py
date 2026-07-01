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

"""Behavioral guards for ``VeCPCRBuilder._upload_to_tos``.

This method is security-critical: before uploading source code (which can
contain secrets) it verifies via ListBuckets that the target TOS bucket is
owned by the current account, and it maps low-level TOS/service errors into
actionable, non-leaky messages. These tests exercise the real branch logic by
substituting a hand-rolled ``_FakeTOSService`` for the lazily-imported
``agentkit.toolkit.volcengine.services.tos_service.TOSService`` symbol, matching
the exact method surface the production code calls:

  - ``bucket_exists()``          -> bool
  - ``create_bucket()``          -> raises tos.exceptions.TosServerError on conflict
  - ``bucket_is_owned(name)``    -> bool  (ListBuckets ownership gate)
  - ``get_bucket_location(name)``-> Optional[str]
  - ``upload_file(path, key)``   -> str (URL)
  - ``generate_bucket_name()``   -> staticmethod
  - ``.config`` (has a mutable ``.bucket`` attr) and ``.actual_region``

``time.sleep`` is patched so the eventual-consistency polling loops never wait.
"""

from __future__ import annotations

import pytest

import tos.exceptions as _tos_exceptions
from agentkit.toolkit.builders.ve_pipeline import VeCPCRBuilder, VeCPCRBuilderConfig

# Source module where _upload_to_tos performs its lazy import; this is the
# symbol we must replace so the fake is picked up.
_TOS_MODULE = "agentkit.toolkit.volcengine.services.tos_service"

# A secret-shaped token we inject into low-level error strings to prove the
# mapped, user-facing messages never echo raw response contents / credentials.
_SECRET_MARKER = "AKLTsecret-do-not-leak-1234567890"


def _make_tos_server_error(status_code: int, message: str = "conflict") -> _tos_exceptions.TosServerError:
    """Build a genuine ``tos.exceptions.TosServerError`` with a chosen status.

    The real constructor reads ``request_id``, ``headers`` and ``status`` off a
    response object, so we hand it a minimal fake response. The result is a true
    instance (isinstance passes) with a working ``__str__``.
    """

    class _FakeResp:
        def __init__(self, status: int) -> None:
            self.request_id = "req-fake"
            self.headers = {}
            self.status = status

    return _tos_exceptions.TosServerError(
        _FakeResp(status_code), message, "Conflict", "host-fake", "resource-fake"
    )


class _FakeTOSService:
    """Stand-in for the real TOSService with recorded, scriptable behavior.

    Class-level knobs let each test script the outcome of every collaborator
    method the production code touches. Instances record their calls so tests
    can assert *which* methods ran (e.g. that ``upload_file`` was NEVER reached
    when ownership verification failed).
    """

    # ---- scriptable behavior (reset by the autouse fixture) -----------------
    bucket_exists_returns = True
    bucket_exists_raises: Exception | None = None
    create_bucket_raises: Exception | None = None
    bucket_is_owned_returns = True
    bucket_is_owned_raises: Exception | None = None
    get_bucket_location_returns: str | None = None
    upload_file_returns = "https://bucket.tos-cn-beijing.volces.com/agentkit-builds/app.tar.gz"
    generated_names: list[str] = ["auto-generated-bucket"]

    # ---- recorded calls (reset by the autouse fixture) ----------------------
    instances: list["_FakeTOSService"] = []

    def __init__(self, config, provider=None):
        self.config = config
        self.provider = provider
        # Mirror the real service attribute used for region resolution.
        self.actual_region = getattr(config, "region", "") or "cn-beijing"
        self.calls: list[tuple] = []
        type(self).instances.append(self)

    # generate_bucket_name is a *staticmethod* on the real class and is called
    # as TOSService.generate_bucket_name(); model it the same way.
    _name_cursor = 0

    @staticmethod
    def generate_bucket_name(prefix: str = "agentkit") -> str:
        names = _FakeTOSService.generated_names
        idx = min(_FakeTOSService._name_cursor, len(names) - 1)
        _FakeTOSService._name_cursor += 1
        return names[idx]

    def bucket_exists(self) -> bool:
        self.calls.append(("bucket_exists", self.config.bucket))
        if self.bucket_exists_raises is not None:
            raise self.bucket_exists_raises
        return self.bucket_exists_returns

    def create_bucket(self) -> bool:
        self.calls.append(("create_bucket", self.config.bucket))
        if self.create_bucket_raises is not None:
            raise self.create_bucket_raises
        return True

    def bucket_is_owned(self, bucket_name=None) -> bool:
        self.calls.append(("bucket_is_owned", bucket_name))
        if self.bucket_is_owned_raises is not None:
            raise self.bucket_is_owned_raises
        return self.bucket_is_owned_returns

    def get_bucket_location(self, bucket_name=None):
        self.calls.append(("get_bucket_location", bucket_name))
        return self.get_bucket_location_returns

    def upload_file(self, local_path: str, object_key: str) -> str:
        self.calls.append(("upload_file", local_path, object_key))
        return self.upload_file_returns


@pytest.fixture(autouse=True)
def _reset_fake_state(monkeypatch):
    """Reset all class-level fake state and neutralize sleeps for each test."""
    _FakeTOSService.bucket_exists_returns = True
    _FakeTOSService.bucket_exists_raises = None
    _FakeTOSService.create_bucket_raises = None
    _FakeTOSService.bucket_is_owned_returns = True
    _FakeTOSService.bucket_is_owned_raises = None
    _FakeTOSService.get_bucket_location_returns = None
    _FakeTOSService.upload_file_returns = (
        "https://bucket.tos-cn-beijing.volces.com/agentkit-builds/app.tar.gz"
    )
    _FakeTOSService.generated_names = ["auto-generated-bucket"]
    _FakeTOSService._name_cursor = 0
    _FakeTOSService.instances = []

    # The polling loops call time.sleep; patch the module-level import in the
    # tos_service source is not where sleep lives -- _upload_to_tos does
    # `import time` locally, so patch time.sleep globally.
    import time as _time

    monkeypatch.setattr(_time, "sleep", lambda *_a, **_k: None)
    yield


def _install_fake_tos(monkeypatch):
    """Patch the TOSService symbol at its source module path."""
    monkeypatch.setattr(f"{_TOS_MODULE}.TOSService", _FakeTOSService)


def _make_config(**overrides) -> VeCPCRBuilderConfig:
    """Build a config with a concrete (rendered) bucket by default.

    ``__post_init__`` renders template fields, so we must pass an already-valid
    bucket name and mutate it afterwards if a test needs an unrendered one.
    """
    params = dict(
        tos_bucket="my-real-bucket",
        tos_region="cn-beijing",
        tos_prefix="agentkit-builds",
    )
    params.update(overrides)
    return VeCPCRBuilderConfig(**params)


# ---------------------------------------------------------------------------
# Ownership gate: bucket exists but is NOT owned by the current account.
# ---------------------------------------------------------------------------

def test_upload_blocked_when_bucket_not_owned_by_current_account(monkeypatch, tmp_path):
    _install_fake_tos(monkeypatch)
    archive = tmp_path / "app.tar.gz"
    archive.write_bytes(b"payload")

    # User-specified bucket that DOES exist (so no create attempt) but is NOT
    # in the current account's ListBuckets result.
    _FakeTOSService.bucket_exists_returns = True
    _FakeTOSService.bucket_is_owned_returns = False

    builder = VeCPCRBuilder()
    config = _make_config(tos_bucket="someone-elses-bucket")

    with pytest.raises(Exception) as excinfo:
        builder._upload_to_tos(str(archive), config)

    msg = str(excinfo.value)
    # Security notice message from L1026-1032.
    assert "is not owned by the current account" in msg
    assert "someone-elses-bucket" in msg

    # The gate must fire BEFORE any upload: upload_file must never run.
    svc = _FakeTOSService.instances[-1]
    called_methods = [c[0] for c in svc.calls]
    assert "bucket_is_owned" in called_methods
    assert "upload_file" not in called_methods


# ---------------------------------------------------------------------------
# Cross-region conflict: name taken (409, not created here) but owned, and it
# lives in a different region than the one currently targeted.
# ---------------------------------------------------------------------------

def test_cross_region_bucket_conflict_raises_region_scoped_error(monkeypatch, tmp_path):
    _install_fake_tos(monkeypatch)
    archive = tmp_path / "app.tar.gz"
    archive.write_bytes(b"payload")

    # Bucket does not exist in the current region -> attempt create -> 409
    # conflict -> name_conflict_not_created=True; ownership check passes;
    # location resolves to a *different* region.
    _FakeTOSService.bucket_exists_returns = False
    _FakeTOSService.create_bucket_raises = _make_tos_server_error(409)
    _FakeTOSService.bucket_is_owned_returns = True
    _FakeTOSService.get_bucket_location_returns = "cn-shanghai"

    builder = VeCPCRBuilder()
    config = _make_config(tos_bucket="regional-bucket", tos_region="cn-beijing")

    with pytest.raises(Exception) as excinfo:
        builder._upload_to_tos(str(archive), config)

    msg = str(excinfo.value)
    # Conflict/region-scoped message from L1040-1046.
    assert "regional-bucket" in msg
    assert "cn-shanghai" in msg
    assert "cannot be accessed across regions" in msg

    # Upload must not have happened for a bucket we cannot reach.
    svc = _FakeTOSService.instances[-1]
    assert "upload_file" not in [c[0] for c in svc.calls]


def test_owned_conflict_without_location_raises_generic_region_error(monkeypatch, tmp_path):
    _install_fake_tos(monkeypatch)
    archive = tmp_path / "app.tar.gz"
    archive.write_bytes(b"payload")

    # Same as above but location lookup returns None -> the else branch
    # (L1048-1053) fires instead of the specific-region message.
    _FakeTOSService.bucket_exists_returns = False
    _FakeTOSService.create_bucket_raises = _make_tos_server_error(409)
    _FakeTOSService.bucket_is_owned_returns = True
    _FakeTOSService.get_bucket_location_returns = None

    builder = VeCPCRBuilder()
    config = _make_config(tos_bucket="regional-bucket", tos_region="cn-beijing")

    with pytest.raises(Exception) as excinfo:
        builder._upload_to_tos(str(archive), config)

    msg = str(excinfo.value)
    assert "does not exist" in msg
    assert "cannot be accessed across regions" in msg
    assert "cn-beijing" in msg


# ---------------------------------------------------------------------------
# Error-string mapping in the except tail (L1091-1120).
# ---------------------------------------------------------------------------

def test_account_disable_error_is_mapped_to_enable_services_message(monkeypatch, tmp_path):
    _install_fake_tos(monkeypatch)
    archive = tmp_path / "app.tar.gz"
    archive.write_bytes(b"payload")

    # A user-specified bucket whose accessibility check raises a plain
    # Exception (NOT a TosServerError, so it is not swallowed by the inner
    # handler) carrying the AccountDisable signature plus a fake secret.
    inner = Exception(
        f"ServiceError code=AccountDisable token={_SECRET_MARKER} raw-response-body"
    )
    _FakeTOSService.bucket_exists_raises = inner

    builder = VeCPCRBuilder()
    config = _make_config(tos_bucket="user-bucket", tos_region="cn-beijing")

    with pytest.raises(Exception) as excinfo:
        builder._upload_to_tos(str(archive), config)

    msg = str(excinfo.value)
    # L1112-1115 message: enable TOS + include the enable-services console URL.
    assert "Tos Service is not enabled" in msg
    assert "Enable services at:" in msg
    # Provider-independent: the console host differs by cloud provider
    # (volcengine vs byteplus), and provider global state can leak across the
    # full suite; assert the invariant enable-URL shape, not a specific host.
    assert "https://console." in msg and "/agentkit" in msg
    # No secret / raw-response leakage into the user-facing message.
    assert _SECRET_MARKER not in msg
    assert "raw-response-body" not in msg


def test_account_disable_url_honors_region_hint_from_config(monkeypatch, tmp_path):
    _install_fake_tos(monkeypatch)
    archive = tmp_path / "app.tar.gz"
    archive.write_bytes(b"payload")

    _FakeTOSService.bucket_exists_raises = Exception("boom AccountDisable")

    builder = VeCPCRBuilder()
    # agentkit_region takes precedence over cp/cr/tos region in the hint chain
    # (L1101-1106). Feed a distinct region and assert it lands in the URL.
    config = _make_config(tos_bucket="user-bucket", tos_region="cn-beijing")
    config.agentkit_region = "ap-southeast-1"

    with pytest.raises(Exception) as excinfo:
        builder._upload_to_tos(str(archive), config)

    assert "ap-southeast-1" in str(excinfo.value)


def test_too_many_buckets_error_is_mapped_to_quota_message(monkeypatch, tmp_path):
    _install_fake_tos(monkeypatch)
    archive = tmp_path / "app.tar.gz"
    archive.write_bytes(b"payload")

    _FakeTOSService.bucket_exists_raises = Exception(
        f"TooManyBuckets secret={_SECRET_MARKER}"
    )

    builder = VeCPCRBuilder()
    config = _make_config(tos_bucket="user-bucket")

    with pytest.raises(Exception) as excinfo:
        builder._upload_to_tos(str(archive), config)

    msg = str(excinfo.value)
    # L1116-1119 quota message.
    assert "maximum number of buckets" in msg
    assert "delete some buckets" in msg
    # Fixed message must not echo the raw secret.
    assert _SECRET_MARKER not in msg


def test_generic_error_is_wrapped_with_failed_to_upload_prefix(monkeypatch, tmp_path):
    _install_fake_tos(monkeypatch)
    archive = tmp_path / "app.tar.gz"
    archive.write_bytes(b"payload")

    # An error with none of the recognized signatures -> generic wrap (L1120).
    _FakeTOSService.bucket_exists_raises = Exception("unexpected transient network glitch")

    builder = VeCPCRBuilder()
    config = _make_config(tos_bucket="user-bucket")

    with pytest.raises(Exception) as excinfo:
        builder._upload_to_tos(str(archive), config)

    msg = str(excinfo.value)
    assert msg.startswith("Failed to upload to TOS:")
    assert "unexpected transient network glitch" in msg
    # AccountDisable/TooManyBuckets branches must NOT have fired.
    assert "Tos Service is not enabled" not in msg
    assert "maximum number of buckets" not in msg


def test_ownership_check_failure_is_wrapped_as_blocked_for_security(monkeypatch, tmp_path):
    _install_fake_tos(monkeypatch)
    archive = tmp_path / "app.tar.gz"
    archive.write_bytes(b"payload")

    # bucket exists but the ListBuckets ownership probe itself throws (e.g. no
    # ListBuckets permission). check_owned() (L999-1010) converts this into a
    # security-blocking Exception, which then flows through the generic wrap.
    _FakeTOSService.bucket_exists_returns = True
    _FakeTOSService.bucket_is_owned_raises = Exception(
        f"AccessDenied listing buckets {_SECRET_MARKER}"
    )

    builder = VeCPCRBuilder()
    config = _make_config(tos_bucket="user-bucket")

    with pytest.raises(Exception) as excinfo:
        builder._upload_to_tos(str(archive), config)

    msg = str(excinfo.value)
    assert "Upload has been blocked for security reasons" in msg
    assert "ListBuckets permission" in msg
    # The raw underlying error string (with the fake secret) is logged, not
    # surfaced in the wrapped user message.
    assert _SECRET_MARKER not in msg

    svc = _FakeTOSService.instances[-1]
    assert "upload_file" not in [c[0] for c in svc.calls]


# ---------------------------------------------------------------------------
# Unrendered template variables in bucket name -> ValueError before any
# service call (L933-936). The config is constructed valid then mutated so
# __post_init__ template rendering does not intercept first.
# ---------------------------------------------------------------------------

def test_unrendered_template_bucket_name_raises_value_error_before_service_use(
    monkeypatch, tmp_path
):
    _install_fake_tos(monkeypatch)
    archive = tmp_path / "app.tar.gz"
    archive.write_bytes(b"payload")

    builder = VeCPCRBuilder()
    config = _make_config(tos_bucket="placeholder-bucket")
    # Inject an unrendered template AFTER construction to reach the L933 guard.
    config.tos_bucket = "{{agent_name}}-bucket"

    # After the fix: an `except ValueError: raise` clause precedes the broad
    # `except Exception` tail, so the documented ValueError propagates unwrapped
    # (rather than being masked as a generic "Failed to upload to TOS:"), and
    # callers can catch this config error as ValueError per the docstring.
    with pytest.raises(ValueError) as excinfo:
        builder._upload_to_tos(str(archive), config)

    msg = str(excinfo.value)
    assert "unrendered template variables" in msg
    assert "{{agent_name}}-bucket" in msg

    # The guard still runs before any real upload flow: because the bucket name
    # is validated before a TOSService instance is constructed, no fake service
    # instance is created and no upload is attempted.
    assert _FakeTOSService.instances == []


# ---------------------------------------------------------------------------
# Happy path: owned, existing bucket -> upload proceeds and returns URL+region.
# ---------------------------------------------------------------------------

def test_happy_path_uploads_and_returns_url_and_actual_region(monkeypatch, tmp_path):
    _install_fake_tos(monkeypatch)
    archive = tmp_path / "app.tar.gz"
    archive.write_bytes(b"payload")

    _FakeTOSService.bucket_exists_returns = True
    _FakeTOSService.bucket_is_owned_returns = True
    _FakeTOSService.upload_file_returns = (
        "https://user-bucket.tos-cn-beijing.volces.com/agentkit-builds/app.tar.gz"
    )

    builder = VeCPCRBuilder()
    config = _make_config(tos_bucket="user-bucket", tos_region="cn-beijing", tos_prefix="agentkit-builds")

    url, region = builder._upload_to_tos(str(archive), config)

    assert url == "https://user-bucket.tos-cn-beijing.volces.com/agentkit-builds/app.tar.gz"
    assert region == "cn-beijing"

    svc = _FakeTOSService.instances[-1]
    # upload_file called with the object key derived from prefix + archive name.
    upload_calls = [c for c in svc.calls if c[0] == "upload_file"]
    assert len(upload_calls) == 1
    assert upload_calls[0][1] == str(archive)
    assert upload_calls[0][2] == "agentkit-builds/app.tar.gz"

    # object key persisted back onto the config for later reference (L1086).
    assert config.tos_object_key == "agentkit-builds/app.tar.gz"
