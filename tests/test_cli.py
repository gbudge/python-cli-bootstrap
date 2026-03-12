import shutil
from pathlib import Path

from click.testing import CliRunner

from cli.loader import RootCommand, discover_specs
from cli.utils.metadata import Metadata


def _write_plugin(
    base: Path,
    command: str,
    subcommand: str,
    short_help: str = "Help",
    **kwargs: bool | None,
) -> None:
    # Extract optional parameters from kwargs
    hidden = kwargs.get("hidden", False)
    enabled = kwargs.get("enabled", True)
    command_hidden = kwargs.get("command_hidden")
    command_enabled = kwargs.get("command_enabled")

    target = base / command / subcommand
    target.mkdir(parents=True, exist_ok=True)
    (target / "entry.py").write_text(
        "import click\n\n@click.command()\ndef cli():\n    click.echo('ok')\n",
        encoding="utf-8",
    )
    (target / "meta.yaml").write_text(
        f"shortHelp: {short_help}\nhidden: {str(hidden).lower()}\nenabled: {str(enabled).lower()}\n",
        encoding="utf-8",
    )

    # Optionally write command-level meta.yaml
    if command_hidden is not None or command_enabled is not None:
        cmd_hidden = command_hidden if command_hidden is not None else False
        cmd_enabled = command_enabled if command_enabled is not None else True
        group_meta_path = base / command / "meta.yaml"
        if not group_meta_path.exists():
            group_meta_path.write_text(
                f"shortHelp: {command} commands\nhidden: {str(cmd_hidden).lower()}\nenabled: {str(cmd_enabled).lower()}\n",
                encoding="utf-8",
            )


def test_discovery_valid_plugins(tmp_path: Path) -> None:
    commands_dir = tmp_path / "commands"
    _write_plugin(commands_dir, "alpha", "bravo", "Alpha Bravo")

    specs = discover_specs(commands_dir)

    assert "alpha" in specs
    assert "bravo" in specs["alpha"].subcommands


def test_root_help_includes_dev_and_dynamic(tmp_path: Path) -> None:
    commands_dir = tmp_path / "commands"
    _write_plugin(commands_dir, "compute", "add", "Add two integers.")
    (commands_dir / "compute" / "meta.yaml").write_text(
        "shortHelp: Compute related utilities.\nhidden: false\nenabled: true\n",
        encoding="utf-8",
    )

    root = RootCommand(commands_dir)
    runner = CliRunner()
    result = runner.invoke(root, ["--help"])

    assert result.exit_code == 0

    # All commands appear in the Commands section.
    assert "Commands:\n" in result.output
    assert "  compute" in result.output
    assert "Compute related utilities." in result.output


def test_hidden_command_not_shown_in_help(tmp_path: Path) -> None:
    commands_dir = tmp_path / "commands"
    _write_plugin(commands_dir, "visible", "cmd", "Visible command")
    _write_plugin(commands_dir, "hidden", "cmd", "Hidden command", command_hidden=True)

    root = RootCommand(commands_dir)
    runner = CliRunner()
    result = runner.invoke(root, ["--help"])

    assert result.exit_code == 0
    assert "visible" in result.output
    assert "hidden" not in result.output

    # But hidden command still works
    result_hidden = runner.invoke(root, ["hidden", "cmd"])
    assert result_hidden.exit_code == 0
    assert "ok" in result_hidden.output


def test_disabled_command_is_hidden_and_fails(tmp_path: Path) -> None:
    commands_dir = tmp_path / "commands"
    _write_plugin(commands_dir, "working", "cmd", "Working command")
    _write_plugin(commands_dir, "disabled", "cmd", "Disabled command", command_enabled=False)

    root = RootCommand(commands_dir)
    runner = CliRunner()
    result = runner.invoke(root, ["--help"])

    assert result.exit_code == 0
    assert "working" in result.output
    assert "disabled" not in result.output

    # Disabled command should fail (Click returns exit code 2 for "no such command")
    result_disabled = runner.invoke(root, ["disabled", "cmd"])
    assert result_disabled.exit_code != 0
    # Group is disabled so command won't be found


def test_hidden_subcommand_not_shown_but_works(tmp_path: Path) -> None:
    commands_dir = tmp_path / "commands"
    _write_plugin(commands_dir, "tools", "visible", "Visible subcommand")
    _write_plugin(commands_dir, "tools", "hidden", "Hidden subcommand", hidden=True)

    root = RootCommand(commands_dir)
    runner = CliRunner()
    result = runner.invoke(root, ["tools", "--help"])

    assert result.exit_code == 0
    assert "visible" in result.output
    assert "hidden" not in result.output

    # But hidden subcommand still works
    result_hidden = runner.invoke(root, ["tools", "hidden"])
    assert result_hidden.exit_code == 0
    assert "ok" in result_hidden.output


