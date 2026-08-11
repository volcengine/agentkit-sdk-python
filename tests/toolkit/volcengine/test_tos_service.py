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

from agentkit.toolkit.volcengine.services.tos_service import TOSService


class _FakeClient:
    def __init__(self) -> None:
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1


def test_close_releases_client_once() -> None:
    service = TOSService.__new__(TOSService)
    client = _FakeClient()
    service.client = client

    service.close()
    service.close()

    assert client.close_calls == 1
    assert service.client is None


def test_context_manager_closes_client() -> None:
    service = TOSService.__new__(TOSService)
    client = _FakeClient()
    service.client = client

    with service as entered:
        assert entered is service

    assert client.close_calls == 1
    assert service.client is None
