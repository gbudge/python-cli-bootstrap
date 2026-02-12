"""Developer utilities."""

from __future__ import annotations

import re

import click

from your_cli.utils.metadata import Metadata

VALID_NAME = re.compile(r"^[A-Za-z0-9_-]+$")


@click.group()
def cli() -> None:
    """Developer utilities."""


@cli.command("new-plugin")
@click.argument("command")
@click.argument("subcommand")
@click.option("--short-help", "short_help", default=None, help="Short help text.")
@click.option("--force", is_flag=True, help="Overwrite existing files.")
def new_plugin(command: str, subcommand: str, short_help: str | None, force: bool) -> None:
    """Create a new plugin skeleton."""
    for token_name, token in [("command", command), ("subcommand", subcommand)]:
        if not VALID_NAME.match(token):
            _abort(f"Invalid {token_name} '{token}'. Use only letters, numbers, underscore, and hyphen.")
    commands_dir = Metadata.COMMANDS_DIR
    target_dir = commands_dir / command / subcommand
    try:
        resolved_target = target_dir.resolve()
        resolved_root = commands_dir.resolve()
        resolved_target.relative_to(resolved_root)
    except Exception:  # noqa: BLE001
        _abort("Target path must be within commands directory.")

    entry_path = target_dir / "entry.py"
    meta_path = target_dir / "meta.yaml"
    if not force and (entry_path.exists() or meta_path.exists()):
        _abort("Plugin already exists. Use --force to overwrite existing entry.py and meta.yaml.")

    target_dir.mkdir(parents=True, exist_ok=True)
    help_text = short_help or f"TODO: describe {command} {subcommand}."

    meta_content = f"shortHelp: {help_text}\n"
    entry_content = (
        'import click\n\n@click.command()\ndef cli():\n    click.echo("not implemented")\n    raise SystemExit(2)\n'
    )
    meta_path.write_text(meta_content, encoding="utf-8")
    entry_path.write_text(entry_content, encoding="utf-8")

    click.echo(str(meta_path))
    click.echo(str(entry_path))


def _abort(message: str) -> None:
    click.echo(message, err=True)
    raise SystemExit(2)
