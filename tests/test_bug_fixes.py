"""Tests for bug fixes."""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock


class TestAllTestsPassedFix:
    """Bug fix: MigrationResult.all_tests_passed should return False when empty."""

    def test_all_tests_passed_empty_returns_false(self):
        """all_tests_passed must be False when test_results is empty."""
        from oyd_migrator.models.migration import MigrationResult
        from oyd_migrator.core.constants import MigrationPath

        result = MigrationResult(
            result_id="r1",
            migration_path=MigrationPath.SEARCH_TOOL,
            plan_id="p1",
            test_results=[],
        )
        assert result.all_tests_passed is False

    def test_all_tests_passed_with_successes(self):
        """all_tests_passed returns True when all tests succeed."""
        from oyd_migrator.models.migration import MigrationResult, TestResult
        from oyd_migrator.core.constants import MigrationPath

        result = MigrationResult(
            result_id="r1",
            migration_path=MigrationPath.SEARCH_TOOL,
            plan_id="p1",
            test_results=[
                TestResult(agent_name="a", query="q1", success=True),
                TestResult(agent_name="a", query="q2", success=True),
            ],
        )
        assert result.all_tests_passed is True

    def test_all_tests_passed_with_failure(self):
        """all_tests_passed returns False when any test fails."""
        from oyd_migrator.models.migration import MigrationResult, TestResult
        from oyd_migrator.core.constants import MigrationPath

        result = MigrationResult(
            result_id="r1",
            migration_path=MigrationPath.SEARCH_TOOL,
            plan_id="p1",
            test_results=[
                TestResult(agent_name="a", query="q1", success=True),
                TestResult(agent_name="a", query="q2", success=False),
            ],
        )
        assert result.all_tests_passed is False


class TestDatetimeUtcnowFix:
    """Bug fix: datetime.utcnow() replaced with datetime.now(timezone.utc)."""

    def test_migration_plan_created_at_is_aware(self):
        from oyd_migrator.models.migration import MigrationPlan
        from oyd_migrator.core.constants import MigrationPath

        plan = MigrationPlan(
            plan_id="p1",
            migration_path=MigrationPath.SEARCH_TOOL,
            target_project_name="proj",
            target_project_endpoint="https://example.com",
        )
        assert plan.created_at.tzinfo is not None

    def test_test_result_timestamp_is_aware(self):
        from oyd_migrator.models.migration import TestResult

        result = TestResult(agent_name="a", query="q")
        assert result.timestamp.tzinfo is not None

    def test_comparison_report_generated_at_is_aware(self):
        from oyd_migrator.models.migration import ComparisonReport
        from oyd_migrator.core.constants import MigrationPath

        report = ComparisonReport(
            report_id="r1",
            source_deployment="d1",
            target_agent="a1",
            migration_path=MigrationPath.SEARCH_TOOL,
        )
        assert report.generated_at.tzinfo is not None

    def test_migration_result_completed_at_is_aware(self):
        from oyd_migrator.models.migration import MigrationResult
        from oyd_migrator.core.constants import MigrationPath

        result = MigrationResult(
            result_id="r1",
            migration_path=MigrationPath.SEARCH_TOOL,
            plan_id="p1",
        )
        assert result.completed_at.tzinfo is not None

    def test_agent_thread_created_at_is_aware(self):
        from oyd_migrator.models.foundry import AgentThread

        thread = AgentThread(thread_id="t1", agent_id="a1")
        assert thread.created_at.tzinfo is not None

    def test_agent_run_created_at_is_aware(self):
        from oyd_migrator.models.foundry import AgentRun

        run = AgentRun(run_id="r1", thread_id="t1", agent_id="a1", status="queued")
        assert run.created_at.tzinfo is not None


