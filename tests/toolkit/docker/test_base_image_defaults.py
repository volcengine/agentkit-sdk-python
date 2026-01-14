from pathlib import Path

from agentkit.platform.provider import CloudProvider
from agentkit.toolkit.docker.base_images import resolve_dockerfile_base_image_defaults
from agentkit.toolkit.docker.dockerfile.manager import DockerfileManager


def test_resolve_python_default_base_image_for_volcengine() -> None:
    defaults = resolve_dockerfile_base_image_defaults(
        language="Python", language_version="3.12", provider=CloudProvider.VOLCENGINE
    )
    assert defaults.context["base_image_default"] == (
        "agentkit-prod-public-cn-beijing.cr.volces.com/base/py-simple:"
        "python3.12-bookworm-slim-latest"
    )


def test_resolve_python_default_base_image_for_byteplus() -> None:
    defaults = resolve_dockerfile_base_image_defaults(
        language="Python", language_version="3.12", provider=CloudProvider.BYTEPLUS
    )
    assert defaults.context["base_image_default"] == (
        "agentkit-prod-public-ap-southeast-1.cr.bytepluses.com/base/py-simple:"
        "python3.12-bookworm-slim-latest"
    )


def test_managed_dockerfile_regenerates_when_provider_changes(tmp_path: Path) -> None:
    manager = DockerfileManager(tmp_path)

    config_hash_dict_v1 = {
        "language": "Python",
        "language_version": "3.12",
        "entry_point": "agent.py",
        "dependencies_file": "requirements.txt",
        "dockerfile_template": "Dockerfile.j2",
        "dockerfile_template_hash": "hash_v1",
        "docker_build": {"base_image": None, "build_script": None},
        "cloud_provider_resolved": "volcengine",
        "dockerfile_base_image_defaults": {
            "base_image_default": "agentkit-prod-public-cn-beijing.cr.volces.com/base/py-simple:python3.12-bookworm-slim-latest"
        },
    }

    def content_generator_v1() -> str:
        return "FROM agentkit-prod-public-cn-beijing.cr.volces.com/base/py-simple:python3.12-bookworm-slim-latest\n"

    generated_1, _ = manager.prepare_dockerfile(
        config_hash_dict=config_hash_dict_v1,
        content_generator=content_generator_v1,
        force_regenerate=False,
    )
    assert generated_1 is True

    config_hash_dict_v2 = dict(config_hash_dict_v1)
    config_hash_dict_v2["cloud_provider_resolved"] = "byteplus"
    config_hash_dict_v2["dockerfile_base_image_defaults"] = {
        "base_image_default": "agentkit-prod-public-ap-southeast-1.cr.bytepluses.com/base/py-simple:python3.12-bookworm-slim-latest"
    }

    def content_generator_v2() -> str:
        return "FROM agentkit-prod-public-ap-southeast-1.cr.bytepluses.com/base/py-simple:python3.12-bookworm-slim-latest\n"

    generated_2, _ = manager.prepare_dockerfile(
        config_hash_dict=config_hash_dict_v2,
        content_generator=content_generator_v2,
        force_regenerate=False,
    )
    assert generated_2 is True

    backup_dir = tmp_path / ".agentkit" / "dockerfile_backups"
    backups = list(backup_dir.glob("Dockerfile.backup.*"))
    assert len(backups) == 1
