"""Tests for generators, endpoint parsing, model edge cases, and exceptions."""

import json
import pytest

from oyd_migrator.core.constants import MigrationPath, AuthMethod


# ---------------------------------------------------------------------------
# Generator tests
# ---------------------------------------------------------------------------

class TestCurlSampleGenerator:
    """Tests for cURL command generation."""

    def test_generates_valid_bash_script(self):
        from oyd_migrator.generators.curl_samples import generate_curl_commands

        result = generate_curl_commands(
            agent_name="test-agent",
            project_endpoint="https://myaccount.services.ai.azure.com/api/projects/myproj",
            model="gpt-4.1",
        )
        assert result.startswith("#!/bin/bash")
        assert "test-agent" in result
        assert "myaccount.services.ai.azure.com" in result

    def test_contains_curl_post(self):
        from oyd_migrator.generators.curl_samples import generate_curl_commands

        result = generate_curl_commands("a", "https://ep.example.com")
        assert "curl" in result
        assert "POST" in result


class TestSdkSampleGenerator:
    """Tests for Python SDK sample generation."""

    def test_search_tool_sample_contains_imports(self):
        from oyd_migrator.generators.sdk_samples import generate_python_sample

        result = generate_python_sample(
            agent_name="my-agent",
            project_endpoint="https://ep.example.com",
            migration_path=MigrationPath.SEARCH_TOOL,
            index_name="products-index",
            connection_id="conn-123",
        )
        assert "AzureAISearchAgentTool" in result
        assert "my-agent" in result
        assert "products-index" in result
        assert "conn-123" in result

    def test_knowledge_base_sample_contains_mcp(self):
        from oyd_migrator.generators.sdk_samples import generate_python_sample

        result = generate_python_sample(
            agent_name="kb-agent",
            project_endpoint="https://ep.example.com",
            migration_path=MigrationPath.KNOWLEDGE_BASE,
            knowledge_base_name="my-kb",
            connection_id="mcp-conn",
        )
        assert "MCPTool" in result
        assert "kb-agent" in result
        assert "my-kb" in result

    def test_defaults_applied_when_optional_args_missing(self):
        from oyd_migrator.generators.sdk_samples import generate_python_sample

        result = generate_python_sample(
            agent_name="a",
            project_endpoint="https://ep.example.com",
            migration_path=MigrationPath.SEARCH_TOOL,
        )
        assert "your-index-name" in result
        assert "your-connection-id" in result


class TestMigrationReportGenerator:
    """Tests for migration report generation."""

    @pytest.fixture
    def minimal_state(self):
        from oyd_migrator.core.config import MigrationState
        return MigrationState(session_id="rpt-test-001")

    def test_markdown_report_contains_session_id(self, minimal_state):
        from oyd_migrator.generators.migration_report import generate_report

        report = generate_report(minimal_state, format="markdown")
        assert "rpt-test-001" in report
        assert "# OYD to Foundry Migration Report" in report

    def test_json_report_is_valid_json(self, minimal_state):
        from oyd_migrator.generators.migration_report import generate_report

        report = generate_report(minimal_state, format="json")
        data = json.loads(report)
        assert data["metadata"]["session_id"] == "rpt-test-001"
        assert "summary" in data
        assert "source" in data
        assert "target" in data

    def test_html_report_contains_html_tags(self, minimal_state):
        from oyd_migrator.generators.migration_report import generate_report

        report = generate_report(minimal_state, format="html")
        assert "<!DOCTYPE html>" in report
        assert "rpt-test-001" in report

    def test_report_with_test_results(self):
        from oyd_migrator.core.config import MigrationState
        from oyd_migrator.generators.migration_report import generate_report

        state = MigrationState(
            session_id="rpt-002",
            test_results={"query-1": True, "query-2": False},
        )
        report = generate_report(state, format="markdown")
        assert "✅ Passed" in report
        assert "❌ Failed" in report

    def test_json_report_counts_tests(self):
        from oyd_migrator.core.config import MigrationState
        from oyd_migrator.generators.migration_report import generate_report

        state = MigrationState(
            session_id="rpt-003",
            test_results={"a": True, "b": True, "c": False},
        )
        data = json.loads(generate_report(state, format="json"))
        assert data["summary"]["tests_passed"] == 2
        assert data["summary"]["tests_total"] == 3


