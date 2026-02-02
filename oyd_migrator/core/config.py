"""Configuration management for the OYD Foundry Migrator."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from oyd_migrator.core.constants import AuthMethod, MigrationPath, Paths


class AzureConfig(BaseModel):
    """Azure authentication and subscription configuration."""

    subscription_id: str = Field(description="Azure subscription ID")
    tenant_id: str | None = Field(default=None, description="Azure AD tenant ID")
    auth_method: AuthMethod = Field(
        default=AuthMethod.CLI,
        description="Authentication method to use",
    )
    client_id: str | None = Field(
        default=None, description="Service principal client/app ID"
    )
    client_secret: str | None = Field(
        default=None, description="Service principal client secret"
    )
    managed_identity_client_id: str | None = Field(
        default=None, description="User-assigned managed identity client ID"
    )


class SearchConfig(BaseModel):
    """Azure AI Search service configuration."""

    service_name: str = Field(description="Search service name")
    resource_group: str = Field(description="Resource group containing the service")
    endpoint: str = Field(description="Search service endpoint URL")
    api_key: str | None = Field(default=None, description="Admin or query API key")
    use_managed_identity: bool = Field(
        default=False, description="Use managed identity instead of API key"
    )


class AOAIConfig(BaseModel):
    """Azure OpenAI service configuration (source for migration)."""

    resource_name: str = Field(description="AOAI resource name")
    resource_group: str = Field(description="Resource group containing the resource")
    endpoint: str = Field(description="AOAI endpoint URL")
    deployment_name: str = Field(description="Deployment with OYD configured")
    api_key: str | None = Field(default=None, description="AOAI API key")


class FoundryConfig(BaseModel):
    """Azure AI Foundry project configuration (target for migration)."""

    project_name: str = Field(description="Foundry project name")
    resource_group: str = Field(description="Resource group containing the project")
    project_endpoint: str = Field(description="Foundry project endpoint URL")
    model_deployment: str = Field(
        default="gpt-4.1", description="Model deployment to use for agents"
    )
    location: str = Field(
        default="eastus", description="Azure region for new project"
    )
    hub_resource_id: str | None = Field(
        default=None, description="Parent Foundry Hub resource ID"
    )


class MigrationOptions(BaseModel):
    """Options for the migration process."""

    migration_path: MigrationPath = Field(
        default=MigrationPath.SEARCH_TOOL,
        description="Target migration architecture",
    )
    create_new_project: bool = Field(
        default=False, description="Create new Foundry project vs use existing"
    )
    preserve_query_type: bool = Field(
        default=True, description="Preserve original OYD query type in migration"
    )
    migrate_system_message: bool = Field(
        default=True, description="Migrate role_information to agent instructions"
    )
    test_after_migration: bool = Field(
        default=True, description="Run test queries after migration"
    )
    generate_samples: bool = Field(
        default=True, description="Generate SDK code samples"
    )


class MigrationState(BaseModel):
    """Persisted migration session state for resume capability."""

    session_id: str = Field(description="Unique session identifier")
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    current_stage: str = Field(default="auth", description="Current wizard stage")
    completed: bool = Field(default=False)

    # Configuration collected during wizard
    azure_config: AzureConfig | None = None
    aoai_configs: list[AOAIConfig] = Field(default_factory=list)
    search_configs: list[SearchConfig] = Field(default_factory=list)
    foundry_config: FoundryConfig | None = None
    migration_options: MigrationOptions = Field(default_factory=MigrationOptions)

    # Resources created during migration
    created_connections: list[str] = Field(default_factory=list)
    created_agents: list[str] = Field(default_factory=list)

    # Validation results
    test_results: dict[str, bool] = Field(default_factory=dict)

    def save(self, config_dir: Path) -> None:
        """Save session state to disk."""
        sessions_dir = config_dir / Paths.SESSIONS_DIR
        sessions_dir.mkdir(parents=True, exist_ok=True)
        session_file = sessions_dir / f"{self.session_id}.json"
        self.updated_at = datetime.now(timezone.utc)
        session_file.write_text(self.model_dump_json(indent=2))

    @classmethod
    def load(cls, session_id: str, config_dir: Path) -> MigrationState | None:
        """Load session state from disk."""
        session_file = config_dir / Paths.SESSIONS_DIR / f"{session_id}.json"
        if session_file.exists():
            return cls.model_validate_json(session_file.read_text())
        return None

    @classmethod
    def list_sessions(cls, config_dir: Path) -> list[MigrationState]:
        """List all saved sessions."""
        sessions_dir = config_dir / Paths.SESSIONS_DIR
        if not sessions_dir.exists():
            return []
        sessions = []
        for session_file in sessions_dir.glob("*.json"):
            try:
                sessions.append(cls.model_validate_json(session_file.read_text()))
            except Exception:
                continue
        return sorted(sessions, key=lambda s: s.updated_at, reverse=True)


class AppSettings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="OYD_MIGRATOR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Paths
    config_dir: Path = Field(
        default_factory=lambda: Path.home() / Paths.CONFIG_DIR_NAME,
        description="Directory for config and session files",
    )

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", description="Logging level"
    )
    log_file: Path | None = Field(
        default=None, description="Optional log file path"
    )

    # Display
    no_color: bool = Field(default=False, description="Disable colored output")
    verbose: bool = Field(default=False, description="Enable verbose output")

    # Azure defaults
    default_location: str = Field(
        default="eastus", description="Default Azure region for new resources"
    )

    def ensure_config_dir(self) -> Path:
        """Ensure config directory exists and return its path."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        return self.config_dir


@lru_cache
def get_settings() -> AppSettings:
    """Get cached application settings."""
    return AppSettings()
