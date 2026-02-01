"""Custom exceptions for the OYD Foundry Migrator."""

from typing import Any


class MigrationError(Exception):
    """Base exception for all migration-related errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


class AuthenticationError(MigrationError):
    """Azure authentication failed."""

    def __init__(
        self,
        message: str = "Failed to authenticate with Azure",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)


class DiscoveryError(MigrationError):
    """Failed to discover OYD configurations or Azure resources."""

    def __init__(
        self,
        message: str = "Failed to discover Azure resources",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)


class ProvisioningError(MigrationError):
    """Failed to provision Azure resources (Foundry project, connections, etc.)."""

    def __init__(
        self,
        message: str = "Failed to provision Azure resource",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)


class ConnectionError(MigrationError):
    """Failed to create or validate project connections."""

    def __init__(
        self,
        message: str = "Failed to create or validate connection",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)


class AgentCreationError(MigrationError):
    """Failed to create Foundry agent."""

    def __init__(
        self,
        message: str = "Failed to create Foundry agent",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)


class ValidationError(MigrationError):
    """Validation of migrated resources failed."""

    def __init__(
        self,
        message: str = "Validation failed",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)


class ConfigurationError(MigrationError):
    """Configuration file or settings error."""

    def __init__(
        self,
        message: str = "Configuration error",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)


class ResourceNotFoundError(MigrationError):
    """Requested Azure resource was not found."""

    def __init__(
        self,
        resource_type: str,
        resource_name: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        message = f"{resource_type} '{resource_name}' not found"
        super().__init__(message, details)
        self.resource_type = resource_type
        self.resource_name = resource_name


class PermissionDeniedError(MigrationError):
    """Insufficient permissions to perform operation."""

    def __init__(
        self,
        operation: str,
        required_role: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        message = f"Permission denied for operation: {operation}"
        if required_role:
            message += f". Required role: {required_role}"
        super().__init__(message, details)
        self.operation = operation
        self.required_role = required_role


class NetworkError(MigrationError):
    """Network connectivity error (VNet, private endpoints, etc.)."""

    def __init__(
        self,
        message: str = "Network connectivity error",
        endpoint: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        if endpoint:
            message = f"{message} for endpoint: {endpoint}"
        super().__init__(message, details)
        self.endpoint = endpoint


class UnsupportedConfigurationError(MigrationError):
    """OYD configuration uses features not supported in migration target."""

    def __init__(
        self,
        feature: str,
        migration_path: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        message = f"Feature '{feature}' is not supported in migration path '{migration_path}'"
        super().__init__(message, details)
        self.feature = feature
        self.migration_path = migration_path
