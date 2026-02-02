"""Migration configuration wizard."""

from __future__ import annotations

import questionary
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from oyd_migrator.core.config import MigrationState, FoundryConfig, MigrationOptions
from oyd_migrator.core.constants import Display, MigrationPath
from oyd_migrator.core.logging import get_logger

logger = get_logger("wizard.migration")


def run_migration_wizard(state: MigrationState, console: Console) -> MigrationState:
    """
    Run the migration configuration wizard.

    Guides the user through selecting migration path and target configuration.

    Args:
        state: Current migration state
        console: Rich console for output

    Returns:
        Updated migration state with migration configuration
    """
    from oyd_migrator.services.auth import AzureAuthService
    from oyd_migrator.services.foundry_provisioner import FoundryProvisionerService

    console.print("Let's configure your migration target.\n")

    # Display feature comparison
    _display_comparison(console)

    # Select migration path
    console.print("\n[bold]Select your migration path:[/bold]\n")

    path = questionary.select(
        "Which architecture do you want to migrate to?",
        choices=[
            questionary.Choice(
                title="Foundry Agent + Azure AI Search Tool (Recommended for simple RAG)",
                value=MigrationPath.SEARCH_TOOL,
            ),
            questionary.Choice(
                title="Foundry Agent + Foundry IQ Knowledge Base (Better for complex reasoning)",
                value=MigrationPath.KNOWLEDGE_BASE,
            ),
        ],
    ).ask()

    if not path:
        raise KeyboardInterrupt()

    state.migration_options = MigrationOptions(migration_path=path)

    # Path-specific guidance
    if path == MigrationPath.SEARCH_TOOL:
        console.print(f"\n{Display.INFO} Azure AI Search Tool migration selected.\n")
        console.print("This approach:")
        console.print("  • Directly connects to your existing search index")
        console.print("  • Uses the AzureAISearchAgentTool SDK")
        console.print("  • Supports all query types (simple, semantic, vector, hybrid)")
        console.print("  • Best for straightforward RAG scenarios\n")
    else:
        console.print(f"\n{Display.INFO} Foundry IQ Knowledge Base migration selected.\n")
        console.print("This approach:")
        console.print("  • Creates a Knowledge Base on top of your search index")
        console.print("  • Uses MCP protocol with knowledge_base_retrieve tool")
        console.print("  • Enables advanced query planning and decomposition")
        console.print("  • Best for complex reasoning and multi-source scenarios\n")

    # Configure Foundry project
    console.print("[bold]Configure your Foundry project:[/bold]\n")

    # Get credential
    auth_service = AzureAuthService()
    credential = auth_service.get_credential_from_config(state.azure_config)

    # Check for existing projects
    provisioner = FoundryProvisionerService(
        credential=credential,
        subscription_id=state.azure_config.subscription_id,
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Checking for existing Foundry projects...", total=None)
        existing_projects = provisioner.list_projects()
        progress.update(task, completed=True)

    if existing_projects:
        console.print(f"\n{Display.INFO} Found {len(existing_projects)} existing Foundry project(s).\n")

        use_existing = questionary.confirm(
            "Would you like to use an existing project?",
            default=True,
        ).ask()

        if use_existing:
            project_choices = [
                questionary.Choice(
                    title=f"{p.name} ({p.resource_group})",
                    value=p,
                )
                for p in existing_projects
            ]

            selected_project = questionary.select(
                "Select a project:",
                choices=project_choices,
            ).ask()

            if not selected_project:
                raise KeyboardInterrupt()

            state.foundry_config = FoundryConfig(
                project_name=selected_project.name,
                resource_group=selected_project.resource_group,
                project_endpoint=selected_project.endpoint,
            )
            state.migration_options.create_new_project = False
        else:
            state.foundry_config = _configure_new_project(console, provisioner)
            state.migration_options.create_new_project = True
    else:
        console.print(f"\n{Display.INFO} No existing Foundry projects found.\n")
        state.foundry_config = _configure_new_project(console, provisioner)
        state.migration_options.create_new_project = True

    # Select model
    console.print("\n[bold]Select the model for your agents:[/bold]\n")

    model = questionary.select(
        "Which model should the agents use?",
        choices=[
            questionary.Choice(
                title="gpt-4.1 (Recommended - best quality)",
                value="gpt-4.1",
            ),
            questionary.Choice(
                title="gpt-4.1-mini (Good balance of quality and cost)",
                value="gpt-4.1-mini",
            ),
            questionary.Choice(
                title="gpt-4o (If you need it for compatibility)",
                value="gpt-4o",
            ),
            questionary.Choice(
                title="Other (specify)",
                value="other",
            ),
        ],
    ).ask()

    if model == "other":
        model = questionary.text(
            "Enter model deployment name:",
            validate=lambda x: len(x) > 0 or "Required",
        ).ask()

    if not model:
        raise KeyboardInterrupt()

    state.foundry_config.model_deployment = model

    # Additional options
    console.print("\n[bold]Additional options:[/bold]\n")

    state.migration_options.preserve_query_type = questionary.confirm(
        "Preserve original query type from OYD configuration?",
        default=True,
    ).ask()

    state.migration_options.migrate_system_message = questionary.confirm(
        "Migrate role_information to agent instructions?",
        default=True,
    ).ask()

    state.migration_options.test_after_migration = questionary.confirm(
        "Run test queries after migration?",
        default=True,
    ).ask()

    state.migration_options.generate_samples = questionary.confirm(
        "Generate SDK code samples?",
        default=True,
    ).ask()

    # Summary
    console.print("\n[bold]Migration Configuration Summary:[/bold]\n")
    console.print(f"  • Migration path: [cyan]{path.value}[/cyan]")
    console.print(f"  • Project: [cyan]{state.foundry_config.project_name}[/cyan]")
    console.print(f"  • Model: [cyan]{state.foundry_config.model_deployment}[/cyan]")
    console.print(f"  • Create new project: {'Yes' if state.migration_options.create_new_project else 'No'}")
    console.print(f"  • Preserve query type: {'Yes' if state.migration_options.preserve_query_type else 'No'}")
    console.print(f"  • Migrate system message: {'Yes' if state.migration_options.migrate_system_message else 'No'}")
    console.print(f"  • Test after migration: {'Yes' if state.migration_options.test_after_migration else 'No'}")
    console.print()

    return state


def _display_comparison(console: Console) -> None:
    """Display a condensed feature comparison."""
    table = Table(title="Migration Path Comparison", box=box.ROUNDED, show_header=True)
    table.add_column("Feature", style="white")
    table.add_column("Search Tool", justify="center")
    table.add_column("IQ Knowledge Base", justify="center")

    comparisons = [
        ("Setup Complexity", "Lower", "Higher"),
        ("Query Control", "Direct", "Automated"),
        ("Multi-Index", Display.SUCCESS, Display.SUCCESS),
        ("Query Decomposition", Display.FAILURE, Display.SUCCESS),
        ("Agentic Reasoning", "Basic", "Full"),
        ("Best For", "Simple RAG", "Complex Reasoning"),
    ]

    for feature, search, kb in comparisons:
        table.add_row(feature, search, kb)

    console.print(table)


def _configure_new_project(console: Console, provisioner=None) -> FoundryConfig:
    """Configure a new Foundry project."""
    console.print("\nEnter details for the new Foundry project:\n")
    
    # If provisioner is provided, let user select from existing Foundry Accounts
    foundry_account_id = None
    if provisioner:
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                progress.add_task("Checking for existing Foundry Accounts...", total=None)
                accounts = provisioner.list_foundry_accounts()
            
            if accounts:
                console.print(f"\n{Display.INFO} Found {len(accounts)} existing Foundry Account(s).\n")
                console.print("[dim]A Foundry Account provides the AI Services connection for your project.[/dim]\n")
                
                account_choices = [
                    questionary.Choice(
                        title=f"{a.name} ({a.resource_group}) - {a.location}",
                        value=a,
                    )
                    for a in accounts
                ]
                account_choices.append(questionary.Choice(
                    title="Skip - Create standalone project (advanced)",
                    value=None,
                ))
                
                selected_account = questionary.select(
                    "Select a Foundry Account for your new project:",
                    choices=account_choices,
                ).ask()
                
                if selected_account:
                    foundry_account_id = selected_account.resource_id
                    console.print(f"\n{Display.SUCCESS} Using Foundry Account: {selected_account.name}\n")
        except Exception as e:
            logger.debug(f"Could not list Foundry accounts: {e}")

    project_name = questionary.text(
        "Project name:",
        default="oyd-migration-project",
        validate=lambda x: len(x) > 0 or "Required",
    ).ask()

    resource_group = questionary.text(
        "Resource group:",
        validate=lambda x: len(x) > 0 or "Required",
    ).ask()
    
    location = questionary.text(
        "Location (Azure region):",
        default="eastus",
        validate=lambda x: len(x) > 0 or "Required",
    ).ask()

    if not all([project_name, resource_group]):
        raise KeyboardInterrupt()

    config = FoundryConfig(
        project_name=project_name,
        resource_group=resource_group,
        project_endpoint="",  # Will be set after creation
        location=location,
    )
    
    # Store foundry_account_id (hub_resource_id) for later use during creation
    if foundry_account_id:
        config.hub_resource_id = foundry_account_id
    
    return config
