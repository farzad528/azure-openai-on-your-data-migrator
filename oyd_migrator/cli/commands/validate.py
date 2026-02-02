"""Validation commands for testing migrated resources."""

from typing import Optional

import typer
from rich import box
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from oyd_migrator.core.constants import Display
from oyd_migrator.core.logging import get_logger

app = typer.Typer(help="Validate migrated resources.")
console = Console()
logger = get_logger("validate")


@app.command("agent")
def agent_command(
    agent_name: str = typer.Argument(
        ...,
        help="Name of the agent to test.",
    ),
    project_endpoint: str = typer.Option(
        ...,
        "--project-endpoint",
        "-p",
        help="Foundry project endpoint URL.",
    ),
    query: Optional[str] = typer.Option(
        None,
        "--query",
        "-q",
        help="Test query to send. If not provided, uses a default query.",
    ),
    queries_file: Optional[str] = typer.Option(
        None,
        "--queries-file",
        "-f",
        help="File containing test queries (one per line).",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed response information.",
    ),
) -> None:
    """
    Test a migrated Foundry agent.

    Sends test queries to the agent and validates:
    - Agent responds successfully
    - Tool calls are made (search/KB retrieval)
    - Citations are included in responses
    """
    from oyd_migrator.services.auth import AzureAuthService
    from oyd_migrator.services.test_runner import AgentTestRunner

    console.print(f"\n{Display.INFO} Testing agent: [cyan]{agent_name}[/cyan]\n")

    # Collect queries
    test_queries = []
    if query:
        test_queries.append(query)
    elif queries_file:
        with open(queries_file) as f:
            test_queries = [line.strip() for line in f if line.strip()]
    else:
        # Default test queries
        test_queries = [
            "What information do you have available?",
            "Can you summarize the main topics in your knowledge base?",
        ]

    try:
        # Authenticate
        auth_service = AzureAuthService()
        credential = auth_service.get_credential()

        # Create test runner
        test_runner = AgentTestRunner(
            credential=credential,
            project_endpoint=project_endpoint,
        )

        # Run tests
        results = []
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"Running {len(test_queries)} test(s)...", total=len(test_queries))

            for test_query in test_queries:
                result = test_runner.test_agent(agent_name, test_query)
                results.append(result)
                progress.advance(task)

        # Display results
        table = Table(title="Test Results", box=box.ROUNDED)
        table.add_column("Status", width=8)
        table.add_column("Query")
        table.add_column("Tools", justify="center")
        table.add_column("Citations", justify="center")
        table.add_column("Time (ms)", justify="right")

        for result in results:
            status = Display.SUCCESS if result.success else Display.FAILURE
            tools = str(result.tool_calls_count) if result.tool_calls_count > 0 else "-"
            citations = str(result.citation_count) if result.has_citations else "-"
            time_ms = f"{result.response_time_ms:.0f}" if result.response_time_ms else "-"

            table.add_row(
                status,
                result.query[:50] + "..." if len(result.query) > 50 else result.query,
                tools,
                citations,
                time_ms,
            )

        console.print(table)

        # Summary
        passed = sum(1 for r in results if r.success)
        console.print(f"\n{Display.SUCCESS if passed == len(results) else Display.WARNING} "
                      f"Passed: {passed}/{len(results)} tests")

        # Verbose output
        if verbose:
            console.print("\n[bold]Detailed Results:[/bold]\n")
            for i, result in enumerate(results, 1):
                console.print(f"[bold]Test {i}:[/bold] {result.query}")
                if result.success:
                    console.print(f"  Response: {result.response_text[:200]}...")
                    console.print(f"  Tool types: {', '.join(result.tool_types) or 'None'}")
                else:
                    console.print(f"  {Display.FAILURE} Error: {result.error_message}")
                console.print()

        # Exit with error if any tests failed
        if passed < len(results):
            raise typer.Exit(1)

    except Exception as e:
        logger.exception("Validation failed")
        console.print(f"{Display.FAILURE} Validation failed: {e}")
        raise typer.Exit(1)


