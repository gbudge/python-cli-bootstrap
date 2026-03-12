"""Rebrand the CLI display name and executable command."""

from __future__ import annotations

import os
import re
from pathlib import Path

import click
import tomllib

from cli.utils.metadata import Metadata

CLI_COMMAND_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
TEXT_REWRITE_PATHS = (
    Path("uv.lock"),
    Path("README.md"),
    Path(".env-build.example"),
    Path(".env.example"),
    Path("src/cli/main.py"),
    Path("src/cli/commands/admin/entry.py"),
    Path("src/cli/commands/admin/meta.yaml"),
    Path("src/cli/commands/admin/new_command/entry.py"),
    Path("src/cli/commands/samples/entry.py"),
    Path("src/cli/utils/__init__.py"),
    Path("tests/test_coverage.py")
)


class BrandState:
    def __init__(
        self,
        *,
        app_name: str,
        command_name: str,
        metadata_package_name: str,
        project_package_name: str,
        script_name: str,
    ) -> None:
        self.app_name = app_name
        self.command_name = command_name
        self.metadata_package_name = metadata_package_name
        self.project_package_name = project_package_name
        self.script_name = script_name


@click.command()
@click.option("--name", "display_name", required=True, help="New branded display name shown in help and metadata.")
@click.option("--cli", "--cli-cmd", "cli", required=True, help="New CLI command and package name.")
@click.option("--confirm", is_flag=True, help="Skip the interactive confirmation prompt.")
def cli(display_name: str, cli: str, confirm: bool) -> None:
    """Rebrand the CLI display name and executable command."""
    new_app_name = _validate_display_name(display_name)
    new_command_name = _validate_cli_command(cli)
    project_root = _project_root()
    current = _read_brand_state(project_root)

    _echo_plan(current, new_app_name, new_command_name)
    if _is_noop(current, new_app_name, new_command_name):
        click.echo("Branding already matches the requested values.")
        return

    if not confirm:
        click.confirm("Apply these changes?", default=False, abort=True)

    touched_paths = _apply_rebrand(project_root, current, new_app_name, new_command_name)
    for path in touched_paths:
        click.echo(str(path.relative_to(project_root)))


def _validate_display_name(value: str) -> str:
    display_name = value.strip()
    if not display_name:
        raise click.ClickException("--name must be a non-empty string.")
    if "\n" in display_name or "\r" in display_name:
        raise click.ClickException("--name must be a single line.")
    return display_name


def _validate_cli_command(value: str) -> str:
    command_name = value.strip()
    if not CLI_COMMAND_PATTERN.fullmatch(command_name):
        raise click.ClickException(
            "--cli/--cli-cmd must use only letters, numbers, hyphens, and underscores, "
            "and must start with a letter or number."
        )
    return command_name


def _project_root() -> Path:
    override = os.environ.get(Metadata.env_var("REBRAND_PROJECT_ROOT"))
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[5]


def _read_brand_state(project_root: Path) -> BrandState:
    metadata_path = project_root / "src/cli/utils/metadata.py"
    pyproject_path = project_root / "pyproject.toml"

    metadata_text = _read_text(metadata_path)
    pyproject = tomllib.loads(_read_text(pyproject_path))

    project = pyproject.get("project")
    if not isinstance(project, dict):
        raise click.ClickException(f"Missing [project] table in {pyproject_path}.")

    project_name = project.get("name")
    if not isinstance(project_name, str) or not project_name.strip():
        raise click.ClickException(f"Missing project.name in {pyproject_path}.")

    scripts = project.get("scripts")
    if not isinstance(scripts, dict) or not scripts:
        raise click.ClickException(f"Missing [project.scripts] table in {pyproject_path}.")

    script_name = _discover_script_name(scripts, pyproject_path)

    tool_foxy = pyproject.get("tool")
    if isinstance(tool_foxy, dict):
        tool_foxy = tool_foxy.get("foxy")
    else:
        tool_foxy = None

    app_name = _extract_tool_foxy_value(tool_foxy, "name") or _extract_metadata_constant(metadata_text, "APP_NAME") or script_name
    command_name = (
        _extract_tool_foxy_value(tool_foxy, "cli_name")
        or _extract_metadata_constant(metadata_text, "COMMAND_NAME")
        or script_name
    )
    metadata_package_name = _extract_metadata_constant(metadata_text, "PACKAGE_NAME") or project_name

    return BrandState(
        app_name=app_name,
        command_name=command_name,
        metadata_package_name=metadata_package_name,
        project_package_name=project_name,
        script_name=script_name,
    )


