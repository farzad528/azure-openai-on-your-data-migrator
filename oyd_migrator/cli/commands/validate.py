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
