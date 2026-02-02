"""Discovery commands for finding OYD configurations and Azure resources."""

from typing import Optional

import typer
from rich import box
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from oyd_migrator.core.constants import Display
from oyd_migrator.core.logging import get_logger

app = typer.Typer(help="Discover OYD configurations and Azure resources.")
console = Console()
logger = get_logger("discover")


@app.command("aoai")
def aoai_command(
    subscription_id: Optional[str] = typer.Option(
        None,
        "--subscription",
        "-s",
        help="Azure subscription ID. Uses default if not specified.",
    ),
    resource_group: Optional[str] = typer.Option(
        None,
        "--resource-group",
        "-g",
        help="Filter by resource group.",
    ),
    output_format: str = typer.Option(
        "table",
        "--format",
        "-f",
        help="Output format: table, json, yaml.",
    ),
) -> None:
    """
    Discover Azure OpenAI resources with On Your Data (OYD) configured.

    Scans your Azure subscription for AOAI deployments that have OYD data sources
    configured, showing details about each configuration.
    """
    from oyd_migrator.services.auth import AzureAuthService
    from oyd_migrator.services.aoai_discovery import AOAIDiscoveryService

    console.print(f"\n{Display.INFO} Discovering Azure OpenAI resources with OYD...\n")

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
            console.print(f"Using subscription: [cyan]{subscription_id}[/cyan]\n")

        # Discover AOAI resources
        discovery_service = AOAIDiscoveryService(credential, subscription_id)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Scanning AOAI resources...", total=None)

            deployments = discovery_service.discover_oyd_deployments(
                resource_group=resource_group
            )

            progress.update(task, completed=True)

        if not deployments:
            console.print(f"{Display.WARNING} No OYD configurations found.")
            return

        # Display results
        if output_format == "json":
            import json
            console.print(json.dumps([d.model_dump() for d in deployments], indent=2, default=str))
        elif output_format == "yaml":
            import yaml
            console.print(yaml.dump([d.model_dump() for d in deployments], default_flow_style=False))
        else:
            # Table format
            table = Table(title="Azure OpenAI Deployments with OYD", box=box.ROUNDED)
            table.add_column("Resource", style="cyan")
            table.add_column("Deployment", style="green")
            table.add_column("Model")
            table.add_column("Data Sources", justify="center")
            table.add_column("Index Names")

            for deployment in deployments:
                index_names = []
                if deployment.oyd_config:
                    for ds in deployment.oyd_config.get_azure_search_sources():
                        index_names.append(ds.index_name)

                table.add_row(
                    deployment.resource_name,
                    deployment.deployment_name,
                    deployment.model_name,
                    str(deployment.data_source_count),
                    ", ".join(index_names) or "-",
                )

            console.print(table)
            console.print(f"\n{Display.SUCCESS} Found {len(deployments)} OYD deployment(s).")

    except Exception as e:
        logger.exception("Discovery failed")
        console.print(f"{Display.FAILURE} Discovery failed: {e}")
        raise typer.Exit(1)


