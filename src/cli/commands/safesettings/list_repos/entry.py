"""List SafeSettings repository files."""

from __future__ import annotations

from pathlib import Path

import click


def _repos_dir(ss_root: Path) -> Path:
    return ss_root / ".github" / "repos"


@click.command()
@click.option("--prefix", default="", help="Only list repositories with this prefix.")
@click.option("--page-size", type=click.IntRange(min=1), default=50, show_default=True, help="Max results to show.")
@click.option("--no-paginate", is_flag=True, help="List all matching repositories.")
@click.option(
    "--ss-root",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    default=Path.cwd,
    show_default="current working directory",
    help="SafeSettings root directory.",
)
def cli(prefix: str, page_size: int, no_paginate: bool, ss_root: Path) -> None:
    """List repo files from <ss-root>/.github/repos."""
    repos_dir = _repos_dir(ss_root)
    if not repos_dir.exists():
        click.echo("No repositories found.")
        return

    repo_names = sorted(path.stem for path in repos_dir.glob("*.yaml"))
    if prefix:
        repo_names = [name for name in repo_names if name.startswith(prefix)]

    if not repo_names:
        click.echo("No repositories found.")
        return

    visible_names = repo_names if no_paginate else repo_names[:page_size]
    for repo_name in visible_names:
        click.echo(repo_name)

    if not no_paginate and len(repo_names) > page_size:
        click.echo(f"Showing {page_size} of {len(repo_names)} repositories. Use --no-paginate to list all.")
