#!/usr/bin/env python3
"""Filter commands for packaging based on meta.yaml 'packaged' field.

This script identifies commands/subcommands that should be excluded from
the package build based on their meta.yaml configuration.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import yaml

# Minimum number of required command-line arguments (script name + action)
MIN_REQUIRED_ARGS = 2


def load_meta(meta_path: Path) -> dict:
    """Load and parse a meta.yaml file."""
    try:
        with meta_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except Exception as exc:  # noqa: BLE001
        print(f"Warning: Failed to load {meta_path}: {exc}", file=sys.stderr)
        return {}


def should_package(meta_path: Path) -> bool:
    """Determine if a command/subcommand should be packaged.

    Returns True if 'packaged: true', False otherwise (default is False).
    """
    meta = load_meta(meta_path)
    return meta.get("packaged", False) is True


def find_commands_to_exclude(commands_dir: Path) -> list[Path]:
    """Find all command directories that should be excluded from packaging."""
    if not commands_dir.exists():
        return []

    excluded: list[Path] = []

    # Scan all subdirectories in commands/
    for command_dir in sorted(commands_dir.iterdir()):
        if not command_dir.is_dir():
            continue
        if command_dir.name.startswith(".") or command_dir.name.startswith("__"):
            continue

        # Check if command group has meta.yaml
        command_meta = command_dir / "meta.yaml"
        if command_meta.exists() and not should_package(command_meta):
            # Entire command group should be excluded
            excluded.append(command_dir)
            continue

        # Check nested subcommands recursively
        excluded.extend(scan_subcommands(command_dir))

    return excluded


def scan_subcommands(parent_dir: Path, max_depth: int = 5, current_depth: int = 0) -> list[Path]:
    """Recursively scan for subcommands to exclude."""
    if current_depth >= max_depth:
        return []

    excluded: list[Path] = []

    for sub_dir in sorted(parent_dir.iterdir()):
        if not sub_dir.is_dir():
            continue
        if sub_dir.name.startswith(".") or sub_dir.name.startswith("__"):
            continue

        # Check if this subcommand has entry.py and meta.yaml
        entry_path = sub_dir / "entry.py"
        meta_path = sub_dir / "meta.yaml"

        if entry_path.exists() and meta_path.exists() and not should_package(meta_path):
            # This is a subcommand that should be excluded
            excluded.append(sub_dir)
            continue

        if entry_path.exists() and meta_path.exists():
            # Check nested subcommands for packaged subcommands
            excluded.extend(scan_subcommands(sub_dir, max_depth, current_depth + 1))

    return excluded


def create_backup_dir(commands_dir: Path) -> Path:
    """Create a backup directory for excluded commands."""
    backup_dir = commands_dir.parent.parent / ".build_excluded"
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def move_excluded_commands(commands_dir: Path, excluded: list[Path], backup_dir: Path) -> None:
    """Move excluded commands to backup directory."""
    commands_backup = backup_dir / "commands"
    commands_backup.mkdir(parents=True, exist_ok=True)

    for excluded_path in excluded:
        relative_path = excluded_path.relative_to(commands_dir)
        backup_path = commands_backup / relative_path
        backup_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"Excluding from build: {relative_path}")
        shutil.move(str(excluded_path), str(backup_path))


def restore_excluded_commands(commands_dir: Path, backup_dir: Path) -> None:
    """Restore excluded commands from backup directory."""
    commands_backup = backup_dir / "commands"

    if not commands_backup.exists():
        return

    # Move each top-level directory back
    for backup_subdir in commands_backup.iterdir():
        if not backup_subdir.is_dir():
            continue

        target_path = commands_dir / backup_subdir.name

        # If target already exists, remove it first
        if target_path.exists():
            shutil.rmtree(target_path)

        # Move the backup directory back
        shutil.move(str(backup_subdir), str(target_path))
        print(f"Restored: {backup_subdir.name}")

    # Clean up backup directory
    shutil.rmtree(backup_dir, ignore_errors=True)


def main() -> int:
    """Main entry point."""
    if len(sys.argv) < MIN_REQUIRED_ARGS:
        print("Usage: filter_commands.py <prepare|restore>", file=sys.stderr)
        return 1

    action = sys.argv[1]

    # Find the src/your_cli/commands directory
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    commands_dir = project_root / "src" / "your_cli" / "commands"
    backup_dir = project_root / ".build_excluded"

    if action == "prepare":
        print("Preparing build: excluding non-packaged commands...")
        excluded = find_commands_to_exclude(commands_dir)

        if not excluded:
            print("No commands to exclude (all are packaged or none exist)")
            return 0

        move_excluded_commands(commands_dir, excluded, backup_dir)
        print(f"Excluded {len(excluded)} command(s) from build")
        return 0

    elif action == "restore":
        print("Restoring excluded commands...")
        restore_excluded_commands(commands_dir, backup_dir)
        print("Restore complete")
        return 0

    else:
        print(f"Unknown action: {action}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
