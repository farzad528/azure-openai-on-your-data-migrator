"""Azure OpenAI discovery service for finding OYD configurations."""

from __future__ import annotations

from azure.core.credentials import TokenCredential
from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient

from oyd_migrator.core.constants import ApiVersions
from oyd_migrator.core.exceptions import DiscoveryError
from oyd_migrator.core.logging import get_logger
from oyd_migrator.models.oyd import (
    OYDDeployment,
    OYDConfiguration,
    OYDAzureSearchSource,
    OYDFieldMapping,
)

logger = get_logger("services.aoai_discovery")


class AOAIDiscoveryService:
    """Service for discovering Azure OpenAI resources with OYD configurations."""

    def __init__(self, credential: TokenCredential, subscription_id: str) -> None:
        """
        Initialize the discovery service.

        Args:
            credential: Azure credential
            subscription_id: Azure subscription ID
        """
        self.credential = credential
        self.subscription_id = subscription_id
        self._mgmt_client = CognitiveServicesManagementClient(
            credential, subscription_id
        )

    def discover_oyd_deployments(
        self, resource_group: str | None = None
    ) -> list[OYDDeployment]:
        """
        Discover AOAI deployments with On Your Data configured.

        Args:
            resource_group: Optional resource group to filter by

        Returns:
            List of OYD deployments found
        """
        deployments = []

        try:
            # List all Cognitive Services accounts
            if resource_group:
                accounts = self._mgmt_client.accounts.list_by_resource_group(
                    resource_group
                )
            else:
                accounts = self._mgmt_client.accounts.list()

            for account in accounts:
                # Filter for OpenAI accounts
                if account.kind != "OpenAI":
                    continue

                logger.debug(f"Checking AOAI resource: {account.name}")

                # Get deployments for this account
                rg = account.id.split("/resourceGroups/")[1].split("/")[0]

                try:
                    account_deployments = self._mgmt_client.deployments.list(
                        resource_group_name=rg,
                        account_name=account.name,
                    )

                    for deployment in account_deployments:
                        # Check if deployment has OYD by examining properties
                        oyd_config = self._extract_oyd_config(
                            account, rg, deployment
                        )

                        oyd_deployment = OYDDeployment(
                            resource_name=account.name,
                            resource_group=rg,
                            subscription_id=self.subscription_id,
                            endpoint=f"https://{account.name}.openai.azure.com",
                            deployment_name=deployment.name,
                            model_name=deployment.properties.model.name if deployment.properties.model else "unknown",
                            model_version=deployment.properties.model.version if deployment.properties.model else None,
                            oyd_config=oyd_config,
                            has_oyd=oyd_config is not None and len(oyd_config.data_sources) > 0,
                            data_source_count=len(oyd_config.data_sources) if oyd_config else 0,
                        )

                        if oyd_deployment.has_oyd:
                            deployments.append(oyd_deployment)
                            logger.info(
                                f"Found OYD deployment: {account.name}/{deployment.name}"
                            )

                except Exception as e:
                    logger.warning(
                        f"Could not list deployments for {account.name}: {e}"
                    )
                    continue

        except Exception as e:
            logger.error(f"Discovery failed: {e}")
            raise DiscoveryError(
                f"Failed to discover AOAI resources: {e}",
                details={"subscription_id": self.subscription_id},
            )

        logger.info(f"Discovered {len(deployments)} OYD deployment(s)")
        return deployments

    def _extract_oyd_config(
        self, account, resource_group: str, deployment
    ) -> OYDConfiguration | None:
        """
        Extract OYD configuration from a deployment.

        Note: The management API doesn't directly expose OYD configuration.
        We need to make a data plane call to get the full configuration.
        """
        import httpx

        try:
            # Get access token for AOAI
            from oyd_migrator.core.constants import AzureScopes
            token = self.credential.get_token(AzureScopes.COGNITIVE_SERVICES)

            # Make data plane call to get extensions configuration
            endpoint = f"https://{account.name}.openai.azure.com"
            url = f"{endpoint}/openai/deployments/{deployment.name}/extensions?api-version={ApiVersions.AOAI_DATA_PLANE}"

            headers = {
                "Authorization": f"Bearer {token.token}",
                "Content-Type": "application/json",
            }

            # Note: This endpoint may not exist or may require different auth
            # In practice, OYD config is often stored differently
            # This is a best-effort extraction

            response = httpx.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                data = response.json()
                return self._parse_oyd_response(deployment.name, deployment.properties.model.name, data)
            else:
                # Try alternative: check if there's any data source config in properties
                logger.debug(f"Extensions endpoint returned {response.status_code}")
                return self._check_deployment_properties(deployment)

        except Exception as e:
            logger.debug(f"Could not extract OYD config for {deployment.name}: {e}")
            return self._check_deployment_properties(deployment)

    def _check_deployment_properties(self, deployment) -> OYDConfiguration | None:
        """
        Check deployment properties for OYD configuration hints.

        This is a fallback when we can't get the full OYD config.
        """
        # The management API doesn't expose OYD config directly
        # We return a minimal config if we detect OYD features

        # Check for known OYD-related capabilities or settings
        if hasattr(deployment.properties, 'capabilities'):
            caps = deployment.properties.capabilities or {}
            if caps.get('chatCompletion') and caps.get('embeddings'):
                # This could indicate OYD capability, but not definitive
                pass

        # Return None if we can't determine OYD status
        # The user can manually specify deployments in this case
        return None

    def _parse_oyd_response(
        self, deployment_name: str, model_name: str, data: dict
    ) -> OYDConfiguration:
        """
        Parse OYD configuration from API response.

        Args:
            deployment_name: Name of the deployment
            model_name: Model name
            data: API response data

        Returns:
            Parsed OYD configuration
        """
        data_sources = []

        for source in data.get("data_sources", []):
            source_type = source.get("type")

            if source_type == "azure_search":
                params = source.get("parameters", {})

                # Extract field mappings
                fields_mapping = OYDFieldMapping(
                    content_fields=params.get("fields_mapping", {}).get("content_fields", []),
                    title_field=params.get("fields_mapping", {}).get("title_field"),
                    url_field=params.get("fields_mapping", {}).get("url_field"),
                    filepath_field=params.get("fields_mapping", {}).get("filepath_field"),
                    vector_fields=params.get("fields_mapping", {}).get("vector_fields", []),
                )

                search_source = OYDAzureSearchSource(
                    endpoint=params.get("endpoint", ""),
                    index_name=params.get("index_name", ""),
                    authentication=params.get("authentication", {}),
                    query_type=params.get("query_type", "simple"),
                    semantic_configuration=params.get("semantic_configuration"),
                    filter=params.get("filter"),
                    fields_mapping=fields_mapping,
                    in_scope=params.get("in_scope", True),
                    role_information=params.get("role_information"),
                    strictness=params.get("strictness", 3),
                    top_n_documents=params.get("top_n_documents", 5),
                    embedding_dependency=params.get("embedding_dependency"),
                )
                data_sources.append(search_source)

        return OYDConfiguration(
            deployment_name=deployment_name,
            model=model_name,
            data_sources=data_sources,
        )

    def get_oyd_config_from_deployment(
        self,
        resource_name: str,
        resource_group: str,
        deployment_name: str,
    ) -> OYDConfiguration | None:
        """
        Get OYD configuration for a specific deployment.

        Args:
            resource_name: AOAI resource name
            resource_group: Resource group name
            deployment_name: Deployment name

        Returns:
            OYD configuration if found
        """
        try:
            deployment = self._mgmt_client.deployments.get(
                resource_group_name=resource_group,
                account_name=resource_name,
                deployment_name=deployment_name,
            )

            account = self._mgmt_client.accounts.get(
                resource_group_name=resource_group,
                account_name=resource_name,
            )

            return self._extract_oyd_config(account, resource_group, deployment)

        except Exception as e:
            logger.error(f"Failed to get OYD config: {e}")
            return None