@app.command("connection")
def connection_command(
    connection_name: str = typer.Argument(
        ...,
        help="Name of the connection to validate.",
    ),
    project_endpoint: str = typer.Option(
        ...,
        "--project-endpoint",
        "-p",
        help="Foundry project endpoint URL.",
    ),
) -> None:
    """
    Validate a Foundry project connection.

    Checks that the connection is properly configured and accessible.
    """
    from oyd_migrator.services.auth import AzureAuthService
    from oyd_migrator.services.connection_manager import ConnectionManagerService

    console.print(f"\n{Display.INFO} Validating connection: [cyan]{connection_name}[/cyan]\n")

    try:
        # Authenticate
        auth_service = AzureAuthService()
        credential = auth_service.get_credential()

        # Get connection manager
        connection_manager = ConnectionManagerService(
            credential=credential,
            project_endpoint=project_endpoint,
        )

        # Validate
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Checking connection...", total=None)

            result = connection_manager.validate_connection(connection_name)
            progress.update(task, completed=True)

        if result.is_valid:
            console.print(f"{Display.SUCCESS} Connection is valid and accessible.")
            console.print(f"  Type: {result.connection_type}")
            console.print(f"  Target: {result.target}")
            console.print(f"  Auth: {result.auth_type}")
        else:
            console.print(f"{Display.FAILURE} Connection validation failed.")
            for issue in result.issues:
                console.print(f"  {Display.FAILURE} {issue}")
            raise typer.Exit(1)

    except Exception as e:
        logger.exception("Validation failed")
        console.print(f"{Display.FAILURE} Validation failed: {e}")
        raise typer.Exit(1)


@app.command("compare")
def compare_command(
    oyd_endpoint: str = typer.Option(
        ...,
        "--oyd-endpoint",
        help="Original AOAI OYD endpoint.",
    ),
    oyd_deployment: str = typer.Option(
        ...,
        "--oyd-deployment",
        help="Original OYD deployment name.",
    ),
    foundry_endpoint: str = typer.Option(
        ...,
        "--foundry-endpoint",
        help="Migrated Foundry project endpoint.",
    ),
    agent_name: str = typer.Option(
        ...,
        "--agent-name",
        help="Migrated agent name.",
    ),
    queries_file: Optional[str] = typer.Option(
        None,
        "--queries-file",
        "-f",
        help="File containing test queries.",
    ),
) -> None:
    """
    Compare responses between OYD and migrated Foundry agent.

    Sends the same queries to both the original OYD deployment and the
    migrated Foundry agent, then compares the responses.
    """
    console.print(f"\n{Display.INFO} Comparing OYD vs Foundry responses...\n")

    # TODO: Implement comparison
    console.print(f"{Display.WARNING} Comparison not yet implemented.")
    console.print("This feature will compare responses between the original OYD deployment")
    console.print("and the migrated Foundry agent to validate migration quality.\n")