class TestConnectionErrorRenameFix:
    """Bug fix: Custom ConnectionError renamed to ProjectConnectionError."""

    def test_project_connection_error_exists(self):
        from oyd_migrator.core.exceptions import ProjectConnectionError, MigrationError

        assert issubclass(ProjectConnectionError, MigrationError)

    def test_project_connection_error_does_not_shadow_builtin(self):
        """The custom exception should not shadow Python's builtin ConnectionError."""
        from oyd_migrator.core import exceptions

        # Verify our module does NOT export a class named 'ConnectionError'
        assert not hasattr(exceptions, "ConnectionError")

    def test_project_connection_error_message(self):
        from oyd_migrator.core.exceptions import ProjectConnectionError

        err = ProjectConnectionError("test error", details={"key": "val"})
        assert "test error" in str(err)
        assert err.details == {"key": "val"}


class TestSupportsHybridFix:
    """Bug fix: supports_hybrid requires vector + text + semantic."""

    def _make_index(self, has_text=True, has_vector=True, has_semantic=True):
        from oyd_migrator.models.search import (
            SearchIndex, IndexField, SemanticConfig,
            SemanticPrioritizedFields, SemanticField,
        )

        fields = [
            IndexField(name="id", type="Edm.String", key=True),
        ]
        if has_text:
            fields.append(IndexField(name="content", type="Edm.String", searchable=True))
        if has_vector:
            fields.append(IndexField(
                name="vec", type="Collection(Edm.Single)",
                dimensions=1536, vector_search_profile="p1",
            ))

        semantic_configs = []
        if has_semantic:
            semantic_configs.append(SemanticConfig(
                name="default",
                prioritized_fields=SemanticPrioritizedFields(
                    content_fields=[SemanticField(field_name="content")],
                ),
            ))

        return SearchIndex(
            name="test-index",
            service_name="svc",
            service_endpoint="https://svc.search.windows.net",
            fields=fields,
            semantic_configurations=semantic_configs,
        )

    def test_hybrid_requires_semantic(self):
        """supports_hybrid should be False without semantic config."""
        from oyd_migrator.services.search_inventory import SearchInventoryService

        index = self._make_index(has_text=True, has_vector=True, has_semantic=False)

        # Call analyze_index without needing a real service
        svc = SearchInventoryService.__new__(SearchInventoryService)
        analysis = svc.analyze_index(index)

        assert analysis.supports_hybrid is False
        assert analysis.recommended_query_type == "vector_simple_hybrid"

    def test_hybrid_with_all_capabilities(self):
        """supports_hybrid should be True with vector + text + semantic."""
        from oyd_migrator.services.search_inventory import SearchInventoryService

        index = self._make_index(has_text=True, has_vector=True, has_semantic=True)
        svc = SearchInventoryService.__new__(SearchInventoryService)
        analysis = svc.analyze_index(index)

        assert analysis.supports_hybrid is True
        assert analysis.recommended_query_type == "vector_semantic_hybrid"

    def test_no_vector_no_hybrid(self):
        """supports_hybrid should be False without vector fields."""
        from oyd_migrator.services.search_inventory import SearchInventoryService

        index = self._make_index(has_text=True, has_vector=False, has_semantic=True)
        svc = SearchInventoryService.__new__(SearchInventoryService)
        analysis = svc.analyze_index(index)

        assert analysis.supports_hybrid is False
        assert analysis.recommended_query_type == "semantic"


class TestGetProjectNameFix:
    """Bug fix: _get_project_name handles various endpoint formats."""

    def _make_builder(self, endpoint):
        from oyd_migrator.services.agent_builder import AgentBuilderService

        builder = AgentBuilderService.__new__(AgentBuilderService)
        builder.project_endpoint = endpoint
        return builder

    def test_services_ai_azure_com_endpoint(self):
        builder = self._make_builder(
            "https://myaccount.services.ai.azure.com/api/projects/myproject"
        )
        assert builder._get_project_name() == "myproject"

    def test_cognitiveservices_endpoint(self):
        builder = self._make_builder(
            "https://myresource.cognitiveservices.azure.com/"
        )
        assert builder._get_project_name() == "myresource"

    def test_openai_endpoint(self):
        builder = self._make_builder(
            "https://myoai.openai.azure.com/"
        )
        assert builder._get_project_name() == "myoai"

    def test_no_projects_path_extracts_host(self):
        builder = self._make_builder(
            "https://some-resource.example.com/other/path"
        )
        assert builder._get_project_name() == "some-resource"
