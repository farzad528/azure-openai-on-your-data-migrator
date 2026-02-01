"""Models representing Azure AI Search resources."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class IndexField(BaseModel):
    """A field in a search index."""

    name: str = Field(description="Field name")
    type: str = Field(description="Field type (Edm.String, Collection(Edm.Single), etc.)")

    # Field attributes
    searchable: bool = Field(default=False)
    filterable: bool = Field(default=False)
    sortable: bool = Field(default=False)
    facetable: bool = Field(default=False)
    retrievable: bool = Field(default=True)
    key: bool = Field(default=False)

    # Vector field configuration
    dimensions: int | None = Field(
        default=None,
        description="Vector dimensions (for vector fields)",
    )
    vector_search_profile: str | None = Field(
        default=None,
        description="Vector search profile name",
    )

    # Analyzer
    analyzer: str | None = Field(default=None, description="Analyzer name")
    search_analyzer: str | None = Field(default=None)
    index_analyzer: str | None = Field(default=None)

    @property
    def is_vector_field(self) -> bool:
        """Check if this is a vector field."""
        return self.type == "Collection(Edm.Single)" and self.dimensions is not None

    @property
    def is_text_field(self) -> bool:
        """Check if this is a searchable text field."""
        return self.type == "Edm.String" and self.searchable


class SemanticField(BaseModel):
    """A field reference in a semantic configuration."""

    field_name: str = Field(description="Name of the referenced field")


class SemanticPrioritizedFields(BaseModel):
    """Prioritized fields for semantic search."""

    title_field: SemanticField | None = Field(default=None)
    content_fields: list[SemanticField] = Field(default_factory=list)
    keyword_fields: list[SemanticField] = Field(default_factory=list)


class SemanticConfig(BaseModel):
    """A semantic search configuration."""

    name: str = Field(description="Semantic configuration name")
    prioritized_fields: SemanticPrioritizedFields = Field(
        default_factory=SemanticPrioritizedFields
    )


class VectorSearchAlgorithm(BaseModel):
    """A vector search algorithm configuration."""

    name: str = Field(description="Algorithm name")
    kind: str = Field(description="Algorithm kind (hnsw, exhaustiveKnn)")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Algorithm parameters (m, efConstruction, efSearch, etc.)",
    )


class VectorSearchProfile(BaseModel):
    """A vector search profile."""

    name: str = Field(description="Profile name")
    algorithm_configuration_name: str = Field(description="Algorithm to use")
    vectorizer_name: str | None = Field(
        default=None,
        description="Vectorizer for query-time embedding",
    )


class VectorConfig(BaseModel):
    """Vector search configuration for an index."""

    algorithms: list[VectorSearchAlgorithm] = Field(default_factory=list)
    profiles: list[VectorSearchProfile] = Field(default_factory=list)
    vectorizers: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Configured vectorizers",
    )


class SearchIndex(BaseModel):
    """An Azure AI Search index."""

    name: str = Field(description="Index name")
    service_name: str = Field(description="Search service name")
    service_endpoint: str = Field(description="Search service endpoint")

    # Schema
    fields: list[IndexField] = Field(default_factory=list)

    # Semantic search
    semantic_configurations: list[SemanticConfig] = Field(default_factory=list)
    default_semantic_configuration: str | None = Field(default=None)

    # Vector search
    vector_search: VectorConfig | None = Field(default=None)

    # Statistics
    document_count: int | None = Field(default=None)
    storage_size: int | None = Field(default=None)

    def get_key_field(self) -> IndexField | None:
        """Get the key field."""
        for field in self.fields:
            if field.key:
                return field
        return None

    def get_text_fields(self) -> list[IndexField]:
        """Get all searchable text fields."""
        return [f for f in self.fields if f.is_text_field]

    def get_vector_fields(self) -> list[IndexField]:
        """Get all vector fields."""
        return [f for f in self.fields if f.is_vector_field]

    def get_retrievable_fields(self) -> list[IndexField]:
        """Get all retrievable fields."""
        return [f for f in self.fields if f.retrievable]

    def has_semantic_search(self) -> bool:
        """Check if semantic search is configured."""
        return len(self.semantic_configurations) > 0

    def has_vector_search(self) -> bool:
        """Check if vector search is configured."""
        return len(self.get_vector_fields()) > 0


class SearchService(BaseModel):
    """An Azure AI Search service."""

    name: str = Field(description="Service name")
    resource_group: str = Field(description="Resource group name")
    subscription_id: str = Field(description="Azure subscription ID")
    location: str = Field(description="Azure region")
    endpoint: str = Field(description="Service endpoint URL")

    # SKU and capacity
    sku: str = Field(description="SKU tier (free, basic, standard, etc.)")
    replica_count: int = Field(default=1)
    partition_count: int = Field(default=1)

    # Network configuration
    public_network_access: str = Field(
        default="enabled",
        description="Public network access status",
    )
    private_endpoint_connections: list[str] = Field(
        default_factory=list,
        description="Private endpoint connection IDs",
    )

    # Authentication
    disable_local_auth: bool = Field(
        default=False,
        description="Whether API key auth is disabled",
    )

    # Indexes
    indexes: list[SearchIndex] = Field(default_factory=list)

    @property
    def resource_id(self) -> str:
        """Get the full Azure resource ID."""
        return (
            f"/subscriptions/{self.subscription_id}"
            f"/resourceGroups/{self.resource_group}"
            f"/providers/Microsoft.Search"
            f"/searchServices/{self.name}"
        )

    @property
    def has_private_endpoints(self) -> bool:
        """Check if private endpoints are configured."""
        return len(self.private_endpoint_connections) > 0

    @property
    def requires_managed_identity(self) -> bool:
        """Check if managed identity is required (local auth disabled)."""
        return self.disable_local_auth


class IndexAnalysis(BaseModel):
    """Analysis results for a search index."""

    index_name: str = Field(description="Index name")

    # Field analysis
    total_fields: int = Field(default=0)
    text_fields: int = Field(default=0)
    vector_fields: int = Field(default=0)
    filterable_fields: int = Field(default=0)

    # Capability flags
    supports_semantic: bool = Field(default=False)
    supports_vector: bool = Field(default=False)
    supports_hybrid: bool = Field(default=False)

    # Migration compatibility
    compatible_with_search_tool: bool = Field(default=True)
    compatible_with_knowledge_base: bool = Field(default=True)
    compatibility_issues: list[str] = Field(default_factory=list)

    # Recommendations
    recommended_query_type: str = Field(default="simple")
    recommendations: list[str] = Field(default_factory=list)
