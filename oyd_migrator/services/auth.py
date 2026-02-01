"""Azure authentication service."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from azure.identity import (
    DefaultAzureCredential,
    ClientSecretCredential,
    ManagedIdentityCredential,
    AzureCliCredential,
)
from azure.core.credentials import TokenCredential
from azure.mgmt.resource import SubscriptionClient

from oyd_migrator.core.config import AzureConfig
from oyd_migrator.core.constants import AuthMethod, AzureScopes, RequiredRoles
from oyd_migrator.core.exceptions import AuthenticationError
from oyd_migrator.core.logging import get_logger

logger = get_logger("services.auth")


@dataclass
class Subscription:
    """Azure subscription info."""

    subscription_id: str
    display_name: str
    tenant_id: str
    state: str


@dataclass
class PermissionCheckResult:
    """Result of permission validation."""

    has_required: bool = True
    has_warnings: bool = False
    warnings: list[str] = field(default_factory=list)
    missing_roles: list[str] = field(default_factory=list)


class AzureAuthService:
    """Service for Azure authentication and authorization."""

    _credential: TokenCredential | None = None

    def authenticate(
        self,
        method: AuthMethod = AuthMethod.CLI,
        tenant_id: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        managed_identity_client_id: str | None = None,
    ) -> TokenCredential:
        """
        Authenticate with Azure using the specified method.

        Args:
            method: Authentication method to use
            tenant_id: Azure AD tenant ID (for service principal)
            client_id: Service principal client ID
            client_secret: Service principal client secret
            managed_identity_client_id: User-assigned MI client ID

        Returns:
            Azure credential object

        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            if method == AuthMethod.CLI:
                logger.debug("Using Azure CLI authentication")
                credential = AzureCliCredential()
            elif method == AuthMethod.SERVICE_PRINCIPAL:
                if not all([tenant_id, client_id, client_secret]):
                    raise AuthenticationError(
                        "Service principal requires tenant_id, client_id, and client_secret"
                    )
                logger.debug(f"Using service principal authentication for tenant {tenant_id}")
                credential = ClientSecretCredential(
                    tenant_id=tenant_id,
                    client_id=client_id,
                    client_secret=client_secret,
                )
            elif method == AuthMethod.MANAGED_IDENTITY:
                logger.debug("Using managed identity authentication")
                if managed_identity_client_id:
                    credential = ManagedIdentityCredential(
                        client_id=managed_identity_client_id
                    )
                else:
                    credential = ManagedIdentityCredential()
            else:
                logger.debug("Using default credential chain")
                credential = DefaultAzureCredential()

            # Validate credential by getting a token
            credential.get_token(AzureScopes.MANAGEMENT)
            self._credential = credential
            return credential

        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise AuthenticationError(
                f"Failed to authenticate: {e}",
                details={"method": method.value},
            )

    def get_credential(self) -> TokenCredential:
        """
        Get the current credential, or create a default one.

        Returns:
            Azure credential object
        """
        if self._credential is None:
            self._credential = DefaultAzureCredential()
        return self._credential

    def get_credential_from_config(self, config: AzureConfig) -> TokenCredential:
        """
        Get credential from a saved configuration.

        Args:
            config: Azure configuration with auth details

        Returns:
            Azure credential object
        """
        return self.authenticate(
            method=config.auth_method,
            tenant_id=config.tenant_id,
            client_id=config.client_id,
            client_secret=config.client_secret,
            managed_identity_client_id=config.managed_identity_client_id,
        )

    def list_subscriptions(
        self, credential: TokenCredential | None = None
    ) -> list[Subscription]:
        """
        List accessible Azure subscriptions.

        Args:
            credential: Credential to use (defaults to current)

        Returns:
            List of accessible subscriptions
        """
        credential = credential or self.get_credential()

        try:
            client = SubscriptionClient(credential)
            subscriptions = []

            for sub in client.subscriptions.list():
                subscriptions.append(
                    Subscription(
                        subscription_id=sub.subscription_id,
                        display_name=sub.display_name or sub.subscription_id,
                        tenant_id=sub.tenant_id or "",
                        state=sub.state or "Unknown",
                    )
                )

            logger.debug(f"Found {len(subscriptions)} subscription(s)")
            return subscriptions

        except Exception as e:
            logger.error(f"Failed to list subscriptions: {e}")
            raise AuthenticationError(f"Failed to list subscriptions: {e}")

    def check_permissions(
        self,
        credential: TokenCredential,
        subscription_id: str,
        resource_group: str | None = None,
    ) -> PermissionCheckResult:
        """
        Check if the credential has required permissions.

        Args:
            credential: Credential to check
            subscription_id: Subscription to check in
            resource_group: Optional resource group to check

        Returns:
            Permission check result with warnings
        """
        result = PermissionCheckResult()

        try:
            from azure.mgmt.authorization import AuthorizationManagementClient

            auth_client = AuthorizationManagementClient(
                credential, subscription_id
            )

            # Get role assignments for the current principal
            # This is a simplified check - in production you'd check specific resources

            # Check subscription-level access
            scope = f"/subscriptions/{subscription_id}"
            if resource_group:
                scope = f"{scope}/resourceGroups/{resource_group}"

            assignments = list(auth_client.role_assignments.list_for_scope(scope))

            if not assignments:
                result.has_warnings = True
                result.warnings.append(
                    "No role assignments found. You may need additional permissions."
                )

            # We can't easily check specific roles without the principal ID
            # So we just verify we can list assignments (basic read access)

            logger.debug(f"Found {len(assignments)} role assignment(s)")

        except Exception as e:
            logger.warning(f"Permission check failed: {e}")
            result.has_warnings = True
            result.warnings.append(
                f"Could not verify permissions: {e}. Proceeding with best effort."
            )

        return result

    def get_access_token(
        self,
        credential: TokenCredential | None = None,
        scope: str = AzureScopes.MANAGEMENT,
    ) -> str:
        """
        Get an access token for the specified scope.

        Args:
            credential: Credential to use
            scope: OAuth scope for the token

        Returns:
            Access token string
        """
        credential = credential or self.get_credential()
        token = credential.get_token(scope)
        return token.token
