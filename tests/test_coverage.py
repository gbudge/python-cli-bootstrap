from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

import your_cli.main as main_mod
from your_cli.loader import CommandSpec, RootCommand, discover_specs, load_click_command, load_meta


def test_main_instantiates_root_command(monkeypatch, tmp_path: Path) -> None:
    called: dict[str, object] = {}

    class DummyRoot:
        def __init__(self, commands_dir: Path, app_context: dict | None = None):
            called["commands_dir"] = commands_dir
            called["app_context"] = app_context

        def __call__(self, prog_name: str) -> None:
            called["prog_name"] = prog_name

    # Mock Metadata to return test paths
    class MockMetadata:
        PACKAGE_ROOT_DIR = tmp_path
        COMMANDS_DIR = tmp_path / "commands"
        PACKAGE_NAME = "your-cli"
        APP_NAME = "YourCLI"
        COMMAND_NAME = "yourcli"
        VERSION = "1.0.0"

    monkeypatch.setattr(main_mod, "RootCommand", DummyRoot)
    monkeypatch.setattr(main_mod, "Metadata", MockMetadata)

    (tmp_path / "commands").mkdir()

    main_mod.main()

    assert called["prog_name"] == "yourcli"
    assert called["commands_dir"] == tmp_path / "commands"


def test_execute_builtin_commands_demo_add_and_sub() -> None:
    commands_dir = Path(__file__).parent.parent / "src" / "your_cli" / "commands"
    root = RootCommand(commands_dir)
    runner = CliRunner()

    add = runner.invoke(root, ["samples", "add", "1", "2"])
    assert add.exit_code == 0
    assert add.output.strip() == "3"

    sub = runner.invoke(root, ["samples", "sub", "1", "2"])
    assert sub.exit_code == 0
    assert sub.output.strip() == "-1"


def test_dev_new_plugin_rejects_invalid_names(tmp_path: Path) -> None:
    commands_dir = tmp_path / "commands"

    # Copy admin command structure to test directory
    real_commands = Path(__file__).parent.parent / "src" / "your_cli" / "commands"
    admin_src = real_commands / "admin"
    admin_dst = commands_dir / "admin"

    shutil.copytree(admin_src, admin_dst)

    root = RootCommand(commands_dir)
    runner = CliRunner()

    result = runner.invoke(root, ["admin", "new-command", "bad!name", "ok"])

    assert result.exit_code == 2
    assert "Invalid command" in result.output


def test_dev_new_plugin_rejects_existing_plugin_without_force(tmp_path: Path, monkeypatch) -> None:
    commands_dir = tmp_path / "commands"
    monkeypatch.setenv("YOUR_CLI_COMMANDS_DIR", str(commands_dir))

    # Copy admin command structure to test directory
    real_commands = Path(__file__).parent.parent / "src" / "your_cli" / "commands"
    admin_src = real_commands / "admin"
    admin_dst = commands_dir / "admin"

    shutil.copytree(admin_src, admin_dst)

    existing = commands_dir / "compute" / "mul"
    existing.mkdir(parents=True)
    (existing / "entry.py").write_text("# existing\n", encoding="utf-8")
    (existing / "meta.yaml").write_text("HelpSummary: existing\n", encoding="utf-8")

    root = RootCommand(commands_dir)
    runner = CliRunner()
    result = runner.invoke(root, ["admin", "new-command", "compute", "mul", "--short-help", "Multiply."])

    assert result.exit_code == 2
    assert "Plugin already exists" in result.output