# ---------------------------------------------------------------------------
# Endpoint parsing tests
# ---------------------------------------------------------------------------

class TestConnectionManagerParseEndpoint:
    """Tests for ConnectionManagerService._parse_endpoint."""

    def _make_manager(self, endpoint):
        from oyd_migrator.services.connection_manager import ConnectionManagerService
        mgr = ConnectionManagerService.__new__(ConnectionManagerService)
        mgr.project_endpoint = endpoint
        mgr._parse_endpoint()
        return mgr

    def test_services_ai_endpoint(self):
        mgr = self._make_manager(
            "https://myaccount.services.ai.azure.com/api/projects/myproject"
        )
        assert mgr.resource_name == "myaccount"
        assert mgr.project_name == "myproject"

    def test_cognitiveservices_endpoint(self):
        mgr = self._make_manager(
            "https://myresource.cognitiveservices.azure.com/"
        )
        assert mgr.resource_name == "myresource"
        assert mgr.project_name == ""

    def test_endpoint_without_projects_path(self):
        mgr = self._make_manager("https://svc.example.com/other")
        assert mgr.resource_name == "svc"
        assert mgr.project_name == ""


# ---------------------------------------------------------------------------
# Model edge cases
# ---------------------------------------------------------------------------

class TestMigrationPlanModel:
    """Tests for MigrationPlan model."""

    def test_get_mapping_for_deployment_found(self):
        from oyd_migrator.models.migration import MigrationPlan, MigrationMapping

        plan = MigrationPlan(
            plan_id="p1",
            migration_path=MigrationPath.SEARCH_TOOL,
            target_project_name="proj",
            target_project_endpoint="https://ep.example.com",
            mappings=[
                MigrationMapping(
                    source_deployment="dep-1",
                    source_index="idx-1",
                    target_agent_name="agent-1",
                    target_connection_name="conn-1",
                ),
            ],
        )
        m = plan.get_mapping_for_deployment("dep-1")
        assert m is not None
        assert m.target_agent_name == "agent-1"

    def test_get_mapping_for_deployment_not_found(self):
        from oyd_migrator.models.migration import MigrationPlan

        plan = MigrationPlan(
            plan_id="p1",
            migration_path=MigrationPath.SEARCH_TOOL,
            target_project_name="proj",
            target_project_endpoint="https://ep.example.com",
        )
        assert plan.get_mapping_for_deployment("nonexistent") is None


class TestMigrationResultModel:
    """Tests for MigrationResult model."""

    def test_deployments_migrated_count(self):
        from oyd_migrator.models.migration import MigrationResult
        from oyd_migrator.models.foundry import FoundryAgent

        result = MigrationResult(
            result_id="r1",
            migration_path=MigrationPath.SEARCH_TOOL,
            plan_id="p1",
            agents_created=[
                FoundryAgent(
                    name="a1", project_name="p", project_endpoint="https://ep",
                    model="gpt-4.1", instructions="i",
                    migration_path=MigrationPath.SEARCH_TOOL,
                ),
                FoundryAgent(
                    name="a2", project_name="p", project_endpoint="https://ep",
                    model="gpt-4.1", instructions="i",
                    migration_path=MigrationPath.SEARCH_TOOL,
                ),
            ],
        )
        assert result.deployments_migrated == 2


