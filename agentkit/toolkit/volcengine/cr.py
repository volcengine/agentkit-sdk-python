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

import logging
import time

from agentkit.platform import resolve_endpoint, VolcConfiguration
from agentkit.utils.ve_sign import ve_request

logger = logging.getLogger(__name__)

DEFAULT_CR_INSTANCE_NAME = "agentkit-platform-instance"
DEFAULT_CR_NAMESPACE_NAME = "agenkit-platform-namespace"
DEFAULT_CR_REPO_NAME = "agentkit-platform-repo"


class VeCR:
    def __init__(self, access_key: str, secret_key: str, region: str = "cn-beijing"):
        self.ak = access_key
        self.sk = secret_key

        config = VolcConfiguration(region=region or None)
        ep = resolve_endpoint(
            "cr",
            region=region or None,
            platform_config=config,
        )
        self.region = ep.region
        self.version = ep.api_version
        self.host = ep.host
        self.scheme = ep.scheme

    def _create_instance(
        self,
        instance_name: str = DEFAULT_CR_INSTANCE_NAME,
        instance_type: str = "Micro",
    ) -> str:
        """
        Create CR instance.

        Args:
            instance_name: CR instance name.
            instance_type: Instance type, must be "Micro" or "Enterprise". Defaults to "Micro".

        Returns:
            CR instance name.

        Raises:
            ValueError: If instance_type is invalid or instance creation fails.
        """
        if instance_type not in ("Micro", "Enterprise"):
            raise ValueError(
                f"Invalid instance_type: {instance_type}. Must be 'Micro' or 'Enterprise'."
            )

        status = self._check_instance(instance_name)
        if status != "NONEXIST":
            logger.debug(f"cr instance {instance_name} already running")
            return instance_name
        response = ve_request(
            request_body={
                "Name": instance_name,
                "ResourceTags": [
                    {"Key": "provider", "Value": "agentkit-cli"},
                ],
                "Type": instance_type,
            },
            action="CreateRegistry",
            ak=self.ak,
            sk=self.sk,
            service="cr",
            version=self.version,
            region=self.region,
            host=self.host,
            scheme=self.scheme,
        )
        logger.debug(f"create cr instance {instance_name}: {response}")

        if "Error" in response["ResponseMetadata"]:
            error_code = response["ResponseMetadata"]["Error"]["Code"]
            error_message = response["ResponseMetadata"]["Error"]["Message"]
            if error_code == "AlreadyExists.Registry":
                logger.debug(f"cr instance {instance_name} already exists")
                return instance_name
            else:
                logger.error(
                    f"Error create cr instance {instance_name}: {error_code} {error_message}"
                )
                raise ValueError(
                    f"Error create cr instance {instance_name}: {error_code} {error_message}"
                )

        while True:
            status = self._check_instance(instance_name)
            if status == "Running":
                break
            elif status == "Failed":
                raise ValueError(f"cr instance {instance_name} create failed")
            else:
                logger.debug(f"cr instance status: {status}")
                time.sleep(30)

        return instance_name

    def _check_instance(self, instance_name: str) -> str:
        """
        check cr instance status

        Args:
            instance_name: cr instance name

        Returns:
            cr instance status
        """
        response = ve_request(
            request_body={
                "Filter": {
                    "Names": [instance_name],
                }
            },
            action="ListRegistries",
            ak=self.ak,
            sk=self.sk,
            service="cr",
            version=self.version,
            region=self.region,
            host=self.host,
            scheme=self.scheme,
        )
        logger.debug(f"check cr instance {instance_name}: {response}")

        try:
            if response["Result"]["TotalCount"] == 0:
                return "NONEXIST"
            return response["Result"]["Items"][0]["Status"]["Phase"]
        except Exception as _:
            raise ValueError(f"Error check cr instance {instance_name}: {response}")

    def _create_namespace(
        self,
        instance_name: str = DEFAULT_CR_INSTANCE_NAME,
        namespace_name: str = DEFAULT_CR_NAMESPACE_NAME,
    ) -> str:
        """
        create cr namespace

        Args:
            instance_name: cr instance name
            namespace_name: cr namespace name

        Returns:
            cr namespace name
        """
        response = ve_request(
            request_body={
                "Name": namespace_name,
                "Registry": instance_name,
            },
            action="CreateNamespace",
            ak=self.ak,
            sk=self.sk,
            service="cr",
            version=self.version,
            region=self.region,
            host=self.host,
            scheme=self.scheme,
        )
        logger.debug(f"create cr namespace {namespace_name}: {response}")

        if "Error" in response["ResponseMetadata"]:
            error_code = response["ResponseMetadata"]["Error"]["Code"]
            error_message = response["ResponseMetadata"]["Error"]["Message"]
            if error_code == "AlreadyExists.Namespace":
                logger.warning(f"cr namespace {namespace_name} already exists")
                return namespace_name
            else:
                logger.error(
                    f"Error create cr namespace {namespace_name}: {error_code} {error_message}"
                )
                raise ValueError(
                    f"Error create cr namespace {namespace_name}: {error_code} {error_message}"
                )

        return namespace_name

    def _create_repo(
        self,
        instance_name: str = DEFAULT_CR_INSTANCE_NAME,
        namespace_name: str = DEFAULT_CR_NAMESPACE_NAME,
        repo_name: str = DEFAULT_CR_REPO_NAME,
    ) -> str:
        """
        create cr repo

        Args:
            instance_name: cr instance name
            namespace_name: cr namespace name
            repo_name: cr repo name

        Returns:
            cr repo name
        """
        response = ve_request(
            request_body={
                "Name": repo_name,
                "Registry": instance_name,
                "Namespace": namespace_name,
                "Type": "Micro",
                "Description": "veadk cr repo",
            },
            action="CreateRepository",
            ak=self.ak,
            sk=self.sk,
            service="cr",
            version=self.version,
            region=self.region,
            host=self.host,
            scheme=self.scheme,
        )
        logger.debug(f"create cr repo {repo_name}: {response}")

        if "Error" in response["ResponseMetadata"]:
            error_code = response["ResponseMetadata"]["Error"]["Code"]
            error_message = response["ResponseMetadata"]["Error"]["Message"]
            if error_code == "AlreadyExists.Repository":
                logger.debug(f"cr repo {repo_name} already exists")
                return repo_name
            else:
                logger.error(
                    f"Error create cr repo {repo_name}: {error_code} {error_message}"
                )
                raise ValueError(
                    f"Error create cr repo {repo_name}: {error_code} {error_message}"
                )
        return repo_name

    def _get_authorization_token(self, instance_name: str):
        """
        get cr authorization token
        """
        response = ve_request(
            request_body={
                "Registry": instance_name,
            },
            action="GetAuthorizationToken",
            ak=self.ak,
            sk=self.sk,
            service="cr",
            version=self.version,
            region=self.region,
            host=self.host,
            scheme=self.scheme,
        )
        logger.debug(f"get cr authorization token: {response}")

        if "Error" in response["ResponseMetadata"]:
            error_code = response["ResponseMetadata"]["Error"]["Code"]
            error_message = response["ResponseMetadata"]["Error"]["Message"]
            logger.error(
                f"Error get cr authorization token: {error_code} {error_message}"
            )
            raise ValueError(
                f"Error get cr authorization token: {error_code} {error_message}"
            )
        # print(json.dumps(response, indent=2))
        return (
            response["Result"]["Username"],
            response["Result"]["Token"],
            response["Result"]["ExpireTime"],
        )

    # GetPublicEndpoint
    def _get_public_endpoint(self, instance_name: str = DEFAULT_CR_INSTANCE_NAME):
        """
        get cr public endpoint
        """
        response = ve_request(
            request_body={
                "Registry": instance_name,
            },
            action="GetPublicEndpoint",
            ak=self.ak,
            sk=self.sk,
            service="cr",
            version=self.version,
            region=self.region,
            host=self.host,
            scheme=self.scheme,
        )
        logger.debug(f"get cr public endpoint: {response}")
        if "Error" in response["ResponseMetadata"]:
            error_code = response["ResponseMetadata"]["Error"]["Code"]
            error_message = response["ResponseMetadata"]["Error"]["Message"]
            logger.error(f"Error get cr public endpoint: {error_code} {error_message}")
            raise ValueError(
                f"Error get cr public endpoint: {error_code} {error_message}"
            )
        return response["Result"]

    def _update_public_endpoint(self, instance_name: str, enabled: bool):
        """
        update cr public endpoint
        """
        response = ve_request(
            request_body={
                "Registry": instance_name,
                "Enabled": enabled,
            },
            action="UpdatePublicEndpoint",
            ak=self.ak,
            sk=self.sk,
            service="cr",
            version=self.version,
            region=self.region,
            host=self.host,
            scheme=self.scheme,
        )
        logger.debug(f"update cr public endpoint: {response}")
        if "Error" in response["ResponseMetadata"]:
            error_code = response["ResponseMetadata"]["Error"]["Code"]
            error_message = response["ResponseMetadata"]["Error"]["Message"]
            logger.error(
                f"Error update cr public endpoint: {error_code} {error_message}"
            )
            raise ValueError(
                f"Error update cr public endpoint: {error_code} {error_message}"
            )
        return None

    def _create_endpoint_acl_policies(
        self,
        instance_name: str = DEFAULT_CR_INSTANCE_NAME,
        acl_policies: list = [],
        policy_type: str = "Public",
        description: str = "",
    ):
        """
        create endpoint acl policies
        """
        response = ve_request(
            request_body={
                "Registry": instance_name,
                "Type": policy_type,
                "Entries": acl_policies,
                "Description": description,
            },
            action="CreateEndpointAclPolicies",
            ak=self.ak,
            sk=self.sk,
            service="cr",
            version=self.version,
            region=self.region,
            host=self.host,
            scheme=self.scheme,
        )
        logger.debug(f"create endpoint acl policies: {response}")

        if "Error" in response["ResponseMetadata"]:
            error_code = response["ResponseMetadata"]["Error"]["Code"]
            error_message = response["ResponseMetadata"]["Error"]["Message"]
            logger.error(
                f"Error create endpoint acl policies: {error_code} {error_message}"
            )
            raise ValueError(
                f"Error create endpoint acl policies: {error_code} {error_message}"
            )
        return None

    def _list_domains(self, instance_name: str = DEFAULT_CR_INSTANCE_NAME):
        """
        list cr domains
        """
        response = ve_request(
            request_body={
                "Registry": instance_name,
            },
            action="ListDomains",
            ak=self.ak,
            sk=self.sk,
            service="cr",
            version=self.version,
            region=self.region,
            host=self.host,
            scheme=self.scheme,
        )
        logger.debug(f"list cr domains: {response}")
        if "Error" in response["ResponseMetadata"]:
            error_code = response["ResponseMetadata"]["Error"]["Code"]
            error_message = response["ResponseMetadata"]["Error"]["Message"]
            logger.error(f"Error list cr domains: {error_code} {error_message}")
            raise ValueError(f"Error list cr domains: {error_code} {error_message}")
        return response["Result"]["Items"]

    def _get_default_domain(self, instance_name: str = DEFAULT_CR_INSTANCE_NAME):
        """
        get default cr domain
        """
        domains = self._list_domains(instance_name=instance_name)
        try:
            if isinstance(domains, list) and len(domains) == 1:
                single = domains[0]
                if isinstance(single, dict) and "Domain" in single:
                    return single["Domain"]
        except Exception:
            pass
        for domain in domains:
            if domain["Default"]:
                return domain["Domain"]
        return None
