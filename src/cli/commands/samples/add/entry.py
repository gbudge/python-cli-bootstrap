import click


@click.command()
@click.argument("a", type=int)
@click.argument("b", type=int)
def cli(a: int, b: int) -> None:
    """Add two integers."""
    click.echo(str(a + b))