class TestOYDConfigEdgeCases:
    """Tests for OYD model edge cases."""

    def test_no_search_sources(self):
        from oyd_migrator.models.oyd import OYDConfiguration, OYDBlobSource

        config = OYDConfiguration(
            deployment_name="d",
            model="gpt-4o",
            data_sources=[
                OYDBlobSource(container_url="https://blob.example.com/c"),
            ],
        )
        assert config.get_azure_search_sources() == []
        assert config.get_primary_search_source() is None

    def test_empty_data_sources(self):
        from oyd_migrator.models.oyd import OYDConfiguration

        config = OYDConfiguration(
            deployment_name="d", model="gpt-4o", data_sources=[]
        )
        assert config.get_primary_search_source() is None


class TestSearchIndexEdgeCases:
    """Tests for SearchIndex model edge cases."""

    def test_no_key_field(self):
        from oyd_migrator.models.search import SearchIndex, IndexField

        index = SearchIndex(
            name="idx", service_name="svc",
            service_endpoint="https://svc.search.windows.net",
            fields=[IndexField(name="content", type="Edm.String", searchable=True)],
        )
        assert index.get_key_field() is None

    def test_no_text_or_vector_fields(self):
        from oyd_migrator.models.search import SearchIndex, IndexField

        index = SearchIndex(
            name="idx", service_name="svc",
            service_endpoint="https://svc.search.windows.net",
            fields=[IndexField(name="id", type="Edm.String", key=True)],
        )
        assert index.get_text_fields() == []
        assert index.get_vector_fields() == []
        assert index.has_semantic_search() is False
        assert index.has_vector_search() is False


class TestFoundryAgentToolFilters:
    """Tests for FoundryAgent tool filtering methods."""

    def test_get_search_tools(self):
        from oyd_migrator.models.foundry import (
            FoundryAgent, SearchToolConfig, MCPToolConfig,
        )

        agent = FoundryAgent(
            name="a", project_name="p", project_endpoint="https://ep",
            model="gpt-4.1", instructions="i",
            migration_path=MigrationPath.SEARCH_TOOL,
            tools=[
                SearchToolConfig(connection_id="c1", index_name="idx1"),
                MCPToolConfig(
                    server_label="kb", server_url="https://kb.example.com",
                    connection_id="c2",
                ),
                SearchToolConfig(connection_id="c3", index_name="idx2"),
            ],
        )
        assert len(agent.get_search_tools()) == 2
        assert len(agent.get_mcp_tools()) == 1


# ---------------------------------------------------------------------------
# Exception tests
# ---------------------------------------------------------------------------

class TestExceptions:
    """Tests for custom exception formatting."""

    def test_resource_not_found_message(self):
        from oyd_migrator.core.exceptions import ResourceNotFoundError

        err = ResourceNotFoundError("SearchIndex", "my-index")
        assert "SearchIndex" in str(err)
        assert "my-index" in str(err)
        assert err.resource_type == "SearchIndex"
        assert err.resource_name == "my-index"

    def test_permission_denied_with_role(self):
        from oyd_migrator.core.exceptions import PermissionDeniedError

        err = PermissionDeniedError("create agent", required_role="Azure AI User")
        assert "create agent" in str(err)
        assert "Azure AI User" in str(err)

    def test_unsupported_configuration(self):
        from oyd_migrator.core.exceptions import UnsupportedConfigurationError

        err = UnsupportedConfigurationError("cosmos_db", "search_tool")
        assert "cosmos_db" in str(err)
        assert "search_tool" in str(err)

    def test_migration_error_with_details(self):
        from oyd_migrator.core.exceptions import MigrationError

        err = MigrationError("failed", details={"code": 500})
        assert "Details:" in str(err)
        assert "500" in str(err)

    def test_migration_error_without_details(self):
        from oyd_migrator.core.exceptions import MigrationError

        err = MigrationError("simple failure")
        assert str(err) == "simple failure"


# ---------------------------------------------------------------------------
# AgentBuilder._extract_index_name
# ---------------------------------------------------------------------------

