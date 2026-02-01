"""Tests for data models."""

import pytest
from datetime import datetime


class TestOYDModels:
    """Tests for OYD data models."""

    def test_oyd_configuration_creation(self, sample_oyd_config):
        """Test creating an OYD configuration."""
        assert sample_oyd_config.deployment_name == "gpt-4o-deployment"
        assert sample_oyd_config.model == "gpt-4o"
        assert len(sample_oyd_config.data_sources) == 1

    def test_get_azure_search_sources(self, sample_oyd_config):
        """Test filtering Azure Search sources."""
        sources = sample_oyd_config.get_azure_search_sources()
        assert len(sources) == 1
        assert sources[0].index_name == "products-index"

    def test_get_primary_search_source(self, sample_oyd_config):
        """Test getting primary search source."""
        primary = sample_oyd_config.get_primary_search_source()
        assert primary is not None
        assert primary.endpoint == "https://test-search.search.windows.net"


class TestSearchModels:
    """Tests for search data models."""

    def test_search_index_creation(self, sample_search_index):
        """Test creating a search index."""
        assert sample_search_index.name == "products-index"
        assert len(sample_search_index.fields) == 4

    def test_get_key_field(self, sample_search_index):
        """Test getting key field."""
        key_field = sample_search_index.get_key_field()
        assert key_field is not None
        assert key_field.name == "id"

    def test_get_text_fields(self, sample_search_index):
        """Test getting text fields."""
        text_fields = sample_search_index.get_text_fields()
        assert len(text_fields) == 2
        field_names = [f.name for f in text_fields]
        assert "content" in field_names
        assert "title" in field_names

    def test_get_vector_fields(self, sample_search_index):
        """Test getting vector fields."""
        vector_fields = sample_search_index.get_vector_fields()
        assert len(vector_fields) == 1
        assert vector_fields[0].name == "contentVector"
        assert vector_fields[0].dimensions == 1536

    def test_has_semantic_search(self, sample_search_index):
        """Test semantic search detection."""
        assert sample_search_index.has_semantic_search() is True

    def test_has_vector_search(self, sample_search_index):
        """Test vector search detection."""
        assert sample_search_index.has_vector_search() is True


class TestMigrationModels:
    """Tests for migration models."""

    def test_migration_state_creation(self):
        """Test creating migration state."""
        from oyd_migrator.core.config import MigrationState

        state = MigrationState(session_id="test-123")
        assert state.session_id == "test-123"
        assert state.current_stage == "auth"
        assert state.completed is False

    def test_migration_state_save_load(self, temp_config_dir):
        """Test saving and loading migration state."""
        from oyd_migrator.core.config import MigrationState, AzureConfig
        from oyd_migrator.core.constants import AuthMethod

        # Create and save state
        state = MigrationState(
            session_id="test-456",
            azure_config=AzureConfig(
                subscription_id="sub-123",
                auth_method=AuthMethod.CLI,
            ),
        )
        state.save(temp_config_dir)

        # Load state
        loaded = MigrationState.load("test-456", temp_config_dir)
        assert loaded is not None
        assert loaded.session_id == "test-456"
        assert loaded.azure_config.subscription_id == "sub-123"

    def test_test_result_creation(self):
        """Test creating test result."""
        from oyd_migrator.models.migration import TestResult

        result = TestResult(
            agent_name="test-agent",
            query="What is the answer?",
            success=True,
            response_text="The answer is 42.",
            tool_calls_count=1,
            citation_count=2,
            has_citations=True,
            response_time_ms=1500.0,
        )

        assert result.success is True
        assert result.tool_calls_count == 1
        assert result.has_citations is True
