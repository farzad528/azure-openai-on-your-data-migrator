"""Main CLI application entry point."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from oyd_migrator import __version__
from oyd_migrator.core.config import get_settings
from oyd_migrator.core.constants import Display
from oyd_migrator.core.logging import setup_logging

# Create main app
app = typer.Typer(
    name="oyd-migrator",
    help=Display.APP_DESCRIPTION,
    add_completion=True,
    rich_markup_mode="rich",
    no_args_is_help=True,
)

# Console for rich output
console = Console()


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"[bold]{Display.APP_NAME}[/bold] version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-V",
        help="Enable verbose output.",
    ),
    config_dir: Optional[Path] = typer.Option(
        None,
        "--config-dir",
        "-c",
        help="Configuration directory path.",
        envvar="OYD_MIGRATOR_CONFIG_DIR",
    ),
) -> None:
    """
    OYD Foundry Migrator - Migrate Azure OpenAI On Your Data to Foundry Agent Service.

    This CLI tool helps you migrate from the deprecated Azure OpenAI "On Your Data"
    (OYD) feature to the new Foundry Agent Service architecture.

    Migration targets:
    - Foundry Agent Service with Azure AI Search Tool
    - Foundry Agent Service with Foundry IQ Knowledge Base (MCP)
    """
    # Setup logging
    setup_logging(verbose=verbose)

    # Override config dir if specified
    if config_dir:
        settings = get_settings()
        settings.config_dir = config_dir


# Import and register command groups
from oyd_migrator.cli.commands import discover, migrate, validate, generate

app.add_typer(discover.app, name="discover", help="Discover OYD configurations and Azure resources.")
app.add_typer(migrate.app, name="migrate", help="Run the migration wizard.")
app.add_typer(validate.app, name="validate", help="Validate migrated resources.")
app.add_typer(generate.app, name="generate", help="Generate code samples and reports.")


# Quick commands (aliases for common operations)
@app.command("wizard")
def wizard_command(
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

    This is an alias for 'oyd-migrator migrate interactive'.
    """
    from oyd_migrator.cli.commands.migrate import interactive_command
    interactive_command(resume=resume, config_file=config_file)


@app.command("compare")
def compare_command() -> None:
    """
    Display the feature comparison matrix.

    This is an alias for 'oyd-migrator generate comparison'.
    """
    from oyd_migrator.cli.commands.generate import comparison_command
    comparison_command(output=None, format="table")


if __name__ == "__main__":
    app()
