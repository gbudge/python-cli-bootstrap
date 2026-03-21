"""Administrative command group."""

from __future__ import annotations

import click

from cli.utils.metadata import Metadata

GROUP_HELP = f"Developer utilities for {Metadata.APP_NAME}"


@click.group(help=GROUP_HELP)
def cli() -> None:
    """Developer utilities."""
