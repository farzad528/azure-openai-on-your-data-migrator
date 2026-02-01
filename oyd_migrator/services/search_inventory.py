"""Azure AI Search inventory service."""

from __future__ import annotations

from azure.core.credentials import TokenCredential
from azure.mgmt.search import SearchManagementClient

from oyd_migrator.core.constants import ApiVersions
from oyd_migrator.core.exceptions import DiscoveryError
from oyd_migrator.core.logging import get_logger
from oyd_migrator.models.search import (
    SearchService,
    SearchIndex,
    IndexField,
    SemanticConfig,
    SemanticPrioritizedFields,
    SemanticField,
    VectorConfig,
    VectorSearchAlgorithm,
    VectorSearchProfile,
    IndexAnalysis,
)

logger = get_logger("services.search_inventory")


class SearchInventoryService:
    """Service for inventorying Azure AI Search resources."""

    def __init__(self, credential: TokenCredential, subscription_id: str) -> None:
        """
        Initialize the inventory service.

        Args:
            credential: Azure credential
            subscription_id: Azure subscription ID
        """
        self.credential = credential
        self.subscription_id = subscription_id
        self._mgmt_client = SearchManagementClient(credential, subscription_id)

    def list_search_services(
        self, resource_group: str | None = None
    ) -> list[SearchService]:
        """
        List Azure AI Search services.

        Args:
            resource_group: Optional resource group to filter by

        Returns:
            List of search services
        """
        services = []

        try:
            if resource_group:
                raw_services = self._mgmt_client.services.list_by_resource_group(
                    resource_group
                )
            else:
                raw_services = self._mgmt_client.services.list_by_subscription()

            for svc in raw_services:
                rg = svc.id.split("/resourceGroups/")[1].split("/")[0]

                # Get private endpoint connections
                pe_connections = []
                if svc.private_endpoint_connections:
                    pe_connections = [pe.id for pe in svc.private_endpoint_connections]

                service = SearchService(
                    name=svc.name,
                    resource_group=rg,
                    subscription_id=self.subscription_id,
                    location=svc.location,
                    endpoint=f"https://{svc.name}.search.windows.net",
                    sku=svc.sku.name if svc.sku else "unknown",
                    replica_count=svc.replica_count or 1,
                    partition_count=svc.partition_count or 1,
                    public_network_access=svc.public_network_access or "enabled",
                    private_endpoint_connections=pe_connections,
                    disable_local_auth=svc.disable_local_auth or False,
                )
                services.append(service)

            logger.debug(f"Found {len(services)} search service(s)")

        except Exception as e:
            logger.error(f"Failed to list search services: {e}")
            raise DiscoveryError(f"Failed to list search services: {e}")

        return services

    def get_service_by_endpoint(self, endpoint: str) -> SearchService | None:
        """
        Find a search service by its endpoint URL.

        Args:
            endpoint: Search service endpoint URL

        Returns:
            Search service if found
        """
        # Extract service name from endpoint
        # Format: https://{service-name}.search.windows.net
        try:
            import urllib.parse
            parsed = urllib.parse.urlparse(endpoint)
            service_name = parsed.netloc.split(".")[0]

            services = self.list_search_services()
            for service in services:
                if service.name == service_name:
                    return service

        except Exception as e:
            logger.warning(f"Could not find service for endpoint {endpoint}: {e}")

        return None

    def get_indexes(self, service: SearchService) -> list[SearchIndex]:
        """
        Get all indexes for a search service.

        Args:
            service: Search service to query

        Returns:
            List of indexes
        """
        import httpx

        indexes = []

        try:
            # Get admin key for data plane access
            keys = self._mgmt_client.admin_keys.get(
                resource_group_name=service.resource_group,
                search_service_name=service.name,
            )
            admin_key = keys.primary_key

            # List indexes via data plane API
            url = f"{service.endpoint}/indexes?api-version={ApiVersions.SEARCH_DATA_PLANE}"
            headers = {
                "api-key": admin_key,
                "Content-Type": "application/json",
            }

            response = httpx.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            data = response.json()

            for idx_data in data.get("value", []):
                index = self._parse_index(service, idx_data)
                indexes.append(index)

                # Get document count
                stats_url = f"{service.endpoint}/indexes/{index.name}/docs/$count?api-version={ApiVersions.SEARCH_DATA_PLANE}"
                try:
                    stats_response = httpx.get(stats_url, headers=headers, timeout=10)
                    if stats_response.status_code == 200:
                        index.document_count = int(stats_response.text)
                except Exception:
                    pass

            logger.debug(f"Found {len(indexes)} index(es) in {service.name}")

        except Exception as e:
            logger.warning(f"Could not get indexes for {service.name}: {e}")

        return indexes

    def _parse_index(self, service: SearchService, data: dict) -> SearchIndex:
        """Parse index data from API response."""
        # Parse fields
        fields = []
        for field_data in data.get("fields", []):
            field = IndexField(
                name=field_data.get("name", ""),
                type=field_data.get("type", ""),
                searchable=field_data.get("searchable", False),
                filterable=field_data.get("filterable", False),
                sortable=field_data.get("sortable", False),
                facetable=field_data.get("facetable", False),
                retrievable=field_data.get("retrievable", True),
                key=field_data.get("key", False),
                dimensions=field_data.get("dimensions"),
                vector_search_profile=field_data.get("vectorSearchProfile"),
                analyzer=field_data.get("analyzer"),
                search_analyzer=field_data.get("searchAnalyzer"),
                index_analyzer=field_data.get("indexAnalyzer"),
            )
            fields.append(field)

        # Parse semantic configurations
        semantic_configs = []
        semantic_data = data.get("semantic", {})
        for config_data in semantic_data.get("configurations", []):
            prioritized = config_data.get("prioritizedFields", {})

            title_field = None
            if prioritized.get("titleField"):
                title_field = SemanticField(
                    field_name=prioritized["titleField"].get("fieldName", "")
                )

            content_fields = [
                SemanticField(field_name=f.get("fieldName", ""))
                for f in prioritized.get("contentFields", [])
            ]

            keyword_fields = [
                SemanticField(field_name=f.get("fieldName", ""))
                for f in prioritized.get("keywordFields", [])
            ]

            semantic_config = SemanticConfig(
                name=config_data.get("name", ""),
                prioritized_fields=SemanticPrioritizedFields(
                    title_field=title_field,
                    content_fields=content_fields,
                    keyword_fields=keyword_fields,
                ),
            )
            semantic_configs.append(semantic_config)

        # Parse vector search configuration
        vector_config = None
        vector_data = data.get("vectorSearch", {})
        if vector_data:
            algorithms = [
                VectorSearchAlgorithm(
                    name=alg.get("name", ""),
                    kind=alg.get("kind", ""),
                    parameters=alg.get(alg.get("kind", ""), {}),
                )
                for alg in vector_data.get("algorithms", [])
            ]

            profiles = [
                VectorSearchProfile(
                    name=prof.get("name", ""),
                    algorithm_configuration_name=prof.get("algorithmConfigurationName", ""),
                    vectorizer_name=prof.get("vectorizerName"),
                )
                for prof in vector_data.get("profiles", [])
            ]

            vector_config = VectorConfig(
                algorithms=algorithms,
                profiles=profiles,
                vectorizers=vector_data.get("vectorizers", []),
            )

        return SearchIndex(
            name=data.get("name", ""),
            service_name=service.name,
            service_endpoint=service.endpoint,
            fields=fields,
            semantic_configurations=semantic_configs,
            default_semantic_configuration=semantic_data.get("defaultConfiguration"),
            vector_search=vector_config,
        )

    def analyze_index(self, index: SearchIndex) -> IndexAnalysis:
        """
        Analyze an index for migration compatibility.

        Args:
            index: Index to analyze

        Returns:
            Analysis results with recommendations
        """
        analysis = IndexAnalysis(
            index_name=index.name,
            total_fields=len(index.fields),
            text_fields=len(index.get_text_fields()),
            vector_fields=len(index.get_vector_fields()),
            filterable_fields=len([f for f in index.fields if f.filterable]),
            supports_semantic=index.has_semantic_search(),
            supports_vector=index.has_vector_search(),
        )

        # Determine hybrid support
        analysis.supports_hybrid = (
            analysis.supports_vector and analysis.text_fields > 0
        )

        # Check compatibility
        if not index.get_text_fields():
            analysis.compatible_with_search_tool = False
            analysis.compatible_with_knowledge_base = False
            analysis.compatibility_issues.append(
                "No searchable text fields found. At least one is required."
            )

        if not index.get_retrievable_fields():
            analysis.compatibility_issues.append(
                "No retrievable fields found. Citations may not work properly."
            )

        # Determine recommended query type
        if analysis.supports_hybrid and analysis.supports_semantic:
            analysis.recommended_query_type = "vector_semantic_hybrid"
            analysis.recommendations.append(
                "Index supports hybrid + semantic search (recommended)"
            )
        elif analysis.supports_hybrid:
            analysis.recommended_query_type = "vector_simple_hybrid"
            analysis.recommendations.append(
                "Index supports hybrid search. Consider adding semantic configuration."
            )
        elif analysis.supports_vector:
            analysis.recommended_query_type = "vector"
            analysis.recommendations.append(
                "Index supports vector search only."
            )
        elif analysis.supports_semantic:
            analysis.recommended_query_type = "semantic"
            analysis.recommendations.append(
                "Index supports semantic search. Consider adding vector fields."
            )
        else:
            analysis.recommended_query_type = "simple"
            analysis.recommendations.append(
                "Index supports simple keyword search only. "
                "Consider adding semantic config or vector fields."
            )

        return analysis
