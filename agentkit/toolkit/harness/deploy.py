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

"""Deploy a harness spec (``<name>.harness.json``) as an AgentKit runtime.

Loads the layered harness spec, flattens it into the runtime's environment,
builds a cloud AgentKit launch config, and runs a cloud build + runtime create
(no local Docker). On success the deployed runtime is recorded in a
``harness.json`` registry next to the spec so it can be invoked by name.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

from ..models import LifecycleResult
from ..reporter import Reporter

from .config_builder import build_agentkit_config
from .env_mapping import to_runtime_env

logger = logging.getLogger(__name__)

# Default harness/runtime name when neither a `--harness` value nor a deployable
# name is available (kept for parity; `deploy_harness` always passes `name`).
_DEFAULT_HARNESS_NAME = "default"

# Tag stamped on every runtime created by a harness deploy. `agentkit list
# harness` uses this exact key/value to recognize harness runtimes.
HARNESS_TAG_KEY = "agentkit:agenttype"
HARNESS_TAG_VALUE = "harness"


def _resolve_auth(
    spec_auth: Optional[Dict[str, Any]],
    discovery_url: Optional[str],
    allowed_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    """Merge the spec ``auth`` block with deploy flag overrides.

    Returns a normalized ``{discovery_url, allowed_ids}`` to deploy with OAuth2/JWT
    (custom_jwt), or ``None`` to keep the default API-key auth — the presence of an
    ``auth`` block (or the flags) is the switch. Fails fast on a partial config.
    """
    auth = dict(spec_auth) if spec_auth else {}
    if discovery_url:
        auth["discovery_url"] = discovery_url
    if allowed_id:
        auth["allowed_ids"] = [s.strip() for s in allowed_id.split(",") if s.strip()]
    if not auth:
        return None
    discovery = auth.get("discovery_url")
    allowed = auth.get("allowed_ids") or []
    if not discovery or not allowed:
        raise ValueError(
            "OAuth deploy needs both `auth.discovery_url` and `auth.allowed_ids` "
            "(or --discovery-url and --allowed-id)."
        )
    return {"discovery_url": discovery, "allowed_ids": list(allowed)}


def _harness_json_path(directory: Union[str, Path]) -> Path:
    return Path(directory).resolve() / "harness.json"


def _load_harness_json(directory: Union[str, Path]) -> Dict[str, Any]:
    """Load the ``{name: {url, key, runtime_id}}`` registry, or {} if absent."""
    path = _harness_json_path(directory)
    return json.loads(path.read_text()) if path.is_file() else {}


def load_harness_registry(directory: Union[str, Path] = ".") -> Dict[str, Any]:
    """Load the ``{name: {url, key, runtime_id}}`` registry written by deploy.

    Returns ``{}`` when no ``harness.json`` exists in ``directory``. Used by
    ``agentkit invoke harness`` to resolve a deployed harness by name.
    """
    return _load_harness_json(directory)


def _record_harness(
    directory: Union[str, Path],
    name: str,
    url: str,
    runtime_id: str,
    *,
    key: Optional[str] = None,
    auth: Optional[Dict[str, Any]] = None,
) -> Path:
    """Record/replace a deployed harness in ``harness.json``.

    key_auth records ``{url, key, runtime_id}``; custom_jwt records
    ``{url, runtime_id, auth_type, discovery_url, allowed_ids}`` (no key — a
    user-pool JWT is supplied per request, not stored).
    """
    path = _harness_json_path(directory)
    data = _load_harness_json(directory)
    if auth:
        data[name] = {
            "url": url,
            "runtime_id": runtime_id,
            "auth_type": "custom_jwt",
            "discovery_url": auth["discovery_url"],
            "allowed_ids": auth["allowed_ids"],
        }
    else:
        data[name] = {"url": url, "key": key or "", "runtime_id": runtime_id}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return path


def _existing_runtime_ids(client, name: str) -> list:
    """Return the ids of every runtime whose name equals ``name`` (all pages).

    Used to fast-fail before a harness deploy: the harness config always sets
    ``runtime_id: Auto`` (always create-new), so without this check re-deploying
    would pile up duplicate same-name runtimes.
    """
    from agentkit.sdk.runtime import types as rt_types

    ids = []
    next_token = None
    while True:
        resp = client.list_runtimes(
            rt_types.ListRuntimesRequest(max_results=50, next_token=next_token)
        )
        for runtime in resp.agent_kit_runtimes or []:
            if runtime.name == name:
                ids.append(runtime.runtime_id or "")
        next_token = resp.next_token
        if not next_token:
            break
    return ids


def _load_harness_spec(path: Path) -> Dict[str, Any]:
    """Load a ``<name>.harness.json`` spec; fast-fail when it is missing."""
    if not path.is_file():
        raise FileNotFoundError(
            f"No harness spec at '{path}'. Expected `<name>.harness.json` in the "
            "deploy directory."
        )
    return json.loads(path.read_text()) or {}


def deploy_harness(
    name: str,
    path: Union[str, Path] = ".",
    *,
    region: Optional[str] = None,
    access_key: Optional[str] = None,
    secret_key: Optional[str] = None,
    discovery_url: Optional[str] = None,
    allowed_id: Optional[str] = None,
    reporter: Optional[Reporter] = None,
) -> LifecycleResult:
    """Deploy a harness spec as an AgentKit runtime (cloud build, no local Docker).

    Reads ``<path>/<name>.harness.json``, flattens it into the runtime's
    environment, and runs an AgentKit cloud build + runtime create. The deploy
    directory must also contain the harness server ``Dockerfile``. On success the
    runtime is recorded in ``<path>/harness.json`` (keyed by ``name``).

    Args:
        name: Harness name; locates ``<name>.harness.json`` and names the runtime.
        path: Directory containing the spec and Dockerfile (default: cwd).
        region: AgentKit region (default ``cn-beijing`` or ``VOLCENGINE_REGION``).
        access_key / secret_key: Volcengine credentials (default: ``VOLCENGINE_*`` env).
        discovery_url / allowed_id: OAuth2/JWT overrides for the spec ``auth`` block.
        reporter: Progress reporter forwarded to the launch (default: silent).

    Returns:
        LifecycleResult: the build+deploy result from ``sdk.launch``.

    Raises:
        NotADirectoryError / FileNotFoundError / ValueError: on invalid inputs
        (fast-fail). Deployment failures are returned in ``LifecycleResult.error``.
    """
    # Heavy imports are lazy: this module is imported by `agentkit.toolkit.sdk`
    # at package init, and these pull in the runtime client / executors.
    from agentkit.toolkit.sdk.lifecycle import launch
    from agentkit.toolkit.models import PreflightMode
    from agentkit.toolkit.config.utils import load_dotenv_file
    from agentkit.sdk.runtime import types as rt_types
    from agentkit.sdk.runtime.client import AgentkitRuntimeClient

    proj_dir = Path(path).resolve()
    if not proj_dir.is_dir():
        raise NotADirectoryError(f"Path '{proj_dir}' is not a directory.")

    # Load `<dir>/.env` so deploy credentials (and region) can come from a local
    # .env file. Already-exported environment variables take precedence.
    for key, value in load_dotenv_file(proj_dir).items():
        os.environ.setdefault(key, value)

    spec = _load_harness_spec(proj_dir / f"{name}.harness.json")
    runtime_envs = to_runtime_env(spec)
    runtime_name = name
    auth = _resolve_auth(spec.get("auth"), discovery_url, allowed_id)

    # AgentKit authenticates via the Volcengine SDK, which reads VOLC_ACCESSKEY /
    # VOLC_SECRETKEY from the environment. Mirror whatever AK/SK was passed (or
    # already set as VOLCENGINE_*) into those names.
    ak = access_key or os.getenv("VOLCENGINE_ACCESS_KEY", "")
    sk = secret_key or os.getenv("VOLCENGINE_SECRET_KEY", "")
    if ak and sk:
        os.environ["VOLC_ACCESSKEY"] = ak
        os.environ["VOLC_SECRETKEY"] = sk
    if not os.getenv("VOLC_ACCESSKEY") or not os.getenv("VOLC_SECRETKEY"):
        raise ValueError(
            "Volcengine credentials are required. Pass access_key / secret_key, "
            "or set VOLCENGINE_ACCESS_KEY / VOLCENGINE_SECRET_KEY."
        )

    resolved_region = region or os.getenv("VOLCENGINE_REGION") or "cn-beijing"

    # Fast-fail on a name collision: the harness config sets `runtime_id: Auto`
    # (always create-new), so deploying over an existing same-name runtime would
    # silently create a duplicate. Refuse and let the user delete/rename first.
    existing_ids = _existing_runtime_ids(
        AgentkitRuntimeClient(region=resolved_region), runtime_name
    )
    if existing_ids:
        raise ValueError(
            f"A runtime named '{runtime_name}' already exists "
            f"(runtime_id: {', '.join(i for i in existing_ids if i)}). "
            "Delete it or use a different harness name before deploying."
        )

    cfg = build_agentkit_config(runtime_name, resolved_region, runtime_envs, auth)

    # AgentKit's launch path exposes no hook for runtime tags, so tag the runtime
    # at creation by wrapping the SDK's create_runtime: every harness runtime is
    # tagged `agentkit:agenttype=harness`. Scoped to this deploy and restored after.
    orig_create_runtime = AgentkitRuntimeClient.create_runtime

    def _create_runtime_with_harness_tag(self, request):
        request.tags = [
            *(request.tags or []),
            rt_types.TagsItemForCreateRuntime.model_validate(
                {"Key": HARNESS_TAG_KEY, "Value": HARNESS_TAG_VALUE}
            ),
        ]
        return orig_create_runtime(self, request)

    logger.info("Deploying harness runtime '%s' from %s", runtime_name, proj_dir)
    cwd = os.getcwd()
    os.chdir(proj_dir)
    AgentkitRuntimeClient.create_runtime = _create_runtime_with_harness_tag
    try:
        result = launch(
            config_dict=cfg,
            preflight_mode=PreflightMode.WARN,
            reporter=reporter,
        )
    finally:
        AgentkitRuntimeClient.create_runtime = orig_create_runtime
        os.chdir(cwd)

    if not result.success:
        return result

    # The AgentKit runner returns the created runtime's id / endpoint / api key in
    # the deploy result's metadata (key auth). Record them so the harness can be
    # invoked by name.
    deploy_result = result.deploy_result
    meta = deploy_result.metadata if (deploy_result and deploy_result.metadata) else {}
    endpoint = deploy_result.endpoint_url if deploy_result else None
    apikey = meta.get("runtime_apikey")
    runtime_id = meta.get("runtime_id")

    if endpoint:
        _record_harness(
            proj_dir, runtime_name, endpoint, runtime_id or "", key=apikey, auth=auth
        )

    return result
