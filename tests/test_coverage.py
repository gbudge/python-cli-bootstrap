from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

import cli.main as main_mod
from cli.loader import CommandSpec, RootCommand, discover_specs, load_click_command, load_meta
from cli.utils.metadata import Metadata


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
        PACKAGE_NAME = "Foxy"
        APP_NAME = "Foxy"
        COMMAND_NAME = "Foxy"
        VERSION = "1.0.0"

    monkeypatch.setattr(main_mod, "RootCommand", DummyRoot)
    monkeypatch.setattr(main_mod, "Metadata", MockMetadata)

    (tmp_path / "commands").mkdir()

    main_mod.main()

    assert called["prog_name"] == "Foxy"
    assert called["commands_dir"] == tmp_path / "commands"


def test_execute_builtin_commands_demo_add_and_sub() -> None:
    commands_dir = Path(__file__).parent.parent / "src" / "cli" / "commands"
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
    real_commands = Path(__file__).parent.parent / "src" / "cli" / "commands"
    admin_src = real_commands / "admin"
    admin_dst = commands_dir / "admin"

    shutil.copytree(admin_src, admin_dst)

    root = RootCommand(commands_dir)
    runner = CliRunner()

    result = runner.invoke(root, ["admin", "new-command", "bad!name", "--short-help", "Help"])

    assert result.exit_code == 2
    assert "Invalid command" in result.output


def test_dev_new_plugin_rejects_existing_plugin_without_force(tmp_path: Path, monkeypatch) -> None:
    commands_dir = tmp_path / "commands"
    monkeypatch.setenv(Metadata.env_var("COMMANDS_DIR"), str(commands_dir))

    # Copy admin command structure to test directory
    real_commands = Path(__file__).parent.parent / "src" / "cli" / "commands"
    admin_src = real_commands / "admin"
    admin_dst = commands_dir / "admin"

    shutil.copytree(admin_src, admin_dst)

    existing = commands_dir / "tools" / "compute"
    existing.mkdir(parents=True)
    (existing / "entry.py").write_text("# existing\n", encoding="utf-8")
    (existing / "meta.yaml").write_text("short_help: existing\n", encoding="utf-8")

    root = RootCommand(commands_dir)
    runner = CliRunner()
    result = runner.invoke(
        root,
        ["admin", "new-command", "compute", "--parent", "tools", "--short-help", "Compute command."],
    )

    assert result.exit_code == 2
    assert "Command already exists" in result.output


def test_dev_new_plugin_force_overwrites(tmp_path: Path, monkeypatch) -> None:
    commands_dir = tmp_path / "commands"
    monkeypatch.setenv(Metadata.env_var("COMMANDS_DIR"), str(commands_dir))

    # Copy admin command structure to test directory
    real_commands = Path(__file__).parent.parent / "src" / "cli" / "commands"
    admin_src = real_commands / "admin"
    admin_dst = commands_dir / "admin"

    shutil.copytree(admin_src, admin_dst)

    existing = commands_dir / "tools" / "compute"
    existing.mkdir(parents=True)
    (existing / "entry.py").write_text("# existing\n", encoding="utf-8")
    (existing / "meta.yaml").write_text("short_help: existing\n", encoding="utf-8")

    root = RootCommand(commands_dir)
    runner = CliRunner()
    result = runner.invoke(
        root,
        [
            "admin",
            "new-command",
            "compute",
            "--parent",
            "tools",
            "--short-help",
            "Compute command.",
            "--force",
        ],
    )

    assert result.exit_code == 0
    assert "meta.yaml" in result.output
    assert "entry.py" in result.output

    meta_text = (existing / "meta.yaml").read_text(encoding="utf-8")
    assert "short_help: Compute command." in meta_text


def test_dev_new_plugin_rejects_invalid_parent_dot_notation(tmp_path: Path, monkeypatch) -> None:
    commands_dir = tmp_path / "commands"
    monkeypatch.setenv(Metadata.env_var("COMMANDS_DIR"), str(commands_dir))

    # Copy admin command structure to test directory
    real_commands = Path(__file__).parent.parent / "src" / "cli" / "commands"
    admin_src = real_commands / "admin"
    admin_dst = commands_dir / "admin"

    shutil.copytree(admin_src, admin_dst)

    root = RootCommand(commands_dir)
    runner = CliRunner()
    result = runner.invoke(
        root,
        ["admin", "new-command", "compute", "--parent", "github..repo", "--short-help", "Compute command."],
    )

    assert result.exit_code == 2
    assert "Invalid --parent" in result.output


