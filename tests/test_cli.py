import os
from pathlib import Path

from click.testing import CliRunner

from your_cli import dev
from your_cli.loader import RootCommand, discover_specs


def _write_plugin(base: Path, command: str, subcommand: str, short_help: str = "Help") -> None:
    target = base / command / subcommand
    target.mkdir(parents=True, exist_ok=True)
    (target / "entry.py").write_text(
        "import click\n\n@click.command()\n"
        "def cli():\n"
        "    click.echo('ok')\n",
        encoding="utf-8",
    )
    (target / "meta.yaml").write_text(f"shortHelp: {short_help}\n", encoding="utf-8")


def test_discovery_valid_plugins(tmp_path: Path) -> None:
    commands_dir = tmp_path / "commands"
    _write_plugin(commands_dir, "alpha", "bravo", "Alpha Bravo")

    specs = discover_specs(commands_dir)

    assert "alpha" in specs
    assert "bravo" in specs["alpha"]


def test_root_help_includes_dev_and_dynamic(tmp_path: Path) -> None:
    commands_dir = tmp_path / "commands"
    _write_plugin(commands_dir, "compute", "add", "Add two integers.")

    root = RootCommand(commands_dir, dev.cli)
    runner = CliRunner()
    result = runner.invoke(root, ["--help"])

    assert result.exit_code == 0
    assert "dev" in result.output
    assert "compute" in result.output


def test_group_help_lists_subcommands_with_short_help() -> None:
    commands_dir = Path(__file__).parent.parent / "src" / "your_cli" / "commands"
    root = RootCommand(commands_dir, dev.cli)
    runner = CliRunner()
    result = runner.invoke(root, ["compute", "--help"])

    assert result.exit_code == 0
    assert "add" in result.output
    assert "Add two integers." in result.output


def test_scaffolder_creates_plugin(tmp_path: Path, monkeypatch) -> None:
    commands_dir = tmp_path / "commands"
    monkeypatch.setenv("YOUR_CLI_COMMANDS_DIR", str(commands_dir))

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            dev.cli,
            [
                "new-plugin",
                "compute",
                "mul",
                "--short-help",
                "Multiply two integers.",
            ],
        )

    assert result.exit_code == 0
    assert (commands_dir / "compute" / "mul" / "entry.py").exists()
    assert (commands_dir / "compute" / "mul" / "meta.yaml").exists()
