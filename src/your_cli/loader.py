"""Command discovery and lazy loading for your_cli."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import util
from pathlib import Path

import click
import yaml


@dataclass(frozen=True)
class CommandSpec:
    command: str
    subcommand: str
    entry_path: Path
    meta_path: Path
    import_command: str
    import_subcommand: str


def _safe_name(name: str) -> str:
    return name.replace("_", "-")


def load_meta(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - surface any parse error
        raise RuntimeError(f"Invalid meta.yaml at {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"Invalid meta.yaml at {path}: expected mapping")
    short_help = data.get("shortHelp")
    if not isinstance(short_help, str) or not short_help.strip():
        raise RuntimeError(f"Invalid meta.yaml at {path}: shortHelp must be a non-empty string")
    return data


def discover_specs(commands_dir: Path) -> dict[str, dict[str, CommandSpec]]:
    errors: list[str] = []
    specs: dict[str, dict[str, CommandSpec]] = {}
    if not commands_dir.exists():
        return specs

    for command_dir in sorted(p for p in commands_dir.iterdir() if p.is_dir()):
        command_name = _safe_name(command_dir.name)
        import_command = command_dir.name
        for sub_dir in sorted(p for p in command_dir.iterdir() if p.is_dir()):
            sub_name = _safe_name(sub_dir.name)
            import_subcommand = sub_dir.name
            entry_path = sub_dir / "entry.py"
            meta_path = sub_dir / "meta.yaml"
            missing: list[str] = []
            if not entry_path.is_file():
                missing.append("entry.py")
            if not meta_path.is_file():
                missing.append("meta.yaml")
            if missing:
                errors.append(f"{command_dir.name}/{sub_dir.name}: missing {', '.join(missing)}")
                continue
            try:
                load_meta(meta_path)
            except RuntimeError as exc:
                errors.append(str(exc))
                continue
            specs.setdefault(command_name, {})[sub_name] = CommandSpec(
                command=command_name,
                subcommand=sub_name,
                entry_path=entry_path,
                meta_path=meta_path,
                import_command=import_command,
                import_subcommand=import_subcommand,
            )

    if errors:
        message = "Invalid command plugins detected:\n" + "\n".join(f"- {err}" for err in errors)
        raise RuntimeError(message)
    return specs


def load_click_command(spec: CommandSpec) -> click.Command:
    meta = load_meta(spec.meta_path)
    module_name = f"your_cli.commands.{spec.import_command}.{spec.import_subcommand}.entry"
    module_spec = util.spec_from_file_location(module_name, spec.entry_path)
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError(f"Failed to import entry.py at {spec.entry_path}")
    module = util.module_from_spec(module_spec)
    try:
        module_spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - surface any import error
        raise RuntimeError(f"Failed to import entry.py at {spec.entry_path}: {exc}") from exc
    cli = getattr(module, "cli", None)
    if not isinstance(cli, click.core.Command):
        raise RuntimeError(f"{spec.entry_path} must export 'cli' as a click.Command")
    cli.short_help = meta["shortHelp"]
    cli.help = meta["shortHelp"]
    return cli


class LazySubGroup(click.Group):
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


class RootCommand(click.Group):
    def __init__(self, commands_dir: Path, dev_group: click.Group) -> None:
        super().__init__(name="your-cli")
        self._commands_dir = commands_dir
        self._dev_group = dev_group
        self._specs = discover_specs(commands_dir)

    def list_commands(self, ctx: click.Context) -> list[str]:
        dynamic = sorted(self._specs)
        return sorted(dynamic + ["dev"])

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        if cmd_name == "dev":
            return self._dev_group
        specs = self._specs.get(cmd_name)
        if specs is None:
            return None
        return LazySubGroup(cmd_name, specs)
