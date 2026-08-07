from __future__ import annotations

from types import SimpleNamespace

from agentkit.platform import Credentials
from agentkit.toolkit.volcengine.code_pipeline import VeCodePipeline
from agentkit.toolkit.volcengine.cr import VeCR
from agentkit.toolkit.volcengine.services import tos_service
from agentkit.toolkit.volcengine.services.tos_service import (
    TOSService,
    TOSServiceConfig,
)


def test_tos_uses_explicit_credentials(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _Configuration:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

        def get_service_credentials(self, _service: str):
            return SimpleNamespace(
                access_key="explicit-ak",
                secret_key="explicit-sk",
                session_token="explicit-token",
            )

        def get_service_endpoint(self, _service: str):
            return SimpleNamespace(host="tos.example.com", region="ap-southeast-1")

    monkeypatch.setattr("agentkit.platform.VolcConfiguration", _Configuration)
    monkeypatch.setattr(
        tos_service,
        "tos",
        SimpleNamespace(TosClientV2=lambda *_args, **_kwargs: object()),
    )
    monkeypatch.setattr(tos_service, "TOS_AVAILABLE", True)

    TOSService(
        TOSServiceConfig(bucket="bucket-a", region="ap-southeast-1"),
        provider="byteplus",
        credentials=Credentials(
            access_key="explicit-ak",
            secret_key="explicit-sk",
            session_token="explicit-token",
        ),
    )

    assert captured == {
        "region": "ap-southeast-1",
        "provider": "byteplus",
        "access_key": "explicit-ak",
        "secret_key": "explicit-sk",
        "session_token": "explicit-token",
    }


def test_tos_list_buckets_returns_names_locations_and_creation_times() -> None:
    service = object.__new__(TOSService)
    service.actual_region = "cn-beijing"
    service.client = SimpleNamespace(
        list_buckets=lambda: SimpleNamespace(
            buckets=[
                SimpleNamespace(
                    name="source-bucket",
                    location="cn-beijing",
                    creation_date="2026-08-07T00:00:00Z",
                )
            ]
        )
    )

    assert service.list_buckets() == [
        {
            "Name": "source-bucket",
            "Location": "cn-beijing",
            "CreationDate": "2026-08-07T00:00:00Z",
        }
    ]


def test_cr_resource_lists_use_parent_filters_and_pagination() -> None:
    client = object.__new__(VeCR)
    calls: list[tuple[str, dict]] = []

    def request(request_body: dict, action: str) -> dict:
        calls.append((action, request_body))
        return {"Result": {"Items": [{"Name": action}], "TotalCount": 1}}

    client._ve_request = request

    assert client.list_registries(page_number=2, page_size=20)["TotalCount"] == 1
    assert client.list_namespaces("registry-a", page_size=50)["TotalCount"] == 1
    assert (
        client.list_repositories("registry-a", "namespace-a", page_size=100)[
            "TotalCount"
        ]
        == 1
    )
    assert calls == [
        ("ListRegistries", {"PageNumber": 2, "PageSize": 20}),
        (
            "ListNamespaces",
            {"Registry": "registry-a", "PageNumber": 1, "PageSize": 50},
        ),
        (
            "ListRepositories",
            {
                "Registry": "registry-a",
                "Namespace": "namespace-a",
                "PageNumber": 1,
                "PageSize": 100,
            },
        ),
    ]


def test_code_pipeline_list_item_can_be_checked_for_agentkit_compatibility() -> None:
    spec = "\n".join(
        f"value: $({{parameters.{key}}})"
        for key in VeCodePipeline.AGENTKIT_BUILD_PARAMETER_KEYS
    )

    assert VeCodePipeline.is_agentkit_build_pipeline({"Spec": spec}) is True
    assert VeCodePipeline.is_agentkit_build_pipeline({"Spec": "value: $OTHER"}) is False
