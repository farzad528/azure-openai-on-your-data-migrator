"""Authentication wizard for Azure login."""

from __future__ import annotations

import questionary
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from oyd_migrator.core.config import MigrationState, AzureConfig
from oyd_migrator.core.constants import AuthMethod, Display
from oyd_migrator.core.logging import get_logger

logger = get_logger("wizard.auth")


def run_auth_wizard(state: MigrationState, console: Console) -> MigrationState:
    """
    Run the authentication wizard.

    Guides the user through Azure authentication setup.

    Args:
        state: Current migration state
        console: Rich console for output

    Returns:
        Updated migration state with Azure configuration
    """
    from oyd_migrator.services.auth import AzureAuthService

    console.print("Let's set up Azure authentication.\n")

    # Select authentication method
    auth_method = questionary.select(
        "How would you like to authenticate?",
        choices=[
            questionary.Choice(
                title="Azure CLI (az login) - Recommended for interactive use",
                value=AuthMethod.CLI,
            ),
            questionary.Choice(
                title="Service Principal (client ID + secret)",
                value=AuthMethod.SERVICE_PRINCIPAL,
            ),
            questionary.Choice(
                title="Managed Identity (for Azure-hosted environments)",
                value=AuthMethod.MANAGED_IDENTITY,
            ),
        ],
    ).ask()

    if not auth_method:
        raise KeyboardInterrupt()

    # Collect additional details based on method
    tenant_id = None
    client_id = None
    client_secret = None
    mi_client_id = None

    if auth_method == AuthMethod.SERVICE_PRINCIPAL:
        console.print("\nEnter your service principal details:\n")

        tenant_id = questionary.text(
            "Tenant ID:",
            validate=lambda x: len(x) > 0 or "Tenant ID is required",
        ).ask()

        client_id = questionary.text(
            "Client ID (Application ID):",
            validate=lambda x: len(x) > 0 or "Client ID is required",
        ).ask()

        client_secret = questionary.password(
            "Client Secret:",
            validate=lambda x: len(x) > 0 or "Client Secret is required",
        ).ask()

        if not all([tenant_id, client_id, client_secret]):
            raise KeyboardInterrupt()

    elif auth_method == AuthMethod.MANAGED_IDENTITY:
        use_user_assigned = questionary.confirm(
            "Use user-assigned managed identity?",
            default=False,
        ).ask()

        if use_user_assigned:
            mi_client_id = questionary.text(
                "User-assigned managed identity client ID:",
                validate=lambda x: len(x) > 0 or "Client ID is required",
            ).ask()

            if not mi_client_id:
                raise KeyboardInterrupt()

    # Create auth service and validate
    console.print()
    auth_service = AzureAuthService()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Authenticating with Azure...", total=None)

        try:
            credential = auth_service.authenticate(
                method=auth_method,
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret,
                managed_identity_client_id=mi_client_id,
            )
            progress.update(task, description="Fetching subscriptions...")

            # Get subscriptions
            subscriptions = auth_service.list_subscriptions(credential)
            progress.update(task, completed=True)

        except Exception as e:
            progress.update(task, completed=True)
            console.print(f"\n{Display.FAILURE} Authentication failed: {e}")
            raise

    if not subscriptions:
        console.print(f"\n{Display.FAILURE} No subscriptions found for this account.")
        raise ValueError("No subscriptions available")

    console.print(f"\n{Display.SUCCESS} Authentication successful!\n")

    # Select subscription
    if len(subscriptions) == 1:
        selected_sub = subscriptions[0]
        console.print(f"Using subscription: [cyan]{selected_sub.display_name}[/cyan] ({selected_sub.subscription_id})\n")
    else:
        sub_choices = [
            questionary.Choice(
                title=f"{sub.display_name} ({sub.subscription_id})",
                value=sub,
            )
            for sub in subscriptions
        ]

        selected_sub = questionary.select(
            "Select the Azure subscription to use:",
            choices=sub_choices,
        ).ask()

        if not selected_sub:
            raise KeyboardInterrupt()

    # Validate permissions
    console.print()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Checking permissions...", total=None)

        permission_result = auth_service.check_permissions(
            credential=credential,
            subscription_id=selected_sub.subscription_id,
        )
        progress.update(task, completed=True)

    if permission_result.has_warnings:
        console.print(f"\n{Display.WARNING} Permission warnings:\n")
        for warning in permission_result.warnings:
            console.print(f"  {Display.WARNING} {warning}")
        console.print()

        proceed = questionary.confirm(
            "Continue with limited permissions?",
            default=True,
        ).ask()

        if not proceed:
            raise KeyboardInterrupt()
    else:
        console.print(f"\n{Display.SUCCESS} Permissions validated.\n")

    # Save configuration to state
    state.azure_config = AzureConfig(
        subscription_id=selected_sub.subscription_id,
        tenant_id=tenant_id or selected_sub.tenant_id,
        auth_method=auth_method,
        client_id=client_id,
        client_secret=client_secret,
        managed_identity_client_id=mi_client_id,
    )

    return state
