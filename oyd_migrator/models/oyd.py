"""Models representing Azure OpenAI On Your Data (OYD) configurations."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from oyd_migrator.core.constants import OYDDataSourceType


class OYDFieldMapping(BaseModel):
    """Field mappings for Azure AI Search data source in OYD."""

    content_fields: list[str] = Field(
        default_factory=list,
        description="Fields containing main content for grounding",
    )
    title_field: str | None = Field(
        default=None,
        description="Field containing document title (used in citations)",
    )
    url_field: str | None = Field(
        default=None,
        description="Field containing document URL (used in citations)",
    )
    filepath_field: str | None = Field(
        default=None,
        description="Field containing file path",
    )
    vector_fields: list[str] = Field(
        default_factory=list,
        description="Fields containing vector embeddings",
    )


class OYDAzureSearchSource(BaseModel):
    """Azure AI Search data source configuration in OYD."""

    type: Literal["azure_search"] = "azure_search"

    # Connection details
    endpoint: str = Field(description="Search service endpoint URL")
    index_name: str = Field(description="Name of the search index")

    # Authentication
    authentication: dict[str, Any] = Field(
        default_factory=dict,
        description="Authentication configuration (api_key, managed_identity, etc.)",
    )

    # Query configuration
    query_type: str = Field(
        default="simple",
        description="Search query type (simple, semantic, vector, hybrid)",
    )
    semantic_configuration: str | None = Field(
        default=None,
        description="Semantic configuration name for semantic search",
    )
    filter: str | None = Field(
        default=None,
        description="OData filter expression",
    )

    # Field mappings
    fields_mapping: OYDFieldMapping = Field(
        default_factory=OYDFieldMapping,
        description="Field mappings for content, title, URL, etc.",
    )

    # Behavior options
    in_scope: bool = Field(
        default=True,
        description="Limit responses to data from this source only",
    )
    role_information: str | None = Field(
        default=None,
        description="System message/role information for the model",
    )
    strictness: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Search strictness (1-5)",
    )
    top_n_documents: int = Field(
        default=5,
        description="Number of documents to retrieve",
    )

    # Embedding configuration (for vector search)
    embedding_dependency: dict[str, Any] | None = Field(
        default=None,
        description="Embedding model configuration",
    )


class OYDBlobSource(BaseModel):
    """Azure Blob Storage data source configuration in OYD."""

    type: Literal["azure_blob_storage"] = "azure_blob_storage"

    # Connection details
    container_url: str = Field(description="Blob container URL")

    # Authentication
    authentication: dict[str, Any] = Field(
        default_factory=dict,
        description="Authentication configuration",
    )

    # Linked search index (OYD creates an index from blob data)
    search_service_endpoint: str | None = Field(
        default=None,
        description="Search service endpoint for the generated index",
    )
    index_name: str | None = Field(
        default=None,
        description="Generated search index name",
    )


class OYDCosmosDBSource(BaseModel):
    """Azure Cosmos DB data source configuration in OYD."""

    type: Literal["azure_cosmos_db"] = "azure_cosmos_db"

    # Connection details
    endpoint: str = Field(description="Cosmos DB endpoint URL")
    database_name: str = Field(description="Database name")
    container_name: str = Field(description="Container name")

    # Authentication
    authentication: dict[str, Any] = Field(
        default_factory=dict,
        description="Authentication configuration",
    )

    # Field mappings
    fields_mapping: OYDFieldMapping = Field(
        default_factory=OYDFieldMapping,
        description="Field mappings",
    )


# Union type for all OYD data sources
OYDDataSource = OYDAzureSearchSource | OYDBlobSource | OYDCosmosDBSource


class OYDConfiguration(BaseModel):
    """Complete OYD configuration extracted from an AOAI deployment."""

    # Source deployment info
    deployment_name: str = Field(description="AOAI deployment name")
    model: str = Field(description="Model name (e.g., gpt-4o)")

    # Data sources
    data_sources: list[OYDDataSource] = Field(
        default_factory=list,
        description="Configured data sources",
    )

    # Global OYD settings
    max_tokens: int | None = Field(
        default=None,
        description="Maximum tokens for completion",
    )
    temperature: float | None = Field(
        default=None,
        description="Temperature setting",
    )

    def get_azure_search_sources(self) -> list[OYDAzureSearchSource]:
        """Get all Azure AI Search data sources."""
        return [
            ds for ds in self.data_sources if isinstance(ds, OYDAzureSearchSource)
        ]

    def get_primary_search_source(self) -> OYDAzureSearchSource | None:
        """Get the primary (first) Azure AI Search data source."""
        search_sources = self.get_azure_search_sources()
        return search_sources[0] if search_sources else None


class OYDDeployment(BaseModel):
    """An Azure OpenAI deployment with OYD configured."""

    # Resource identification
    resource_name: str = Field(description="AOAI resource name")
    resource_group: str = Field(description="Resource group name")
    subscription_id: str = Field(description="Azure subscription ID")
    endpoint: str = Field(description="AOAI endpoint URL")

    # Deployment details
    deployment_name: str = Field(description="Deployment name")
    model_name: str = Field(description="Base model (e.g., gpt-4o)")
    model_version: str | None = Field(default=None, description="Model version")

    # OYD configuration
    oyd_config: OYDConfiguration | None = Field(
        default=None,
        description="Extracted OYD configuration",
    )

    # Status
    has_oyd: bool = Field(
        default=False,
        description="Whether OYD is configured",
    )
    data_source_count: int = Field(
        default=0,
        description="Number of configured data sources",
    )

    @property
    def resource_id(self) -> str:
        """Get the full Azure resource ID."""
        return (
            f"/subscriptions/{self.subscription_id}"
            f"/resourceGroups/{self.resource_group}"
            f"/providers/Microsoft.CognitiveServices"
            f"/accounts/{self.resource_name}"
        )