def _discover_script_name(scripts: dict[object, object], pyproject_path: Path) -> str:
    matching = [name for name, target in scripts.items() if isinstance(name, str) and target == "cli.main:main"]
    if len(matching) == 1:
        return matching[0]
    if len(scripts) == 1:
        script_name = next(iter(scripts))
        if isinstance(script_name, str):
            return script_name
    raise click.ClickException(
        f"Expected exactly one console script targeting 'cli.main:main' in {pyproject_path}."
    )


def _extract_metadata_constant(text: str, constant: str) -> str | None:
    pattern = re.compile(rf'(?m)^\s*{re.escape(constant)}\s*=\s*"([^"]*)".*$')
    match = pattern.search(text)
    if match is None:
        return None
    value = match.group(1).strip()
    return value or None


def _extract_tool_foxy_value(tool_foxy: object, key: str) -> str | None:
    if not isinstance(tool_foxy, dict):
        return None
    value = tool_foxy.get(key)
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _echo_plan(current: BrandState, new_app_name: str, new_command_name: str) -> None:
    click.echo(f"Display name: {current.app_name} -> {new_app_name}")
    click.echo(f"CLI command: {current.script_name} -> {new_command_name}")
    click.echo(f"Package name: {current.project_package_name} -> {new_command_name}")


def _is_noop(current: BrandState, new_app_name: str, new_command_name: str) -> bool:
    return (
        current.app_name == new_app_name
        and current.command_name == new_command_name
        and current.metadata_package_name == new_command_name
        and current.project_package_name == new_command_name
        and current.script_name == new_command_name
    )


def _apply_rebrand(project_root: Path, current: BrandState, new_app_name: str, new_command_name: str) -> list[Path]:
    touched_paths: list[Path] = []

    pyproject_path = project_root / "pyproject.toml"
    pyproject_text = _read_text(pyproject_path)
    rewritten_pyproject = _rewrite_pyproject(pyproject_text, new_app_name, new_command_name)
    if rewritten_pyproject != pyproject_text:
        tomllib.loads(rewritten_pyproject)
        pyproject_path.write_text(rewritten_pyproject, encoding="utf-8")
        touched_paths.append(pyproject_path)

    metadata_path = project_root / "src/cli/utils/metadata.py"
    metadata_text = _read_text(metadata_path)
    rewritten_metadata = _rewrite_metadata(metadata_text, new_app_name, new_command_name)
    if rewritten_metadata != metadata_text:
        metadata_path.write_text(rewritten_metadata, encoding="utf-8")
        touched_paths.append(metadata_path)

    for relative_path in TEXT_REWRITE_PATHS:
        path = project_root / relative_path
        if not path.is_file():
            continue
        text = _read_text(path)
        rewritten = _rewrite_text_branding(text, current, new_app_name, new_command_name)
        if rewritten != text:
            path.write_text(rewritten, encoding="utf-8")
            touched_paths.append(path)

    return touched_paths


def _rewrite_pyproject(text: str, new_app_name: str, new_command_name: str) -> str:
    rewritten = _replace_first_in_section(
        "project",
        text,
        r'^name[ \t]*=[ \t]*"[^"]+"[ \t]*$',
        f'name = "{_escape_toml(new_command_name)}"',
    )
    rewritten = _replace_first_in_section(
        "project.scripts",
        rewritten,
        r'^[A-Za-z0-9_-]+[ \t]*=[ \t]*"cli\.main:main"[ \t]*$',
        f'{new_command_name} = "cli.main:main"',
    )
    rewritten = _upsert_tool_foxy_value(rewritten, "name", new_app_name)
    return _upsert_tool_foxy_value(rewritten, "cli_name", new_command_name)


