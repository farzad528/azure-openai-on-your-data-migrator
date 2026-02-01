"""Logging configuration for the OYD Foundry Migrator."""

import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

from oyd_migrator.core.config import get_settings


def setup_logging(
    level: str | None = None,
    log_file: Path | None = None,
    verbose: bool = False,
) -> logging.Logger:
    """
    Configure logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR). Defaults to settings.
        log_file: Optional file path for logging output.
        verbose: Enable verbose (DEBUG) output regardless of level setting.

    Returns:
        Configured logger instance.
    """
    settings = get_settings()

    # Determine log level
    if verbose:
        log_level = logging.DEBUG
    elif level:
        log_level = getattr(logging, level.upper())
    else:
        log_level = getattr(logging, settings.log_level)

    # Create logger
    logger = logging.getLogger("oyd_migrator")
    logger.setLevel(log_level)
    logger.handlers.clear()

    # Console handler with Rich formatting
    console = Console(stderr=True, force_terminal=not settings.no_color)
    rich_handler = RichHandler(
        console=console,
        show_time=verbose,
        show_path=verbose,
        rich_tracebacks=True,
        tracebacks_show_locals=verbose,
        markup=True,
    )
    rich_handler.setLevel(log_level)
    rich_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(rich_handler)

    # File handler if specified
    file_path = log_file or settings.log_file
    if file_path:
        file_handler = logging.FileHandler(file_path, encoding="utf-8")
        file_handler.setLevel(log_level)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(file_handler)

    # Reduce noise from Azure SDK loggers
    azure_loggers = [
        "azure.core.pipeline.policies.http_logging_policy",
        "azure.identity",
        "azure.mgmt",
        "urllib3",
        "httpx",
    ]
    for azure_logger in azure_loggers:
        logging.getLogger(azure_logger).setLevel(logging.WARNING)

    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Optional logger name. If None, returns the root app logger.

    Returns:
        Logger instance.
    """
    if name:
        return logging.getLogger(f"oyd_migrator.{name}")
    return logging.getLogger("oyd_migrator")
