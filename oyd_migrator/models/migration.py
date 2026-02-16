"""Models for migration planning and results."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from oyd_migrator.core.constants import MigrationPath
from oyd_migrator.models.oyd import OYDDeployment
from oyd_migrator.models.foundry import FoundryAgent, ProjectConnection
from oyd_migrator.models.search import SearchIndex, IndexAnalysis


class MigrationMapping(BaseModel):
    """Mapping of OYD configuration to Foundry configuration."""

    # Source
    source_deployment: str = Field(description="OYD deployment name")
    source_index: str = Field(description="Source search index name")

    # Target
    target_agent_name: str = Field(description="Target Foundry agent name")
    target_connection_name: str = Field(description="Target connection name")

    # Configuration mappings
    query_type_mapping: dict[str, str] = Field(
        default_factory=dict,
        description="OYD query type -> Foundry query type",
    )
    instruction_mapping: str | None = Field(
        default=None,
        description="Migrated instructions from role_information",
    )
    filter_mapping: str | None = Field(
        default=None,
        description="Migrated filter expression",
    )


class MigrationPlan(BaseModel):
    """A complete migration plan."""

    plan_id: str = Field(description="Unique plan identifier")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Migration configuration
    migration_path: MigrationPath = Field(description="Target architecture")

    # Source resources
    source_deployments: list[OYDDeployment] = Field(default_factory=list)
    source_indexes: list[SearchIndex] = Field(default_factory=list)
    index_analyses: list[IndexAnalysis] = Field(default_factory=list)

    # Target configuration
    target_project_name: str = Field(description="Target Foundry project")
    target_project_endpoint: str = Field(description="Project endpoint URL")
    target_model: str = Field(default="gpt-4.1", description="Model to use")

    # Mappings
    mappings: list[MigrationMapping] = Field(default_factory=list)

    # Validation
    is_valid: bool = Field(default=False)
    validation_errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    def get_mapping_for_deployment(
        self, deployment_name: str
    ) -> MigrationMapping | None:
        """Get the mapping for a specific deployment."""
        for mapping in self.mappings:
            if mapping.source_deployment == deployment_name:
                return mapping
        return None


class TestQuery(BaseModel):
    """A test query for validation."""

    query: str = Field(description="Test query text")
    expected_topics: list[str] = Field(
        default_factory=list,
        description="Topics expected in the response",
    )
    source: str = Field(
        default="custom",
        description="Source of this query (oyd, custom, generated)",
    )


class TestResult(BaseModel):
    """Result of testing a migrated agent."""

    agent_name: str = Field(description="Agent that was tested")
    query: str = Field(description="Test query")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Response
    success: bool = Field(default=False)
    response_text: str | None = Field(default=None)
    response_time_ms: float | None = Field(default=None)

    # Tool execution
    tool_calls_count: int = Field(default=0)
    tool_types: list[str] = Field(default_factory=list)

    # Citations
    citation_count: int = Field(default=0)
    has_citations: bool = Field(default=False)

    # Token usage
    total_tokens: int = Field(default=0)

    # Error details
    error_message: str | None = Field(default=None)
    error_type: str | None = Field(default=None)


class ComparisonResult(BaseModel):
    """Comparison of OYD response vs Foundry response."""

    query: str = Field(description="Query used for comparison")

    # OYD response
    oyd_response: str | None = Field(default=None)
    oyd_citations: int = Field(default=0)
    oyd_response_time_ms: float | None = Field(default=None)

    # Foundry response
    foundry_response: str | None = Field(default=None)
    foundry_citations: int = Field(default=0)
    foundry_response_time_ms: float | None = Field(default=None)

    # Comparison metrics
    similarity_score: float | None = Field(
        default=None,
        description="Semantic similarity between responses (0-1)",
    )
    topic_coverage: float | None = Field(
        default=None,
        description="Coverage of expected topics (0-1)",
    )

    # Assessment
    is_equivalent: bool = Field(
        default=False,
        description="Whether responses are functionally equivalent",
    )
    differences: list[str] = Field(
        default_factory=list,
        description="Notable differences between responses",
    )


class ComparisonReport(BaseModel):
    """Full comparison report between OYD and Foundry."""

    report_id: str = Field(description="Report identifier")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Context
    source_deployment: str = Field(description="OYD deployment name")
    target_agent: str = Field(description="Foundry agent name")
    migration_path: MigrationPath = Field(description="Migration path used")

    # Results
    comparisons: list[ComparisonResult] = Field(default_factory=list)

    # Summary statistics
    total_queries: int = Field(default=0)
    successful_comparisons: int = Field(default=0)
    equivalent_responses: int = Field(default=0)
    average_similarity: float | None = Field(default=None)

    # Assessment
    overall_success: bool = Field(default=False)
    recommendations: list[str] = Field(default_factory=list)


class MigrationResult(BaseModel):
    """Final result of a migration operation."""

    result_id: str = Field(description="Result identifier")
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    duration_seconds: float = Field(default=0)

    # Migration details
    migration_path: MigrationPath = Field(description="Migration path used")
    plan_id: str = Field(description="Migration plan ID")

    # Resources created
    connections_created: list[ProjectConnection] = Field(default_factory=list)
    agents_created: list[FoundryAgent] = Field(default_factory=list)

    # Test results
    test_results: list[TestResult] = Field(default_factory=list)
    comparison_report: ComparisonReport | None = Field(default=None)

    # Generated artifacts
    artifacts: dict[str, str] = Field(
        default_factory=dict,
        description="Generated files (path -> content type)",
    )

    # Overall status
    success: bool = Field(default=False)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @property
    def deployments_migrated(self) -> int:
        """Count of deployments successfully migrated."""
        return len(self.agents_created)

    @property
    def all_tests_passed(self) -> bool:
        """Check if all tests passed."""
        return len(self.test_results) > 0 and all(t.success for t in self.test_results)
