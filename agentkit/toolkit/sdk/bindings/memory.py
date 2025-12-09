from pathlib import Path
from typing import Optional, Union, Dict

from agentkit.sdk.memory import (
    AgentkitMemoryClient,
    GetMemoryCollectionRequest,
    GetMemoryConnectionInfoRequest,
)
from ..config import AgentConfig


def bind_memory_env_to_config_for_veadk(
    project_dir: Union[str, Path],
    memory_id: str,
    *,
    strategy_name: Optional[str] = "cloud",
    overwrite: bool = False,
    connection_index: int = 0,
    memory_client: Optional[AgentkitMemoryClient] = None,
) -> AgentConfig:
    """Bind an AgentKit Memory collection to a VeADK project config.

    This helper is specifically designed for VeADK (Volcengine Agent Development Kit)
    and will configure the required environment variables for VeADK's memory integration.

    This function will:
    1) Query AgentKit Memory service for the given MemoryId
    2) Derive connection environment variables based on provider type
       - MEM0: DATABASE_MEM0_BASE_URL / DATABASE_MEM0_API_KEY
       - VIKINGDB_MEMORY: DATABASE_VIKINGMEM_COLLECTION / DATABASE_VIKINGMEM_MEMORY_TYPE
    3) Write these environment variables into the specified strategy's
       runtime_envs in agentkit.yaml, then save the config.

    Note: This function is specific to VeADK framework. For other frameworks
    like LangChain or GoogleADK, please use their respective binding functions.

    Args:
        project_dir: Project root directory or directory containing agentkit.yaml.
        memory_id: AgentKit Memory collection ID (e.g. "mem-xxxx").
        strategy_name: Strategy name to bind to ("local", "cloud", "hybrid").
            If None, uses current launch_type from AgentConfig.
        overwrite: Whether to overwrite existing env values with the same key.
        connection_index: Index of connection info to use when multiple are
            returned (default: 0).
        memory_client: Optional pre-configured AgentkitMemoryClient. If None,
            a new client will be created using AGENTKIT_* environment
            credentials.

    Returns:
        Updated AgentConfig instance after binding and saving.

    Raises:
        ValueError: If memory info cannot be retrieved, provider type is
            unsupported, or no connection infos are available.
    """
    client = memory_client or AgentkitMemoryClient()

    # 1) Get basic memory info to determine provider type and metadata
    coll_resp = client.get_memory_collection(
        GetMemoryCollectionRequest(memory_id=memory_id)
    )
    provider_type = (coll_resp.provider_type or "").upper()

    if not provider_type:
        raise ValueError(f"Memory {memory_id} has empty provider_type")

    # 2) Get connection information (base_url / auth_key etc.)
    conn_resp = client.get_memory_connection_info(
        GetMemoryConnectionInfoRequest(memory_id=memory_id)
    )
    connections = conn_resp.connection_infos or []
    if not connections:
        raise ValueError(f"Memory {memory_id} has no connection infos")

    if connection_index < 0 or connection_index >= len(connections):
        raise ValueError(
            f"connection_index {connection_index} is out of range for "
            f"memory {memory_id} (available: {len(connections)})"
        )

    conn = connections[connection_index]

    # 3) Map provider_type to env variables
    envs: Dict[str, str] = {}

    if provider_type == "MEM0":
        if not conn.base_url or not conn.auth_key:
            raise ValueError(
                f"Memory {memory_id} (MEM0) has incomplete connection info: "
                f"base_url/auth_key missing"
            )
        envs["DATABASE_MEM0_BASE_URL"] = conn.base_url
        envs["DATABASE_MEM0_API_KEY"] = conn.auth_key

    elif provider_type == "VIKINGDB_MEMORY":
        collection = coll_resp.provider_collection_id or ""
        if not collection:
            raise ValueError(
                f"Memory {memory_id} (VIKINGDB_MEMORY) has empty ProviderCollectionId"
            )

        # Derive memory_type from long term strategies' Name; fall back to a
        # reasonable default if none are present.
        strategies = []
        if (
            coll_resp.long_term_configuration
            and coll_resp.long_term_configuration.strategies
        ):
            strategies = coll_resp.long_term_configuration.strategies

        names = [s.name for s in strategies if getattr(s, "name", None)]
        memory_type = ",".join(names) if names else "event_v1"

        envs["DATABASE_VIKINGMEM_COLLECTION"] = collection
        envs["DATABASE_VIKINGMEM_MEMORY_TYPE"] = memory_type

    else:
        raise ValueError(
            f"Unsupported memory provider_type '{provider_type}' for memory {memory_id}. "
            f"Expected 'MEM0' or 'VIKINGDB_MEMORY'."
        )

    # 4) Load and update project config
    cfg = AgentConfig.load(project_dir)

    target_strategy = strategy_name or cfg.launch_type

    # Read existing strategy config and runtime_envs
    strategy_cfg = cfg.get_strategy_config(target_strategy) or {}
    current_envs = dict(strategy_cfg.get("runtime_envs") or {})

    for key, value in envs.items():
        if not overwrite and key in current_envs and current_envs[key]:
            # Keep existing non-empty value
            continue
        current_envs[key] = value

    cfg.update_strategy_config(
        {"runtime_envs": current_envs}, strategy_name=target_strategy
    )
    cfg.save()

    return cfg
