from dataclasses import dataclass, field
from typing import Dict, List
from .dataclass_utils import AutoSerializableMixin
from .constants import (
    AUTH_TYPE_CUSTOM_JWT,
    AUTH_TYPE_KEY_AUTH,
    AUTO_CREATE_VE,
    DEFAULT_CR_NAMESPACE,
    DEFAULT_IMAGE_TAG,
    DEFAULT_IMAGE_TAG_TEMPLATE,
    DEFAULT_WORKSPACE_NAME,
    DEFAULT_CR_INSTANCE_TEMPLATE_NAME,
    DEFAULT_TOS_BUCKET_TEMPLATE_NAME,
)


@dataclass
class LocalStrategyConfig(AutoSerializableMixin):
    """Local Docker strategy configuration for running agents in Docker containers."""

    # User-configurable fields
    image_tag: str = field(
        default="latest", metadata={"description": "Docker image tag", "icon": "🏷️"}
    )
    invoke_port: int = field(
        default=8000,
        metadata={"description": "Port for agent application invocation", "icon": "🌐"},
    )

    # System internal fields (not visible to users during configuration)
    container_name: str = field(
        default="",
        metadata={
            "system": True,
            "description": "Container name, auto-generated from agent name if empty",
        },
    )
    ports: List[str] = field(
        default_factory=lambda: ["8000:8000"],
        metadata={
            "system": True,
            "description": "Port mappings in host:container format",
        },
    )
    volumes: List[str] = field(
        default_factory=list,
        metadata={
            "system": True,
            "description": "Volume mappings in host:container format",
        },
    )
    restart_policy: str = field(
        default="unless-stopped",
        metadata={"system": True, "description": "Container restart policy"},
    )
    memory_limit: str = field(
        default="1g", metadata={"system": True, "description": "Container memory limit"}
    )
    cpu_limit: str = field(
        default="1", metadata={"system": True, "description": "Container CPU limit"}
    )
    container_id: str = field(
        default="",
        metadata={"system": True, "description": "Container ID after deployment"},
    )
    image_id: str = field(
        default="", metadata={"system": True, "description": "Docker image ID"}
    )
    build_timestamp: str = field(
        default="", metadata={"system": True, "description": "Timestamp of image build"}
    )
    deploy_timestamp: str = field(
        default="",
        metadata={"system": True, "description": "Timestamp of container deployment"},
    )
    full_image_name: str = field(
        default="",
        metadata={
            "system": True,
            "description": "Full Docker image name with registry",
        },
    )
    runtime_envs: Dict[str, str] = field(
        default_factory=dict,
        metadata={
            "system": True,
            "description": "Runtime environment variables (format: KEY=VALUE, one per line, use 'del KEY' to remove, 'list' to view)",
            "examples": "MODEL_AGENT_API_KEY=your_key_here, DEBUG=true",
            "icon": "🔧",
        },
    )
    _config_metadata = {
        "name": "Local Strategy Configuration",
        "welcome_message": "Welcome to AgentKit Local Docker Mode Configuration Wizard",
        "next_step_hint": "This wizard will help you configure your agent for local Docker deployment. Please provide the required information or press Enter to use default values.",
        "completion_message": "Great! Local Docker configuration is complete!",
        "next_action_hint": 'You can now use "agentkit launch" to start your application.',
    }