def _upsert_tool_foxy_value(text: str, key: str, value: str) -> str:
    section_pattern = re.compile(r"(?ms)(^\[tool\.foxy\]\n)(.*?)(?=^\[|\Z)")
    section_match = section_pattern.search(text)
    rendered = f'{key} = "{_escape_toml(value)}"'

    if section_match is None:
        return f"{text.rstrip()}\n\n[tool.foxy]\n{rendered}\n"

    body = section_match.group(2)
    key_pattern = re.compile(rf'(?m)^{re.escape(key)}[ \t]*=[ \t]*"[^"]*"[ \t]*$')
    rewritten_body, count = key_pattern.subn(rendered, body, count=1)
    if count == 0:
        if rewritten_body and not rewritten_body.endswith("\n"):
            rewritten_body = f"{rewritten_body}\n"
        rewritten_body = f"{rewritten_body}{rendered}\n"

    return f"{text[:section_match.start(2)]}{rewritten_body}{text[section_match.end(2):]}"


def _rewrite_metadata(text: str, new_app_name: str, new_command_name: str) -> str:
    rewritten = _replace_metadata_constant(text, "PACKAGE_NAME", new_command_name)
    rewritten = _replace_metadata_constant(rewritten, "APP_NAME", new_app_name)
    return _replace_metadata_constant(rewritten, "COMMAND_NAME", new_command_name)


def _replace_metadata_constant(text: str, constant: str, value: str) -> str:
    pattern = re.compile(rf'(?m)^(\s*{re.escape(constant)}\s*=\s*)"[^"]*"(.*)$')

    def _replacement(match: re.Match[str]) -> str:
        return f'{match.group(1)}"{_escape_python(value)}"{match.group(2)}'

    rewritten, count = pattern.subn(_replacement, text, count=1)
    if count == 0:
        return text
    return rewritten


def _rewrite_text_branding(text: str, current: BrandState, new_app_name: str, new_command_name: str) -> str:
    rewritten = text
    if current.app_name != new_app_name:
        rewritten = rewritten.replace(current.app_name, new_app_name)

    if new_app_name != new_command_name:
        rewritten = rewritten.replace(f"`{new_app_name}`", f"`{new_command_name}`")
        rewritten = re.sub(
            rf"(?m)^#\s+{re.escape(new_app_name)}\s*$",
            f"# {new_command_name}",
            rewritten,
        )

    old_values = {
        current.command_name,
        current.metadata_package_name,
        current.project_package_name,
        current.script_name,
    }
    for old_value in sorted((value for value in old_values if value and value != new_command_name), key=len, reverse=True):
        rewritten = rewritten.replace(old_value, new_command_name)
    return rewritten


def _replace_first_in_section(section_name: str, text: str, pattern: str, replacement: str) -> str:
    section_pattern = re.compile(rf"(?ms)(^\[{re.escape(section_name)}\]\n)(.*?)(?=^\[|\Z)")
    section_match = section_pattern.search(text)
    if section_match is None:
        raise click.ClickException(f"Missing [{section_name}] section in pyproject.toml.")

    body = section_match.group(2)
    rewritten_body, count = re.subn(pattern, replacement, body, count=1, flags=re.MULTILINE)
    if count != 1:
        raise click.ClickException(f"Could not rewrite [{section_name}] in pyproject.toml.")

    return f"{text[:section_match.start(2)]}{rewritten_body}{text[section_match.end(2):]}"


def _read_text(path: Path) -> str:
    if not path.is_file():
        raise click.ClickException(f"Missing required file: {path}")
    return path.read_text(encoding="utf-8")


def _escape_python(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _escape_toml(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
