"""Entry point for your_cli."""

from pathlib import Path

from your_cli import dev
from your_cli.loader import RootCommand


def main() -> None:
    pkg_root = Path(__file__).resolve().parent
    commands_dir = pkg_root / "commands"
    cli = RootCommand(commands_dir, dev.cli)
    cli(prog_name="your-cli")


if __name__ == "__main__":
    main()
