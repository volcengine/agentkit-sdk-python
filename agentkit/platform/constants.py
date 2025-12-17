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

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class ServiceMeta:
    code: str
    host_template: str
    default_version: str
    scheme: str = "https"


DEFAULT_REGION_RULES = {
    "cn-shanghai": {
        "cp": "cn-beijing",
        "tos": "cn-beijing",
    }
}


# Unified Service Registry
# Using data-driven configuration instead of hardcoded logic
SERVICE_METADATA: Dict[str, ServiceMeta] = {
    "agentkit": ServiceMeta(
        code="agentkit",
        host_template="open.volcengineapi.com",
        default_version="2025-10-30",
    ),
    "iam": ServiceMeta(
        code="iam",
        host_template="open.volcengineapi.com",
        default_version="2018-01-01",
    ),
    "sts": ServiceMeta(
        code="sts",
        host_template="sts.volcengineapi.com",
        default_version="2018-01-01",
    ),
    "identity": ServiceMeta(
        code="cis_test",
        host_template="open.volcengineapi.com",
        default_version="2023-10-01",
    ),
    "cr": ServiceMeta(
        code="cr",
        host_template="cr.{region}.volcengineapi.com",
        default_version="2022-05-12",
    ),
    "tos": ServiceMeta(
        code="tos",
        host_template="tos-{region}.volces.com",
        default_version="",
    ),
    "cp": ServiceMeta(
        code="CP",
        host_template="open.volcengineapi.com",
        default_version="2023-05-01",
    ),
}

DEFAULT_REGION = "cn-beijing"
