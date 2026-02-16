"""Agent test runner service."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from azure.core.credentials import TokenCredential

from oyd_migrator.core.constants import ApiVersions
from oyd_migrator.core.exceptions import ValidationError
from oyd_migrator.core.logging import get_logger
from oyd_migrator.models.migration import TestResult

logger = get_logger("services.test_runner")


class AgentTestRunner:
    """Service for testing Foundry agents."""

    def __init__(self, credential: TokenCredential, project_endpoint: str) -> None:
        """
        Initialize the test runner.

        Args:
            credential: Azure credential
            project_endpoint: Foundry project endpoint URL
        """
        self.credential = credential
        self.project_endpoint = project_endpoint

    def test_agent(
        self,
        agent_name: str,
        query: str,
        timeout_seconds: int = 60,
    ) -> TestResult:
        """
        Test an agent with a query.

        Args:
            agent_name: Name of the agent to test
            query: Test query to send
            timeout_seconds: Maximum time to wait for response

        Returns:
            Test result
        """
        result = TestResult(
            agent_name=agent_name,
            query=query,
            timestamp=datetime.now(timezone.utc),
        )

        start_time = time.time()

        try:
            import httpx
            from oyd_migrator.core.constants import AzureScopes

            token = self.credential.get_token(AzureScopes.AI_FOUNDRY)

            # Create a conversation/thread
            thread_url = f"{self.project_endpoint}/openai/conversations?api-version=2025-11-15-preview"

            headers = {
                "Authorization": f"Bearer {token.token}",
                "Content-Type": "application/json",
            }

            thread_response = httpx.post(
                thread_url, headers=headers, json={}, timeout=30
            )
            thread_response.raise_for_status()
            thread_data = thread_response.json()
            conversation_id = thread_data.get("id")

            # Send query to agent
            response_url = f"{self.project_endpoint}/openai/responses?api-version=2025-11-15-preview"

            body = {
                "conversation": conversation_id,
                "input": query,
                "agent": {
                    "name": agent_name,
                    "type": "agent_reference",
                },
            }

            response = httpx.post(
                response_url,
                headers=headers,
                json=body,
                timeout=timeout_seconds,
            )

            response.raise_for_status()
            data = response.json()

            # Parse response
            result.success = True
            result.response_text = data.get("output_text", "")

            # Count tool calls
            tool_calls = data.get("tool_calls", [])
            result.tool_calls_count = len(tool_calls)
            result.tool_types = list(set(tc.get("type", "") for tc in tool_calls))

            # Check for citations
            citations = data.get("citations", [])
            result.citation_count = len(citations)
            result.has_citations = len(citations) > 0

            # Token usage
            usage = data.get("usage", {})
            result.total_tokens = usage.get("total_tokens", 0)

        except httpx.TimeoutException:
            result.success = False
            result.error_message = f"Request timed out after {timeout_seconds}s"
            result.error_type = "timeout"

        except httpx.HTTPStatusError as e:
            result.success = False
            result.error_message = f"HTTP error: {e.response.status_code}"
            result.error_type = "http_error"

        except Exception as e:
            result.success = False
            result.error_message = str(e)
            result.error_type = "exception"
            logger.warning(f"Test failed for {agent_name}: {e}")

        # Calculate response time
        result.response_time_ms = (time.time() - start_time) * 1000

        return result

    def run_test_suite(
        self,
        agent_name: str,
        queries: list[str],
    ) -> list[TestResult]:
        """
        Run multiple test queries against an agent.

        Args:
            agent_name: Name of the agent to test
            queries: List of test queries

        Returns:
            List of test results
        """
        results = []

        for query in queries:
            result = self.test_agent(agent_name, query)
            results.append(result)

            # Small delay between requests to avoid rate limiting
            time.sleep(0.5)

        return results

    def generate_test_queries(self, context: str = "") -> list[str]:
        """
        Generate default test queries.

        Args:
            context: Optional context to customize queries

        Returns:
            List of test queries
        """
        base_queries = [
            "What information do you have available?",
            "Can you provide a summary of the main topics?",
            "What are the key points I should know about?",
        ]

        if context:
            base_queries.append(f"Tell me about {context}")

        return base_queries

    def validate_agent_response(
        self,
        result: TestResult,
        require_citations: bool = True,
        require_tool_calls: bool = True,
    ) -> tuple[bool, list[str]]:
        """
        Validate an agent response meets requirements.

        Args:
            result: Test result to validate
            require_citations: Require citations in response
            require_tool_calls: Require tool calls to be made

        Returns:
            Tuple of (is_valid, issues)
        """
        issues = []

        if not result.success:
            issues.append(f"Request failed: {result.error_message}")
            return False, issues

        if not result.response_text:
            issues.append("Empty response received")

        if require_citations and not result.has_citations:
            issues.append("No citations in response")

        if require_tool_calls and result.tool_calls_count == 0:
            issues.append("No tool calls made")

        return len(issues) == 0, issues
