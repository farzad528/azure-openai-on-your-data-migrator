"""Pytest configuration and fixtures."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock


@pytest.fixture
def mock_credential():
    """Create a mock Azure credential."""
    credential = MagicMock()
    credential.get_token.return_value = MagicMock(token="mock-token")
    return credential


@pytest.fixture
def sample_oyd_config():
    """Create a sample OYD configuration."""
    from oyd_migrator.models.oyd import (
        OYDConfiguration,
        OYDAzureSearchSource,
        OYDFieldMapping,
    )

    return OYDConfiguration(
        deployment_name="gpt-4o-deployment",
        model="gpt-4o",
        data_sources=[
            OYDAzureSearchSource(
                endpoint="https://test-search.search.windows.net",
                index_name="products-index",
                query_type="vector_semantic_hybrid",
                semantic_configuration="default-config",
                fields_mapping=OYDFieldMapping(
                    content_fields=["content", "description"],
                    title_field="title",
                    url_field="url",
                ),
                in_scope=True,
                role_information="You are a helpful product assistant.",
                strictness=3,
                top_n_documents=5,
            ),
        ],
    )


@pytest.fixture
def sample_search_index():
    """Create a sample search index."""
    from oyd_migrator.models.search import (
        SearchIndex,
        IndexField,
        SemanticConfig,
        SemanticPrioritizedFields,
        SemanticField,
    )

    return SearchIndex(
        name="products-index",
        service_name="test-search",
        service_endpoint="https://test-search.search.windows.net",
        fields=[
            IndexField(name="id", type="Edm.String", key=True, retrievable=True),
            IndexField(name="content", type="Edm.String", searchable=True, retrievable=True),
            IndexField(name="title", type="Edm.String", searchable=True, retrievable=True),
            IndexField(
                name="contentVector",
                type="Collection(Edm.Single)",
                dimensions=1536,
                vector_search_profile="default-profile",
            ),
        ],
        semantic_configurations=[
            SemanticConfig(
                name="default-config",
                prioritized_fields=SemanticPrioritizedFields(
                    title_field=SemanticField(field_name="title"),
                    content_fields=[SemanticField(field_name="content")],
                ),
            ),
        ],
        document_count=1000,
    )


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create a temporary configuration directory."""
    config_dir = tmp_path / ".oyd-migrator"
    config_dir.mkdir()
    return config_dir
