"""Models representing Azure AI Foundry resources."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from oyd_migrator.core.constants import MigrationPath


class FoundryResource(BaseModel):
    """Azure AI Foundry resource (formerly Azure AI hub)."""

    name: str = Field(description="Resource name")
    resource_group: str = Field(description="Resource group name")
    subscription_id: str = Field(description="Azure subscription ID")
    location: str = Field(description="Azure region")
    endpoint: str = Field(description="Resource endpoint URL")

    @property
    def resource_id(self) -> str:
        """Get the full Azure resource ID."""
        return (
            f"/subscriptions/{self.subscription_id}"
            f"/resourceGroups/{self.resource_group}"
            f"/providers/Microsoft.MachineLearningServices"
            f"/workspaces/{self.name}"
        )


class FoundryProject(BaseModel):
    """Azure AI Foundry project."""

    name: str = Field(description="Project name")
    resource_name: str = Field(description="Parent Foundry resource name")
    resource_group: str = Field(description="Resource group name")
    subscription_id: str = Field(description="Azure subscription ID")
    location: str = Field(description="Azure region")
    endpoint: str = Field(description="Project endpoint URL")

    # Capabilities
    has_agent_service: bool = Field(
        default=False,
        description="Whether Agent Service is enabled",
    )
    deployment_type: Literal["basic", "standard"] = Field(
        default="basic",
        description="Deployment type (standard required for VNet)",
    )

    @property
    def resource_id(self) -> str:
        """Get the full Azure resource ID."""
        return (
            f"/subscriptions/{self.subscription_id}"
            f"/resourceGroups/{self.resource_group}"
            f"/providers/Microsoft.MachineLearningServices"
            f"/workspaces/{self.resource_name}"
            f"/projects/{self.name}"
        )


class ProjectConnection(BaseModel):
    """A connection configured in a Foundry project."""

    name: str = Field(description="Connection name")
    connection_type: str = Field(description="Connection type (e.g., azure_ai_search)")
    target: str = Field(description="Target endpoint URL")
    auth_type: str = Field(
        default="api_key",
        description="Authentication type (api_key, managed_identity, etc.)",
    )
    is_shared: bool = Field(
        default=True,
        description="Whether connection is shared to all project users",
    )

    # Full resource ID
    connection_id: str | None = Field(
        default=None,
        description="Full Azure resource ID of the connection",
    )


class SearchToolConfig(BaseModel):
    """Configuration for Azure AI Search Agent Tool."""

    connection_id: str = Field(description="Project connection resource ID")
    index_name: str = Field(description="Search index name")
    query_type: str = Field(
        default="vector_semantic_hybrid",
        description="Query type (simple, vector, semantic, etc.)",
    )
    top_k: int = Field(default=5, description="Number of results to retrieve")
    filter: str | None = Field(default=None, description="OData filter expression")


class MCPToolConfig(BaseModel):
    """Configuration for MCP (Knowledge Base) tool."""

    server_label: str = Field(description="Server label identifier")
    server_url: str = Field(description="MCP server URL (knowledge base endpoint)")
    connection_id: str = Field(description="Project connection resource ID")
    allowed_tools: list[str] = Field(
        default_factory=lambda: ["knowledge_base_retrieve"],
        description="Allowed MCP tools",
    )
    require_approval: str = Field(
        default="never",
        description="Tool approval requirement",
    )
    headers: dict[str, str] = Field(
        default_factory=dict,
        description="Additional headers (e.g., x-ms-query-source-authorization)",
    )


# Union type for tool configurations
AgentTool = SearchToolConfig | MCPToolConfig


class FoundryAgent(BaseModel):
    """A Foundry Agent Service agent."""

    name: str = Field(description="Agent name")
    agent_id: str | None = Field(default=None, description="Agent ID after creation")
    version: str | None = Field(default=None, description="Agent version")

    # Project context
    project_name: str = Field(description="Parent project name")
    project_endpoint: str = Field(description="Project endpoint URL")

    # Agent configuration
    model: str = Field(description="Model deployment name (e.g., gpt-4.1)")
    instructions: str = Field(description="Agent instructions/system message")

    # Tools
    migration_path: MigrationPath = Field(description="Migration architecture used")
    tools: list[AgentTool] = Field(
        default_factory=list,
        description="Configured tools",
    )

    # Metadata
    created_at: datetime | None = Field(default=None)
    source_deployment: str | None = Field(
        default=None,
        description="Original OYD deployment this was migrated from",
    )

    def get_search_tools(self) -> list[SearchToolConfig]:
        """Get all Azure AI Search tools."""
        return [t for t in self.tools if isinstance(t, SearchToolConfig)]

    def get_mcp_tools(self) -> list[MCPToolConfig]:
        """Get all MCP/Knowledge Base tools."""
        return [t for t in self.tools if isinstance(t, MCPToolConfig)]


class AgentThread(BaseModel):
    """A conversation thread for an agent."""

    thread_id: str = Field(description="Thread ID")
    agent_id: str = Field(description="Associated agent ID")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AgentRun(BaseModel):
    """A run (execution) of an agent on a thread."""

    run_id: str = Field(description="Run ID")
    thread_id: str = Field(description="Thread ID")
    agent_id: str = Field(description="Agent ID")
    status: str = Field(description="Run status (queued, in_progress, completed, etc.)")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = Field(default=None)

    # Results
    response_text: str | None = Field(default=None, description="Generated response")
    tool_calls: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Tool calls made during the run",
    )
    citations: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Citations in the response",
    )

    # Token usage
    prompt_tokens: int = Field(default=0)
    completion_tokens: int = Field(default=0)
    total_tokens: int = Field(default=0)
