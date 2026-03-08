"""Create a new command plugin skeleton."""

from __future__ import annotations

import os
import re
from pathlib import Path

import click

VALID_NAME = re.compile(r"^[A-Za-z0-9_-]+$")

CLI_NAME = "yourcli"
META_TEMPLATE_TOKEN = "{{SHORT_HELP}}"
COMMAND_TEMPLATE_TOKEN = "{{COMMAND_NAME}}"


@click.command()
@click.argument("command")
@click.option(
    "--parent",
    default=None,
    help=(
        "Optional parent command path in dot notation "
        f"(for example: github.repo, creating `{CLI_NAME} github repo <command>`)."
    ),
)
@click.option("--short-help", required=True, help="Short help text for the new command.")
@click.option("--force", is_flag=True, help="Overwrite existing files.")
def cli(
    command: str,
    parent: str | None,
    short_help: str,
    force: bool,
) -> None:
    """Create a new command plugin skeleton."""
    _validate_token("command", command)
    parent_parts = _parse_parent(parent)
    command_path = parent_parts + [command]
    commands_dir = _commands_dir()
    target_dir = commands_dir.joinpath(*command_path)
    _assert_within_commands_dir(commands_dir, target_dir)

    entry_path = target_dir / "entry.py"
    meta_path = target_dir / "meta.yaml"
    if not force and (entry_path.exists() or meta_path.exists()):
        _abort("Command already exists. Use --force to overwrite existing entry.py/meta.yaml.")

    written_paths = _ensure_parent_groups(commands_dir, parent_parts)

    target_dir.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(_new_command_meta_content(short_help, command), encoding="utf-8")
    entry_path.write_text(_new_command_entry_content(command), encoding="utf-8")
    written_paths.extend([meta_path, entry_path])

    for path in written_paths:
        click.echo(str(path))


def _parse_parent(parent: str | None) -> list[str]:
    if parent is None:
        return []
    parent_value = parent.strip()
    if not parent_value:
        _abort("Invalid --parent ''. Use dot notation tokens with letters, numbers, underscore, and hyphen.")

    tokens = parent_value.split(".")
    if any(token == "" for token in tokens):
        _abort(
            f"Invalid --parent '{parent}'. Use dot notation tokens with letters, numbers, underscore, and hyphen."
        )

    for token in tokens:
        _validate_token("parent segment", token)
    return tokens


def _validate_token(token_name: str, token: str) -> None:
    if not VALID_NAME.match(token):
        _abort(f"Invalid {token_name} '{token}'. Use only letters, numbers, underscore, and hyphen.")


def _assert_within_commands_dir(commands_dir: Path, target_dir: Path) -> None:
    try:
        resolved_target = target_dir.resolve()
        resolved_root = commands_dir.resolve()
        resolved_target.relative_to(resolved_root)
    except Exception:  # noqa: BLE001
        _abort("Target path must be within commands directory.")


def _ensure_parent_groups(commands_dir: Path, parent_parts: list[str]) -> list[Path]:
    written_paths: list[Path] = []
    for index in range(len(parent_parts)):
        group_parts = parent_parts[: index + 1]
        group_dir = commands_dir.joinpath(*group_parts)
        _assert_within_commands_dir(commands_dir, group_dir)
        group_dir.mkdir(parents=True, exist_ok=True)

        group_meta_path = group_dir / "meta.yaml"
        if not group_meta_path.exists():
            help_text = f"TODO: describe {' '.join(group_parts)}."
            group_meta_path.write_text(_meta_content(help_text), encoding="utf-8")
            written_paths.append(group_meta_path)

        group_entry_path = group_dir / "entry.py"
        if not group_entry_path.exists():
            group_entry_path.write_text(_group_entry_content(), encoding="utf-8")
            written_paths.append(group_entry_path)
        elif _upgrade_scaffold_command_to_group(group_entry_path):
            written_paths.append(group_entry_path)
    return written_paths


def _meta_content(help_text: str) -> str:
    return (
        f"short_help: {help_text}\n"
        "hidden: false\n"
        "enabled: true\n"
        "help_group: Commands\n"
        "packaged: true\n"
        "no_args_is_help: false\n"
    )


def _new_command_meta_content(short_help: str, command_name: str) -> str:
    content = _load_template_file("meta.yaml")
    if META_TEMPLATE_TOKEN not in content:
        _abort(
            "Template meta.yaml must include '{{SHORT_HELP}}' placeholder for --short-help."
        )
    return _replace_command_template_tokens(content.replace(META_TEMPLATE_TOKEN, short_help), command_name)


def _new_command_entry_content(command_name: str) -> str:
    return _replace_command_template_tokens(_load_template_file("entry.py"), command_name)


def _replace_command_template_tokens(content: str, command_name: str) -> str:
    return content.replace(COMMAND_TEMPLATE_TOKEN, command_name)


def _load_template_file(filename: str) -> str:
    template_path = _template_dir() / filename
    if not template_path.is_file():
        _abort(f"Missing required template file: {template_path}")
    return template_path.read_text(encoding="utf-8")


def _template_dir() -> Path:
    return Path(__file__).resolve().parent / ".template"


def _legacy_command_entry_content() -> str:
    return 'import click\n\n@click.command()\ndef cli():\n    click.echo("not implemented")\n    raise SystemExit(2)\n'


def _group_entry_content() -> str:
    return 'import click\n\n@click.group()\ndef cli():\n    """Group command."""\n'


def _upgrade_scaffold_command_to_group(entry_path: Path) -> bool:
    current_text = entry_path.read_text(encoding="utf-8")
    scaffold_content = _new_command_entry_content(entry_path.parent.name)
    if current_text not in {scaffold_content, _legacy_command_entry_content()}:
        return False
    entry_path.write_text(_group_entry_content(), encoding="utf-8")
    return True


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