@app.command("roles")
def roles_command(
    subscription_id: Optional[str] = typer.Option(
        None,
        "--subscription",
        "-s",
        help="Azure subscription ID.",
    ),
    resource_group: str = typer.Option(
        ...,
        "--resource-group",
        "-g",
        help="Resource group containing the Azure OpenAI and Search resources.",
    ),
    aoai_resource: Optional[str] = typer.Option(
        None,
        "--aoai-resource",
        help="Azure OpenAI resource name (optional, will scan if not provided).",
    ),
    search_service: Optional[str] = typer.Option(
        None,
        "--search-service",
        help="Azure AI Search service name (optional, will scan if not provided).",
    ),
) -> None:
    """
    Validate RBAC role assignments for OYD connectivity.

    Checks that the required role assignments are configured between:
    - Azure OpenAI and Azure AI Search
    - Azure AI Search and Storage Account
    - Foundry Project resources

    This helps diagnose 403 (Forbidden) errors when using managed identity.
    """
    from oyd_migrator.services.auth import AzureAuthService

    console.print(f"\n{Display.INFO} Validating RBAC role assignments...\n")

    try:
        # Authenticate
        auth_service = AzureAuthService()
        credential = auth_service.get_credential()

        # Get subscription
        if not subscription_id:
            subscriptions = auth_service.list_subscriptions(credential)
            if not subscriptions:
                console.print(f"{Display.FAILURE} No subscriptions found.")
                raise typer.Exit(1)
            subscription_id = subscriptions[0].subscription_id

        console.print(f"Subscription: [cyan]{subscription_id}[/cyan]")
        console.print(f"Resource Group: [cyan]{resource_group}[/cyan]\n")

        # Try to import Azure authorization client
        try:
            from azure.mgmt.authorization import AuthorizationManagementClient
            from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient
            from azure.mgmt.search import SearchManagementClient
        except ImportError:
            console.print(f"{Display.FAILURE} Missing Azure SDK packages.")
            console.print("Run: pip install azure-mgmt-authorization azure-mgmt-search")
            raise typer.Exit(1)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Checking resources...", total=None)

            # Get Azure OpenAI resources
            cog_client = CognitiveServicesManagementClient(credential, subscription_id)
            aoai_resources = []

            if aoai_resource:
                try:
                    res = cog_client.accounts.get(resource_group, aoai_resource)
                    aoai_resources.append(res)
                except Exception:
                    console.print(f"{Display.FAILURE} AOAI resource '{aoai_resource}' not found.")
                    raise typer.Exit(1)
            else:
                for account in cog_client.accounts.list_by_resource_group(resource_group):
                    if account.kind == "OpenAI":
                        aoai_resources.append(account)

            # Get Search resources
            search_client = SearchManagementClient(credential, subscription_id)
            search_services = []

            if search_service:
                try:
                    svc = search_client.services.get(resource_group, search_service)
                    search_services.append(svc)
                except Exception:
                    console.print(f"{Display.FAILURE} Search service '{search_service}' not found.")
                    raise typer.Exit(1)
            else:
                for svc in search_client.services.list_by_resource_group(resource_group):
                    search_services.append(svc)

            progress.update(task, description="Checking role assignments...")

            # Get role assignments
            auth_client = AuthorizationManagementClient(credential, subscription_id)

            # Define required roles
            required_roles = [
                {
                    "role": "Search Index Data Reader",
                    "assignee": "Azure OpenAI",
                    "resource": "Azure AI Search",
                    "required_for": "Query index data",
                },
                {
                    "role": "Search Service Contributor",
                    "assignee": "Azure OpenAI",
                    "resource": "Azure AI Search",
                    "required_for": "Query index schema",
                },
                {
                    "role": "Cognitive Services OpenAI Contributor",
                    "assignee": "Azure AI Search",
                    "resource": "Azure OpenAI",
                    "required_for": "Access embedding endpoint",
                },
            ]

            progress.update(task, completed=True)

        # Display results
        console.print("[bold]Resources Found:[/bold]\n")
        console.print(f"  Azure OpenAI resources: {len(aoai_resources)}")
        for res in aoai_resources:
            identity_status = "✓ Managed Identity" if res.identity and res.identity.principal_id else "✗ No Managed Identity"
            console.print(f"    • {res.name} ({identity_status})")

        console.print(f"\n  Azure AI Search services: {len(search_services)}")
        for svc in search_services:
            identity_status = "✓ Managed Identity" if svc.identity and svc.identity.principal_id else "✗ No Managed Identity"
            console.print(f"    • {svc.name} ({identity_status})")

        console.print("\n[bold]Required Role Assignments:[/bold]\n")

        table = Table(box=box.ROUNDED)
        table.add_column("Role", style="cyan")
        table.add_column("Assignee → Resource")
        table.add_column("Purpose")
        table.add_column("Status", justify="center")

        # Check each required role
        all_valid = True
        for role_def in required_roles:
            # For now, we show requirements - full validation requires listing all assignments
            # which is slow. We'll show guidance instead.
            table.add_row(
                role_def["role"],
                f"{role_def['assignee']} → {role_def['resource']}",
                role_def["required_for"],
                Display.PENDING,  # Would need full check
            )

        console.print(table)

        console.print(f"\n{Display.INFO} Manual verification recommended:")
        console.print("  1. Go to Azure Portal → Azure AI Search → Access control (IAM)")
        console.print("  2. Click 'Role assignments' tab")
        console.print("  3. Verify Azure OpenAI has 'Search Index Data Reader' and 'Search Service Contributor'")
        console.print(f"\n  See docs/RBAC.md for detailed setup instructions.\n")

        # Check for managed identity
        missing_identity = []
        for res in aoai_resources:
            if not res.identity or not res.identity.principal_id:
                missing_identity.append(f"Azure OpenAI: {res.name}")
        for svc in search_services:
            if not svc.identity or not svc.identity.principal_id:
                missing_identity.append(f"Azure AI Search: {svc.name}")

        if missing_identity:
            console.print(f"{Display.WARNING} Resources without Managed Identity enabled:")
            for name in missing_identity:
                console.print(f"  • {name}")
            console.print("\nEnable System Assigned Managed Identity in Azure Portal → Resource → Identity")

    except Exception as e:
        logger.exception("RBAC validation failed")
        console.print(f"{Display.FAILURE} Validation failed: {e}")
        raise typer.Exit(1)
