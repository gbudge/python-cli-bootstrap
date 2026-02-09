from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

import your_cli.main as main_mod
from your_cli import dev
from your_cli.loader import CommandSpec, RootCommand, discover_specs, load_click_command, load_meta


def test_main_instantiates_root_command(monkeypatch, tmp_path: Path) -> None:
    called: dict[str, object] = {}

    class DummyRoot:
        def __init__(self, commands_dir: Path, dev_group):
            called["commands_dir"] = commands_dir
            called["dev_group"] = dev_group

        def __call__(self, prog_name: str) -> None:
            called["prog_name"] = prog_name

    monkeypatch.setattr(main_mod, "RootCommand", DummyRoot)
    monkeypatch.setattr(main_mod, "__file__", str(tmp_path / "main.py"))

    (tmp_path / "commands").mkdir()

    main_mod.main()

    assert called["prog_name"] == "your-cli"
    assert called["commands_dir"] == tmp_path / "commands"
    assert called["dev_group"] is dev.cli


def test_execute_builtin_commands_compute_add_and_sub() -> None:
    commands_dir = Path(__file__).parent.parent / "src" / "your_cli" / "commands"
    root = RootCommand(commands_dir, dev.cli)
    runner = CliRunner()

    add = runner.invoke(root, ["compute", "add", "1", "2"])
    assert add.exit_code == 0
    assert add.output.strip() == "3"

    sub = runner.invoke(root, ["compute", "sub", "1", "2"])
    assert sub.exit_code == 0
    assert sub.output.strip() == "-1"


def test_dev_new_plugin_rejects_invalid_names() -> None:
    runner = CliRunner()

    result = runner.invoke(dev.cli, ["new-plugin", "bad!name", "ok"])

    assert result.exit_code == 2
    assert "Invalid command" in result.output


def test_dev_new_plugin_rejects_existing_plugin_without_force(tmp_path: Path, monkeypatch) -> None:
    commands_dir = tmp_path / "commands"
    monkeypatch.setenv("YOUR_CLI_COMMANDS_DIR", str(commands_dir))

    existing = commands_dir / "compute" / "mul"
    existing.mkdir(parents=True)
    (existing / "entry.py").write_text("# existing\n", encoding="utf-8")
    (existing / "meta.yaml").write_text("shortHelp: existing\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(dev.cli, ["new-plugin", "compute", "mul", "--short-help", "Multiply."])

    assert result.exit_code == 2
    assert "Plugin already exists" in result.output


def test_dev_new_plugin_force_overwrites_and_default_help(tmp_path: Path, monkeypatch) -> None:
    commands_dir = tmp_path / "commands"
    monkeypatch.setenv("YOUR_CLI_COMMANDS_DIR", str(commands_dir))

    existing = commands_dir / "compute" / "mul"
    existing.mkdir(parents=True)
    (existing / "entry.py").write_text("# existing\n", encoding="utf-8")
    (existing / "meta.yaml").write_text("shortHelp: existing\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(dev.cli, ["new-plugin", "compute", "mul", "--force"])

    assert result.exit_code == 0
    assert "meta.yaml" in result.output
    assert "entry.py" in result.output

    meta_text = (existing / "meta.yaml").read_text(encoding="utf-8")
    assert meta_text.startswith("shortHelp: TODO: describe compute mul.")


def test_load_meta_rejects_invalid_yaml(tmp_path: Path) -> None:
    meta = tmp_path / "meta.yaml"
    meta.write_text("- not-a-mapping\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match=r"expected mapping"):
        load_meta(meta)


def test_load_meta_rejects_missing_or_empty_short_help(tmp_path: Path) -> None:
    meta_missing = tmp_path / "missing.yaml"
    meta_missing.write_text("{}\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match=r"shortHelp must be a non-empty string"):
        load_meta(meta_missing)

    meta_empty = tmp_path / "empty.yaml"
    meta_empty.write_text("shortHelp: ''\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match=r"shortHelp must be a non-empty string"):
        load_meta(meta_empty)


def test_discover_specs_reports_missing_files(tmp_path: Path) -> None:
    commands_dir = tmp_path / "commands"
    (commands_dir / "alpha" / "bravo").mkdir(parents=True)

    with pytest.raises(RuntimeError, match=r"missing entry\.py, meta\.yaml"):
        discover_specs(commands_dir)


def test_discover_specs_reports_invalid_meta(tmp_path: Path) -> None:
    commands_dir = tmp_path / "commands"
    plugin_dir = commands_dir / "alpha" / "bravo"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "entry.py").write_text(
        "import click\n\n@click.command()\ndef cli():\n    click.echo('ok')\n",
        encoding="utf-8",
    )
    (plugin_dir / "meta.yaml").write_text("[]\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match=r"Invalid meta\.yaml"):
        discover_specs(commands_dir)


def test_load_click_command_requires_entry_file_to_exist(tmp_path: Path) -> None:
    missing_entry = tmp_path / "missing" / "entry.py"
    meta = tmp_path / "meta.yaml"
    meta.write_text("shortHelp: ok\n", encoding="utf-8")

    spec = CommandSpec(
        command="alpha",
        subcommand="bravo",
        entry_path=missing_entry,
        meta_path=meta,
        import_command="alpha",
        import_subcommand="bravo",
    )

    with pytest.raises(RuntimeError, match=r"Failed to import entry\.py"):
        load_click_command(spec)


def test_load_click_command_requires_cli_export_to_be_click_command(tmp_path: Path) -> None:
    entry = tmp_path / "entry.py"
    entry.write_text("cli = 123\n", encoding="utf-8")

    meta = tmp_path / "meta.yaml"
    meta.write_text("shortHelp: ok\n", encoding="utf-8")

    spec = CommandSpec(
        command="alpha",
        subcommand="bravo",
        entry_path=entry,
        meta_path=meta,
        import_command="alpha",
        import_subcommand="bravo",
    )

    with pytest.raises(RuntimeError, match=r"must export 'cli' as a click\.Command"):
        load_click_command(spec)
