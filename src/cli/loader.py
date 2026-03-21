"""Command discovery and lazy loading."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha1
from importlib import util
from pathlib import Path

import click
import yaml

from cli import __version__

IGNORED_COMMAND_DIR_PREFIXES = (".", "__")
DEFAULT_COMMAND_MODULE_BASE = "cli.commands"
USER_COMMAND_MODULE_PREFIX = "cli.user_commands"


@dataclass(frozen=True)
class CommandSpec:
    name: str
    entry_path: Path
    meta_path: Path
    import_path: list[str]  # Path segments for import (e.g., ["admin", "sdk", "add"])
    module_name: str
    hidden: bool
    enabled: bool
    help_group: str
    is_group: bool  # True if this is a group with subcommands
    subcommands: dict[str, CommandSpec] | None = None  # Nested subcommands if is_group=True
    no_args_is_help: bool = False


@dataclass(frozen=True)
class CommandGroupSpec:
    help_summary: str | None
    entry_path: Path | None
    module_name: str | None
    subcommands: dict[str, CommandSpec]
    hidden: bool
    enabled: bool
    help_group: str
    no_args_is_help: bool = False
    has_meta: bool = False


def _safe_name(name: str) -> str:
    return name.replace("_", "-")


def _build_module_name(module_base: str, import_path: list[str]) -> str:
    return f"{module_base}.{'.'.join(import_path)}.entry"


def user_command_module_base(commands_dir: Path) -> str:
    digest = sha1(str(commands_dir.expanduser().resolve()).encode("utf-8"), usedforsecurity=False).hexdigest()[:12]
    return f"{USER_COMMAND_MODULE_PREFIX}.{digest}"


def _should_ignore_command_dir(path: Path) -> bool:
    return path.name.startswith(IGNORED_COMMAND_DIR_PREFIXES)


def load_meta(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - surface any parse error
        raise RuntimeError(f"Invalid meta.yaml at {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"Invalid meta.yaml at {path}: expected mapping")

    # Support short_help and legacy aliases for backwards compatibility.
    help_summary = data.get("short_help") or data.get("HelpSummary") or data.get("shortHelp")
    if not isinstance(help_summary, str) or not help_summary.strip():
        raise RuntimeError(f"Invalid meta.yaml at {path}: short_help must be a non-empty string")

    # Normalize to short_help
    data["short_help"] = help_summary

    # Extract hidden, enabled, and help_group with defaults.
    data.setdefault("hidden", False)
    data.setdefault("enabled", True)
    data["help_group"] = data.get("help_group") or data.get("HelpGroup") or "Commands"
    data.setdefault("no_args_is_help", False)

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

    # Support short_help and legacy aliases for backwards compatibility.
    help_summary = data.get("short_help") or data.get("HelpSummary") or data.get("shortHelp")
    if help_summary is None:
        return None
    if not isinstance(help_summary, str) or not help_summary.strip():
        raise RuntimeError(f"Invalid meta.yaml at {path}: short_help must be a non-empty string")

    # Normalize to short_help
    data["short_help"] = help_summary

    # Extract hidden, enabled, and help_group with defaults.
    data.setdefault("hidden", False)
    data.setdefault("enabled", True)
    data["help_group"] = data.get("help_group") or data.get("HelpGroup") or "Commands"
    data.setdefault("no_args_is_help", False)

    # If disabled, override hidden to True
    if not data["enabled"]:
        data["hidden"] = True

    return data


def _discover_nested_commands(
    base_dir: Path,
    import_path: list[str],
    module_base: str,
    remaining_depth: int,
    errors: list[str],
) -> dict[str, CommandSpec]:
    """Recursively discover commands up to max_depth levels.

    Args:
        base_dir: Directory to scan for commands
        import_path: List of import segments leading to this directory
        remaining_depth: Remaining nesting depth allowance
        errors: List to accumulate error messages

    Returns:
        Dictionary of command name -> CommandSpec
    """
    if remaining_depth <= 0:
        return {}

    specs: dict[str, CommandSpec] = {}

    for sub_dir in sorted(p for p in base_dir.iterdir() if p.is_dir()):
        # Ignore interpreter / tooling artefacts and support directories.
        if _should_ignore_command_dir(sub_dir):
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
            module_base,
            remaining_depth - 1,
            errors,
        )

        # Determine if this is a group or terminal command
        is_group = len(nested_specs) > 0

        specs[cmd_name] = CommandSpec(
            name=cmd_name,
            entry_path=entry_path,
            meta_path=meta_path,
            import_path=nested_import_path,
            module_name=_build_module_name(module_base, nested_import_path),
            hidden=meta["hidden"],
            enabled=meta["enabled"],
            help_group=meta["help_group"],
            no_args_is_help=meta["no_args_is_help"],
            is_group=is_group,
            subcommands=nested_specs if is_group else None,
        )

    return specs


def discover_specs(
    commands_dir: Path,
    max_depth: int = 5,
    module_base: str = DEFAULT_COMMAND_MODULE_BASE,
) -> dict[str, CommandGroupSpec]:
    """Discover command groups with nested subcommands up to max_depth levels."""
    errors: list[str] = []
    specs: dict[str, CommandGroupSpec] = {}
    if not commands_dir.exists():
        return specs

    for command_dir in sorted(p for p in commands_dir.iterdir() if p.is_dir()):
        # Ignore interpreter / tooling artefacts and support directories.
        if _should_ignore_command_dir(command_dir):
            continue

        command_name = _safe_name(command_dir.name)
        import_command = command_dir.name

        group_help_summary: str | None = None
        group_hidden = False
        group_enabled = True
        group_help_group = "Commands"
        group_no_args_is_help = False
        try:
            group_meta = load_group_meta(command_dir / "meta.yaml")
        except RuntimeError as exc:
            errors.append(str(exc))
            group_meta = None
        if group_meta is not None:
            group_help_summary = group_meta["short_help"].strip()
            group_hidden = group_meta["hidden"]
            group_enabled = group_meta["enabled"]
            group_help_group = group_meta["help_group"]
            group_no_args_is_help = group_meta["no_args_is_help"]

        group_entry_path = command_dir / "entry.py"
        if not group_entry_path.is_file():
            group_entry_path = None

        # Discover nested subcommands recursively
        sub_specs = _discover_nested_commands(
            command_dir,
            [import_command],
            module_base,
            remaining_depth=max_depth,
            errors=errors,
        )

        # Include groups that have:
        # - at least one valid subcommand, OR
        # - an entry.py file (allowing standalone commands)
        if sub_specs or group_entry_path is not None:
            specs[command_name] = CommandGroupSpec(
                help_summary=group_help_summary,
                entry_path=group_entry_path,
                module_name=_build_module_name(module_base, [import_command]) if group_entry_path is not None else None,
                subcommands=sub_specs,
                hidden=group_hidden,
                enabled=group_enabled,
                help_group=group_help_group,
                no_args_is_help=group_no_args_is_help,
                has_meta=group_meta is not None,
            )

    if errors:
        message = "Invalid command plugins detected:\n" + "\n".join(f"- {err}" for err in errors)
        raise RuntimeError(message)
    return specs


def _merge_command_specs(existing: CommandSpec, incoming: CommandSpec) -> CommandSpec:
    if existing.is_group and incoming.is_group:
        merged_subcommands = _merge_command_maps(existing.subcommands or {}, incoming.subcommands or {})
        return CommandSpec(
            name=incoming.name,
            entry_path=incoming.entry_path,
            meta_path=incoming.meta_path,
            import_path=incoming.import_path,
            module_name=incoming.module_name,
            hidden=incoming.hidden,
            enabled=incoming.enabled,
            help_group=incoming.help_group,
            is_group=True,
            subcommands=merged_subcommands,
            no_args_is_help=incoming.no_args_is_help,
        )
    return incoming


def _merge_command_maps(
    existing: dict[str, CommandSpec],
    incoming: dict[str, CommandSpec],
) -> dict[str, CommandSpec]:
    merged = dict(existing)
    for name, spec in incoming.items():
        current = merged.get(name)
        merged[name] = spec if current is None else _merge_command_specs(current, spec)
    return merged


def _merge_group_specs(existing: CommandGroupSpec, incoming: CommandGroupSpec) -> CommandGroupSpec:
    merged_subcommands = _merge_command_maps(existing.subcommands, incoming.subcommands)

    if incoming.has_meta:
        help_summary = incoming.help_summary
        hidden = incoming.hidden
        enabled = incoming.enabled
        help_group = incoming.help_group
        no_args_is_help = incoming.no_args_is_help
    else:
        help_summary = existing.help_summary
        hidden = existing.hidden
        enabled = existing.enabled
        help_group = existing.help_group
        no_args_is_help = existing.no_args_is_help

    entry_path = incoming.entry_path if incoming.entry_path is not None else existing.entry_path
    module_name = incoming.module_name if incoming.entry_path is not None else existing.module_name

    return CommandGroupSpec(
        help_summary=help_summary,
        entry_path=entry_path,
        module_name=module_name,
        subcommands=merged_subcommands,
        hidden=hidden,
        enabled=enabled,
        help_group=help_group,
        no_args_is_help=no_args_is_help,
        has_meta=existing.has_meta or incoming.has_meta,
    )


def discover_merged_specs(
    command_roots: Sequence[tuple[Path, str]],
    max_depth: int = 5,
) -> dict[str, CommandGroupSpec]:
    specs: dict[str, CommandGroupSpec] = {}
    seen_roots: set[Path] = set()

    for commands_dir, module_base in command_roots:
        resolved_dir = commands_dir.expanduser().resolve()
        if resolved_dir in seen_roots:
            continue
        seen_roots.add(resolved_dir)

        discovered = discover_specs(commands_dir, max_depth=max_depth, module_base=module_base)
        for name, group_spec in discovered.items():
            current = specs.get(name)
            specs[name] = group_spec if current is None else _merge_group_specs(current, group_spec)

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
    module_spec = util.spec_from_file_location(spec.module_name, spec.entry_path)
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

    cli.short_help = meta["short_help"]
    cli.help = meta["short_help"]
    cli.hidden = spec.hidden
    cli.no_args_is_help = spec.no_args_is_help
    cli.name = spec.name
    return cli


def load_click_group(group_name: str, entry_path: Path, module_name: str) -> click.Group:
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


def load_click_command_from_entry(cmd_name: str, entry_path: Path, module_name: str) -> click.Command:
    """Load a click.Command or click.Group from entry.py."""
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
        """Format help with commands grouped by their help_group."""

        def _rows(items: list[tuple[str, click.Command]]) -> list[tuple[str, str]]:
            if not items:
                return []
            limit = formatter.width - 6 - max(len(name) for name, _ in items)
            return [(name, cmd.get_short_help_str(limit)) for name, cmd in items]

        # Group commands by their help_group.
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
        """Format help with commands grouped by their help_group."""

        def _rows(items: list[tuple[str, click.Command]]) -> list[tuple[str, str]]:
            if not items:
                return []
            limit = formatter.width - 6 - max(len(name) for name, _ in items)
            return [(name, cmd.get_short_help_str(limit)) for name, cmd in items]

        # Group commands by their help_group.
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
        """Format help with commands grouped by their help_group."""

        def _rows(items: list[tuple[str, click.Command]]) -> list[tuple[str, str]]:
            if not items:
                return []
            limit = formatter.width - 6 - max(len(name) for name, _ in items)
            return [(name, cmd.get_short_help_str(limit)) for name, cmd in items]

        # Group commands by their help_group.
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
    def __init__(
        self,
        commands_dir: Path,
        app_context: dict | None = None,
        extra_commands_dirs: Sequence[Path] | None = None,
    ) -> None:
        super().__init__(name=app_context.get("COMMAND_NAME", "cli") if app_context else "cli")

        self._commands_dir = commands_dir
        self._extra_commands_dirs = tuple(extra_commands_dirs or ())
        command_roots = [(commands_dir, DEFAULT_COMMAND_MODULE_BASE)]
        command_roots.extend((path, user_command_module_base(path)) for path in self._extra_commands_dirs)
        self._specs = discover_merged_specs(command_roots)
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
                base_group = load_click_group(cmd_name, group_spec.entry_path, group_spec.module_name or cmd_name)
                group: click.Group | click.Command = LazyPluginGroup(base_group, group_spec.subcommands)
            else:
                # Has entry.py but no subcommands - standalone command
                group = load_click_command_from_entry(
                    cmd_name, group_spec.entry_path, group_spec.module_name or cmd_name
                )
        else:
            # No entry.py - must have subcommands
            group = LazySubGroup(cmd_name, group_spec.subcommands)

        if group_spec.help_summary:
            # Always use meta.yaml help text, overriding any myclistring
            group.short_help = group_spec.help_summary
            group.help = group_spec.help_summary

        # Apply hidden flag
        group.hidden = group_spec.hidden
        group.no_args_is_help = group_spec.no_args_is_help

        return group

    def format_commands(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        """Format root help with commands grouped by their help_group."""

        def _rows(items: list[tuple[str, click.Command]]) -> list[tuple[str, str]]:
            if not items:
                return []
            limit = formatter.width - 6 - max(len(name) for name, _ in items)
            return [(name, cmd.get_short_help_str(limit)) for name, cmd in items]

        # Group commands by their help_group.
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