@dataclass
class HybridStrategyConfig(AutoSerializableMixin):
    """Hybrid deployment strategy configuration combining local Docker and Volcano Engine services."""

    # User-configurable fields
    image_tag: str = field(
        default=DEFAULT_IMAGE_TAG,
        metadata={
            "system": True,
            "description": "Docker image tag",
            "icon": "🏷️",
            "render_template": True,
            "default_template": DEFAULT_IMAGE_TAG_TEMPLATE,
        },
    )

    # System internal fields (not visible to users during configuration)
    image_id: str = field(
        default="", metadata={"system": True, "description": "Docker image ID"}
    )
    build_timestamp: str = field(
        default="", metadata={"system": True, "description": "Timestamp of image build"}
    )
    full_image_name: str = field(
        default="",
        metadata={
            "system": True,
            "description": "Full Docker image name with registry",
        },
    )

    region: str = field(
        default="cn-beijing",
        metadata={
            "description": "Volcano Engine service region",
            "icon": "🌏",
            "aliases": ["ve_region"],
            "choices": [
                {"value": "cn-beijing", "description": "Beijing"},
                {"value": "cn-shanghai", "description": "Shanghai"},
            ],
        },
    )

    region_overrides: Dict[str, str] = field(
        default_factory=dict,
        metadata={
            "description": "Service region overrides (advanced)",
            "hidden": True,
        },
    )

    # Container Registry (CR) configuration
    cr_instance_name: str = field(
        default=AUTO_CREATE_VE,
        metadata={
            "description": "Container Registry instance name",
            "icon": "📦",
            "render_template": True,
            "default_template": DEFAULT_CR_INSTANCE_TEMPLATE_NAME,
            "aliases": ["ve_cr_instance_name"],
        },
    )
    cr_namespace_name: str = field(
        default=DEFAULT_CR_NAMESPACE,
        metadata={
            "description": "Container Registry namespace",
            "icon": "📁",
            "render_template": True,
            "aliases": ["ve_cr_namespace_name"],
        },
    )
    cr_repo_name: str = field(
        default="",
        metadata={
            "description": "Container Registry repository name",
            "icon": "📋",
            "aliases": ["ve_cr_repo_name"],
        },
    )
    cr_auto_create_instance_type: str = field(
        default="Micro",
        metadata={
            "description": "CR instance type when auto-creating (Micro or Enterprise)",
            "icon": "⚙️",
            "choices": [
                {"value": "Micro", "description": "Micro"},
                {"value": "Enterprise", "description": "Enterprise"},
            ],
            "hidden": True,
        },
    )
    cr_image_full_url: str = field(
        default="",
        metadata={
            "system": True,
            "description": "Full Container Registry image URL",
            "aliases": ["ve_cr_image_full_url"],
        },
    )

    # Runtime configuration
    runtime_id: str = field(
        default="",
        metadata={
            "system": True,
            "description": "Runtime instance ID",
            "aliases": ["ve_runtime_id"],
        },
    )
    runtime_name: str = field(
        default=AUTO_CREATE_VE,
        metadata={
            "system": True,
            "description": "AgentKit Runtime instance name",
            "icon": "⚙️",
            "aliases": ["ve_runtime_name"],
        },
    )
    runtime_role_name: str = field(
        default=AUTO_CREATE_VE,
        metadata={
            "system": True,
            "description": "Runtime authorization role name",
            "icon": "🔐",
            "aliases": ["ve_runtime_role_name"],
        },
    )
    runtime_auth_type: str = field(
        default=AUTH_TYPE_KEY_AUTH,
        metadata={
            "description": "Runtime authentication type",
            "icon": "🔑",
            "choices": [
                {"value": AUTH_TYPE_KEY_AUTH, "description": "API Key authentication"},
                {
                    "value": AUTH_TYPE_CUSTOM_JWT,
                    "description": "OAuth2/JWT authentication",
                },
            ],
        },
    )
    runtime_apikey_name: str = field(
        default=AUTO_CREATE_VE,
        metadata={
            "system": True,
            "description": "Runtime API key secret name",
            "aliases": ["ve_runtime_apikey_name"],
        },
    )
    runtime_apikey: str = field(
        default="",
        metadata={
            "system": True,
            "description": "Runtime API key",
            "aliases": ["ve_runtime_apikey"],
        },
    )
    runtime_jwt_discovery_url: str = field(
        default="",
        metadata={
            "description": "OIDC Discovery URL for JWT validation (required when auth_type is custom_jwt)",
            "examples": "https://userpool-xxx.userpool.auth.id.cn-beijing.volces.com/.well-known/openid-configuration",
            "prompt_condition": {
                "depends_on": "runtime_auth_type",
                "values": [AUTH_TYPE_CUSTOM_JWT],
            },
            "validation": {
                "type": "conditional",
                "depends_on": "runtime_auth_type",
                "rules": {
                    AUTH_TYPE_CUSTOM_JWT: {
                        "required": True,
                        "pattern": r"^https://.+",
                        "hint": "(must be a valid https URL)",
                        "message": "must be a valid https URL",
                    }
                },
            },
        },
    )
    runtime_jwt_allowed_clients: List[str] = field(
        default_factory=list,
        metadata={
            "description": "Allowed OAuth2 client IDs (required when auth_type is custom_jwt)",
            "examples": "['fa99ec54-8a1c-49b2-9a9e-3f3ba31d9a33']",
            "prompt_condition": {
                "depends_on": "runtime_auth_type",
                "values": [AUTH_TYPE_CUSTOM_JWT],
            },
        },
    )
    runtime_endpoint: str = field(
        default="",
        metadata={
            "system": True,
            "description": "Runtime application access endpoint",
            "aliases": ["ve_runtime_endpoint"],
        },
    )
    runtime_envs: Dict[str, str] = field(
        default_factory=dict,
        metadata={
            "system": True,
            "description": "Runtime environment variables (format: KEY=VALUE, one per line, use 'del KEY' to remove, 'list' to view)",
            "examples": "MODEL_AGENT_API_KEY=your_key_here, DEBUG=true",
            "icon": "🔧",
        },
    )
    _config_metadata = {
        "name": "Hybrid Strategy Configuration",
        "welcome_message": "Welcome to AgentKit Hybrid Deployment Mode Configuration Wizard",
        "next_step_hint": "This wizard will help you configure your agent for hybrid deployment combining local Docker and Volcano Engine services. Please provide the required information or press Enter to use default values.",
        "completion_message": "Great! Hybrid deployment configuration is complete!",
        "next_action_hint": 'You can now use "agentkit launch" to deploy your application.',
    }


