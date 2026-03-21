"""Remove a SafeSettings repository file."""

from __future__ import annotations

import re
from pathlib import Path

import click

VALID_REPO_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


def _repo_file(ss_root: Path, repo_name: str) -> Path:
    return ss_root / ".github" / "repos" / f"{repo_name}.yaml"


@click.command()
@click.option("--repo", "repo_name", required=True, help="Repository name.")
@click.option("--dry-run", is_flag=True, help="Print the action without deleting files.")
@click.option("--force", is_flag=True, help="Delete the repo file.")
@click.option(
    "--ss-root",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True, writable=True),
    default=Path.cwd,
    show_default="current working directory",
    help="SafeSettings root directory.",
)
def cli(repo_name: str, dry_run: bool, force: bool, ss_root: Path) -> None:
    """Delete a repo file from <ss-root>/.github/repos/<repo>.yaml."""
    if not VALID_REPO_NAME.fullmatch(repo_name):
        raise click.BadParameter(
            "Repository name must contain only letters, numbers, dot, underscore, and hyphen.",
            param_hint="--repo",
        )

    target = _repo_file(ss_root, repo_name)
    if not target.exists():
        raise click.ClickException(f"Repo file does not exist: {target}")

    if dry_run:
        click.echo(f"Would remove {target}")
        return

    if not force:
        raise click.UsageError("Pass --force to remove the repo file.")

    target.unlink()
    click.echo(str(target))
