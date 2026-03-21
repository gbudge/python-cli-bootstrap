"""Create a SafeSettings repository file."""

from __future__ import annotations

import re
from pathlib import Path

import click
import yaml

VALID_REPO_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


def _repo_file(ss_root: Path, repo_name: str) -> Path:
    return ss_root / ".github" / "repos" / f"{repo_name}.yaml"


@click.command()
@click.option("--repo", "repo_name", required=True, help="Repository name.")
@click.option("--policy", required=True, help="Policy name to write into the repo file.")
@click.option("--dry-run", is_flag=True, help="Print the action without writing files.")
@click.option("--force", is_flag=True, help="Overwrite an existing repo file.")
@click.option(
    "--ss-root",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True, writable=True),
    default=Path.cwd,
    show_default="current working directory",
    help="SafeSettings root directory.",
)
def cli(
    repo_name: str,
    policy: str,
    dry_run: bool,
    force: bool,
    ss_root: Path,
) -> None:
    """Create a repo file at <ss-root>/.github/repos/<repo>.yaml."""
    if not VALID_REPO_NAME.fullmatch(repo_name):
        raise click.BadParameter(
            "Repository name must contain only letters, numbers, dot, underscore, and hyphen.",
            param_hint="--repo",
        )

    target = _repo_file(ss_root, repo_name)
    if target.exists() and not force:
        raise click.ClickException(f"Repo file already exists: {target}. Use --force to overwrite it.")

    payload = {"repo": repo_name, "policy": policy}
    rendered = yaml.safe_dump(payload, sort_keys=False)

    if dry_run:
        click.echo(f"Would write {target}")
        click.echo(rendered.rstrip())
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered, encoding="utf-8")
    click.echo(str(target))
