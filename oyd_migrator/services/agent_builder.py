"""Agent builder service for creating Foundry agents."""

from __future__ import annotations

from datetime import datetime

from azure.core.credentials import TokenCredential

from oyd_migrator.core.constants import ApiVersions, MigrationPath
from oyd_migrator.core.exceptions import AgentCreationError
from oyd_migrator.core.logging import get_logger
from oyd_migrator.models.foundry import (
    FoundryAgent,
    ProjectConnection,
    SearchToolConfig,
    MCPToolConfig,
)

logger = get_logger("services.agent_builder")


class AgentBuilderService:
    """Service for building and creating Foundry agents."""

    def __init__(self, credential: TokenCredential, project_endpoint: str) -> None:
        """
        Initialize the agent builder.

        Args:
            credential: Azure credential
            project_endpoint: Foundry project endpoint URL
        """
        self.credential = credential
        self.project_endpoint = project_endpoint

    def create_search_tool_agent(
        self,
        name: str,
        model: str,
        instructions: str,
        search_connections: list[ProjectConnection],
        query_type: str = "vector_semantic_hybrid",
        top_k: int = 5,
    ) -> FoundryAgent:
        """
        Create an agent with Azure AI Search Tool.

        Args:
            name: Agent name
            model: Model deployment name
            instructions: Agent instructions
            search_connections: List of search connections to use
            query_type: Search query type
            top_k: Number of results to retrieve

        Returns:
            Created agent

        Raises:
            AgentCreationError: If creation fails
        """
        try:
            # Build tool configurations
            tools = []
            tool_configs = []

            for conn in search_connections:
                # Extract index name from connection or use default
                index_name = self._extract_index_name(conn)

                tool_config = SearchToolConfig(
                    connection_id=conn.connection_id or "",
                    index_name=index_name,
                    query_type=query_type,
                    top_k=top_k,
                )
                tool_configs.append(tool_config)

                # Build SDK-compatible tool definition
                tools.append({
                    "type": "azure_ai_search",
                    "azure_ai_search": {
                        "indexes": [
                            {
                                "project_connection_id": conn.connection_id,
                                "index_name": index_name,
                                "query_type": query_type,
                                "top_k": top_k,
                            }
                        ]
                    }
                })

            # Create agent via API
            agent_id = self._create_agent_api(
                name=name,
                model=model,
                instructions=instructions,
                tools=tools,
            )

            agent = FoundryAgent(
                name=name,
                agent_id=agent_id,
                project_name=self._get_project_name(),
                project_endpoint=self.project_endpoint,
                model=model,
                instructions=instructions,
                migration_path=MigrationPath.SEARCH_TOOL,
                tools=tool_configs,
                created_at=datetime.utcnow(),
            )

            logger.info(f"Created search tool agent: {name}")
            return agent

        except Exception as e:
            logger.error(f"Failed to create search tool agent: {e}")
            raise AgentCreationError(
                f"Failed to create agent: {e}",
                details={"name": name, "model": model},
            )

    def create_knowledge_base_agent(
        self,
        name: str,
        model: str,
        instructions: str,
        search_connections: list[ProjectConnection],
        knowledge_base_names: list[str] | None = None,
    ) -> FoundryAgent:
        """
        Create an agent with Foundry IQ Knowledge Base (MCP).

        Args:
            name: Agent name
            model: Model deployment name
            instructions: Agent instructions
            search_connections: List of search connections
            knowledge_base_names: Optional KB names (defaults from connections)

        Returns:
            Created agent

        Raises:
            AgentCreationError: If creation fails
        """
        try:
            # Build MCP tool configurations
            tools = []
            tool_configs = []

            for i, conn in enumerate(search_connections):
                # Generate KB name if not provided
                kb_name = (
                    knowledge_base_names[i]
                    if knowledge_base_names and i < len(knowledge_base_names)
                    else f"kb-{conn.name}"
                )

                # Build MCP server URL
                search_endpoint = conn.target
                mcp_url = f"{search_endpoint}/knowledgebases/{kb_name}/mcp?api-version={ApiVersions.SEARCH_DATA_PLANE}"

                tool_config = MCPToolConfig(
                    server_label=kb_name.replace("-", "_"),
                    server_url=mcp_url,
                    connection_id=conn.connection_id or "",
                    allowed_tools=["knowledge_base_retrieve"],
                    require_approval="never",
                )
                tool_configs.append(tool_config)

                # Build SDK-compatible tool definition
                tools.append({
                    "type": "mcp",
                    "server_label": tool_config.server_label,
                    "server_url": mcp_url,
                    "require_approval": "never",
                    "allowed_tools": ["knowledge_base_retrieve"],
                    "project_connection_id": conn.connection_id,
                })

            # Create agent via API
            agent_id = self._create_agent_api(
                name=name,
                model=model,
                instructions=instructions,
                tools=tools,
            )

            agent = FoundryAgent(
                name=name,
                agent_id=agent_id,
                project_name=self._get_project_name(),
                project_endpoint=self.project_endpoint,
                model=model,
                instructions=instructions,
                migration_path=MigrationPath.KNOWLEDGE_BASE,
                tools=tool_configs,
                created_at=datetime.utcnow(),
            )

            logger.info(f"Created knowledge base agent: {name}")
            return agent

        except Exception as e:
            logger.error(f"Failed to create KB agent: {e}")
            raise AgentCreationError(
                f"Failed to create agent: {e}",
                details={"name": name, "model": model},
            )

    def _create_agent_api(
        self,
        name: str,
        model: str,
        instructions: str,
        tools: list[dict],
    ) -> str:
        """
        Create agent via the Foundry Agent Service API.

        Returns:
            Agent ID
        """
        import httpx
        from oyd_migrator.core.constants import AzureScopes

        token = self.credential.get_token(AzureScopes.AI_FOUNDRY)

        url = f"{self.project_endpoint}/agents?api-version={ApiVersions.FOUNDRY_AGENTS}"

        headers = {
            "Authorization": f"Bearer {token.token}",
            "Content-Type": "application/json",
        }

        body = {
            "name": name,
            "model": model,
            "instructions": instructions,
            "tools": tools,
        }

        response = httpx.post(url, headers=headers, json=body, timeout=60)

        if response.status_code not in [200, 201]:
            raise AgentCreationError(
                f"Agent API returned {response.status_code}: {response.text}"
            )

        data = response.json()
        return data.get("id", name)

    def _extract_index_name(self, connection: ProjectConnection) -> str:
        """Extract index name from connection or generate a default."""
        # The index name might be in the connection metadata
        # For now, return a placeholder that should be replaced
        return connection.name.replace("-connection", "-index")

    def _get_project_name(self) -> str:
        """Extract project name from endpoint."""
        import urllib.parse

        parsed = urllib.parse.urlparse(self.project_endpoint)
        path_parts = parsed.path.strip("/").split("/")

        if "projects" in path_parts:
            idx = path_parts.index("projects")
            if idx + 1 < len(path_parts):
                return path_parts[idx + 1]

        return "unknown"

    def get_agent(self, name: str) -> FoundryAgent | None:
        """
        Get an existing agent by name.

        Args:
            name: Agent name

        Returns:
            Agent if found
        """
        import httpx
        from oyd_migrator.core.constants import AzureScopes

        try:
            token = self.credential.get_token(AzureScopes.AI_FOUNDRY)

            url = f"{self.project_endpoint}/agents/{name}?api-version={ApiVersions.FOUNDRY_AGENTS}"

            headers = {
                "Authorization": f"Bearer {token.token}",
            }

            response = httpx.get(url, headers=headers, timeout=30)

            if response.status_code == 404:
                return None

            response.raise_for_status()

            data = response.json()

            return FoundryAgent(
                name=data.get("name", name),
                agent_id=data.get("id"),
                project_name=self._get_project_name(),
                project_endpoint=self.project_endpoint,
                model=data.get("model", ""),
                instructions=data.get("instructions", ""),
                migration_path=MigrationPath.SEARCH_TOOL,  # Default, would need to inspect tools
                tools=[],
            )

        except Exception as e:
            logger.warning(f"Could not get agent {name}: {e}")
            return None

    def delete_agent(self, name: str) -> bool:
        """
        Delete an agent.

        Args:
            name: Agent name

        Returns:
            True if deleted successfully
        """
        import httpx
        from oyd_migrator.core.constants import AzureScopes

        try:
            token = self.credential.get_token(AzureScopes.AI_FOUNDRY)

            url = f"{self.project_endpoint}/agents/{name}?api-version={ApiVersions.FOUNDRY_AGENTS}"

            headers = {
                "Authorization": f"Bearer {token.token}",
            }

            response = httpx.delete(url, headers=headers, timeout=30)

            if response.status_code in [200, 204]:
                logger.info(f"Deleted agent: {name}")
                return True
            else:
                logger.warning(f"Delete returned status {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Failed to delete agent: {e}")
            return False
