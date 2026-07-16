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
from typing import Any, Callable, Dict, Optional, Union

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

# Volcengine deploy credentials: needed locally to authenticate the build/deploy,
# but must never be uploaded into the cloud runtime's environment (the runtime
# gets its Volcengine access from its IAM role). A harness's own `.env` carries
# these for deploy; they are excluded from the runtime env upload (see
# COMPAT_ENV_EXCLUDE). Credentials a harness genuinely needs at runtime come from
# its spec instead, so they are not affected.
_DEPLOY_CREDENTIAL_ENV_KEYS = {
    "VOLCENGINE_ACCESS_KEY",
    "VOLCENGINE_SECRET_KEY",
    "VOLCENGINE_SESSION_TOKEN",
    "VOLC_ACCESSKEY",
    "VOLC_SECRETKEY",
    "VOLC_SESSIONTOKEN",
}


class HarnessDeployAborted(Exception):
    """Raised when the user declines to update an existing same-name harness."""


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


def _find_runtimes_by_name(client, name: str) -> list:
    """Return ``[{runtime_id, is_harness}]`` for every runtime named ``name``.

    Scans all pages. ``is_harness`` is derived from the deploy-time harness tag on
    the list item (no extra get_runtime call). Used to decide between create,
    update, and fast-fail before a harness deploy.
    """
    from agentkit.sdk.runtime import types as rt_types

    matches = []
    next_token = None
    while True:
        resp = client.list_runtimes(
            rt_types.ListRuntimesRequest(max_results=50, next_token=next_token)
        )
        for runtime in resp.agent_kit_runtimes or []:
            if runtime.name == name:
                is_harness = any(
                    tag.key == HARNESS_TAG_KEY and tag.value == HARNESS_TAG_VALUE
                    for tag in (runtime.tags or [])
                )
                matches.append(
                    {"runtime_id": runtime.runtime_id or "", "is_harness": is_harness}
                )
        next_token = resp.next_token
        if not next_token:
            break
    return matches