@dataclass
class CloudStrategyConfig(AutoSerializableMixin):
    """Cloud build and deployment strategy configuration for Volcano Engine."""

    region: str = field(
        default="cn-beijing",
        metadata={
            "description": "Volcano Engine service region",
            "icon": "🌏",
            "choices": [
                {"value": "cn-beijing", "description": "Beijing"},
                {"value": "cn-shanghai", "description": "Shanghai"},
            ],
        },
    )

    region_overrides: Dict[str, str] = field(
        default_factory=dict,
        metadata={
            "description": "Service region overrides (advanced)",
            "hidden": True,
        },
    )

    # Tencent Object Storage (TOS) configuration for build artifacts
    tos_bucket: str = field(
        default=AUTO_CREATE_VE,
        metadata={
            "system": True,
            "description": "TOS bucket name for storing build artifacts",
            "icon": "🗂️",
            "render_template": True,
            "default_template": DEFAULT_TOS_BUCKET_TEMPLATE_NAME,
        },
    )
    tos_prefix: str = field(
        default="agentkit-builds",
        metadata={
            "system": True,
            "description": "TOS object prefix for build artifacts",
        },
    )
    tos_object_key: str = field(
        default="",
        metadata={
            "system": True,
            "description": "TOS object key for uploaded build artifact",
        },
    )
    tos_object_url: str = field(
        default="",
        metadata={"system": True, "description": "TOS object URL for build artifact"},
    )

    # Container Registry (CR) configuration for Docker images
    image_tag: str = field(
        default=DEFAULT_IMAGE_TAG,
        metadata={
            "system": True,
            "description": "Docker image tag",
            "icon": "🏷️",
            "render_template": True,
            "default_template": DEFAULT_IMAGE_TAG_TEMPLATE,
        },
    )
    cr_instance_name: str = field(
        default=AUTO_CREATE_VE,
        metadata={
            "description": "Container Registry instance name",
            "icon": "📦",
            "render_template": True,
            "default_template": DEFAULT_CR_INSTANCE_TEMPLATE_NAME,
            "aliases": ["ve_cr_instance_name"],
        },
    )
    cr_namespace_name: str = field(
        default=DEFAULT_CR_NAMESPACE,
        metadata={
            "description": "Container Registry namespace",
            "icon": "📁",
            "render_template": True,
            "aliases": ["ve_cr_namespace_name"],
        },
    )
    cr_repo_name: str = field(
        default="",
        metadata={
            "description": "Container Registry repository name (defaults to AgentKit project name)",
            "icon": "📋",
            "aliases": ["ve_cr_repo_name"],
        },
    )
    cr_auto_create_instance_type: str = field(
        default="Micro",
        metadata={
            "description": "CR instance type when auto-creating (Micro or Enterprise)",
            "icon": "⚙️",
            "choices": [
                {"value": "Micro", "description": "Micro"},
                {"value": "Enterprise", "description": "Enterprise"},
            ],
            "hidden": True,
        },
    )
    cr_image_full_url: str = field(
        default="",
        metadata={
            "system": True,
            "description": "Full Container Registry image URL",
            "aliases": ["ve_cr_image_full_url"],
        },
    )
    build_timeout: int = field(
        default=3600,
        metadata={"system": True, "description": "Build timeout in seconds"},
    )

    # Code Pipeline configuration for CI/CD
    cp_workspace_name: str = field(
        default=DEFAULT_WORKSPACE_NAME,
        metadata={"system": True, "description": "Code Pipeline workspace name"},
    )
    cp_pipeline_name: str = field(
        default=AUTO_CREATE_VE,
        metadata={"system": True, "description": "Code Pipeline pipeline name"},
    )
    cp_pipeline_id: str = field(
        default="",
        metadata={"system": True, "description": "Code Pipeline pipeline ID"},
    )

    # Runtime configuration for deployed application
    runtime_id: str = field(
        default=AUTO_CREATE_VE,
        metadata={
            "system": True,
            "description": "Runtime instance ID",
            "aliases": ["ve_runtime_id"],
        },
    )
    runtime_name: str = field(
        default=AUTO_CREATE_VE,
        metadata={
            "system": True,
            "description": "Runtime instance name",
            "aliases": ["ve_runtime_name"],
        },
    )
    runtime_role_name: str = field(
        default=AUTO_CREATE_VE,
        metadata={
            "system": True,
            "description": "Runtime authorization role name",
            "aliases": ["ve_runtime_role_name"],
        },
    )
    runtime_auth_type: str = field(
        default=AUTH_TYPE_KEY_AUTH,
        metadata={
            "description": "Runtime authentication type",
            "icon": "🔑",
            "choices": [
                {"value": AUTH_TYPE_KEY_AUTH, "description": "API Key authentication"},
                {
                    "value": AUTH_TYPE_CUSTOM_JWT,
                    "description": "OAuth2/JWT authentication",
                },
            ],
        },
    )
    runtime_apikey_name: str = field(
        default=AUTO_CREATE_VE,
        metadata={
            "system": True,
            "description": "Runtime API key secret name",
            "aliases": ["ve_runtime_apikey_name"],
        },
    )
    runtime_apikey: str = field(
        default=AUTO_CREATE_VE,
        metadata={
            "system": True,
            "description": "Runtime API key for authentication",
            "aliases": ["ve_runtime_apikey"],
        },
    )
    runtime_jwt_discovery_url: str = field(
        default="",
        metadata={
            "description": "OIDC Discovery URL for JWT validation (required when auth_type is custom_jwt)",
            "examples": "https://userpool-xxx.userpool.auth.id.cn-beijing.volces.com/.well-known/openid-configuration",
            "prompt_condition": {
                "depends_on": "runtime_auth_type",
                "values": [AUTH_TYPE_CUSTOM_JWT],
            },
            "validation": {
                "type": "conditional",
                "depends_on": "runtime_auth_type",
                "rules": {
                    AUTH_TYPE_CUSTOM_JWT: {
                        "required": True,
                        "pattern": r"^https://.+",
                        "hint": "(must be a valid https URL)",
                        "message": "must be a valid https URL",
                    }
                },
            },
        },
    )
    runtime_jwt_allowed_clients: List[str] = field(
        default_factory=list,
        metadata={
            "description": "Allowed OAuth2 client IDs (required when auth_type is custom_jwt)",
            "examples": "['fa99ec54-8a1c-49b2-9a9e-3f3ba31d9a33']",
            "prompt_condition": {
                "depends_on": "runtime_auth_type",
                "values": [AUTH_TYPE_CUSTOM_JWT],
            },
        },
    )
    runtime_endpoint: str = field(
        default="",
        metadata={
            "system": True,
            "description": "Runtime application access endpoint (auto-populated after deployment)",
            "aliases": ["ve_runtime_endpoint"],
        },
    )
    runtime_envs: Dict[str, str] = field(
        default_factory=dict,
        metadata={
            "system": True,
            "description": "Runtime environment variables (format: KEY=VALUE, one per line, use 'del KEY' to remove, 'list' to view)",
            "examples": "MODEL_AGENT_API_KEY=your_key_here, DEBUG=true",
            "icon": "🔧",
        },
    )

    # Deployment metadata
    build_timestamp: str = field(
        default="", metadata={"system": True, "description": "Timestamp of image build"}
    )
    deploy_timestamp: str = field(
        default="", metadata={"system": True, "description": "Timestamp of deployment"}
    )

    _config_metadata = {
        "name": "Cloud Build and Deployment Configuration",
        "welcome_message": "Welcome to AgentKit Cloud Build and Deployment Mode Configuration Wizard",
        "next_step_hint": "This wizard will help you configure your agent for cloud build and deployment on Volcano Engine. Please provide the required information or press Enter to use default values.",
        "completion_message": "Great! Cloud build and deployment configuration is complete!",
        "next_action_hint": 'You can now use "agentkit launch" to build and deploy your application to the cloud.',
    }
