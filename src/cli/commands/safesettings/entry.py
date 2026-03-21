"""Safe settings image commands."""

from __future__ import annotations

import click


@click.group()
def cli() -> None:
    """Manage safe settings repository files."""
