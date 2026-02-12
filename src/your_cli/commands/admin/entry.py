"""Developer utilities for YourCLI"""

from __future__ import annotations

import click


@click.group()
def cli() -> None:
    """Developer utilities for YourCLI"""