def test_disabled_subcommand_fails_execution(tmp_path: Path) -> None:
    commands_dir = tmp_path / "commands"
    _write_plugin(commands_dir, "tools", "working", "Working subcommand")
    _write_plugin(commands_dir, "tools", "disabled", "Disabled subcommand", enabled=False)

    root = RootCommand(commands_dir)
    runner = CliRunner()

    # Disabled subcommand should not be shown
    result = runner.invoke(root, ["tools", "--help"])
    assert result.exit_code == 0
    assert "working" in result.output
    assert "disabled" not in result.output

    # And should fail when executed
    result_disabled = runner.invoke(root, ["tools", "disabled"])
    assert result_disabled.exit_code == 1
    assert "disabled" in result_disabled.output.lower()


def test_no_args_is_help_is_configurable_per_group_level(tmp_path: Path) -> None:
    commands_dir = tmp_path / "commands"

    tools_dir = commands_dir / "tools"
    (tools_dir / "admin" / "show").mkdir(parents=True, exist_ok=True)

    (tools_dir / "entry.py").write_text(
        "import click\n\n@click.group()\ndef cli():\n    pass\n",
        encoding="utf-8",
    )
    (tools_dir / "meta.yaml").write_text(
        "shortHelp: Tools commands\nhidden: false\nenabled: true\nno_args_is_help: true\n",
        encoding="utf-8",
    )

    (tools_dir / "admin" / "entry.py").write_text(
        "import click\n\n@click.group()\ndef cli():\n    pass\n",
        encoding="utf-8",
    )
    (tools_dir / "admin" / "meta.yaml").write_text(
        "shortHelp: Admin tools\nhidden: false\nenabled: true\nno_args_is_help: false\n",
        encoding="utf-8",
    )

    (tools_dir / "admin" / "show" / "entry.py").write_text(
        "import click\n\n@click.command()\ndef cli():\n    click.echo('ok')\n",
        encoding="utf-8",
    )
    (tools_dir / "admin" / "show" / "meta.yaml").write_text(
        "shortHelp: Show details\nhidden: false\nenabled: true\nno_args_is_help: false\n",
        encoding="utf-8",
    )

    runner = CliRunner()

    root = RootCommand(commands_dir)
    top_level = runner.invoke(root, ["tools"])
    assert top_level.exit_code != 0
    assert "Commands:" in top_level.output
    assert "admin" in top_level.output

    sub_level = runner.invoke(root, ["tools", "admin"])
    assert sub_level.exit_code != 0
    assert "Missing command" in sub_level.output
    assert "Try 'cli tools admin --help' for help." in sub_level.output

    (tools_dir / "admin" / "meta.yaml").write_text(
        "shortHelp: Admin tools\nhidden: false\nenabled: true\nno_args_is_help: true\n",
        encoding="utf-8",
    )

    refreshed_root = RootCommand(commands_dir)
    refreshed_sub_level = runner.invoke(refreshed_root, ["tools", "admin"])
    assert refreshed_sub_level.exit_code != 0
    assert "Commands:" in refreshed_sub_level.output
    assert "show" in refreshed_sub_level.output.lower()
    assert "Try 'cli tools admin --help' for help." not in refreshed_sub_level.output


def test_group_help_lists_subcommands_with_short_help() -> None:
    commands_dir = Path(__file__).parent.parent / "src" / "cli" / "commands"
    root = RootCommand(commands_dir)
    runner = CliRunner()

    # Test that command groups show their subcommands correctly
    result = runner.invoke(root, ["admin", "--help"])
    assert result.exit_code == 0
    assert "new-command" in result.output
    assert "rebrand" in result.output
    assert "Create a new command plugin skeleton." in result.output


