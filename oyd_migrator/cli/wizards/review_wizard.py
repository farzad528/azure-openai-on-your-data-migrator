"""Review and execution wizard."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from oyd_migrator.core.config import MigrationState
from oyd_migrator.core.constants import Display, MigrationPath
from oyd_migrator.core.logging import get_logger
from oyd_migrator.models.migration import MigrationResult, TestResult

logger = get_logger("wizard.review")


def run_review_wizard(state: MigrationState, console: Console) -> MigrationResult:
    """
    Run the review and execution wizard.

    Reviews the migration plan and executes it.

    Args:
        state: Current migration state
        console: Rich console for output

    Returns:
        Migration result
    """
    from oyd_migrator.services.auth import AzureAuthService
    from oyd_migrator.services.connection_manager import ConnectionManagerService
    from oyd_migrator.services.agent_builder import AgentBuilderService
    from oyd_migrator.services.test_runner import AgentTestRunner

    start_time = datetime.now(timezone.utc)

    # Display migration plan
    console.print("[bold]Migration Plan Review:[/bold]\n")

    _display_plan(state, console)

    # Confirm execution
    console.print()
    proceed = questionary.confirm(
        "Ready to execute this migration?",
        default=True,
    ).ask()

    if not proceed:
        console.print(f"\n{Display.INFO} Migration cancelled.")
        raise KeyboardInterrupt()

    # Initialize result
    result = MigrationResult(
        result_id=str(uuid.uuid4())[:8],
        migration_path=state.migration_options.migration_path,
        plan_id=state.session_id,
    )

    # Get credential
    auth_service = AzureAuthService()
    credential = auth_service.get_credential_from_config(state.azure_config)

    console.print("\n[bold]Executing Migration...[/bold]\n")

    try:
        # Step 1: Create project if needed
        if state.migration_options.create_new_project:
            console.print(f"{Display.IN_PROGRESS} Creating Foundry project...")

            from oyd_migrator.services.foundry_provisioner import FoundryProvisionerService

            provisioner = FoundryProvisionerService(
                credential=credential,
                subscription_id=state.azure_config.subscription_id,
            )

            # Pass hub_resource_id and location if configured
            project = provisioner.create_project(
                name=state.foundry_config.project_name,
                resource_group=state.foundry_config.resource_group,
                location=getattr(state.foundry_config, 'location', None),
                hub_resource_id=getattr(state.foundry_config, 'hub_resource_id', None),
            )
            state.foundry_config.project_endpoint = project.endpoint
            console.print(f"{Display.SUCCESS} Project created: {project.name}\n")

        # Step 2: Create connections
        console.print(f"{Display.IN_PROGRESS} Creating project connections...")

        connection_manager = ConnectionManagerService(
            credential=credential,
            project_endpoint=state.foundry_config.project_endpoint,
            subscription_id=state.azure_config.subscription_id,
            resource_group=state.foundry_config.resource_group,
        )

        connections_created = []
        for search_config in state.search_configs:
            connection = connection_manager.create_search_connection(
                name=f"{search_config.service_name}-connection",
                endpoint=search_config.endpoint,
                api_key=search_config.api_key,
                use_managed_identity=search_config.use_managed_identity,
            )
            connections_created.append(connection)
            state.created_connections.append(connection.name)

        result.connections_created = connections_created
        console.print(f"{Display.SUCCESS} Created {len(connections_created)} connection(s)")

        # Wait for connection propagation from ARM to data-plane
        import time
        console.print(f"{Display.INFO} Waiting for connection propagation (15s)...")
        time.sleep(15)
        console.print()

        # Step 3: Create agents
        console.print(f"{Display.IN_PROGRESS} Creating agents...")

        agent_builder = AgentBuilderService(
            credential=credential,
            project_endpoint=state.foundry_config.project_endpoint,
        )

        agents_created = []
        for aoai_config in state.aoai_configs:
            # Determine agent name
            agent_name = f"{aoai_config.deployment_name}-migrated"

            # Build instructions
            instructions = _build_instructions(aoai_config, state)

            # Create agent based on migration path
            if state.migration_options.migration_path == MigrationPath.SEARCH_TOOL:
                # Get index name from search configs if available
                idx_name = None
                if state.search_configs:
                    idx_name = state.search_configs[0].index_name

                agent = agent_builder.create_search_tool_agent(
                    name=agent_name,
                    model=state.foundry_config.model_deployment,
                    instructions=instructions,
                    search_connections=connections_created,
                    index_name=idx_name,
                )
            else:
                agent = agent_builder.create_knowledge_base_agent(
                    name=agent_name,
                    model=state.foundry_config.model_deployment,
                    instructions=instructions,
                    search_connections=connections_created,
                )

            agents_created.append(agent)
            state.created_agents.append(agent.name)

        result.agents_created = agents_created
        console.print(f"{Display.SUCCESS} Created {len(agents_created)} agent(s)\n")

        # Step 4: Run tests if enabled
        if state.migration_options.test_after_migration:
            console.print(f"{Display.IN_PROGRESS} Running validation tests...\n")

            test_runner = AgentTestRunner(
                credential=credential,
                project_endpoint=state.foundry_config.project_endpoint,
            )

            test_results = []
            for agent in agents_created:
                # Run default test queries
                test_queries = [
                    "What information do you have available?",
                    "Can you provide a brief summary of the main topics?",
                ]

                # Use agent_id if available (the API needs the ID, not the name)
                agent_ref = agent.agent_id or agent.name

                for query in test_queries:
                    test_result = test_runner.test_agent(agent_ref, query)
                    test_results.append(test_result)
                    state.test_results[f"{agent.name}:{query[:20]}"] = test_result.success

                    status = Display.SUCCESS if test_result.success else Display.FAILURE
                    console.print(f"  {status} {agent.name}: {query[:40]}...")

            result.test_results = test_results
            console.print()

        # Step 5: Generate samples if enabled
        if state.migration_options.generate_samples:
            console.print(f"{Display.IN_PROGRESS} Generating code samples...")

            from oyd_migrator.generators.sdk_samples import generate_python_sample

            for agent in agents_created:
                sample = generate_python_sample(
                    agent_name=agent.name,
                    project_endpoint=state.foundry_config.project_endpoint,
                )
                result.artifacts[f"{agent.name}_sample.py"] = "python"

            console.print(f"{Display.SUCCESS} Generated {len(agents_created)} sample(s)\n")

        # Calculate duration
        end_time = datetime.now(timezone.utc)
        result.duration_seconds = (end_time - start_time).total_seconds()
        result.success = True

    except Exception as e:
        logger.exception("Migration failed")
        result.errors.append(str(e))
        result.success = False

    return result


def _display_plan(state: MigrationState, console: Console) -> None:
    """Display the migration plan summary."""
    # Source deployments
    console.print("[cyan]Source (OYD Deployments):[/cyan]")
    for config in state.aoai_configs:
        console.print(f"  • {config.resource_name}/{config.deployment_name}")

    # Search services
    console.print(f"\n[cyan]Connected Search Services:[/cyan]")
    for config in state.search_configs:
        console.print(f"  • {config.service_name}")

    # Target configuration
    console.print(f"\n[cyan]Target (Foundry):[/cyan]")
    console.print(f"  • Project: {state.foundry_config.project_name}")
    console.print(f"  • Model: {state.foundry_config.model_deployment}")
    console.print(f"  • Architecture: {state.migration_options.migration_path.value}")

    # Actions to be taken
    console.print(f"\n[cyan]Actions:[/cyan]")
    if state.migration_options.create_new_project:
        console.print(f"  1. {Display.PENDING} Create Foundry project")
    console.print(f"  {'1' if not state.migration_options.create_new_project else '2'}. {Display.PENDING} Create {len(state.search_configs)} connection(s)")
    console.print(f"  {'2' if not state.migration_options.create_new_project else '3'}. {Display.PENDING} Create {len(state.aoai_configs)} agent(s)")
    if state.migration_options.test_after_migration:
        console.print(f"  {'3' if not state.migration_options.create_new_project else '4'}. {Display.PENDING} Run validation tests")
    if state.migration_options.generate_samples:
        console.print(f"  {'4' if not state.migration_options.create_new_project else '5'}. {Display.PENDING} Generate code samples")


def _build_instructions(aoai_config, state: MigrationState) -> str:
    """Build agent instructions from OYD configuration."""
    base_instructions = f"""You are a helpful assistant that answers questions using the connected data sources.

When answering questions:
1. Always use the available tools to search for relevant information
2. Cite your sources in your responses
3. If you cannot find relevant information, say so clearly
"""

    if state.migration_options.migrate_system_message:
        # TODO: Extract role_information from OYD config and merge
        pass

    return base_instructions