def test_dev_new_plugin_force_overwrites_and_default_help(tmp_path: Path, monkeypatch) -> None:
    commands_dir = tmp_path / "commands"
    monkeypatch.setenv("YOUR_CLI_COMMANDS_DIR", str(commands_dir))

    # Copy admin command structure to test directory
    real_commands = Path(__file__).parent.parent / "src" / "your_cli" / "commands"
    admin_src = real_commands / "admin"
    admin_dst = commands_dir / "admin"

    shutil.copytree(admin_src, admin_dst)

    existing = commands_dir / "compute" / "mul"
    existing.mkdir(parents=True)
    (existing / "entry.py").write_text("# existing\n", encoding="utf-8")
    (existing / "meta.yaml").write_text("HelpSummary: existing\n", encoding="utf-8")

    root = RootCommand(commands_dir)
    runner = CliRunner()
    result = runner.invoke(root, ["admin", "new-command", "compute", "mul", "--force"])

    assert result.exit_code == 0
    assert "meta.yaml" in result.output
    assert "entry.py" in result.output

    meta_text = (existing / "meta.yaml").read_text(encoding="utf-8")
    assert meta_text.startswith("HelpSummary: TODO: describe compute mul.")


def test_load_meta_rejects_invalid_yaml(tmp_path: Path) -> None:
    meta = tmp_path / "meta.yaml"
    meta.write_text("- not-a-mapping\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match=r"expected mapping"):
        load_meta(meta)


def test_load_meta_rejects_missing_or_empty_short_help(tmp_path: Path) -> None:
    meta_missing = tmp_path / "missing.yaml"
    meta_missing.write_text("{}\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match=r"HelpSummary must be a non-empty string"):
        load_meta(meta_missing)

    meta_empty = tmp_path / "empty.yaml"
    meta_empty.write_text("HelpSummary: ''\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match=r"HelpSummary must be a non-empty string"):
        load_meta(meta_empty)


def test_discover_specs_reports_missing_files(tmp_path: Path) -> None:
    commands_dir = tmp_path / "commands"
    (commands_dir / "alpha" / "bravo").mkdir(parents=True)

    with pytest.raises(RuntimeError, match=r"missing entry\.py, meta\.yaml"):
        discover_specs(commands_dir)


def test_discover_specs_ignores_pycache_dirs(tmp_path: Path) -> None:
    commands_dir = tmp_path / "commands"

    # Should ignore __pycache__ at both command and subcommand levels.
    (commands_dir / "__pycache__").mkdir(parents=True)
    (commands_dir / "alpha" / "__pycache__").mkdir(parents=True)

    # Valid plugin still discovered.
    plugin_dir = commands_dir / "alpha" / "bravo"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "entry.py").write_text(
        "import click\n\n@click.command()\ndef cli():\n    click.echo('ok')\n",
        encoding="utf-8",
    )
    (plugin_dir / "meta.yaml").write_text("shortHelp: ok\n", encoding="utf-8")

    specs = discover_specs(commands_dir)
    assert "alpha" in specs
    assert "bravo" in specs["alpha"].subcommands


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
    meta.write_text("HelpSummary: ok\nhidden: false\nenabled: true\n", encoding="utf-8")

    spec = CommandSpec(
        name="bravo",
        entry_path=missing_entry,
        meta_path=meta,
        import_path=["alpha", "bravo"],
        hidden=False,
        enabled=True,
        help_group="Commands",
        is_group=False,
        subcommands=None,
    )

    with pytest.raises(RuntimeError, match=r"Failed to import entry\.py"):
        load_click_command(spec)


def test_load_click_command_requires_cli_export_to_be_click_command(tmp_path: Path) -> None:
    entry = tmp_path / "entry.py"
    entry.write_text("cli = 123\n", encoding="utf-8")

    meta = tmp_path / "meta.yaml"
    meta.write_text("HelpSummary: ok\nhidden: false\nenabled: true\n", encoding="utf-8")

    spec = CommandSpec(
        name="bravo",
        entry_path=entry,
        meta_path=meta,
        import_path=["alpha", "bravo"],
        hidden=False,
        enabled=True,
        help_group="Commands",
        is_group=False,
        subcommands=None,
    )

    with pytest.raises(RuntimeError, match=r"must export 'cli' as a click\.Command"):
        load_click_command(spec)
