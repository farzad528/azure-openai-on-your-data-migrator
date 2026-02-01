"""Interactive wizard modules for the migration CLI."""

from oyd_migrator.cli.wizards.auth_wizard import run_auth_wizard
from oyd_migrator.cli.wizards.discovery_wizard import run_discovery_wizard
from oyd_migrator.cli.wizards.migration_wizard import run_migration_wizard
from oyd_migrator.cli.wizards.review_wizard import run_review_wizard

__all__ = [
    "run_auth_wizard",
    "run_discovery_wizard",
    "run_migration_wizard",
    "run_review_wizard",
]
