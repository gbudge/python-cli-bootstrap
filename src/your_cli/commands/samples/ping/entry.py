import subprocess

import click


@click.command()
@click.pass_context
@click.argument("host")
@click.option("--count", default=3, show_default=True, type=int)
@click.option("--verbose", is_flag=True, help="Show verbose output")
def cli(ctx: click.Context, host: str, count: int, verbose: bool) -> None:
    """Ping a host."""
    # Access app context passed from main
    if verbose and ctx.obj:
        app_name = ctx.obj.get("APP_NAME", "Unknown")
        version = ctx.obj.get("VERSION", "Unknown")
        click.echo(f"[{app_name} v{version}] Pinging {host} {count} times...")

    result = subprocess.run(["ping", "-c", str(count), host], check=False)
    raise SystemExit(result.returncode)
