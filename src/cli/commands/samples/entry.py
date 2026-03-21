"""Developer SDK demonstration commands."""

from __future__ import annotations

import click

from cli.utils.metadata import Metadata

GROUP_HELP = f"Developer SDK demonstrations for {Metadata.APP_NAME}."


@click.group(help=GROUP_HELP)
def cli() -> None:
    """Developer SDK demonstrations."""
