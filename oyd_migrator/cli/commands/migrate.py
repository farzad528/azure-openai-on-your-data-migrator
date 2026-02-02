"""Migration commands and wizard."""

from pathlib import Path
from typing import Optional
import uuid

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from oyd_migrator.core.config import get_settings, MigrationState
from oyd_migrator.core.constants import Display, MigrationPath
from oyd_migrator.core.logging import get_logger

app = typer.Typer(help="Run the migration wizard.")
console = Console()
logger = get_logger("migrate")


@app.command("interactive")
def interactive_command(
    resume: Optional[str] = typer.Option(
        None,
        "--resume",
        "-r",
        help="Resume a previous session by ID.",
    ),
    config_file: Optional[Path] = typer.Option(
        None,
        "--config",
        "-f",
        help="Load configuration from YAML file.",
    ),
) -> None:
    """
    Run the interactive migration wizard.

    This wizard will guide you through:
    1. Authentication setup
    2. Discovery of OYD configurations
    3. Migration path selection
    4. Foundry project configuration
    5. Agent creation and testing
    """
    from oyd_migrator.cli.wizards.auth_wizard import run_auth_wizard
    from oyd_migrator.cli.wizards.discovery_wizard import run_discovery_wizard
    from oyd_migrator.cli.wizards.migration_wizard import run_migration_wizard
    from oyd_migrator.cli.wizards.review_wizard import run_review_wizard

    settings = get_settings()
    config_dir = settings.ensure_config_dir()

    # Show welcome banner
    console.print(Panel.fit(
        f"[bold]{Display.APP_NAME}[/bold]\n\n"
        "Migrate Azure OpenAI On Your Data to Foundry Agent Service\n\n"
        "This wizard will guide you through the migration process.",
        title="Welcome",
        border_style="cyan",
    ))

    # Load or create session
    if resume:
        state = MigrationState.load(resume, config_dir)
        if not state:
            console.print(f"{Display.FAILURE} Session '{resume}' not found.")
            raise typer.Exit(1)
        console.print(f"\n{Display.INFO} Resuming session: {resume}")
        console.print(f"  Last stage: {state.current_stage}")
        console.print(f"  Updated: {state.updated_at}\n")
    elif config_file:
        # Load from config file
        import yaml
        with open(config_file) as f:
            config_data = yaml.safe_load(f)
        state = MigrationState(
            session_id=str(uuid.uuid4())[:8],
            **config_data,
        )
        console.print(f"\n{Display.INFO} Loaded configuration from: {config_file}\n")
    else:
        state = MigrationState(session_id=str(uuid.uuid4())[:8])
        console.print(f"\n{Display.INFO} Started new session: {state.session_id}\n")

    try:
        # Stage 1: Authentication
        if state.current_stage in ["auth", "new"]:
            console.print("\n[bold cyan]Stage 1/4: Authentication[/bold cyan]\n")
            state = run_auth_wizard(state, console)
            state.current_stage = "discovery"
            state.save(config_dir)

        # Stage 2: Discovery
        if state.current_stage == "discovery":
            console.print("\n[bold cyan]Stage 2/4: Discovery[/bold cyan]\n")
            state = run_discovery_wizard(state, console)
            state.current_stage = "migration"
            state.save(config_dir)

        # Stage 3: Migration configuration
        if state.current_stage == "migration":
            console.print("\n[bold cyan]Stage 3/4: Migration Configuration[/bold cyan]\n")
            state = run_migration_wizard(state, console)
            state.current_stage = "review"
            state.save(config_dir)

        # Stage 4: Review and execute
        if state.current_stage == "review":
            console.print("\n[bold cyan]Stage 4/4: Review & Execute[/bold cyan]\n")
            result = run_review_wizard(state, console)
            state.completed = True
            state.save(config_dir)

            if result.success:
                console.print(Panel.fit(
                    f"{Display.SUCCESS} Migration completed successfully!\n\n"
                    f"Agents created: {result.deployments_migrated}\n"
                    f"Tests passed: {sum(1 for t in result.test_results if t.success)}/{len(result.test_results)}",
                    title="Migration Complete",
                    border_style="green",
                ))
            else:
                console.print(Panel.fit(
                    f"{Display.FAILURE} Migration completed with errors.\n\n"
                    f"Errors: {len(result.errors)}",
                    title="Migration Issues",
                    border_style="red",
                ))
                for error in result.errors:
                    console.print(f"  {Display.FAILURE} {error}")

    except KeyboardInterrupt:
        console.print(f"\n\n{Display.WARNING} Migration interrupted.")
        console.print(f"Session saved. Resume with: [cyan]oyd-migrator migrate interactive --resume {state.session_id}[/cyan]\n")
        raise typer.Exit(0)
    except Exception as e:
        logger.exception("Migration failed")
        console.print(f"\n{Display.FAILURE} Migration failed: {e}")
        console.print(f"Session saved. Resume with: [cyan]oyd-migrator migrate interactive --resume {state.session_id}[/cyan]\n")
        state.save(config_dir)
        raise typer.Exit(1)


