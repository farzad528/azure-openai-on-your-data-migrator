"""Project connection management service."""

from __future__ import annotations

from dataclasses import dataclass, field

from azure.core.credentials import TokenCredential

from oyd_migrator.core.constants import ApiVersions
from oyd_migrator.core.exceptions import ConnectionError
from oyd_migrator.core.logging import get_logger
from oyd_migrator.models.foundry import ProjectConnection

logger = get_logger("services.connection_manager")


@dataclass
class ConnectionValidationResult:
    """Result of connection validation."""

    is_valid: bool = False
    connection_type: str = ""
    target: str = ""
    auth_type: str = ""
    issues: list[str] = field(default_factory=list)


class ConnectionManagerService:
    """Service for managing Foundry project connections."""

    def __init__(self, credential: TokenCredential, project_endpoint: str) -> None:
        """
        Initialize the connection manager.

        Args:
            credential: Azure credential
            project_endpoint: Foundry project endpoint URL
        """
        self.credential = credential
        self.project_endpoint = project_endpoint

        # Extract project info from endpoint
        # Format: https://{resource}.services.ai.azure.com/api/projects/{project}
        self._parse_endpoint()

    def _parse_endpoint(self) -> None:
        """Parse project endpoint to extract resource and project names."""
        import urllib.parse

        parsed = urllib.parse.urlparse(self.project_endpoint)
        self.host = parsed.netloc

        # Extract resource name from host
        self.resource_name = self.host.split(".")[0]

        # Extract project name from path
        path_parts = parsed.path.strip("/").split("/")
        if "projects" in path_parts:
            idx = path_parts.index("projects")
            if idx + 1 < len(path_parts):
                self.project_name = path_parts[idx + 1]
            else:
                self.project_name = ""
        else:
            self.project_name = ""

    def create_search_connection(
        self,
        name: str,
        endpoint: str,
        api_key: str | None = None,
        use_managed_identity: bool = False,
    ) -> ProjectConnection:
        """
        Create an Azure AI Search connection.

        Args:
            name: Connection name
            endpoint: Search service endpoint
            api_key: Optional API key (not needed if using MI)
            use_managed_identity: Use managed identity instead of API key

        Returns:
            Created connection

        Raises:
            ConnectionError: If creation fails
        """
        import httpx
        from oyd_migrator.core.constants import AzureScopes

        try:
            token = self.credential.get_token(AzureScopes.MANAGEMENT)

            # Build the connection resource URL
            # The exact API depends on whether we're using Azure ML or Foundry APIs
            url = self._build_connection_url(name)

            headers = {
                "Authorization": f"Bearer {token.token}",
                "Content-Type": "application/json",
            }

            body = {
                "name": name,
                "properties": {
                    "category": "AzureAISearch",
                    "target": endpoint,
                    "isSharedToAll": True,
                },
            }

            if use_managed_identity:
                body["properties"]["authType"] = "ManagedIdentity"
            elif api_key:
                body["properties"]["authType"] = "ApiKey"
                body["properties"]["credentials"] = {
                    "key": api_key,
                }
            else:
                # Default to managed identity
                body["properties"]["authType"] = "ManagedIdentity"

            response = httpx.put(url, headers=headers, json=body, timeout=60)

            if response.status_code not in [200, 201]:
                raise ConnectionError(
                    f"Failed to create connection: {response.text}",
                    details={"status_code": response.status_code},
                )

            data = response.json()

            connection = ProjectConnection(
                name=name,
                connection_type="AzureAISearch",
                target=endpoint,
                auth_type=body["properties"]["authType"],
                is_shared=True,
                connection_id=data.get("id"),
            )

            logger.info(f"Created search connection: {name}")
            return connection

        except ConnectionError:
            raise
        except Exception as e:
            logger.error(f"Failed to create connection: {e}")
            raise ConnectionError(
                f"Failed to create search connection: {e}",
                details={"name": name, "endpoint": endpoint},
            )

    def create_mcp_connection(
        self,
        name: str,
        mcp_endpoint: str,
        audience: str = "https://search.azure.com/",
    ) -> ProjectConnection:
        """
        Create an MCP (Knowledge Base) connection.

        Args:
            name: Connection name
            mcp_endpoint: MCP server URL (knowledge base endpoint)
            audience: OAuth audience for the connection

        Returns:
            Created connection

        Raises:
            ConnectionError: If creation fails
        """
        import httpx
        from oyd_migrator.core.constants import AzureScopes

        try:
            token = self.credential.get_token(AzureScopes.MANAGEMENT)

            url = self._build_connection_url(name)

            headers = {
                "Authorization": f"Bearer {token.token}",
                "Content-Type": "application/json",
            }

            body = {
                "name": name,
                "properties": {
                    "authType": "ProjectManagedIdentity",
                    "category": "RemoteTool",
                    "target": mcp_endpoint,
                    "isSharedToAll": True,
                    "audience": audience,
                    "metadata": {
                        "ApiType": "Azure",
                    },
                },
            }

            response = httpx.put(url, headers=headers, json=body, timeout=60)

            if response.status_code not in [200, 201]:
                raise ConnectionError(
                    f"Failed to create MCP connection: {response.text}",
                    details={"status_code": response.status_code},
                )

            data = response.json()

            connection = ProjectConnection(
                name=name,
                connection_type="RemoteTool",
                target=mcp_endpoint,
                auth_type="ProjectManagedIdentity",
                is_shared=True,
                connection_id=data.get("id"),
            )

            logger.info(f"Created MCP connection: {name}")
            return connection

        except ConnectionError:
            raise
        except Exception as e:
            logger.error(f"Failed to create MCP connection: {e}")
            raise ConnectionError(
                f"Failed to create MCP connection: {e}",
                details={"name": name, "mcp_endpoint": mcp_endpoint},
            )

    def _build_connection_url(self, connection_name: str) -> str:
        """Build the ARM URL for connection operations."""
        # This requires knowing the full resource path
        # Format: https://management.azure.com/{project_resource_id}/connections/{name}

        # For now, we'll construct based on known patterns
        # In production, you'd get this from the project properties

        # Placeholder - actual implementation would need subscription/RG info
        base_url = "https://management.azure.com"
        api_version = ApiVersions.FOUNDRY_CONNECTIONS

        # The actual path depends on the project structure
        # This is a simplified version
        return f"{self.project_endpoint}/connections/{connection_name}?api-version={api_version}"

    def list_connections(self) -> list[ProjectConnection]:
        """
        List all connections in the project.

        Returns:
            List of project connections
        """
        import httpx
        from oyd_migrator.core.constants import AzureScopes

        connections = []

        try:
            token = self.credential.get_token(AzureScopes.MANAGEMENT)

            url = f"{self.project_endpoint}/connections?api-version={ApiVersions.FOUNDRY_CONNECTIONS}"

            headers = {
                "Authorization": f"Bearer {token.token}",
                "Content-Type": "application/json",
            }

            response = httpx.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            data = response.json()

            for conn_data in data.get("value", []):
                props = conn_data.get("properties", {})
                connection = ProjectConnection(
                    name=conn_data.get("name", ""),
                    connection_type=props.get("category", ""),
                    target=props.get("target", ""),
                    auth_type=props.get("authType", ""),
                    is_shared=props.get("isSharedToAll", False),
                    connection_id=conn_data.get("id"),
                )
                connections.append(connection)

        except Exception as e:
            logger.warning(f"Could not list connections: {e}")

        return connections

    def validate_connection(self, connection_name: str) -> ConnectionValidationResult:
        """
        Validate a connection is accessible and configured correctly.

        Args:
            connection_name: Name of the connection to validate

        Returns:
            Validation result
        """
        result = ConnectionValidationResult()

        try:
            # Get connection details
            connections = self.list_connections()
            connection = next(
                (c for c in connections if c.name == connection_name), None
            )

            if not connection:
                result.issues.append(f"Connection '{connection_name}' not found")
                return result

            result.connection_type = connection.connection_type
            result.target = connection.target
            result.auth_type = connection.auth_type

            # Try to access the target
            import httpx

            try:
                response = httpx.head(connection.target, timeout=10)
                if response.status_code in [200, 401, 403]:
                    # Target is reachable (auth errors are expected without credentials)
                    result.is_valid = True
                else:
                    result.issues.append(
                        f"Target returned status {response.status_code}"
                    )
            except httpx.ConnectError:
                result.issues.append("Could not connect to target endpoint")
            except Exception as e:
                result.issues.append(f"Connection test failed: {e}")

        except Exception as e:
            result.issues.append(f"Validation error: {e}")

        return result

    def delete_connection(self, connection_name: str) -> bool:
        """
        Delete a connection.

        Args:
            connection_name: Name of the connection to delete

        Returns:
            True if deleted successfully
        """
        import httpx
        from oyd_migrator.core.constants import AzureScopes

        try:
            token = self.credential.get_token(AzureScopes.MANAGEMENT)

            url = f"{self.project_endpoint}/connections/{connection_name}?api-version={ApiVersions.FOUNDRY_CONNECTIONS}"

            headers = {
                "Authorization": f"Bearer {token.token}",
            }

            response = httpx.delete(url, headers=headers, timeout=30)

            if response.status_code in [200, 204]:
                logger.info(f"Deleted connection: {connection_name}")
                return True
            else:
                logger.warning(f"Delete returned status {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Failed to delete connection: {e}")
            return False