def test_load_meta_rejects_invalid_yaml(tmp_path: Path) -> None:
    meta = tmp_path / "meta.yaml"
    meta.write_text("- not-a-mapping\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match=r"expected mapping"):
        load_meta(meta)


def test_load_meta_rejects_missing_or_empty_short_help(tmp_path: Path) -> None:
    meta_missing = tmp_path / "missing.yaml"
    meta_missing.write_text("{}\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match=r"short_help must be a non-empty string"):
        load_meta(meta_missing)

    meta_empty = tmp_path / "empty.yaml"
    meta_empty.write_text("short_help: ''\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match=r"short_help must be a non-empty string"):
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


def test_discover_specs_ignores_dot_prefixed_dirs(tmp_path: Path) -> None:
    commands_dir = tmp_path / "commands"

    # Dot-prefixed folders are support/scaffolding directories and not commands.
    (commands_dir / ".scaffolding").mkdir(parents=True)
    (commands_dir / "alpha" / ".templates").mkdir(parents=True)

    plugin_dir = commands_dir / "alpha" / "bravo"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "entry.py").write_text(
        "import click\n\n@click.command()\ndef cli():\n    click.echo('ok')\n",
        encoding="utf-8",
    )
    (plugin_dir / "meta.yaml").write_text("shortHelp: ok\n", encoding="utf-8")

    specs = discover_specs(commands_dir)

    assert ".scaffolding" not in specs
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
    meta.write_text("short_help: ok\nhidden: false\nenabled: true\n", encoding="utf-8")

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
        no_args_is_help=False,
    )

    with pytest.raises(RuntimeError, match=r"Failed to import entry\.py"):
        load_click_command(spec)


def test_load_click_command_requires_cli_export_to_be_click_command(tmp_path: Path) -> None:
    entry = tmp_path / "entry.py"
    entry.write_text("cli = 123\n", encoding="utf-8")

    meta = tmp_path / "meta.yaml"
    meta.write_text("short_help: ok\nhidden: false\nenabled: true\n", encoding="utf-8")

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
        no_args_is_help=False,
    )

    with pytest.raises(RuntimeError, match=r"must export 'cli' as a click\.Command"):
        load_click_command(spec)


