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

from __future__ import annotations

import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
_REQUIREMENT_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+")


def _pyproject() -> dict[str, object]:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_opentelemetry_bounds_allow_google_adk_2_7_runtime_baseline() -> None:
    dependencies = {
        _REQUIREMENT_NAME_RE.match(requirement).group(0).lower(): requirement
        for requirement in _pyproject()["project"]["dependencies"]
    }

    for package in (
        "opentelemetry-api",
        "opentelemetry-exporter-otlp-proto-common",
        "opentelemetry-exporter-otlp-proto-grpc",
        "opentelemetry-sdk",
    ):
        requirement = dependencies[package]
        normalized = requirement.replace(" ", "")
        assert normalized == f"{package}>=1.32.1"
        assert "==1.43.0" not in normalized
        assert "<1.43.0" not in normalized
        assert "<=1.37.0" not in normalized


def test_next_release_version_records_dependency_metadata_change() -> None:
    pyproject = _pyproject()

    assert pyproject["project"]["version"] == "0.9.2"
