"""Create a new command plugin skeleton."""

from __future__ import annotations

import os
import re
from pathlib import Path

import click

VALID_NAME = re.compile(r"^[A-Za-z0-9_-]+$")

CLI_NAME = "yourcli"


@click.command()
@click.argument("command")
@click.argument("subcommand", required=False)
@click.option(
    "--command-short-help",
    default=None,
    help=f"Short help for the command group (shown under `{CLI_NAME} --help`).",
)
@click.option(
    "--subcommand-short-help",
    default=None,
    help=f"Short help for the subcommand (shown under `{CLI_NAME} <command> --help`). Not required when no subcommand is created.",
)
@click.option("--short-help", default=None, hidden=True)
@click.option("--force", is_flag=True, help="Overwrite existing files.")
def cli(  # noqa: PLR0915
    command: str,
    subcommand: str | None,
    force: bool,
    **kwargs: str | None,
) -> None:
    """Create a new command plugin skeleton."""

    # Extract help options from kwargs
    command_short_help = kwargs.get("command_short_help")
    subcommand_short_help = kwargs.get("subcommand_short_help")
    short_help = kwargs.get("short_help")

    # Backwards compatible: old --short-help applied to subcommand.
    if short_help and not subcommand_short_help:
        subcommand_short_help = short_help

    # Validate command name
    if not VALID_NAME.match(command):
        _abort(f"Invalid command '{command}'. Use only letters, numbers, underscore, and hyphen.")

    commands_dir = _commands_dir()
    command_dir = commands_dir / command

    # If no subcommand, create a standalone command
    if subcommand is None:
        # Validate we have the necessary help text
        if command_short_help is None:
            _abort("--command-short-help is required when creating a standalone command (no subcommand).")

        try:
            resolved_command_dir = command_dir.resolve()
            resolved_root = commands_dir.resolve()
            resolved_command_dir.relative_to(resolved_root)
        except Exception:  # noqa: BLE001
            _abort("Target path must be within commands directory.")

        entry_path = command_dir / "entry.py"
        meta_path = command_dir / "meta.yaml"

        if not force and (entry_path.exists() or meta_path.exists()):
            _abort("Command already exists. Use --force to overwrite existing entry.py/meta.yaml.")

        command_dir.mkdir(parents=True, exist_ok=True)

        help_text = command_short_help
        meta_content = f"HelpSummary: {help_text}\nhidden: false\nenabled: true\nHelpGroup: Commands\npackaged: true\n"
        entry_content = (
            'import click\n\n@click.command()\ndef cli():\n    click.echo("not implemented")\n    raise SystemExit(2)\n'
        )

        meta_path.write_text(meta_content, encoding="utf-8")
        entry_path.write_text(entry_content, encoding="utf-8")

        click.echo(str(meta_path))
        click.echo(str(entry_path))
        return

    # Validate subcommand name
    if not VALID_NAME.match(subcommand):
        _abort(f"Invalid subcommand '{subcommand}'. Use only letters, numbers, underscore, and hyphen.")

    target_dir = command_dir / subcommand
    try:
        resolved_target = target_dir.resolve()
        resolved_root = commands_dir.resolve()
        resolved_target.relative_to(resolved_root)
    except Exception:  # noqa: BLE001
        _abort("Target path must be within commands directory.")

    entry_path = target_dir / "entry.py"
    meta_path = target_dir / "meta.yaml"
    group_meta_path = command_dir / "meta.yaml"

    if not force and (entry_path.exists() or meta_path.exists() or group_meta_path.exists()):
        _abort("Plugin already exists. Use --force to overwrite existing entry.py/meta.yaml and command meta.yaml.")

    target_dir.mkdir(parents=True, exist_ok=True)

    group_help_text = command_short_help or f"TODO: describe {command}."
    sub_help_text = subcommand_short_help or f"TODO: describe {command} {subcommand}."

    group_meta_content = (
        f"HelpSummary: {group_help_text}\nhidden: false\nenabled: true\nHelpGroup: Commands\npackaged: true\n"
    )
    meta_content = f"HelpSummary: {sub_help_text}\nhidden: false\nenabled: true\nHelpGroup: Commands\npackaged: true\n"
    entry_content = (
        'import click\n\n@click.command()\ndef cli():\n    click.echo("not implemented")\n    raise SystemExit(2)\n'
    )

    group_meta_path.parent.mkdir(parents=True, exist_ok=True)
    group_meta_path.write_text(group_meta_content, encoding="utf-8")
    meta_path.write_text(meta_content, encoding="utf-8")
    entry_path.write_text(entry_content, encoding="utf-8")

    click.echo(str(group_meta_path))
    click.echo(str(meta_path))
    click.echo(str(entry_path))


def _commands_dir() -> Path:
    override = os.environ.get("YOUR_CLI_COMMANDS_DIR")
    if override:
        return Path(override)
    # __file__ is: .../commands/admin/new_command/entry.py
    # parent = .../commands/admin/new_command/
    # parent.parent = .../commands/admin/
    # parent.parent.parent = .../commands/
    return Path(__file__).resolve().parent.parent.parent


def _abort(message: str) -> None:
    click.echo(message, err=True)
    raise SystemExit(2)
