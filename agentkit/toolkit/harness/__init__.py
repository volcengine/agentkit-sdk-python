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

"""Harness deploy support: flatten a layered harness spec and deploy it as a runtime."""

from .config_builder import build_agentkit_config
from .deploy import HarnessDeployAborted, deploy_harness, load_harness_registry
from .env_mapping import to_runtime_env
from .sidecar import (
    HarnessSidecarError,
    HarnessSidecarRuntimeUnavailable,
    SidecarBinding,
    doctor_harness_sidecar,
    export_sidecar_env,
    run_with_harness_sidecar,
    start_harness_sidecar,
)
from .sidecar_config import (
    HarnessSidecarConfig,
    MCPGatewayConfig,
    ModelProxyConfig,
    SidecarBindingSpec,
    resolve_sidecar_config,
    sidecar_config_to_env,
)
from .runtime_components import (
    RUNTIME_COMPONENT_ORDER,
    resolve_runtime_components,
    runtime_flavor_for_components,
)
from .component_catalog import (
    CATALOG_SCHEMA_VERSION,
    CATALOG_VERSION,
    PRODUCT_COMPONENT_ORDER,
    ComponentAvailability,
    HarnessComponentDefinition,
    HarnessProfileDefinition,
    HarnessSidecarCatalog,
    get_harness_sidecar_catalog,
)
from .selection import (
    PLAN_SCHEMA_VERSION,
    AutoAddedComponent,
    HarnessActivationTargets,
    HarnessSelectionIntent,
    ResolvedHarnessPlan,
    resolve_harness_sidecar_selection,
)

__all__ = [
    "to_runtime_env",
    "build_agentkit_config",
    "deploy_harness",
    "load_harness_registry",
    "HarnessDeployAborted",
    "HarnessSidecarConfig",
    "HarnessSidecarError",
    "HarnessSidecarRuntimeUnavailable",
    "MCPGatewayConfig",
    "ModelProxyConfig",
    "RUNTIME_COMPONENT_ORDER",
    "SidecarBinding",
    "SidecarBindingSpec",
    "doctor_harness_sidecar",
    "export_sidecar_env",
    "resolve_sidecar_config",
    "resolve_runtime_components",
    "run_with_harness_sidecar",
    "sidecar_config_to_env",
    "start_harness_sidecar",
    "runtime_flavor_for_components",
    "AutoAddedComponent",
    "CATALOG_SCHEMA_VERSION",
    "CATALOG_VERSION",
    "ComponentAvailability",
    "HarnessActivationTargets",
    "HarnessComponentDefinition",
    "HarnessProfileDefinition",
    "HarnessSelectionIntent",
    "HarnessSidecarCatalog",
    "PLAN_SCHEMA_VERSION",
    "PRODUCT_COMPONENT_ORDER",
    "ResolvedHarnessPlan",
    "get_harness_sidecar_catalog",
    "resolve_harness_sidecar_selection",
]
