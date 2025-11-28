python ../tools/generate_types_from_api_json.py account_api.json \
    --output ../agentkit/sdk/account/types.py \
    --base-class-name AccountBaseModel \
    --client-output ../agentkit/sdk/account/client.py \
    --client-class-name AgentkitAccountClient \
    --client-description "AgentKit Account Management Service" \
    --service-name account \
    --types-module agentkit.sdk.account.types \
    --base-class-import agentkit.client \
    --base-client-class BaseAgentkitClient