def test_scaffolder_creates_plugin(tmp_path: Path, monkeypatch) -> None:
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
        [
            "admin",
            "new-command",
            "compute",
            "--parent",
            "math.ops",
            "--short-help",
            "Multiply two integers.",
        ],
    )

    assert result.exit_code == 0
    assert (commands_dir / "math" / "meta.yaml").exists()
    assert (commands_dir / "math" / "entry.py").exists()
    assert (commands_dir / "math" / "ops" / "meta.yaml").exists()
    assert (commands_dir / "math" / "ops" / "entry.py").exists()
    assert (commands_dir / "math" / "ops" / "compute" / "entry.py").exists()
    assert (commands_dir / "math" / "ops" / "compute" / "meta.yaml").exists()

    template_dir = commands_dir / "admin" / "new_command" / ".template"
    expected_entry = (template_dir / "entry.py").read_text(encoding="utf-8").replace(
        "{{COMMAND_NAME}}",
        "compute",
    )
    expected_meta = (template_dir / "meta.yaml").read_text(encoding="utf-8").replace(
        "{{SHORT_HELP}}",
        "Multiply two integers.",
    ).replace(
        "{{COMMAND_NAME}}",
        "compute",
    )
    generated_entry = (commands_dir / "math" / "ops" / "compute" / "entry.py").read_text(encoding="utf-8")
    generated_meta = (commands_dir / "math" / "ops" / "compute" / "meta.yaml").read_text(encoding="utf-8")

    assert generated_entry == expected_entry
    assert generated_meta == expected_meta


def test_scaffolder_upgrades_parent_command_to_group_when_child_is_added(tmp_path: Path, monkeypatch) -> None:
    commands_dir = tmp_path / "commands"
    monkeypatch.setenv(Metadata.env_var("COMMANDS_DIR"), str(commands_dir))

    # Copy admin command structure to test directory
    real_commands = Path(__file__).parent.parent / "src" / "cli" / "commands"
    admin_src = real_commands / "admin"
    admin_dst = commands_dir / "admin"
    shutil.copytree(admin_src, admin_dst)

    root = RootCommand(commands_dir)
    runner = CliRunner()

    create_parent = runner.invoke(
        root,
        [
            "admin",
            "new-command",
            "cicd",
            "--short-help",
            "CI/CD related commands.",
        ],
    )
    assert create_parent.exit_code == 0

    parent_entry = commands_dir / "cicd" / "entry.py"
    assert "@click.command()" in parent_entry.read_text(encoding="utf-8")

    create_child = runner.invoke(
        root,
        [
            "admin",
            "new-command",
            "create-stack",
            "--parent",
            "cicd",
            "--short-help",
            "Create a new stack",
        ],
    )
    assert create_child.exit_code == 0

    parent_entry_text = parent_entry.read_text(encoding="utf-8")
    assert "@click.group()" in parent_entry_text

    refreshed_root = RootCommand(commands_dir)
    run_child = runner.invoke(refreshed_root, ["cicd", "create-stack"])
    assert run_child.exit_code == 0
    assert "Usage:" in run_child.output
    assert "Create a new stack" in run_child.output


def test_scaffolder_upgrades_intermediate_parent_for_dot_parent_chain(tmp_path: Path, monkeypatch) -> None:
    commands_dir = tmp_path / "commands"
    monkeypatch.setenv(Metadata.env_var("COMMANDS_DIR"), str(commands_dir))

    # Copy admin command structure to test directory
    real_commands = Path(__file__).parent.parent / "src" / "cli" / "commands"
    admin_src = real_commands / "admin"
    admin_dst = commands_dir / "admin"
    shutil.copytree(admin_src, admin_dst)

    root = RootCommand(commands_dir)
    runner = CliRunner()

    first = runner.invoke(
        root,
        [
            "admin",
            "new-command",
            "cicd",
            "--short-help",
            "CI/CD related commands.",
        ],
    )
    assert first.exit_code == 0

    second = runner.invoke(
        root,
        [
            "admin",
            "new-command",
            "stack",
            "--parent",
            "cicd",
            "--short-help",
            "Stack operations.",
        ],
    )
    assert second.exit_code == 0

    stack_entry = commands_dir / "cicd" / "stack" / "entry.py"
    assert "@click.command()" in stack_entry.read_text(encoding="utf-8")

    third = runner.invoke(
        root,
        [
            "admin",
            "new-command",
            "create",
            "--parent",
            "cicd.stack",
            "--short-help",
            "Create a new stack.",
        ],
    )
    assert third.exit_code == 0

    stack_entry_text = stack_entry.read_text(encoding="utf-8")
    assert "@click.group()" in stack_entry_text

    refreshed_root = RootCommand(commands_dir)
    run_nested = runner.invoke(refreshed_root, ["cicd", "stack", "create"])
    assert run_nested.exit_code == 0
    assert "Usage:" in run_nested.output
    assert "Create a new stack." in run_nested.output
