"""Entry point for YourCLI."""

from __future__ import annotations

from dotenv import load_dotenv

from your_cli.loader import RootCommand
from your_cli.utils.metadata import Metadata


def main() -> None:
    """
    Docstring for main
    """
    #
    # Create application context with metadata and configuration.
    # The context is passed to commmands for access to common metadata.
    #
    app_context = {
        "PACKAGE_ROOT_DIR": Metadata.PACKAGE_ROOT_DIR,  # Path to package root
        "COMMANDS_DIR": Metadata.COMMANDS_DIR,  # Path to commands directory
        "PACKAGE_NAME": Metadata.PACKAGE_NAME,  # pip package name (kebab-case)
        "APP_NAME": Metadata.APP_NAME,  # Branded application name
        "COMMAND_NAME": Metadata.COMMAND_NAME,  # CLI command name
        "VERSION": Metadata.VERSION,  # Package version
        # Add any runtime configuration here
    }

    #
    # Load environment variables from .env file (if present).
    # Commands can load their own .env file (if needed).
    #
    load_dotenv()

    #
    # Initialize and run the CLI
    #
    commands_dir = Metadata.COMMANDS_DIR
    cli = RootCommand(commands_dir, app_context=app_context)
    cli(prog_name=Metadata.COMMAND_NAME)


if __name__ == "__main__":
    main()
