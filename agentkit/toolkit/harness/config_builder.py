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

"""Build the cloud AgentKit launch config for a harness deploy."""

from typing import Any, Dict, Optional


def build_agentkit_config(
    runtime_name: str,
    region: str,
    envs: Dict[str, str],
    auth: Optional[Dict[str, Any]] = None,
    runtime_id: str = "Auto",
    cloud_provider: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the cloud AgentKit launch config dict (auto-provision).

    Mirrors the structure ``agentkit init`` produces for ``launch_type: cloud``.
    The ``{{account_id}}`` / ``{{timestamp}}`` templates are resolved by AgentKit
    at deploy time and are passed through literally.

    ``runtime_id`` defaults to ``"Auto"`` (create a new runtime). Passing an
    existing runtime id makes the deploy update that runtime in place (the runner
    routes a real id to ``UpdateRuntime``, which the platform releases as a new
    version).

    When ``auth`` (a normalized ``{discovery_url, allowed_ids}`` block) is given,
    the runtime is gated by OAuth2/JWT (``custom_jwt``); otherwise it keeps the
    default API-key auth (``key_auth``). ``cloud_provider`` pins the generated
    launch config to the same provider used to resolve credentials and region.
    """
    cloud: Dict[str, Any] = {
        "region": region,
        "tos_bucket": "agentkit-platform-{{account_id}}",
        "tos_prefix": "agentkit-builds",
        "image_tag": "{{timestamp}}",
        "cr_instance_name": "agentkit-platform-{{account_id}}",
        "cr_namespace_name": "agentkit",
        "cr_repo_name": runtime_name,
        "cr_auto_create_instance_type": "Micro",
        "build_timeout": 3600,
        "cp_workspace_name": "agentkit-cli-workspace",
        "cp_pipeline_name": "Auto",
        "runtime_id": runtime_id,
        "runtime_name": runtime_name,
        "runtime_role_name": "Auto",
    }
    if auth:
        cloud["runtime_auth_type"] = "custom_jwt"
        cloud["runtime_jwt_discovery_url"] = auth["discovery_url"]
        cloud["runtime_jwt_allowed_clients"] = auth["allowed_ids"]
    else:
        cloud["runtime_auth_type"] = "key_auth"
        cloud["runtime_apikey_name"] = "Auto"
        cloud["runtime_apikey"] = "Auto"
        cloud["runtime_jwt_allowed_clients"] = []
    common: Dict[str, Any] = {
        "agent_name": runtime_name,
        "entry_point": "app.py",
        "description": "Harness Server - VeADK",
        "language": "Python",
        "language_version": "3.12",
        "runtime_envs": envs,
        "launch_type": "cloud",
    }
    if cloud_provider:
        common["cloud_provider"] = cloud_provider

    return {
        "common": common,
        "launch_types": {"cloud": cloud},
        "docker_build": {},
    }
