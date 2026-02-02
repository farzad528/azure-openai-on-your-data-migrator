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
        List existing Foundry projects from both architectures:
        1. ML Workspace-based projects (older)
        2. CognitiveServices-based projects (newer Foundry portal)

        Returns:
            List of Foundry projects
        """
        projects = []
        
        # Get projects from both sources
        projects.extend(self._list_ml_workspace_projects())
        projects.extend(self._list_cognitive_services_projects())
        
        # Deduplicate by name (prefer CognitiveServices version if both exist)
        seen_names = set()
        unique_projects = []
        for p in projects:
            if p.name not in seen_names:
                seen_names.add(p.name)
                unique_projects.append(p)
        
        logger.debug(f"Found {len(unique_projects)} Foundry project(s) total")
        return unique_projects
    
    def _list_ml_workspace_projects(self) -> list[FoundryProject]:
        """List projects from ML Workspaces (older architecture)."""
        import httpx
        from oyd_migrator.core.constants import AzureScopes

        projects = []

        try:
            token = self.credential.get_token(AzureScopes.MANAGEMENT)

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
                kind = workspace.get("kind", "")

                if kind == "Project":
                    rg = workspace["id"].split("/resourceGroups/")[1].split("/")[0]
                    props = workspace.get("properties", {})
                    placeholder_endpoint = self._build_project_endpoint(workspace, props)

                    project = FoundryProject(
                        name=workspace["name"],
                        resource_name=props.get("hubResourceId", "").split("/")[-1] if props.get("hubResourceId") else workspace["name"],
                        resource_group=rg,
                        subscription_id=self.subscription_id,
                        location=workspace.get("location", ""),
                        endpoint=placeholder_endpoint,
                        has_agent_service=True,
                    )
                    projects.append(project)

            logger.debug(f"Found {len(projects)} ML Workspace project(s)")

        except Exception as e:
            logger.warning(f"Could not list ML Workspace projects: {e}")

        return projects
    
    def _list_cognitive_services_projects(self) -> list[FoundryProject]:
        """
        List projects from CognitiveServices accounts (newer Foundry architecture).
        
        These are projects created via the new Foundry portal that live under
        Microsoft.CognitiveServices/accounts/{account}/projects/{project}
        """
        import httpx
        from oyd_migrator.core.constants import AzureScopes

        projects = []

        try:
            token = self.credential.get_token(AzureScopes.MANAGEMENT)
            headers = {
                "Authorization": f"Bearer {token.token}",
                "Content-Type": "application/json",
            }

            # First, list all CognitiveServices accounts
            accounts_url = (
                f"https://management.azure.com/subscriptions/{self.subscription_id}"
                f"/providers/Microsoft.CognitiveServices/accounts"
                f"?api-version=2024-10-01"
            )

            response = httpx.get(accounts_url, headers=headers, timeout=30)
            response.raise_for_status()
            accounts_data = response.json()

            for account in accounts_data.get("value", []):
                account_name = account["name"]
                account_id = account["id"]
                rg = account_id.split("/resourceGroups/")[1].split("/")[0]
                location = account.get("location", "")
                
                # Check if this account has projects (it's a Foundry Account)
                # by looking for the projects sub-resource
                projects_url = (
                    f"https://management.azure.com{account_id}/projects"
                    f"?api-version=2024-10-01"
                )

                try:
                    proj_response = httpx.get(projects_url, headers=headers, timeout=30)
                    if proj_response.status_code == 200:
                        proj_data = proj_response.json()
                        
                        for proj in proj_data.get("value", []):
                            proj_name = proj["name"]
                            
                            # Build the endpoint for CognitiveServices-based projects
                            # Format: https://{account}.services.ai.azure.com/api/projects/{project}
                            endpoint = f"https://{account_name}.services.ai.azure.com/api/projects/{proj_name}"
                            
                            project = FoundryProject(
                                name=proj_name,
                                resource_name=account_name,
                                resource_group=rg,
                                subscription_id=self.subscription_id,
                                location=location,
                                endpoint=endpoint,
                                has_agent_service=True,
                            )
                            projects.append(project)
                            
                except Exception as e:
                    # Account doesn't have projects or we can't access them
                    logger.debug(f"Could not list projects for account {account_name}: {e}")
                    continue

            logger.debug(f"Found {len(projects)} CognitiveServices project(s)")

        except Exception as e:
            logger.warning(f"Could not list CognitiveServices projects: {e}")

        return projects

    def resolve_project_endpoint(self, project: 'FoundryProject') -> str:
        """
        Resolve the real AI Services endpoint for a selected project.
        
        This makes an additional API call to get connection details,
        so should only be called for projects the user has selected.
        
        Args:
            project: The Foundry project to resolve endpoint for
            
        Returns:
            The resolved endpoint (may be same as input if resolution fails)
        """
        from oyd_migrator.core.constants import AzureScopes
        
        try:
            token = self.credential.get_token(AzureScopes.MANAGEMENT)
            real_endpoint = self._get_ai_services_endpoint(project, token.token)
            if real_endpoint:
                return real_endpoint
        except Exception as e:
            logger.debug(f"Could not resolve endpoint for {project.name}: {e}")
        
        return project.endpoint

    def list_foundry_accounts(self) -> list[FoundryProject]:
        """
        List existing Foundry Accounts (AI Foundry parent resources).
        
        A Foundry Account provides the AI Services connection and acts as a parent for Projects.
        (Previously known as "Hub" in older Azure terminology)

        Returns:
            List of Foundry accounts (using FoundryProject model for simplicity)
        """
        import httpx
        from oyd_migrator.core.constants import AzureScopes

        accounts = []

        try:
            token = self.credential.get_token(AzureScopes.MANAGEMENT)

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
                kind = workspace.get("kind", "")

                # "Hub" kind represents Foundry Accounts in the API
                if kind == "Hub":
                    rg = workspace["id"].split("/resourceGroups/")[1].split("/")[0]

                    account = FoundryProject(
                        name=workspace["name"],
                        resource_name=workspace["name"],
                        resource_group=rg,
                        subscription_id=self.subscription_id,
                        location=workspace.get("location", ""),
                        endpoint="",  # Accounts don't have direct endpoints
                        has_agent_service=False,
                    )
                    accounts.append(account)

            logger.debug(f"Found {len(accounts)} Foundry account(s)")

        except Exception as e:
            logger.warning(f"Could not list Foundry accounts: {e}")

        return accounts
    
    # Alias for backward compatibility
    list_hubs = list_foundry_accounts

    def _build_project_endpoint(self, workspace: dict, properties: dict) -> str:
        """
        Build the project endpoint URL.
        
        There are two main endpoint formats depending on the Foundry setup:
        
        1. Newer Foundry Accounts (services.ai.azure.com):
           https://{foundry-account-name}.services.ai.azure.com/api/projects/{project-name}
           
        2. Older/Legacy with AI Services connection (cognitiveservices.azure.com):
           https://{ai-services-resource}.cognitiveservices.azure.com/
        
        The actual endpoint is determined when we fetch workspace connections.
        This method provides a fallback for the newer services.ai.azure.com format.
        """
        # First try to get from workspaceUrl if available (some projects have this set)
        workspace_url = properties.get("workspaceUrl", "")
        if workspace_url:
            return workspace_url

        # Get hub info to construct the services.ai.azure.com endpoint
        hub_id = properties.get("hubResourceId", "")
        workspace_name = workspace["name"]
        
        if hub_id:
            # Hub ID format: /subscriptions/.../resourceGroups/.../providers/Microsoft.MachineLearningServices/workspaces/{hub-name}
            parts = hub_id.split("/")
            if len(parts) >= 9:
                hub_name = parts[-1]
                
                # For newer Foundry, the Hub name is often the Foundry Account name
                # Format: https://{foundry-account}.services.ai.azure.com/api/projects/{project}
                return f"https://{hub_name}.services.ai.azure.com/api/projects/{workspace_name}"
        
        # Fallback: use the workspace name as the Foundry Account name
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