@app.command("sessions")
def sessions_command(
    show_completed: bool = typer.Option(
        False,
        "--completed",
        help="Include completed sessions.",
    ),
) -> None:
    """
    List saved migration sessions.

    Shows previous migration sessions that can be resumed.
    """
    from rich.table import Table

    settings = get_settings()
    sessions = MigrationState.list_sessions(settings.config_dir)

    if not show_completed:
        sessions = [s for s in sessions if not s.completed]

    if not sessions:
        console.print(f"{Display.INFO} No saved sessions found.")
        return

    table = Table(title="Migration Sessions", box=box.ROUNDED)
    table.add_column("Session ID", style="cyan")
    table.add_column("Stage")
    table.add_column("Status")
    table.add_column("Updated")

    for session in sessions:
        status = Display.SUCCESS + " Completed" if session.completed else Display.IN_PROGRESS + " In Progress"
        table.add_row(
            session.session_id,
            session.current_stage,
            status,
            session.updated_at.strftime("%Y-%m-%d %H:%M"),
        )

    console.print(table)
    console.print(f"\nResume a session with: [cyan]oyd-migrator migrate interactive --resume <session-id>[/cyan]")


@app.command("search-tool")
def search_tool_command(
    subscription_id: str = typer.Option(
        ...,
        "--subscription",
        "-s",
        help="Azure subscription ID.",
    ),
    aoai_resource: str = typer.Option(
        ...,
        "--aoai-resource",
        help="Source AOAI resource name.",
    ),
    deployment: str = typer.Option(
        ...,
        "--deployment",
        "-d",
        help="Source OYD deployment name.",
    ),
    project_endpoint: str = typer.Option(
        ...,
        "--project-endpoint",
        help="Target Foundry project endpoint.",
    ),
    model: str = typer.Option(
        "gpt-4.1",
        "--model",
        "-m",
        help="Model deployment to use.",
    ),
    skip_test: bool = typer.Option(
        False,
        "--skip-test",
        help="Skip testing after migration.",
    ),
) -> None:
    """
    Migrate to Foundry Agent Service with Azure AI Search Tool.

    Non-interactive migration using the Azure AI Search Tool approach.
    Use 'oyd-migrator discover aoai' first to find deployment details.
    """
    console.print(f"\n{Display.INFO} Starting migration to Foundry + Azure AI Search Tool...\n")

    # TODO: Implement non-interactive migration
    console.print(f"{Display.WARNING} Non-interactive migration not yet implemented.")
    console.print("Use [cyan]oyd-migrator wizard[/cyan] for interactive migration.\n")


@app.command("knowledge-base")
def knowledge_base_command(
    subscription_id: str = typer.Option(
        ...,
        "--subscription",
        "-s",
        help="Azure subscription ID.",
    ),
    aoai_resource: str = typer.Option(
        ...,
        "--aoai-resource",
        help="Source AOAI resource name.",
    ),
    deployment: str = typer.Option(
        ...,
        "--deployment",
        "-d",
        help="Source OYD deployment name.",
    ),
    project_endpoint: str = typer.Option(
        ...,
        "--project-endpoint",
        help="Target Foundry project endpoint.",
    ),
    knowledge_base_name: str = typer.Option(
        ...,
        "--kb-name",
        help="Target knowledge base name.",
    ),
    model: str = typer.Option(
        "gpt-4.1-mini",
        "--model",
        "-m",
        help="Model deployment to use.",
    ),
    skip_test: bool = typer.Option(
        False,
        "--skip-test",
        help="Skip testing after migration.",
    ),
) -> None:
    """
    Migrate to Foundry Agent Service with Foundry IQ Knowledge Base.

    Non-interactive migration using the Foundry IQ Knowledge Base (MCP) approach.
    Use 'oyd-migrator discover aoai' first to find deployment details.
    """
    console.print(f"\n{Display.INFO} Starting migration to Foundry + Foundry IQ Knowledge Base...\n")

    # TODO: Implement non-interactive migration
    console.print(f"{Display.WARNING} Non-interactive migration not yet implemented.")
    console.print("Use [cyan]oyd-migrator wizard[/cyan] for interactive migration.\n")
