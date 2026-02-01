"""Constants and API versions for Azure services."""

from enum import Enum


# API Versions
class ApiVersions:
    """Azure service API versions."""

    # Azure OpenAI
    AOAI_DATA_PLANE = "2024-10-21"  # OYD data plane
    AOAI_MANAGEMENT = "2023-05-01"  # Cognitive Services management

    # Azure AI Search
    SEARCH_DATA_PLANE = "2025-11-01-preview"  # Knowledge bases, MCP
    SEARCH_MANAGEMENT = "2024-06-01-preview"  # Search service management

    # Azure AI Foundry / Projects
    FOUNDRY_AGENTS = "2025-05-01"  # Agent Service
    FOUNDRY_PROJECTS = "2025-01-01-preview"  # Project management
    FOUNDRY_CONNECTIONS = "2025-10-01-preview"  # MCP connections

    # Azure Resource Manager
    ARM = "2023-07-01"


# Azure Scopes for authentication
class AzureScopes:
    """OAuth scopes for Azure services."""

    MANAGEMENT = "https://management.azure.com/.default"
    COGNITIVE_SERVICES = "https://cognitiveservices.azure.com/.default"
    SEARCH = "https://search.azure.com/.default"
    AI_FOUNDRY = "https://ai.azure.com/.default"


# Migration paths
class MigrationPath(str, Enum):
    """Available migration target architectures."""

    SEARCH_TOOL = "search_tool"  # Foundry Agent + AzureAISearchAgentTool
    KNOWLEDGE_BASE = "knowledge_base"  # Foundry Agent + Foundry IQ Knowledge Base (MCP)


# Query types mapping between OYD and Foundry
class QueryTypeMapping:
    """Mapping of OYD query types to Foundry equivalents."""

    OYD_TO_SEARCH_TOOL = {
        "simple": "simple",
        "semantic": "semantic",
        "vector": "vector",
        "vector_simple_hybrid": "vector_simple_hybrid",
        "vector_semantic_hybrid": "vector_semantic_hybrid",
    }

    # Default query type for each migration path
    DEFAULT_SEARCH_TOOL = "vector_semantic_hybrid"
    DEFAULT_KNOWLEDGE_BASE = "hybrid"  # KB handles internally


# Authentication methods
class AuthMethod(str, Enum):
    """Azure authentication methods."""

    CLI = "cli"  # Azure CLI (az login)
    SERVICE_PRINCIPAL = "service_principal"  # Client ID + Secret
    MANAGED_IDENTITY = "managed_identity"  # System/User assigned MI


# RBAC roles needed for migration
class RequiredRoles:
    """Azure RBAC roles required for migration operations."""

    # For reading OYD configurations
    AOAI_READER = "Cognitive Services OpenAI User"
    AOAI_CONTRIBUTOR = "Cognitive Services OpenAI Contributor"

    # For Azure AI Search operations
    SEARCH_INDEX_DATA_READER = "Search Index Data Reader"
    SEARCH_INDEX_DATA_CONTRIBUTOR = "Search Index Data Contributor"
    SEARCH_SERVICE_CONTRIBUTOR = "Search Service Contributor"

    # For Foundry operations
    AI_USER = "Azure AI User"
    AI_PROJECT_MANAGER = "Azure AI Project Manager"


# OYD data source types
class OYDDataSourceType(str, Enum):
    """Supported OYD data source types."""

    AZURE_SEARCH = "azure_search"
    AZURE_BLOB = "azure_blob_storage"
    AZURE_COSMOS_DB = "azure_cosmos_db"
    URL = "url"
    UPLOADED_FILE = "uploaded_file"


# Foundry model recommendations
class RecommendedModels:
    """Recommended models for Foundry Agent Service."""

    # Models that support tool use
    SUPPORTED = [
        "gpt-4.1",
        "gpt-4.1-mini",
        "gpt-4.1-nano",
        "gpt-4o",
        "gpt-4o-mini",
    ]

    # Default recommendation
    DEFAULT = "gpt-4.1"
    DEFAULT_MINI = "gpt-4.1-mini"


# CLI display constants
class Display:
    """Constants for CLI display formatting."""

    APP_NAME = "OYD Foundry Migrator"
    APP_DESCRIPTION = "Migrate Azure OpenAI On Your Data to Foundry Agent Service"

    # Status symbols
    SUCCESS = "[green]✓[/green]"
    FAILURE = "[red]✗[/red]"
    WARNING = "[yellow]![/yellow]"
    INFO = "[blue]ℹ[/blue]"
    PENDING = "[dim]○[/dim]"
    IN_PROGRESS = "[cyan]◐[/cyan]"

    # Table styles
    TABLE_STYLE = "rounded"
    HEADER_STYLE = "bold cyan"


# Session and config paths
class Paths:
    """Default paths for configuration and sessions."""

    CONFIG_DIR_NAME = ".oyd-migrator"
    SESSIONS_DIR = "sessions"
    CONFIG_FILE = "config.yaml"
    CREDENTIALS_FILE = "credentials.json"
