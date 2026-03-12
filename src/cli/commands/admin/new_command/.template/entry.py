"""{{COMMAND_NAME}} command entrypoint.

TODO(developer): Replace this module docstring with a concise, user-facing
description of what the command does and when to use it.
"""
import click


@click.command()
def cli():
    """Run the {{COMMAND_NAME}} command.

    TODO(developer): Replace this placeholder with real command behavior and
    document key side effects, inputs, and output expectations.
    """
    ctx = click.get_current_context()
    if ctx:
        click.echo(ctx.get_help())
