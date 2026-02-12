"""
Metadata and constants for the application.

Not fully used yet.
"""

from __future__ import annotations

import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import click


class Metadata:
    """Centralized metadata and constants for the application."""

    # Core identifiers
    PACKAGE_NAME = "your-cli"  # pip package name (kebab-case)
    APP_NAME = "YourCLI"  # Branded display name
    COMMAND_NAME = "yourcli"  # CLI command (lowercase, no spaces)

    # Derived at runtime
    try:
        VERSION = version(PACKAGE_NAME)
    except PackageNotFoundError:
        # Raise a click exception. Something is wrong.
        raise click.ClickException(f"Package '{PACKAGE_NAME}' not found. Ensure it is installed correctly.") from None

    # Paths
    PACKAGE_ROOT_DIR = Path(__file__).resolve().parent.parent
    COMMANDS_DIR = PACKAGE_ROOT_DIR / "commands"

    # Runtime
    PYTHON_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    IS_TTY = sys.stdout.isatty()

    @classmethod
    def banner(cls) -> str:
        """Generate application banner."""
        return f"{cls.APP_NAME} v{cls.VERSION}"

    @classmethod
    def full_version(cls) -> str:
        """Detailed version information."""
        return f"{cls.APP_NAME} {cls.VERSION}\nPython {cls.PYTHON_VERSION}\nPackage: {cls.PACKAGE_NAME}"
