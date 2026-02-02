"""Foundry project provisioning service."""

from __future__ import annotations

from azure.core.credentials import TokenCredential

from oyd_migrator.core.constants import ApiVersions
from oyd_migrator.core.exceptions import ProvisioningError
from oyd_migrator.core.logging import get_logger
from oyd_migrator.models.foundry import FoundryProject, FoundryResource

logger = get_logger("services.foundry_provisioner")


class FoundryProvisionerService:
    """Service for provisioning Azure AI Foundry resources."""

    def __init__(self, credential: TokenCredential, subscription_id: str) -> None:
        """
        Initialize the provisioner service.

        Args:
            credential: Azure credential
            subscription_id: Azure subscription ID
        """
        self.credential = credential
        self.subscription_id = subscription_id

    def list_projects(self) -> list[FoundryProject]:
        """
        List existing Foundry projects.

        Returns:
            List of Foundry projects
        """
        import httpx
        from oyd_migrator.core.constants import AzureScopes

        projects = []

        try:
            token = self.credential.get_token(AzureScopes.MANAGEMENT)

            # List ML workspaces (Foundry resources are ML workspaces with specific kind)
            url = (
                f"https://management.azure.com/subscriptions/{self.subscription_id}"
                f"/providers/Microsoft.MachineLearningServices/workspaces"
                f"?api-version=2024-04-01"
            )

            headers = {
                "Authorization": f"Bearer {token.token}",
                "Content-Type": "application/json",
            }

            response = httpx.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            data = response.json()

            for workspace in data.get("value", []):
                # Filter for AI Foundry resources (kind = "Project" or "Hub")
                kind = workspace.get("kind", "")

                if kind == "Project":
                    rg = workspace["id"].split("/resourceGroups/")[1].split("/")[0]

                    # Extract endpoint from properties
                    props = workspace.get("properties", {})

                    # Build initial project with placeholder endpoint
                    # We'll update this with the real endpoint from connections
                    placeholder_endpoint = self._build_project_endpoint(workspace, props)

                    project = FoundryProject(
                        name=workspace["name"],
                        resource_name=props.get("hubResourceId", "").split("/")[-1] if props.get("hubResourceId") else workspace["name"],
                        resource_group=rg,
                        subscription_id=self.subscription_id,
                        location=workspace.get("location", ""),
                        endpoint=placeholder_endpoint,
                        has_agent_service=True,  # Assume true for Projects
                    )
                    
                    # Try to get the real AI Services endpoint from connections
                    real_endpoint = self._get_ai_services_endpoint(project, token.token)
                    if real_endpoint:
                        project.endpoint = real_endpoint
                    
                    projects.append(project)

            logger.debug(f"Found {len(projects)} Foundry project(s)")

        except Exception as e:
            logger.warning(f"Could not list Foundry projects: {e}")

        return projects

    def _build_project_endpoint(self, workspace: dict, properties: dict) -> str:
        """Build the project endpoint URL."""
        # The Foundry Agent Service endpoint is based on the AI Services connection
        # Format: https://{ai-services-resource}.cognitiveservices.azure.com/
        # or: https://{ai-services-resource}.services.ai.azure.com/
        
        # First try to get from workspaceUrl if available
        workspace_url = properties.get("workspaceUrl", "")
        if workspace_url:
            return workspace_url

        # Get the AI Services endpoint from the hub's connected resources
        # The hub resource ID tells us where to look
        hub_id = properties.get("hubResourceId", "")
        workspace_name = workspace["name"]
        location = workspace.get("location", "")
        
        if hub_id:
            # Extract hub info and construct endpoint
            # Hub ID format: /subscriptions/.../resourceGroups/.../providers/Microsoft.MachineLearningServices/workspaces/{hub-name}
            parts = hub_id.split("/")
            if len(parts) >= 9:
                rg = parts[4]  # resourceGroups/{rg}
                hub_name = parts[-1]
                
                # The AI Services account is typically named with pattern ai-{hub-name}{random}
                # We'll construct the endpoint using the standard format
                # This will be validated when we actually try to connect
                
                # Try the new services.ai.azure.com format first
                return f"https://{hub_name}.services.ai.azure.com/api/projects/{workspace_name}"
        
        # Fallback: use the workspace name directly
        return f"https://{workspace_name}.services.ai.azure.com/api/projects/{workspace_name}"
    
    def _get_ai_services_endpoint(self, project: 'FoundryProject', token: str) -> str | None:
        """
        Get the AI Services endpoint from project connections during listing.
        
        Args:
            project: Foundry project (partially populated)
            token: Already-acquired bearer token
            
        Returns:
            AI Services endpoint URL, or None if not found
        """
        import httpx
        
        try:
            # List connections for the workspace
            url = (
                f"https://management.azure.com/subscriptions/{self.subscription_id}"
                f"/resourceGroups/{project.resource_group}"
                f"/providers/Microsoft.MachineLearningServices/workspaces/{project.name}"
                f"/connections?api-version=2024-07-01-preview"
            )
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            
            response = httpx.get(url, headers=headers, timeout=30)
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            # Find the AIServices connection (preferred) or AzureOpenAI connection
            for conn in data.get("value", []):
                props = conn.get("properties", {})
                category = props.get("category", "")
                
                if category == "AIServices":
                    target = props.get("target", "")
                    if target:
                        logger.debug(f"Found AIServices endpoint for {project.name}: {target}")
                        return target
            
            # Fallback: try AzureOpenAI connection
            for conn in data.get("value", []):
                props = conn.get("properties", {})
                category = props.get("category", "")
                
                if category == "AzureOpenAI":
                    target = props.get("target", "")
                    if target:
                        # Convert OpenAI endpoint format to cognitiveservices format
                        # e.g., https://x.openai.azure.com/ -> https://x.cognitiveservices.azure.com/
                        if ".openai.azure.com" in target:
                            target = target.replace(".openai.azure.com", ".cognitiveservices.azure.com")
                        logger.debug(f"Using AzureOpenAI endpoint for {project.name}: {target}")
                        return target
            
            return None
            
        except Exception as e:
            logger.debug(f"Could not get AI Services endpoint for {project.name}: {e}")
            return None
    
    def get_project_agent_endpoint(self, project: 'FoundryProject') -> str | None:
        """
        Get the actual AI Services endpoint for Agent Service from project connections.
        
        This fetches the AIServices connection from the workspace to get the correct endpoint.
        
        Args:
            project: Foundry project
            
        Returns:
            The AI Services endpoint URL, or None if not found
        """
        import httpx
        from oyd_migrator.core.constants import AzureScopes
        
        try:
            token = self.credential.get_token(AzureScopes.MANAGEMENT)
            
            # List connections for the workspace
            url = (
                f"https://management.azure.com/subscriptions/{self.subscription_id}"
                f"/resourceGroups/{project.resource_group}"
                f"/providers/Microsoft.MachineLearningServices/workspaces/{project.name}"
                f"/connections?api-version=2024-07-01-preview"
            )
            
            headers = {
                "Authorization": f"Bearer {token.token}",
                "Content-Type": "application/json",
            }
            
            response = httpx.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Find the AIServices connection
            for conn in data.get("value", []):
                props = conn.get("properties", {})
                category = props.get("category", "")
                
                if category == "AIServices":
                    target = props.get("target", "")
                    if target:
                        logger.debug(f"Found AIServices endpoint: {target}")
                        return target
            
            logger.warning(f"No AIServices connection found for project {project.name}")
            return None
            
        except Exception as e:
            logger.warning(f"Could not get agent endpoint for {project.name}: {e}")
            return None

    def create_project(
        self,
        name: str,
        resource_group: str,
        location: str | None = None,
        hub_resource_id: str | None = None,
    ) -> FoundryProject:
        """
        Create a new Foundry project.

        Args:
            name: Project name
            resource_group: Resource group for the project
            location: Azure region (defaults to eastus)
            hub_resource_id: Optional parent hub resource ID

        Returns:
            Created Foundry project

        Raises:
            ProvisioningError: If creation fails
        """
        import httpx
        from oyd_migrator.core.constants import AzureScopes
        from oyd_migrator.core.config import get_settings

        settings = get_settings()
        location = location or settings.default_location

        try:
            token = self.credential.get_token(AzureScopes.MANAGEMENT)

            url = (
                f"https://management.azure.com/subscriptions/{self.subscription_id}"
                f"/resourceGroups/{resource_group}"
                f"/providers/Microsoft.MachineLearningServices/workspaces/{name}"
                f"?api-version=2024-04-01"
            )

            headers = {
                "Authorization": f"Bearer {token.token}",
                "Content-Type": "application/json",
            }

            body = {
                "location": location,
                "kind": "Project",
                "properties": {
                    "friendlyName": name,
                    "description": f"Migrated OYD project - {name}",
                },
            }

            if hub_resource_id:
                body["properties"]["hubResourceId"] = hub_resource_id

            response = httpx.put(url, headers=headers, json=body, timeout=120)

            if response.status_code not in [200, 201, 202]:
                raise ProvisioningError(
                    f"Failed to create project: {response.text}",
                    details={"status_code": response.status_code},
                )

            data = response.json()
            props = data.get("properties", {})
            endpoint = self._build_project_endpoint(data, props)

            project = FoundryProject(
                name=name,
                resource_name=name,
                resource_group=resource_group,
                subscription_id=self.subscription_id,
                location=location,
                endpoint=endpoint,
                has_agent_service=True,
            )

            logger.info(f"Created Foundry project: {name}")
            return project

        except ProvisioningError:
            raise
        except Exception as e:
            logger.error(f"Failed to create project: {e}")
            raise ProvisioningError(
                f"Failed to create Foundry project: {e}",
                details={"name": name, "resource_group": resource_group},
            )

    def get_project(self, name: str, resource_group: str) -> FoundryProject | None:
        """
        Get a specific Foundry project.

        Args:
            name: Project name
            resource_group: Resource group name

        Returns:
            Foundry project if found
        """
        import httpx
        from oyd_migrator.core.constants import AzureScopes

        try:
            token = self.credential.get_token(AzureScopes.MANAGEMENT)

            url = (
                f"https://management.azure.com/subscriptions/{self.subscription_id}"
                f"/resourceGroups/{resource_group}"
                f"/providers/Microsoft.MachineLearningServices/workspaces/{name}"
                f"?api-version=2024-04-01"
            )

            headers = {
                "Authorization": f"Bearer {token.token}",
                "Content-Type": "application/json",
            }

            response = httpx.get(url, headers=headers, timeout=30)

            if response.status_code == 404:
                return None

            response.raise_for_status()

            data = response.json()
            props = data.get("properties", {})
            endpoint = self._build_project_endpoint(data, props)

            return FoundryProject(
                name=name,
                resource_name=name,
                resource_group=resource_group,
                subscription_id=self.subscription_id,
                location=data.get("location", ""),
                endpoint=endpoint,
                has_agent_service=True,
            )

        except Exception as e:
            logger.warning(f"Could not get project {name}: {e}")
            return None