def _get_runtime_version(client, runtime_id: str) -> Optional[int]:
    """Return a runtime's current version number (None if unavailable)."""
    from agentkit.sdk.runtime import types as rt_types

    runtime = client.get_runtime(rt_types.GetRuntimeRequest(runtime_id=runtime_id))
    return runtime.current_version_number


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
    session_token: Optional[str] = None,
    discovery_url: Optional[str] = None,
    allowed_id: Optional[str] = None,
    reporter: Optional[Reporter] = None,
    on_conflict: Optional[Callable[[Dict[str, Any]], bool]] = None,
) -> LifecycleResult:
    """Deploy a harness spec as an AgentKit runtime (cloud build, no local Docker).

    Reads ``<path>/<name>.harness.json``, flattens it into the runtime's
    environment, and runs an AgentKit cloud build + runtime create. The deploy
    directory must also contain the harness server ``Dockerfile``. On success the
    runtime is recorded in ``<path>/harness.json`` (keyed by ``name``).

    Name-collision handling (a same-name runtime already exists):

    * not a harness runtime, or more than one match -> fast-fail (``ValueError``);
    * a single harness runtime -> if ``on_conflict`` is given, it is called with
      ``{name, runtime_id, version}`` and must return ``True`` to update that
      runtime in place (the platform releases a new version) or ``False`` to abort
      (``HarnessDeployAborted``); if ``on_conflict`` is ``None`` (e.g. a
      programmatic caller or a non-interactive CLI), it fast-fails.

    Credentials note: a local ``.env`` is loaded for deploy auth, but the
    Volcengine deploy credentials in it are NOT uploaded into the runtime
    environment (the runtime authenticates via its IAM role); other ``.env`` keys
    are still merged in.

    Args:
        name: Harness name; locates ``<name>.harness.json`` and names the runtime.
        path: Directory containing the spec and Dockerfile (default: cwd).
        region: AgentKit region (default ``cn-beijing`` or ``VOLCENGINE_REGION``).
        access_key / secret_key / session_token: Volcengine credentials
            (default: ``VOLCENGINE_*`` env; session_token is for STS temporary creds).
        discovery_url / allowed_id: OAuth2/JWT overrides for the spec ``auth`` block.
        reporter: Progress reporter forwarded to the launch (default: silent).
        on_conflict: Callback consulted when a single same-name harness exists;
            returns True to update it, False to abort.

    Returns:
        LifecycleResult: the build+deploy result from ``sdk.launch``.

    Raises:
        NotADirectoryError / FileNotFoundError / ValueError: on invalid inputs
        (fast-fail). HarnessDeployAborted when the user declines an update.
        Deployment failures are returned in ``LifecycleResult.error``.
    """
    # Heavy imports are lazy: this module is imported by `agentkit.toolkit.sdk`
    # at package init, and these pull in the runtime client / executors.
    from agentkit.toolkit.sdk.lifecycle import launch
    from agentkit.toolkit.models import PreflightMode
    from agentkit.toolkit.config import utils as cfg_utils
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
    # VOLC_SECRETKEY / VOLC_SESSIONTOKEN from the environment. Mirror whatever
    # AK/SK/token was passed (or already set as VOLCENGINE_*) into those names.
    ak = access_key or os.getenv("VOLCENGINE_ACCESS_KEY", "")
    sk = secret_key or os.getenv("VOLCENGINE_SECRET_KEY", "")
    token = (
        session_token
        or os.getenv("VOLCENGINE_SESSION_TOKEN", "")
        or os.getenv("VOLC_SESSIONTOKEN", "")
    )
    if ak and sk:
        os.environ["VOLC_ACCESSKEY"] = ak
        os.environ["VOLC_SECRETKEY"] = sk
        if token:
            os.environ["VOLC_SESSIONTOKEN"] = token
    if not os.getenv("VOLC_ACCESSKEY") or not os.getenv("VOLC_SECRETKEY"):
        raise ValueError(
            "Volcengine credentials are required. Pass access_key / secret_key, "
            "or set VOLCENGINE_ACCESS_KEY / VOLCENGINE_SECRET_KEY."
        )

    resolved_region = region or os.getenv("VOLCENGINE_REGION") or "cn-beijing"

    # Resolve a name collision into a deploy mode. The harness config defaults to
    # `runtime_id: Auto` (create new); an existing same-name harness can instead
    # be updated in place (new version) after confirmation.
    client = AgentkitRuntimeClient(region=resolved_region, session_token=token or "")
    matches = _find_runtimes_by_name(client, runtime_name)
    update_runtime_id = None
    if len(matches) > 1:
        ids = ", ".join(m["runtime_id"] for m in matches if m["runtime_id"])
        raise ValueError(
            f"Multiple runtimes named '{runtime_name}' already exist "
            f"(runtime_id: {ids}). Clean them up or use a different name."
        )
    if matches:
        match = matches[0]
        if not match["is_harness"]:
            raise ValueError(
                f"'{runtime_name}' already exists but is not a harness application "
                f"(missing {HARNESS_TAG_KEY}={HARNESS_TAG_VALUE} tag). "
                "Refusing to update it."
            )
        existing_id = match["runtime_id"]
        version = _get_runtime_version(client, existing_id)
        version_label = f"v{version}" if version is not None else "unknown"
        if reporter:
            reporter.info(
                f"Harness '{runtime_name}' already exists "
                f"(runtime_id: {existing_id}, current version {version_label})."
            )
        if on_conflict is None:
            raise ValueError(
                f"A runtime named '{runtime_name}' already exists "
                f"(runtime_id: {existing_id}, current version {version_label}). "
                "Re-run interactively to update it, pass --yes, or use a "
                "different name."
            )
        if not on_conflict(
            {"name": runtime_name, "runtime_id": existing_id, "version": version}
        ):
            raise HarnessDeployAborted(
                f"Update of harness '{runtime_name}' was declined."
            )
        update_runtime_id = existing_id

    cfg = build_agentkit_config(
        runtime_name,
        resolved_region,
        runtime_envs,
        auth,
        runtime_id=update_runtime_id or "Auto",
    )

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

    action = "Updating" if update_runtime_id else "Deploying"
    logger.info("%s harness runtime '%s' from %s", action, runtime_name, proj_dir)
    cwd = os.getcwd()
    os.chdir(proj_dir)
    AgentkitRuntimeClient.create_runtime = _create_runtime_with_harness_tag
    # Keep deploy-only Volcengine credentials in the local .env out of the
    # uploaded runtime environment (the compat layer auto-loads .env). Scoped to
    # this launch and restored afterwards.
    prev_exclude = cfg_utils.COMPAT_ENV_EXCLUDE
    cfg_utils.COMPAT_ENV_EXCLUDE = set(prev_exclude) | _DEPLOY_CREDENTIAL_ENV_KEYS
    try:
        result = launch(
            config_dict=cfg,
            preflight_mode=PreflightMode.WARN,
            reporter=reporter,
        )
    finally:
        AgentkitRuntimeClient.create_runtime = orig_create_runtime
        cfg_utils.COMPAT_ENV_EXCLUDE = prev_exclude
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
    runtime_id = meta.get("runtime_id") or update_runtime_id

    # Echo the new version after an in-place update (the platform bumps it).
    if update_runtime_id and reporter:
        new_version = _get_runtime_version(client, update_runtime_id)
        if new_version is not None:
            reporter.success(
                f"Harness '{runtime_name}' updated to version v{new_version}."
            )

    if endpoint:
        _record_harness(
            proj_dir, runtime_name, endpoint, runtime_id or "", key=apikey, auth=auth
        )

    return result
