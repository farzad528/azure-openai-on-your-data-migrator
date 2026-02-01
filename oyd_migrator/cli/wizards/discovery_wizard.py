"""Discovery wizard for finding OYD configurations."""

from __future__ import annotations

import questionary
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from oyd_migrator.core.config import MigrationState, AOAIConfig, SearchConfig
from oyd_migrator.core.constants import Display
from oyd_migrator.core.logging import get_logger
from oyd_migrator.models.oyd import OYDDeployment

logger = get_logger("wizard.discovery")


def run_discovery_wizard(state: MigrationState, console: Console) -> MigrationState:
    """
    Run the discovery wizard.

    Discovers OYD configurations and search indexes.

    Args:
        state: Current migration state
        console: Rich console for output

    Returns:
        Updated migration state with discovered resources
    """
    from oyd_migrator.services.auth import AzureAuthService
    from oyd_migrator.services.aoai_discovery import AOAIDiscoveryService
    from oyd_migrator.services.search_inventory import SearchInventoryService

    if not state.azure_config:
        raise ValueError("Azure configuration not set. Run auth wizard first.")

    console.print("Let's discover your OYD configurations.\n")

    # Get credential
    auth_service = AzureAuthService()
    credential = auth_service.get_credential_from_config(state.azure_config)

    # Discover AOAI resources
    console.print("[bold]Scanning for Azure OpenAI resources with OYD...[/bold]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Discovering AOAI resources...", total=None)

        discovery_service = AOAIDiscoveryService(
            credential=credential,
            subscription_id=state.azure_config.subscription_id,
        )
        deployments = discovery_service.discover_oyd_deployments()
        progress.update(task, completed=True)

    if not deployments:
        console.print(f"\n{Display.WARNING} No OYD configurations found in this subscription.\n")

        # Ask if they want to manually specify
        manual = questionary.confirm(
            "Would you like to manually specify an AOAI resource?",
            default=False,
        ).ask()

        if manual:
            deployments = _manual_aoai_entry(console)
        else:
            console.print("No deployments to migrate. Exiting.\n")
            raise SystemExit(0)

    # Display discovered deployments
    _display_deployments(deployments, console)

    # Select deployments to migrate
    if len(deployments) == 1:
        selected_deployments = deployments
        console.print(f"\n{Display.INFO} Using the single discovered deployment.\n")
    else:
        deployment_choices = [
            questionary.Choice(
                title=f"{d.resource_name}/{d.deployment_name} ({d.model_name}, {d.data_source_count} data source(s))",
                value=d,
            )
            for d in deployments
        ]

        selected_deployments = questionary.checkbox(
            "Select the deployments to migrate:",
            choices=deployment_choices,
        ).ask()

        if not selected_deployments:
            raise KeyboardInterrupt()

    # Store AOAI configs
    state.aoai_configs = [
        AOAIConfig(
            resource_name=d.resource_name,
            resource_group=d.resource_group,
            endpoint=d.endpoint,
            deployment_name=d.deployment_name,
        )
        for d in selected_deployments
    ]

    # Discover related search indexes
    console.print("\n[bold]Analyzing connected Azure AI Search indexes...[/bold]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Fetching index details...", total=None)

        inventory_service = SearchInventoryService(
            credential=credential,
            subscription_id=state.azure_config.subscription_id,
        )

        # Get unique search endpoints from OYD configs
        search_endpoints = set()
        for deployment in selected_deployments:
            if deployment.oyd_config:
                for source in deployment.oyd_config.get_azure_search_sources():
                    search_endpoints.add(source.endpoint)

        # Fetch index details for each endpoint
        search_configs = []
        for endpoint in search_endpoints:
            try:
                service = inventory_service.get_service_by_endpoint(endpoint)
                if service:
                    search_configs.append(SearchConfig(
                        service_name=service.name,
                        resource_group=service.resource_group,
                        endpoint=endpoint,
                        use_managed_identity=service.requires_managed_identity,
                    ))
            except Exception as e:
                logger.warning(f"Could not fetch details for {endpoint}: {e}")

        progress.update(task, completed=True)

    state.search_configs = search_configs

    # Display search index summary
    if search_configs:
        console.print(f"{Display.SUCCESS} Found {len(search_configs)} connected search service(s):\n")
        for config in search_configs:
            auth_type = "Managed Identity" if config.use_managed_identity else "API Key"
            console.print(f"  • {config.service_name} ({auth_type})")
        console.print()
    else:
        console.print(f"{Display.WARNING} No search services found in OYD configurations.\n")

    # Summary
    console.print("[bold]Discovery Summary:[/bold]\n")
    console.print(f"  • Deployments to migrate: {len(selected_deployments)}")
    console.print(f"  • Search services: {len(search_configs)}")

    total_indexes = sum(
        len(d.oyd_config.get_azure_search_sources()) if d.oyd_config else 0
        for d in selected_deployments
    )
    console.print(f"  • Total indexes: {total_indexes}")
    console.print()

    return state


def _display_deployments(deployments: list[OYDDeployment], console: Console) -> None:
    """Display a table of discovered deployments."""
    table = Table(title="Discovered OYD Deployments", box="ROUNDED")
    table.add_column("#", style="dim")
    table.add_column("Resource", style="cyan")
    table.add_column("Deployment", style="green")
    table.add_column("Model")
    table.add_column("Data Sources", justify="center")
    table.add_column("Query Type")

    for i, d in enumerate(deployments, 1):
        query_type = "-"
        if d.oyd_config:
            search_sources = d.oyd_config.get_azure_search_sources()
            if search_sources:
                query_type = search_sources[0].query_type

        table.add_row(
            str(i),
            d.resource_name,
            d.deployment_name,
            d.model_name,
            str(d.data_source_count),
            query_type,
        )

    console.print(table)


def _manual_aoai_entry(console: Console) -> list[OYDDeployment]:
    """Manually enter AOAI resource details."""
    console.print("\nEnter the AOAI resource details:\n")

    resource_name = questionary.text(
        "Resource name:",
        validate=lambda x: len(x) > 0 or "Required",
    ).ask()

    resource_group = questionary.text(
        "Resource group:",
        validate=lambda x: len(x) > 0 or "Required",
    ).ask()

    deployment_name = questionary.text(
        "Deployment name:",
        validate=lambda x: len(x) > 0 or "Required",
    ).ask()

    model_name = questionary.text(
        "Model name (e.g., gpt-4o):",
        default="gpt-4o",
    ).ask()

    if not all([resource_name, resource_group, deployment_name]):
        raise KeyboardInterrupt()

    # Create deployment object
    deployment = OYDDeployment(
        resource_name=resource_name,
        resource_group=resource_group,
        subscription_id="",  # Will be filled from state
        endpoint=f"https://{resource_name}.openai.azure.com",
        deployment_name=deployment_name,
        model_name=model_name,
        has_oyd=True,
        data_source_count=1,  # Assume at least one
    )

    return [deployment]