class TestExtractIndexName:
    """Tests for AgentBuilderService._extract_index_name."""

    def test_strips_connection_suffix(self):
        from oyd_migrator.services.agent_builder import AgentBuilderService
        from oyd_migrator.models.foundry import ProjectConnection

        builder = AgentBuilderService.__new__(AgentBuilderService)
        conn = ProjectConnection(
            name="products-connection",
            connection_type="AzureAISearch",
            target="https://svc.search.windows.net",
        )
        assert builder._extract_index_name(conn) == "products-index"

    def test_no_connection_suffix(self):
        from oyd_migrator.services.agent_builder import AgentBuilderService
        from oyd_migrator.models.foundry import ProjectConnection

        builder = AgentBuilderService.__new__(AgentBuilderService)
        conn = ProjectConnection(
            name="my-search",
            connection_type="AzureAISearch",
            target="https://svc.search.windows.net",
        )
        assert builder._extract_index_name(conn) == "my-search"


# ---------------------------------------------------------------------------
# MigrationState save/load round-trip with full config
# ---------------------------------------------------------------------------

class TestMigrationStateRoundTrip:
    """Tests for MigrationState serialization with full config."""

    def test_round_trip_with_foundry_config(self, tmp_path):
        from oyd_migrator.core.config import (
            MigrationState, AzureConfig, FoundryConfig, MigrationOptions,
        )

        config_dir = tmp_path / ".oyd-migrator"
        config_dir.mkdir()

        state = MigrationState(
            session_id="rt-001",
            azure_config=AzureConfig(
                subscription_id="sub-1",
                auth_method=AuthMethod.CLI,
            ),
            foundry_config=FoundryConfig(
                project_name="my-proj",
                resource_group="my-rg",
                project_endpoint="https://ep.example.com",
                model_deployment="gpt-4.1",
            ),
            migration_options=MigrationOptions(
                migration_path=MigrationPath.KNOWLEDGE_BASE,
            ),
            created_connections=["conn-1"],
            created_agents=["agent-1"],
            test_results={"q1": True},
        )
        state.save(config_dir)

        loaded = MigrationState.load("rt-001", config_dir)
        assert loaded is not None
        assert loaded.foundry_config.project_name == "my-proj"
        assert loaded.migration_options.migration_path == MigrationPath.KNOWLEDGE_BASE
        assert loaded.created_agents == ["agent-1"]
        assert loaded.test_results == {"q1": True}

    def test_list_sessions(self, tmp_path):
        from oyd_migrator.core.config import MigrationState

        config_dir = tmp_path / ".oyd-migrator"
        config_dir.mkdir()

        MigrationState(session_id="s1").save(config_dir)
        MigrationState(session_id="s2").save(config_dir)

        sessions = MigrationState.list_sessions(config_dir)
        assert len(sessions) == 2
        ids = {s.session_id for s in sessions}
        assert ids == {"s1", "s2"}

    def test_list_sessions_empty_dir(self, tmp_path):
        from oyd_migrator.core.config import MigrationState

        config_dir = tmp_path / ".oyd-migrator"
        # Directory doesn't exist yet
        assert MigrationState.list_sessions(config_dir) == []

    def test_load_nonexistent_session(self, tmp_path):
        from oyd_migrator.core.config import MigrationState

        config_dir = tmp_path / ".oyd-migrator"
        config_dir.mkdir()
        assert MigrationState.load("does-not-exist", config_dir) is None


# ---------------------------------------------------------------------------
# QueryTypeMapping constants sanity
# ---------------------------------------------------------------------------

class TestQueryTypeMapping:
    """Sanity checks on query type mapping constants."""

    def test_all_oyd_types_mapped(self):
        from oyd_migrator.core.constants import QueryTypeMapping

        expected = {"simple", "semantic", "vector", "vector_simple_hybrid", "vector_semantic_hybrid"}
        assert set(QueryTypeMapping.OYD_TO_SEARCH_TOOL.keys()) == expected

    def test_defaults_are_valid(self):
        from oyd_migrator.core.constants import QueryTypeMapping

        assert QueryTypeMapping.DEFAULT_SEARCH_TOOL in QueryTypeMapping.OYD_TO_SEARCH_TOOL.values()