@app.command("indexes")
def indexes_command(
    subscription_id: Optional[str] = typer.Option(
        None,
        "--subscription",
        "-s",
        help="Azure subscription ID.",
    ),
    service_name: Optional[str] = typer.Option(
        None,
        "--service",
        help="Filter by search service name.",
    ),
    resource_group: Optional[str] = typer.Option(
        None,
        "--resource-group",
        "-g",
        help="Filter by resource group.",
    ),
    analyze: bool = typer.Option(
        False,
        "--analyze",
        "-a",
        help="Include detailed schema analysis.",
    ),
    output_format: str = typer.Option(
        "table",
        "--format",
        "-f",
        help="Output format: table, json, yaml.",
    ),
) -> None:
    """
    Discover Azure AI Search indexes.

    Lists all search indexes in your subscription with details about their
    schema, semantic configurations, and vector search capabilities.
    """
    from oyd_migrator.services.auth import AzureAuthService
    from oyd_migrator.services.search_inventory import SearchInventoryService

    console.print(f"\n{Display.INFO} Discovering Azure AI Search indexes...\n")

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
            console.print(f"Using subscription: [cyan]{subscription_id}[/cyan]\n")

        # Discover indexes
        inventory_service = SearchInventoryService(credential, subscription_id)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Scanning search services...", total=None)

            services = inventory_service.list_search_services(
                resource_group=resource_group
            )

            if service_name:
                services = [s for s in services if s.name == service_name]

            progress.update(task, description="Fetching index details...")

            all_indexes = []
            for service in services:
                indexes = inventory_service.get_indexes(service)
                all_indexes.extend(indexes)

            progress.update(task, completed=True)

        if not all_indexes:
            console.print(f"{Display.WARNING} No indexes found.")
            return

        # Display results
        if output_format == "json":
            import json
            console.print(json.dumps([i.model_dump() for i in all_indexes], indent=2, default=str))
        elif output_format == "yaml":
            import yaml
            console.print(yaml.dump([i.model_dump() for i in all_indexes], default_flow_style=False))
        else:
            # Table format
            table = Table(title="Azure AI Search Indexes", box=box.ROUNDED)
            table.add_column("Service", style="cyan")
            table.add_column("Index", style="green")
            table.add_column("Fields", justify="center")
            table.add_column("Semantic", justify="center")
            table.add_column("Vector", justify="center")
            table.add_column("Docs", justify="right")

            for index in all_indexes:
                semantic = Display.SUCCESS if index.has_semantic_search() else Display.PENDING
                vector = Display.SUCCESS if index.has_vector_search() else Display.PENDING
                docs = str(index.document_count) if index.document_count else "-"

                table.add_row(
                    index.service_name,
                    index.name,
                    str(len(index.fields)),
                    semantic,
                    vector,
                    docs,
                )

            console.print(table)
            console.print(f"\n{Display.SUCCESS} Found {len(all_indexes)} index(es) across {len(services)} service(s).")

            # Show analysis if requested
            if analyze:
                console.print("\n[bold]Index Analysis:[/bold]\n")
                for index in all_indexes:
                    analysis = inventory_service.analyze_index(index)
                    console.print(f"  [cyan]{index.name}[/cyan]:")
                    console.print(f"    Recommended query type: [green]{analysis.recommended_query_type}[/green]")
                    if analysis.recommendations:
                        for rec in analysis.recommendations:
                            console.print(f"    {Display.INFO} {rec}")
                    if analysis.compatibility_issues:
                        for issue in analysis.compatibility_issues:
                            console.print(f"    {Display.WARNING} {issue}")
                    console.print()

    except Exception as e:
        logger.exception("Discovery failed")
        console.print(f"{Display.FAILURE} Discovery failed: {e}")
        raise typer.Exit(1)


@app.command("all")
def all_command(
    subscription_id: Optional[str] = typer.Option(
        None,
        "--subscription",
        "-s",
        help="Azure subscription ID.",
    ),
    resource_group: Optional[str] = typer.Option(
        None,
        "--resource-group",
        "-g",
        help="Filter by resource group.",
    ),
) -> None:
    """
    Run full discovery of OYD configurations and search indexes.

    This combines 'discover aoai' and 'discover indexes' into a single command
    for a complete view of your migration candidates.
    """
    console.print("\n[bold]Full Discovery Report[/bold]\n")
    console.print("=" * 60)

    # Discover AOAI
    console.print("\n[bold cyan]1. Azure OpenAI Deployments with OYD[/bold cyan]\n")
    aoai_command(
        subscription_id=subscription_id,
        resource_group=resource_group,
        output_format="table",
    )

    console.print("\n" + "=" * 60)

    # Discover Indexes
    console.print("\n[bold cyan]2. Azure AI Search Indexes[/bold cyan]\n")
    indexes_command(
        subscription_id=subscription_id,
        service_name=None,
        resource_group=resource_group,
        analyze=True,
        output_format="table",
    )

    console.print("\n" + "=" * 60)
    console.print(f"\n{Display.SUCCESS} Discovery complete!")
    console.print("\nNext steps:")
    console.print("  1. Review the discovered resources above")
    console.print("  2. Run [cyan]oyd-migrator compare[/cyan] to see migration path options")
    console.print("  3. Run [cyan]oyd-migrator wizard[/cyan] to start the migration\n")
