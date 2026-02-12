"""Command discovery and lazy loading."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import util
from pathlib import Path

import click
import yaml

from your_cli import __version__


@dataclass(frozen=True)
class CommandSpec:
    name: str
    entry_path: Path
    meta_path: Path
    import_path: list[str]  # Path segments for import (e.g., ["admin", "sdk", "add"])
    hidden: bool
    enabled: bool
    help_group: str
    is_group: bool  # True if this is a group with subcommands
    subcommands: dict[str, CommandSpec] | None = None  # Nested subcommands if is_group=True


@dataclass(frozen=True)
class CommandGroupSpec:
    help_summary: str | None
    entry_path: Path | None
    import_command: str
    subcommands: dict[str, CommandSpec]
    hidden: bool
    enabled: bool
    help_group: str


def _safe_name(name: str) -> str:
    return name.replace("_", "-")


def load_meta(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - surface any parse error
        raise RuntimeError(f"Invalid meta.yaml at {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"Invalid meta.yaml at {path}: expected mapping")

    # Support both HelpSummary (new) and shortHelp (legacy) for backwards compatibility
    help_summary = data.get("HelpSummary") or data.get("shortHelp")
    if not isinstance(help_summary, str) or not help_summary.strip():
        raise RuntimeError(f"Invalid meta.yaml at {path}: HelpSummary must be a non-empty string")

    # Normalize to HelpSummary
    data["HelpSummary"] = help_summary

    # Extract hidden, enabled, and HelpGroup with defaults
    data.setdefault("hidden", False)
    data.setdefault("enabled", True)
    data.setdefault("HelpGroup", "Commands")

    # If disabled, override hidden to True
    if not data["enabled"]:
        data["hidden"] = True

    return data


def load_group_meta(path: Path) -> dict | None:
    """Load optional command-group meta.

    A group-level meta.yaml is optional (unlike subcommand meta.yaml).
    """

    if not path.is_file():
        return None

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - surface any parse error
        raise RuntimeError(f"Invalid meta.yaml at {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise RuntimeError(f"Invalid meta.yaml at {path}: expected mapping")

    # Support both HelpSummary (new) and shortHelp (legacy) for backwards compatibility
    help_summary = data.get("HelpSummary") or data.get("shortHelp")
    if help_summary is None:
        return None
    if not isinstance(help_summary, str) or not help_summary.strip():
        raise RuntimeError(f"Invalid meta.yaml at {path}: HelpSummary must be a non-empty string")

    # Normalize to HelpSummary
    data["HelpSummary"] = help_summary

    # Extract hidden, enabled, and HelpGroup with defaults
    data.setdefault("hidden", False)
    data.setdefault("enabled", True)
    data.setdefault("HelpGroup", "Commands")

    # If disabled, override hidden to True
    if not data["enabled"]:
        data["hidden"] = True

    return data


def _discover_nested_commands(
    base_dir: Path,
    import_path: list[str],
    current_depth: int,
    max_depth: int,
    errors: list[str],
) -> dict[str, CommandSpec]:
    """Recursively discover commands up to max_depth levels.

    Args:
        base_dir: Directory to scan for commands
        import_path: List of import segments leading to this directory
        current_depth: Current nesting depth (0 = top level)
        max_depth: Maximum allowed depth
        errors: List to accumulate error messages

    Returns:
        Dictionary of command name -> CommandSpec
    """
    if current_depth >= max_depth:
        return {}

    specs: dict[str, CommandSpec] = {}

    for sub_dir in sorted(p for p in base_dir.iterdir() if p.is_dir()):
        # Ignore interpreter / tooling artefacts.
        if sub_dir.name.startswith(".") or sub_dir.name.startswith("__"):
            continue

        cmd_name = _safe_name(sub_dir.name)
        entry_path = sub_dir / "entry.py"
        meta_path = sub_dir / "meta.yaml"

        # Check if required files exist
        missing: list[str] = []
        if not entry_path.is_file():
            missing.append("entry.py")
        if not meta_path.is_file():
            missing.append("meta.yaml")

        if missing:
            path_str = "/".join(import_path + [sub_dir.name])
            errors.append(f"{path_str}: missing {', '.join(missing)}")
            continue

        # Load metadata
        try:
            meta = load_meta(meta_path)
        except RuntimeError as exc:
            errors.append(str(exc))
            continue

        # Check if this command has nested subcommands
        nested_import_path = import_path + [sub_dir.name]
        nested_specs = _discover_nested_commands(
            sub_dir,
            nested_import_path,
            current_depth + 1,
            max_depth,
            errors,
        )

        # Determine if this is a group or terminal command
        is_group = len(nested_specs) > 0

        specs[cmd_name] = CommandSpec(
            name=cmd_name,
            entry_path=entry_path,
            meta_path=meta_path,
            import_path=nested_import_path,
            hidden=meta["hidden"],
            enabled=meta["enabled"],
            help_group=meta["HelpGroup"],
            is_group=is_group,
            subcommands=nested_specs if is_group else None,
        )

    return specs


def discover_specs(commands_dir: Path, max_depth: int = 5) -> dict[str, CommandGroupSpec]:
    """Discover command groups with nested subcommands up to max_depth levels."""
    errors: list[str] = []
    specs: dict[str, CommandGroupSpec] = {}
    if not commands_dir.exists():
        return specs

    for command_dir in sorted(p for p in commands_dir.iterdir() if p.is_dir()):
        # Ignore interpreter / tooling artefacts.
        if command_dir.name.startswith(".") or command_dir.name.startswith("__"):
            continue

        command_name = _safe_name(command_dir.name)
        import_command = command_dir.name

        group_help_summary: str | None = None
        group_hidden = False
        group_enabled = True
        group_help_group = "Commands"
        try:
            group_meta = load_group_meta(command_dir / "meta.yaml")
        except RuntimeError as exc:
            errors.append(str(exc))
            group_meta = None
        if group_meta is not None:
            group_help_summary = group_meta["HelpSummary"].strip()
            group_hidden = group_meta["hidden"]
            group_enabled = group_meta["enabled"]
            group_help_group = group_meta["HelpGroup"]

        group_entry_path = command_dir / "entry.py"
        if not group_entry_path.is_file():
            group_entry_path = None

        # Discover nested subcommands recursively
        sub_specs = _discover_nested_commands(
            command_dir,
            [import_command],
            current_depth=0,
            max_depth=max_depth,
            errors=errors,
        )

        # Include groups that have:
        # - at least one valid subcommand, OR
        # - an entry.py file (allowing standalone commands)
        if sub_specs or group_entry_path is not None:
            specs[command_name] = CommandGroupSpec(
                help_summary=group_help_summary,
                entry_path=group_entry_path,
                import_command=import_command,
                subcommands=sub_specs,
                hidden=group_hidden,
                enabled=group_enabled,
                help_group=group_help_group,
            )

    if errors:
        message = "Invalid command plugins detected:\n" + "\n".join(f"- {err}" for err in errors)
        raise RuntimeError(message)
    return specs


def load_click_command(spec: CommandSpec) -> click.Command:
    """Load a click command or group from a CommandSpec.

    Handles both terminal commands and nested groups.
    """
    # If disabled, return a stub command that exits with an error.
    if not spec.enabled:
        if spec.is_group:

            @click.group(name=spec.name, hidden=True)
            def disabled_group() -> None:
                cmd_path = ".".join(spec.import_path)
                click.echo(f"Command '{cmd_path}' is disabled.", err=True)
                raise SystemExit(1)

            return disabled_group
        else:

            @click.command(name=spec.name, hidden=True)
            def disabled_command() -> None:
                cmd_path = ".".join(spec.import_path)
                click.echo(f"Command '{cmd_path}' is disabled.", err=True)
                raise SystemExit(1)

            return disabled_command

    meta = load_meta(spec.meta_path)
    module_name = f"your_cli.commands.{'.'.join(spec.import_path)}.entry"
    module_spec = util.spec_from_file_location(module_name, spec.entry_path)
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError(f"Failed to import entry.py at {spec.entry_path}")
    module = util.module_from_spec(module_spec)
    try:
        module_spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - surface any import error
        raise RuntimeError(f"Failed to import entry.py at {spec.entry_path}: {exc}") from exc
    cli = getattr(module, "cli", None)

    # Validate the command type
    if spec.is_group:
        if not isinstance(cli, click.core.Group):
            raise RuntimeError(f"{spec.entry_path} must export 'cli' as a click.Group (found {type(cli).__name__})")
        # Wrap with nested subcommands if present
        if spec.subcommands:
            cli = LazyNestedGroup(cli, spec.subcommands)
    elif not isinstance(cli, click.core.Command):
        raise RuntimeError(f"{spec.entry_path} must export 'cli' as a click.Command (found {type(cli).__name__})")

    cli.short_help = meta["HelpSummary"]
    cli.help = meta["HelpSummary"]
    cli.hidden = spec.hidden
    cli.name = spec.name
    return cli


def load_click_group(group_name: str, entry_path: Path, import_command: str) -> click.Group:
    module_name = f"your_cli.commands.{import_command}.entry"
    module_spec = util.spec_from_file_location(module_name, entry_path)
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError(f"Failed to import entry.py at {entry_path}")
    module = util.module_from_spec(module_spec)
    try:
        module_spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - surface any import error
        raise RuntimeError(f"Failed to import entry.py at {entry_path}: {exc}") from exc

    cli = getattr(module, "cli", None)
    if not isinstance(cli, click.core.Group):
        raise RuntimeError(f"{entry_path} must export 'cli' as a click.Group")

    # Ensure the name matches the directory / invocation.
    cli.name = group_name
    return cli


def load_click_command_from_entry(cmd_name: str, entry_path: Path, import_command: str) -> click.Command:
    """Load a click.Command or click.Group from entry.py."""
    module_name = f"your_cli.commands.{import_command}.entry"
    module_spec = util.spec_from_file_location(module_name, entry_path)
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError(f"Failed to import entry.py at {entry_path}")
    module = util.module_from_spec(module_spec)
    try:
        module_spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - surface any import error
        raise RuntimeError(f"Failed to import entry.py at {entry_path}: {exc}") from exc

    cli = getattr(module, "cli", None)
    if not isinstance(cli, click.core.Command):
        raise RuntimeError(f"{entry_path} must export 'cli' as a click.Command or click.Group")

    # Ensure the name matches the directory / invocation.
    cli.name = cmd_name
    return cli


class LazySubGroup(click.Group):
    """A simple group with no entry.py, just subcommands."""

    def __init__(self, name: str, specs: dict[str, CommandSpec]) -> None:
        super().__init__(name=name)
        self._specs = specs

    def list_commands(self, ctx: click.Context) -> list[str]:
        return sorted(self._specs)

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        spec = self._specs.get(cmd_name)
        if spec is None:
            return None
        return load_click_command(spec)

    def format_commands(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        """Format help with commands grouped by their HelpGroup."""

        def _rows(items: list[tuple[str, click.Command]]) -> list[tuple[str, str]]:
            if not items:
                return []
            limit = formatter.width - 6 - max(len(name) for name, _ in items)
            return [(name, cmd.get_short_help_str(limit)) for name, cmd in items]

        # Group commands by their HelpGroup
        groups: dict[str, list[tuple[str, click.Command]]] = {}
        for cmd_name in sorted(self._specs):
            cmd = self.get_command(ctx, cmd_name)
            if cmd is None or cmd.hidden:
                continue
            spec = self._specs[cmd_name]
            help_group = spec.help_group
            if help_group not in groups:
                groups[help_group] = []
            groups[help_group].append((cmd_name, cmd))

        # Output each group in a consistent order (Commands first, then alphabetically)
        sorted_groups = sorted(groups.keys(), key=lambda g: (g != "Commands", g))
        for group_name in sorted_groups:
            command_rows = _rows(groups[group_name])
            if command_rows:
                with formatter.section(group_name):
                    formatter.write_dl(command_rows)


class LazyPluginGroup(click.Group):
    """A Click group with a real callback/options, but lazily loaded subcommands."""

    def __init__(self, base: click.Group, specs: dict[str, CommandSpec]) -> None:
        super().__init__(
            name=base.name,
            callback=base.callback,
            params=base.params,
            help=base.help,
            short_help=base.short_help,
            epilog=base.epilog,
            invoke_without_command=getattr(base, "invoke_without_command", False),
            no_args_is_help=getattr(base, "no_args_is_help", False),
            context_settings=base.context_settings,
        )
        self._specs = specs

    def list_commands(self, ctx: click.Context) -> list[str]:
        return sorted(self._specs)

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        spec = self._specs.get(cmd_name)
        if spec is None:
            return None
        return load_click_command(spec)

    def format_commands(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        """Format help with commands grouped by their HelpGroup."""

        def _rows(items: list[tuple[str, click.Command]]) -> list[tuple[str, str]]:
            if not items:
                return []
            limit = formatter.width - 6 - max(len(name) for name, _ in items)
            return [(name, cmd.get_short_help_str(limit)) for name, cmd in items]

        # Group commands by their HelpGroup
        groups: dict[str, list[tuple[str, click.Command]]] = {}
        for cmd_name in sorted(self._specs):
            cmd = self.get_command(ctx, cmd_name)
            if cmd is None or cmd.hidden:
                continue
            spec = self._specs[cmd_name]
            help_group = spec.help_group
            if help_group not in groups:
                groups[help_group] = []
            groups[help_group].append((cmd_name, cmd))

        # Output each group in a consistent order (Commands first, then alphabetically)
        sorted_groups = sorted(groups.keys(), key=lambda g: (g != "Commands", g))
        for group_name in sorted_groups:
            command_rows = _rows(groups[group_name])
            if command_rows:
                with formatter.section(group_name):
                    formatter.write_dl(command_rows)


class LazyNestedGroup(click.Group):
    """A group with nested subcommands (supports recursive nesting)."""

    def __init__(self, base: click.Group, specs: dict[str, CommandSpec]) -> None:
        super().__init__(
            name=base.name,
            callback=base.callback,
            params=base.params,
            help=base.help,
            short_help=base.short_help,
            epilog=base.epilog,
            invoke_without_command=getattr(base, "invoke_without_command", False),
            no_args_is_help=getattr(base, "no_args_is_help", False),
            context_settings=base.context_settings,
        )
        self._specs = specs

    def list_commands(self, ctx: click.Context) -> list[str]:
        return sorted(self._specs)

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        spec = self._specs.get(cmd_name)
        if spec is None:
            return None
        return load_click_command(spec)

    def format_commands(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        """Format help with commands grouped by their HelpGroup."""

        def _rows(items: list[tuple[str, click.Command]]) -> list[tuple[str, str]]:
            if not items:
                return []
            limit = formatter.width - 6 - max(len(name) for name, _ in items)
            return [(name, cmd.get_short_help_str(limit)) for name, cmd in items]

        # Group commands by their HelpGroup
        groups: dict[str, list[tuple[str, click.Command]]] = {}
        for cmd_name in sorted(self._specs):
            cmd = self.get_command(ctx, cmd_name)
            if cmd is None or cmd.hidden:
                continue
            spec = self._specs[cmd_name]
            help_group = spec.help_group
            if help_group not in groups:
                groups[help_group] = []
            groups[help_group].append((cmd_name, cmd))

        # Output each group in a consistent order (Commands first, then alphabetically)
        sorted_groups = sorted(groups.keys(), key=lambda g: (g != "Commands", g))
        for group_name in sorted_groups:
            command_rows = _rows(groups[group_name])
            if command_rows:
                with formatter.section(group_name):
                    formatter.write_dl(command_rows)


class RootCommand(click.Group):
    def __init__(self, commands_dir: Path, app_context: dict | None = None) -> None:
        super().__init__(name=app_context.get("COMMAND_NAME", "your_cli") if app_context else "your_cli")

        self._commands_dir = commands_dir
        self._specs = discover_specs(commands_dir)
        self._app_context = app_context or {}
        # Add --version option
        self.params.append(
            click.Option(
                ["--version"],
                is_flag=True,
                expose_value=False,
                is_eager=True,
                help="Show the version and exit.",
                callback=self._version_callback,
            )
        )

    def invoke(self, ctx: click.Context) -> None:
        """Invoke the command and attach app context to Click context."""
        ctx.obj = self._app_context
        return super().invoke(ctx)

    def _version_callback(self, ctx: click.Context, param: click.Parameter, value: bool) -> None:
        """Print version and exit if --version flag is provided."""
        if not value or ctx.resilient_parsing:
            return
        # Get version from app context, fallback to __version__ if not available
        version = self._app_context.get("VERSION", __version__)
        click.echo(f"{version}")
        ctx.exit()

    def list_commands(self, ctx: click.Context) -> list[str]:
        return sorted(self._specs)

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        group_spec = self._specs.get(cmd_name)
        if group_spec is None:
            return None

        # If disabled, return a stub group that exits with an error.
        if not group_spec.enabled:

            @click.group(name=cmd_name, hidden=True)
            def disabled_group() -> None:
                click.echo(f"Command group '{cmd_name}' is disabled.", err=True)
                raise SystemExit(1)

            return disabled_group

        if group_spec.entry_path is not None:
            if group_spec.subcommands:
                # Has both entry.py and subcommands - load as group and wrap
                base_group = load_click_group(cmd_name, group_spec.entry_path, group_spec.import_command)
                group: click.Group | click.Command = LazyPluginGroup(base_group, group_spec.subcommands)
            else:
                # Has entry.py but no subcommands - standalone command
                group = load_click_command_from_entry(cmd_name, group_spec.entry_path, group_spec.import_command)
        else:
            # No entry.py - must have subcommands
            group = LazySubGroup(cmd_name, group_spec.subcommands)

        if group_spec.help_summary:
            # Always use meta.yaml help text, overriding any docstring
            group.short_help = group_spec.help_summary
            group.help = group_spec.help_summary

        # Apply hidden flag
        group.hidden = group_spec.hidden

        return group

    def format_commands(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        """Format root help with commands grouped by their HelpGroup."""

        def _rows(items: list[tuple[str, click.Command]]) -> list[tuple[str, str]]:
            if not items:
                return []
            limit = formatter.width - 6 - max(len(name) for name, _ in items)
            return [(name, cmd.get_short_help_str(limit)) for name, cmd in items]

        # Group commands by their HelpGroup
        groups: dict[str, list[tuple[str, click.Command]]] = {}
        for cmd_name in sorted(self._specs):
            cmd = self.get_command(ctx, cmd_name)
            if cmd is None or cmd.hidden:
                continue
            group_spec = self._specs[cmd_name]
            help_group = group_spec.help_group
            if help_group not in groups:
                groups[help_group] = []
            groups[help_group].append((cmd_name, cmd))

        # Output each group in a consistent order (Commands first, then alphabetically)
        sorted_groups = sorted(groups.keys(), key=lambda g: (g != "Commands", g))
        for group_name in sorted_groups:
            command_rows = _rows(groups[group_name])
            if command_rows:
                with formatter.section(group_name):
                    formatter.write_dl(command_rows)
