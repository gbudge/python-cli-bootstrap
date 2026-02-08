import subprocess

import click


@click.command()
@click.argument("host")
@click.option("--count", default=3, show_default=True, type=int)
def cli(host: str, count: int) -> None:
    """Ping a host."""
    result = subprocess.run(["ping", "-c", str(count), host], check=False)
    raise SystemExit(result.returncode)