def _write_rebrand_fixture(project_root: Path) -> Path:
    commands_dir = project_root / "src" / "cli" / "commands"
    admin_src = Path(__file__).parent.parent / "src" / "cli" / "commands" / "admin"
    shutil.copytree(admin_src, commands_dir / "admin")

    (project_root / "src" / "cli" / "utils").mkdir(parents=True, exist_ok=True)
    (project_root / "src" / "cli" / "commands" / "samples").mkdir(parents=True, exist_ok=True)
    (project_root / "tests").mkdir(parents=True, exist_ok=True)

    (project_root / "pyproject.toml").write_text(
        '[project]\nname = "Foxy"\nversion = "1.0.0"\n\n[project.scripts]\nFoxy = "cli.main:main"\n',
        encoding="utf-8",
    )
    (project_root / "README.md").write_text(
        "# Foxy\n\nFoxy uses `Foxy` today.\nRun `Foxy --help` or `Foxy --help`.\n",
        encoding="utf-8",
    )
    (project_root / "src" / "cli" / "main.py").write_text('"""Entry point for Foxy."""\n', encoding="utf-8")
    (project_root / "src" / "cli" / "utils" / "__init__.py").write_text(
        '"""Shared utilities for the Foxy package."""\n',
        encoding="utf-8",
    )
    (project_root / "src" / "cli" / "utils" / "metadata.py").write_text(
        "\n".join(
            [
                "class Metadata:",
                '    PACKAGE_NAME = "Foxy"',
                '    APP_NAME = "Foxy"',
                '    COMMAND_NAME = "Foxy"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    (project_root / "src" / "cli" / "commands" / "samples" / "entry.py").write_text(
        '"""Developer SDK demonstrations for Foxy."""\n',
        encoding="utf-8",
    )
    (project_root / "tests" / "test_coverage.py").write_text(
        "\n".join(
            [
                "class MockMetadata:",
                '    PACKAGE_NAME = "Foxy"',
                '    APP_NAME = "Foxy"',
                '    COMMAND_NAME = "Foxy"',
                "",
                'assert "Foxy" == "Foxy"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    (project_root / "tests" / "test_safesettimgs.py").write_text(
        '_ROOT = {"COMMAND_NAME": "Foxy"}\n',
        encoding="utf-8",
    )

    return commands_dir


def test_admin_rebrand_updates_branding_files(tmp_path: Path, monkeypatch) -> None:
    commands_dir = _write_rebrand_fixture(tmp_path)
    monkeypatch.setenv(Metadata.env_var("REBRAND_PROJECT_ROOT"), str(tmp_path))

    root = RootCommand(commands_dir)
    runner = CliRunner()

    result = runner.invoke(
        root,
        ["admin", "rebrand", "--name", "Acme CLI", "--cli-cmd", "acme", "--confirm"],
    )

    assert result.exit_code == 0
    assert "Display name: Foxy -> Acme CLI" in result.output
    assert "CLI command: Foxy -> acme" in result.output
    assert "Package name: Foxy -> acme" in result.output

    pyproject_text = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    metadata_text = (tmp_path / "src" / "cli" / "utils" / "metadata.py").read_text(encoding="utf-8")
    readme_text = (tmp_path / "README.md").read_text(encoding="utf-8")
    admin_entry_text = (tmp_path / "src" / "cli" / "commands" / "admin" / "entry.py").read_text(encoding="utf-8")
    admin_meta_text = (tmp_path / "src" / "cli" / "commands" / "admin" / "meta.yaml").read_text(encoding="utf-8")
    new_command_text = (
        tmp_path / "src" / "cli" / "commands" / "admin" / "new_command" / "entry.py"
    ).read_text(encoding="utf-8")
    samples_entry_text = (
        tmp_path / "src" / "cli" / "commands" / "samples" / "entry.py"
    ).read_text(encoding="utf-8")
    coverage_test_text = (tmp_path / "tests" / "test_coverage.py").read_text(encoding="utf-8")
    safesettings_test_text = (tmp_path / "tests" / "test_safesettimgs.py").read_text(encoding="utf-8")

    assert 'name = "acme"' in pyproject_text
    assert 'acme = "cli.main:main"' in pyproject_text
    assert 'PACKAGE_NAME = "acme"' in metadata_text
    assert 'APP_NAME = "Acme CLI"' in metadata_text
    assert 'COMMAND_NAME = "acme"' in metadata_text
    assert "# acme" in readme_text
    assert "Acme CLI uses `acme` today." in readme_text
    assert '"""Developer utilities for Acme CLI"""' in admin_entry_text
    assert "Administrative commands for Acme CLI" in admin_meta_text
    assert 'CLI_NAME = "acme"' in new_command_text
    assert '"""Developer SDK demonstrations for Acme CLI."""' in samples_entry_text
    assert 'APP_NAME = "Acme CLI"' in coverage_test_text
    assert 'PACKAGE_NAME = "acme"' in coverage_test_text
    assert '"COMMAND_NAME": "acme"' in safesettings_test_text


def test_admin_rebrand_requires_confirmation_without_flag(tmp_path: Path, monkeypatch) -> None:
    commands_dir = _write_rebrand_fixture(tmp_path)
    monkeypatch.setenv(Metadata.env_var("REBRAND_PROJECT_ROOT"), str(tmp_path))

    root = RootCommand(commands_dir)
    runner = CliRunner()

    result = runner.invoke(
        root,
        ["admin", "rebrand", "--name", "Acme CLI", "--cli-cmd", "acme"],
        input="n\n",
    )

    assert result.exit_code != 0
    assert "Display name: Foxy -> Acme CLI" in result.output
    assert "Apply these changes?" in result.output
    assert 'name = "Foxy"' in (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
