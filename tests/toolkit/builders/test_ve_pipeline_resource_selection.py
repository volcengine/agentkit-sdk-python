from __future__ import annotations

import itertools

from agentkit.toolkit.builders.ve_pipeline import VeCPCRBuilder, VeCPCRBuilderConfig
from agentkit.toolkit.config import CommonConfig
from agentkit.toolkit.config.constants import AUTO_CREATE_VE, DEFAULT_WORKSPACE_NAME
from agentkit.toolkit.config.strategy_configs import CloudStrategyConfig
from agentkit.toolkit.models import BuildResult
from agentkit.toolkit.strategies.cloud_strategy import CloudStrategy


class _Reporter:
    def info(self, *_args, **_kwargs):
        pass

    def success(self, *_args, **_kwargs):
        pass

    def warning(self, *_args, **_kwargs):
        pass

    def error(self, *_args, **_kwargs):
        pass


def test_prepare_pipeline_uses_configured_workspace_and_existing_pipeline(
    monkeypatch, tmp_path
) -> None:
    class _FakeCodePipeline:
        AGENTKIT_BUILD_PARAMETER_KEYS = frozenset({"TOS_BUCKET_NAME"})

        def __init__(self, **_kwargs):
            self.created = False

        def workspace_exists_by_name(self, name):
            assert name == "custom-workspace"
            return True

        def get_workspaces_by_name(self, name, page_size=10):
            assert name == "custom-workspace"
            return {
                "Items": [{"Id": "workspace-id", "Name": "custom-workspace"}],
                "TotalCount": 1,
            }

        def list_pipelines(self, workspace_id, pipeline_ids=None, **_kwargs):
            assert workspace_id == "workspace-id"
            assert pipeline_ids == ["pipeline-id"]
            return {
                "Items": [
                    {
                        "Id": "pipeline-id",
                        "Name": "existing-pipeline",
                        "Spec": "value: $(parameters.TOS_BUCKET_NAME)",
                    }
                ]
            }

        def is_agentkit_build_pipeline(self, pipeline):
            return pipeline["Id"] == "pipeline-id"

        def create_workspace(self, **_kwargs):
            raise AssertionError("existing workspace must not be recreated")

        def _create_pipeline(self, **_kwargs):
            raise AssertionError("existing pipeline must not be recreated")

    monkeypatch.setattr(
        "agentkit.toolkit.volcengine.code_pipeline.VeCodePipeline",
        _FakeCodePipeline,
    )
    config = VeCPCRBuilderConfig(
        common_config=CommonConfig(agent_name="agent", entry_point="app.py"),
        cp_workspace_name="custom-workspace",
        cp_pipeline_name="existing-pipeline",
        cp_pipeline_id="pipeline-id",
    )
    builder = VeCPCRBuilder(project_dir=tmp_path, reporter=_Reporter())

    pipeline_id = builder._prepare_pipeline_resources(config, "tos://source", object())

    assert pipeline_id == "pipeline-id"
    assert config.cp_pipeline_id == "pipeline-id"
    assert builder._workspace_id == "workspace-id"


def test_cloud_strategy_preserves_custom_pipeline_selection() -> None:
    captured = []

    class _Builder:
        def build(self, config):
            captured.append(config)
            return BuildResult(success=True)

    strategy = CloudStrategy()
    strategy._builder = _Builder()
    config = CloudStrategyConfig(
        runtime_name="runtime-name",
        cp_workspace_name="workspace-name",
        cp_pipeline_name="pipeline-name",
        cp_pipeline_id="pipeline-id",
    )

    strategy.build(CommonConfig(agent_name="agent", entry_point="app.py"), config)

    assert captured[0].cp_workspace_name == "workspace-name"
    assert captured[0].cp_pipeline_name == "pipeline-name"
    assert captured[0].cp_pipeline_id == "pipeline-id"


def test_all_studio_resource_mode_combinations_reach_builder_config() -> None:
    strategy = CloudStrategy()
    common = CommonConfig(agent_name="matrix-agent", entry_point="app.py")

    for tos_mode, cr_mode, cp_mode in itertools.product(
        ("auto", "create", "existing"), repeat=3
    ):
        config = CloudStrategyConfig(region="cn-beijing")
        if tos_mode != "auto":
            config.tos_bucket = f"tos-{tos_mode}"
        if cr_mode != "auto":
            config.cr_instance_name = f"cr-{cr_mode}"
            config.cr_namespace_name = f"namespace-{cr_mode}"
            config.cr_repo_name = f"repository-{cr_mode}"
        if cp_mode != "auto":
            config.cp_workspace_name = f"workspace-{cp_mode}"
            config.cp_pipeline_name = f"pipeline-{cp_mode}"
        if cp_mode == "existing":
            config.cp_pipeline_id = "pipeline-existing-id"

        builder = strategy._to_builder_config(
            common,
            config,
            runtime_name_override="matrix-runtime",
            cp_pipeline_name_override=(
                "matrix-runtime" if cp_mode == "auto" else config.cp_pipeline_name
            ),
        )

        assert builder.tos_bucket == (
            AUTO_CREATE_VE if tos_mode == "auto" else f"tos-{tos_mode}"
        )
        assert builder.cr_instance_name == (
            AUTO_CREATE_VE if cr_mode == "auto" else f"cr-{cr_mode}"
        )
        assert builder.cr_namespace_name == (
            "agentkit" if cr_mode == "auto" else f"namespace-{cr_mode}"
        )
        assert builder.cr_repo_name == (
            "" if cr_mode == "auto" else f"repository-{cr_mode}"
        )
        assert builder.cp_workspace_name == (
            DEFAULT_WORKSPACE_NAME if cp_mode == "auto" else f"workspace-{cp_mode}"
        )
        assert builder.cp_pipeline_name == (
            "matrix-runtime" if cp_mode == "auto" else f"pipeline-{cp_mode}"
        )
        assert builder.cp_pipeline_id == (
            "pipeline-existing-id" if cp_mode == "existing" else ""
        )
