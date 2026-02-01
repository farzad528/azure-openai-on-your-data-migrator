"""Data models for the OYD Foundry Migrator."""

from oyd_migrator.models.oyd import (
    OYDConfiguration,
    OYDDataSource,
    OYDAzureSearchSource,
    OYDBlobSource,
    OYDDeployment,
)
from oyd_migrator.models.foundry import (
    FoundryProject,
    FoundryAgent,
    AgentTool,
    SearchToolConfig,
    MCPToolConfig,
)
from oyd_migrator.models.search import (
    SearchService,
    SearchIndex,
    IndexField,
    SemanticConfig,
    VectorConfig,
    IndexAnalysis,
)
from oyd_migrator.models.migration import (
    MigrationPlan,
    MigrationResult,
    TestResult,
    ComparisonReport,
)

__all__ = [
    # OYD models
    "OYDConfiguration",
    "OYDDataSource",
    "OYDAzureSearchSource",
    "OYDBlobSource",
    "OYDDeployment",
    # Foundry models
    "FoundryProject",
    "FoundryAgent",
    "AgentTool",
    "SearchToolConfig",
    "MCPToolConfig",
    # Search models
    "SearchService",
    "SearchIndex",
    "IndexField",
    "SemanticConfig",
    "VectorConfig",
    "IndexAnalysis",
    # Migration models
    "MigrationPlan",
    "MigrationResult",
    "TestResult",
    "ComparisonReport",
]
