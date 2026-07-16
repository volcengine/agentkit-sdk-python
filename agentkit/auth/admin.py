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

"""Admin provisioning for CLI login — backs ``agentkit auth admin``.

Lets an admin, from the CLI, stand up everything an end user needs to log in
with **only an address**, and publish the (non-secret) discovery document:

1. ``create_user_pool`` — create a UserPool (or reuse an existing one);
2. ``provision_cli_access`` — idempotently ensure the **public PKCE CLI client**,
   the **IAM OIDC provider** (trusting the pool issuer + that client's ``aud``),
   and the scoped **STS role** in the account;
3. ``publish_discovery`` — write ``/.well-known/agentkit-cli`` (issuer / client_id
   / role_trn / provider_trn / region — all non-secret) to a real https URL (TOS
   static hosting) and return the **login address** the end user types.

Everything reads provisioning credentials from the environment; no secret is ever
written into the discovery document or to disk.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from agentkit.auth._openapi import ApiError, OpenApiClient
from agentkit.auth.errors import AuthError

# Conventional, deterministic resource names. snake_case throughout for consistency.
CLI_CLIENT_NAME = "agentkit_cli_native"
OIDC_PROVIDER_NAME = "agentkit_cli_oidc"
ROLE_NAME = "agentkit_cli_role"
POLICY_NAME = "agentkit_cli_sandbox_access"
# AgentKit system policy attached to the CLI role so the federated identity can
# create sandbox sessions (the session/tool-read actions come from the custom policy).
SANDBOX_ACCESS_POLICY = "AgentKitSandboxAccess"
WELL_KNOWN_KEY = ".well-known/agentkit-cli"
ROLE_ACTIONS = (
    "agentkit:CreateSession", "agentkit:GetSession", "agentkit:DeleteSession",
    "agentkit:GetSessionLogs", "agentkit:SetSessionTtl",
    "agentkit:ListTools", "agentkit:GetTool",
)


@dataclass
class SsoSetupResult:
    """Result of the one-shot ``sso-setup`` — everything an end user needs."""

    login_address: str
    coords: "CliAccessCoords"
    manual_steps: list[str]


@dataclass
class CliAccessCoords:
    """The non-secret result of provisioning — feeds the discovery document."""

    account_id: str
    region: str
    user_pool_uid: str
    issuer: str
    client_id: str
    role_trn: str
    provider_trn: str

    def discovery_doc(self) -> dict:
        return {
            "issuer": self.issuer,
            "client_id": self.client_id,
            "role_trn": self.role_trn,
            "provider_trn": self.provider_trn,
            "region": self.region,
            "transport": "sts",
            "scope": "openid profile email offline_access",
        }


def _issuer(user_pool_uid: str, region: str) -> str:
    return f"https://userpool-{user_pool_uid}.userpool.auth.id.{region}.volces.com"


def identity_console_url(region: str = "cn-beijing", *, user_pool_uid: str | None = None) -> str:
    """Volcengine console URL for the Identity (UserPool) management page.

    Where the admin adds login users and configures upstream SSO federation.
    """
    base = f"https://console.volcengine.com/agentkit/region:agentkit+{region}/auth"
    return f"{base}/userPool/{user_pool_uid}" if user_pool_uid else base


def create_user_pool(name: str, *, region: str = "cn-beijing", api: OpenApiClient | None = None) -> tuple[str, str]:
    """Create a UserPool; return ``(uid, issuer)``."""
    api = api or OpenApiClient(region=region)
    res = api.call("id", "CreateUserPool", "2025-10-30", {
        "Name": name, "Description": "AgentKit CLI login pool",
        "PasswordSignInEnabled": True, "SelfSignUpEnabled": False,
    })
    uid = str(res.get("Uid") or res.get("uid") or "")
    if not uid:
        raise AuthError(f"CreateUserPool returned no uid: {json.dumps(res)[:200]}")
    return uid, _issuer(uid, region)


def _ensure_cli_client(api: OpenApiClient, user_pool_uid: str, client_name: str = CLI_CLIENT_NAME) -> str:
    """Create the public PKCE/loopback CLI client if absent; return its id."""
    lst = api.call("id", "ListUserPoolClients", "2025-10-30",
                   {"UserPoolUid": user_pool_uid, "PageNumber": 1, "PageSize": 50})
    for c in (lst.get("Data") or lst.get("data") or []):
        if c.get("Name") == client_name or c.get("name") == client_name:
            return str(c.get("Uid") or c.get("uid"))
    res = api.call("id", "CreateUserPoolClient", "2025-10-30", {
        "UserPoolUid": user_pool_uid, "Name": client_name,
        "ClientType": "MOBILE_APPLICATION",
        "AllowedCallbackUrls": ["http://127.0.0.1/callback", "http://localhost/callback"],
    })
    return str(res.get("Uid") or res.get("uid") or "")


def _find_provider_for_issuer(api: OpenApiClient, issuer: str) -> str | None:
    """Return the name of an existing OIDC provider whose IssuerURL matches, else None."""
    lst = api.call("iam", "ListOIDCProviders", "2018-01-01", {"Limit": 100})
    for p in (lst.get("OIDCProviders") or []):
        name = p.get("ProviderName") or p.get("OIDCProviderName")
        if not name:
            continue
        try:
            got = api.call("iam", "GetOIDCProvider", "2018-01-01", {"OIDCProviderName": name})
        except ApiError:
            continue
        if (got.get("IssuerURL") or got.get("IssuerUrl")) == issuer:
            return str(name)
    return None


def _ensure_oidc_provider(
    api: OpenApiClient, issuer: str, client_id: str, provider_name: str = OIDC_PROVIDER_NAME
) -> str:
    """Ensure an OIDC provider trusts ``issuer`` + ``client_id``; return its name.

    Reuses an existing provider that matches the issuer (adding the client id);
    otherwise creates ``provider_name``.
    """
    existing = _find_provider_for_issuer(api, issuer)
    if existing:
        api.call_ok("iam", "AddClientIDToOIDCProvider", "2018-01-01",
                    {"OIDCProviderName": existing, "ClientID": client_id})
        return existing
    try:
        api.call("iam", "CreateOIDCProvider", "2018-01-01", {
            "OIDCProviderName": provider_name, "IssuerURL": issuer,
            "ClientIDs": [client_id], "Description": "AgentKit CLI SSO -> STS",
        })
    except ApiError as exc:
        if "Exist" not in exc.code and "Conflict" not in exc.code:
            raise
        # A provider with this name already exists. Only reuse it if it trusts the
        # same issuer — otherwise we'd attach the client to the wrong provider.
        got = api.call("iam", "GetOIDCProvider", "2018-01-01", {"OIDCProviderName": provider_name})
        if (got.get("IssuerURL") or got.get("IssuerUrl")) != issuer:
            raise AuthError(
                f"OIDC provider '{provider_name}' already exists for a different issuer; "
                "choose a different provider name or remove the existing one."
            )
        api.call_ok("iam", "AddClientIDToOIDCProvider", "2018-01-01",
                    {"OIDCProviderName": provider_name, "ClientID": client_id})
    return provider_name


def _ensure_role(
    api: OpenApiClient, provider_trn: str, role_name: str = ROLE_NAME, policy_name: str = POLICY_NAME
) -> None:
    trust = {"Statement": [{"Effect": "Allow", "Principal": {"Federated": [provider_trn]},
                            "Action": ["sts:AssumeRoleWithOIDC"]}]}
    try:
        api.call("iam", "CreateRole", "2018-01-01", {
            "RoleName": role_name, "DisplayName": role_name,
            "TrustPolicyDocument": json.dumps(trust), "MaxSessionDuration": 3600,
            "Description": "STS role for AgentKit CLI (UserPool federated)",
        })
    except ApiError as exc:
        if "Exist" not in exc.code and "Conflict" not in exc.code:
            raise
        api.call("iam", "UpdateRole", "2018-01-01",
                 {"RoleName": role_name, "TrustPolicyDocument": json.dumps(trust),
                  "MaxSessionDuration": 3600})
    doc = {"Statement": [{"Effect": "Allow", "Action": list(ROLE_ACTIONS), "Resource": ["*"]}]}
    api.call_ok("iam", "CreatePolicy", "2018-01-01",
                {"PolicyName": policy_name, "PolicyDocument": json.dumps(doc),
                 "Description": "sandbox session control-plane actions for the CLI role"})
    api.call_ok("iam", "AttachRolePolicy", "2018-01-01",
                {"RoleName": role_name, "PolicyName": policy_name, "PolicyType": "Custom"})
    try:
        api.call_ok("iam", "AttachRolePolicy", "2018-01-01",
                    {"RoleName": role_name, "PolicyName": SANDBOX_ACCESS_POLICY, "PolicyType": "System"})
    except ApiError as exc:
        # On a never-activated account the AgentKit system policy doesn't exist; give a
        # clear remediation instead of a raw NoSuchEntity (sso-setup is idempotent to re-run).
        if any(k in exc.code for k in ("NoSuchEntity", "NotExist", "NotFound", "InvalidParameter")):
            raise AuthError(
                f"AgentKit system policy '{SANDBOX_ACCESS_POLICY}' not found — activate AgentKit "
                "on this account first, then re-run sso-setup.",
                hint="run `agentkit auth admin doctor` to check account readiness.",
            ) from exc
        raise


def provision_cli_access(
    user_pool_uid: str,
    *,
    region: str = "cn-beijing",
    account_id: str | None = None,
    client_name: str = CLI_CLIENT_NAME,
    provider_name: str = OIDC_PROVIDER_NAME,
    role_name: str = ROLE_NAME,
    policy_name: str = POLICY_NAME,
    api: OpenApiClient | None = None,
) -> CliAccessCoords:
    """Idempotently ensure the public CLI client + OIDC provider + STS role.

    Resource names default to the conventions but can be overridden. Returns the
    non-secret coordinates for the discovery document.
    """
    api = api or OpenApiClient(region=region, expect_account=account_id)
    acct = account_id or api.account_id
    issuer = _issuer(user_pool_uid, region)
    client_id = _ensure_cli_client(api, user_pool_uid, client_name)
    if not client_id:
        raise AuthError("could not create or find the public CLI client")
    resolved_provider = _ensure_oidc_provider(api, issuer, client_id, provider_name)
    provider_trn = f"trn:iam::{acct}:oidc-provider/{resolved_provider}"
    _ensure_role(api, provider_trn, role_name, policy_name)
    return CliAccessCoords(
        account_id=acct, region=region, user_pool_uid=user_pool_uid, issuer=issuer,
        client_id=client_id, role_trn=f"trn:iam::{acct}:role/{role_name}", provider_trn=provider_trn,
    )


# Upstream IdP federation presets (AgentKit account-side connector endpoints).
_IDP_PRESETS = {
    "bytedance": {
        "authorize": "https://sso.bytedance.com/oauth2/authorize",
        "token": "https://sso.bytedance.com/oauth2/access_token",
        "userinfo": "https://sso.bytedance.com/oauth2/userinfo",
        "scopes": ["openid", "profile", "email", "phone", "read"],
        "id_attribute": "name",
    },
    "feishu": {
        "authorize": "https://open.feishu.cn/open-apis/authen/v1/authorize",
        "token": "https://open.feishu.cn/open-apis/authen/v2/oauth/token",
        "userinfo": "https://open.feishu.cn/open-apis/authen/v1/user_info",
        "scopes": ["contact:user.base:readonly"],
        "id_attribute": '["data","user_id"]',
    },
}


def ensure_federation(
    api: OpenApiClient, user_pool_uid: str, idp: str, idp_client_id: str, idp_secret: str,
    *, region: str = "cn-beijing",
) -> str:
    """Ensure an upstream-IdP (Feishu / ByteDance-SSO) federation connector on the pool.

    Returns the pool-native callback URL that MUST be whitelisted on the upstream
    IdP app (the one step the AgentKit account cannot do via API).
    """
    preset = _IDP_PRESETS.get(idp)
    if not preset:
        raise AuthError(f"unknown idp {idp!r}; supported: {', '.join(_IDP_PRESETS)}")
    callback = f"{_issuer(user_pool_uid, region)}/login/generic_oauth/callback"
    lst = api.call("id", "ListIdentityProviders", "2025-10-30",
                   {"UserPoolUID": user_pool_uid, "PageNumber": 1, "PageSize": 50})
    for it in (lst.get("Data") or lst.get("data") or []):
        if (it.get("Name") or it.get("name")) == idp:
            return callback  # already federated
    # Create an OAuth identity provider on the pool with the given endpoints.
    api.call("id", "CreateIdentityProviderOAuth", "2025-10-30", {
        "UserPoolUid": user_pool_uid, "Name": idp, "Provider": "lark", "Enabled": True,
        "ClientId": idp_client_id, "ClientSecret": idp_secret,
        "AuthorizationEndpoint": preset["authorize"], "TokenEndpoint": preset["token"],
        "UserEndpoint": preset["userinfo"], "IdAttribute": preset["id_attribute"],
        "ScopesList": preset["scopes"], "UsePkce": idp == "bytedance",
        "ProviderOptions": {"IsAutoCreation": True, "IsAutoUpdate": True,
                            "IsCreationAllowed": True, "IsLinkingAllowed": True},
    })
    return callback


def sso_setup(
    *,
    user_pool_uid: str | None = None,
    create_pool_name: str | None = None,
    region: str = "cn-beijing",
    account_id: str | None = None,
    idp: str | None = None,
    idp_client_id: str | None = None,
    idp_secret: str | None = None,
    bucket: str | None = None,
    custom_domain: str | None = None,
    client_name: str = CLI_CLIENT_NAME,
    provider_name: str = OIDC_PROVIDER_NAME,
    role_name: str = ROLE_NAME,
    api: OpenApiClient | None = None,
) -> SsoSetupResult:
    """One shot: ensure pool (+ optional federation) → provision CLI access → publish.

    With only AK/SK in the environment this does every AgentKit-account-side step
    and returns the login address. The single thing it cannot do via API — adding
    the pool-native callback to the upstream IdP app — is returned in
    ``manual_steps`` (empty when reusing an already-federated pool).
    """
    api = api or OpenApiClient(region=region, expect_account=account_id)
    acct = account_id or api.account_id

    if create_pool_name:
        user_pool_uid, _ = create_user_pool(create_pool_name, region=region, api=api)
    if not user_pool_uid:
        raise AuthError("provide a UserPool uid or a name to create one")

    manual: list[str] = []
    if idp:
        if not (idp_client_id and idp_secret):
            raise AuthError(f"idp {idp} needs an app client-id and secret")
        callback = ensure_federation(api, user_pool_uid, idp, idp_client_id, idp_secret, region=region)
        manual.append(
            f"在 {idp} 应用的「允许回调地址」白名单中加入下面这条回调"
            f"(这是唯一需要在本账号之外操作的步骤):\n    {callback}"
        )

    coords = provision_cli_access(
        user_pool_uid, region=region, account_id=acct, api=api,
        client_name=client_name, provider_name=provider_name, role_name=role_name,
    )
    bucket = bucket or f"agentkit-cli-{acct}"
    url = publish_discovery(
        coords, bucket=bucket, custom_domain=custom_domain, access_key=api.ak, secret_key=api.sk,
        session_token=api.token,
    )
    if custom_domain:
        manual.append(
            f"把自定义域名指向该 bucket:CNAME {custom_domain} -> "
            f"{bucket}.tos-{region}.volces.com,并配置 https 证书(TOS/CDN)。"
        )
    return SsoSetupResult(login_address=url, coords=coords, manual_steps=manual)


def publish_discovery(
    coords: CliAccessCoords,
    *,
    bucket: str,
    custom_domain: str | None = None,
    access_key: str | None = None,
    secret_key: str | None = None,
    session_token: str | None = None,
) -> str:
    """Publish the discovery doc to TOS static hosting (real https). Returns the login URL.

    The doc is public-read and carries only non-secret identifiers. If
    ``custom_domain`` is given it is bound to the bucket and used as the URL host
    (the admin still owns the CNAME + cert); otherwise the TOS default host is used.
    The returned URL is what the end user types: ``agentkit login <url>``.
    """
    try:
        import os as _os

        import tos  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dep
        raise AuthError(
            "publishing needs the `tos` package (`pip install tos`), or host the "
            "discovery doc yourself.",
        ) from exc
    ak = access_key or _os.getenv("VOLCENGINE_ACCESS_KEY")
    sk = secret_key or _os.getenv("VOLCENGINE_SECRET_KEY")
    token = session_token or _os.getenv("VOLCENGINE_SESSION_TOKEN") or _os.getenv("VOLC_SESSIONTOKEN")
    endpoint = f"tos-{coords.region}.volces.com"
    client = tos.TosClientV2(ak, sk, endpoint, coords.region, security_token=token)
    try:
        client.create_bucket(bucket, acl=tos.ACLType.ACL_Public_Read)
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        if not any(k in msg for k in ("Exist", "exist", "Owned", "owned", "Conflict", "conflict")):
            raise AuthError(
                f"could not create the TOS bucket for the discovery doc: {msg[:120]}",
                hint="enable TOS on this account and allow public-read buckets, or pass an existing bucket.",
            ) from exc
    client.put_object(
        bucket, WELL_KNOWN_KEY, content=json.dumps(coords.discovery_doc()).encode(),
        acl=tos.ACLType.ACL_Public_Read, content_type="application/json",
    )
    if custom_domain:
        with __import__("contextlib").suppress(Exception):
            client.put_bucket_custom_domain(bucket, domain=custom_domain)  # best-effort bind
        return f"https://{custom_domain}"
    url = f"https://{bucket}.{endpoint}"
    _verify_public_discovery(url)  # fail loudly if the doc isn't anonymously readable
    return url


def _verify_public_discovery(base_url: str) -> None:
    """Assert the just-published discovery doc is ANONYMOUSLY fetchable (200 + JSON).

    Catches the 'block public access' trap where the public-read ACL is silently
    overridden and every end-user ``agentkit login`` would then 403.
    """
    import urllib.error
    import urllib.request

    from agentkit.auth.ssl_trust import harden_default_ssl_context

    harden_default_ssl_context()
    doc_url = base_url.rstrip("/") + "/" + WELL_KNOWN_KEY
    try:
        with urllib.request.urlopen(doc_url, timeout=15) as resp:
            json.loads(resp.read())  # must be valid JSON
    except urllib.error.HTTPError as exc:
        raise AuthError(
            f"the discovery doc is not publicly readable (HTTP {exc.code}) — end users' "
            "`agentkit login` would fail.",
            hint="disable 'block public access' on the account/bucket so the public-read ACL takes effect, then re-run.",
        ) from exc
    except (urllib.error.URLError, ValueError) as exc:
        raise AuthError(f"could not verify the published discovery doc at {doc_url}: {exc}") from exc


def preflight(api: OpenApiClient, *, credential_hosting: bool = True) -> list[dict]:
    """Read-only readiness checks for ``sso-setup`` (and the data plane if
    ``credential_hosting``). Returns ``[{name, status, detail, fix}]`` where status is
    ``ok`` | ``fail`` | ``warn``. Mutates nothing — meant to run BEFORE provisioning so a
    cold account learns what is missing up front instead of failing mid-mutation.
    """
    checks: list[dict] = []

    def probe(name: str, fn, fix: str) -> None:
        try:
            checks.append({"name": name, "status": "ok", "detail": fn() or "", "fix": ""})
        except ApiError as exc:
            checks.append({"name": name, "status": "fail",
                           "detail": f"{exc.code}: {exc.message[:70]}",
                           "fix": getattr(exc, "hint", None) or fix})
        except AuthError as exc:
            checks.append({"name": name, "status": "fail", "detail": str(exc).split(chr(10))[0][:80], "fix": fix})
        except Exception as exc:  # noqa: BLE001 — the doctor reports, never crashes
            checks.append({"name": name, "status": "warn", "detail": str(exc)[:80], "fix": fix})

    probe("caller identity (STS)", lambda: f"account {api.account_id}",
          "export a valid admin VOLCENGINE_ACCESS_KEY / _SECRET_KEY")
    def _pools():
        r = api.call("id", "ListUserPools", "2025-10-30", {"PageNumber": 1, "PageSize": 1})
        return f"reachable ({r.get('TotalCount') or r.get('Total') or len(r.get('Items') or r.get('Data') or [])}+ pools)"
    probe("Identity / UserPool service", _pools, "enable AgentKit Identity in the console")
    probe("IAM",
          lambda: f"reachable ({len(api.call('iam', 'ListOIDCProviders', '2018-01-01', {'Limit': 1}).get('OIDCProviders') or [])} oidc providers)",
          "use admin credentials with IAM permissions")

    def _syspol():
        api.call("iam", "GetPolicy", "2018-01-01", {"PolicyName": SANDBOX_ACCESS_POLICY, "PolicyType": "System"})
        return f"system policy '{SANDBOX_ACCESS_POLICY}' present"
    probe(f"AgentKit system policy ({SANDBOX_ACCESS_POLICY})", _syspol,
          "activate AgentKit on this account first — else sso-setup's system-policy attach fails")

    if credential_hosting:
        probe("API gateway (APIG)",
              lambda: f"{len([g for g in (api.call('apig', 'ListGateways', '2021-03-03', {'PageSize': 100, 'PageNumber': 1}).get('Items') or []) if str(g.get('Status')) in ('', 'Running')])} running gateway(s)",
              "enable the API Gateway service in the console")

        def _vpc():
            vlist = api.call_get("vpc", "DescribeVpcs", "2020-04-01", {"PageNumber": 1, "PageSize": 50}).get("Vpcs") or []
            vpc = next((v for v in vlist if v.get("IsDefault")), None) or (vlist[0] if vlist else None)
            if not vpc:
                raise AuthError("no VPC in this account (a gateway needs one)")
            subs = api.call_get("vpc", "DescribeSubnets", "2020-04-01",
                                {"VpcId": vpc.get("VpcId"), "PageNumber": 1, "PageSize": 50}).get("Subnets") or []
            if not [s for s in subs if s.get("Status") in ("Available", "")]:
                raise AuthError(f"VPC {vpc.get('VpcId')} has no available subnet")
            return f"VPC {vpc.get('VpcId')} + {len(subs)} subnet(s)"
        probe("default VPC + subnet", _vpc, "create a VPC with a subnet in this region")

        probe("VeFaaS",
              lambda: f"reachable (Total={api.call('vefaas', 'ListFunctions', '2021-03-03', {'PageNumber': 1, 'PageSize': 1}).get('Total', '?')})",
              "enable the VeFaaS service in the console")

        def _kms():
            try:
                api.call("id", "GetWorkloadPool", "2025-10-30", {"WorkloadPoolName": "default"})
                return "default workload pool present"
            except ApiError as exc:
                if "NotFound" in exc.code or "not found" in exc.message.lower():
                    return "Identity reachable (default pool will be created on first host)"
                raise
        probe("credential provider backend (Identity/KMS)", _kms,
              "enable AgentKit Identity/KMS in the console")

    return checks
