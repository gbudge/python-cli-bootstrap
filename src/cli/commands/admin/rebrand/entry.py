"""Rebrand the CLI display name and executable command."""

from __future__ import annotations

import os
import re
from pathlib import Path

import click
import tomllib

from cli.utils.metadata import (
    CONSOLE_SCRIPT_TARGET,
    LEGACY_TOOL_METADATA_SECTIONS,
    PREFERRED_TOOL_METADATA_SECTION,
    Metadata,
    app_name_from_pyproject,
    command_name_from_pyproject,
    env_prefix_from_command_name,
    env_prefix_from_pyproject,
    package_name_from_pyproject,
    tool_metadata_section_name,
    tool_metadata_table,
    user_config_dir,
)

CLI_COMMAND_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
TEXT_REWRITE_EXCLUDED_DIR_NAMES = frozenset(
    {
        ".git",
        ".hg",
        ".mypy_cache",
        ".nox",
        ".pytest_cache",
        ".ruff_cache",
        ".svn",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "venv",
    }
)
DIRECTLY_REWRITTEN_PATHS = frozenset(
    {
        Path("pyproject.toml"),
        Path("src/cli/utils/metadata.py"),
    }
)


class BrandState:
    def __init__(  # noqa: PLR0913
        self,
        *,
        app_name: str,
        command_name: str,
        env_prefix: str,
        metadata_package_name: str,
        project_package_name: str,
        script_name: str,
        tool_metadata_section: str | None,
    ) -> None:
        self.app_name = app_name
        self.command_name = command_name
        self.env_prefix = env_prefix
        self.metadata_package_name = metadata_package_name
        self.project_package_name = project_package_name
        self.script_name = script_name
        self.tool_metadata_section = tool_metadata_section


@click.command()
@click.option("--name", "display_name", required=True, help="New branded display name shown in help and metadata.")
@click.option("--cli", "--cli-cmd", "cli", required=True, help="New CLI command and package name.")
@click.option(
    "--skip-user",
    is_flag=True,
    help="Skip renaming the per-user ~/.<name> directory when the CLI/package name changes.",
)
@click.option("--confirm", is_flag=True, help="Skip the interactive confirmation prompt.")
def cli(display_name: str, cli: str, skip_user: bool, confirm: bool) -> None:
    """Rebrand the CLI display name and executable command."""
    new_app_name = _validate_display_name(display_name)
    new_command_name = _validate_cli_command(cli)
    project_root = _project_root()
    current = _read_brand_state(project_root)
    user_config_dir_paths = _user_config_dir_paths(current, new_command_name, skip_user)

    _echo_plan(current, new_app_name, new_command_name, user_config_dir_paths)
    if _is_noop(current, new_app_name, new_command_name):
        click.echo("Branding already matches the requested values.")
        return

    if user_config_dir_paths is not None:
        _validate_user_config_dir_rebrand(*user_config_dir_paths)

    if not confirm:
        click.confirm("Apply these changes?", default=False, abort=True)

    touched_paths = _apply_rebrand(project_root, current, new_app_name, new_command_name)
    renamed_user_config_dir = None
    if user_config_dir_paths is not None:
        renamed_user_config_dir = _rename_user_config_dir(*user_config_dir_paths)
    for path in touched_paths:
        click.echo(str(path.relative_to(project_root)))
    if renamed_user_config_dir is not None:
        source_dir, target_dir = renamed_user_config_dir
        click.echo(f"{_display_path(source_dir)} -> {_display_path(target_dir)}")


def _validate_display_name(value: str) -> str:
    display_name = value.strip()
    if not display_name:
        raise click.ClickException("--name must be a non-empty string.")
    if "\n" in display_name or "\r" in display_name:
        raise click.ClickException("--name must be a single line.")
    return display_name


def _validate_cli_command(value: str) -> str:
    command_name = value.strip().lower()
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
    tool_metadata = tool_metadata_table(pyproject)

    app_name = (
        _extract_tool_metadata_value(tool_metadata, "name")
        or _extract_metadata_constant(metadata_text, "APP_NAME")
        or app_name_from_pyproject(pyproject)
    )
    command_name = (
        _extract_tool_metadata_value(tool_metadata, "cli_name")
        or _extract_metadata_constant(metadata_text, "COMMAND_NAME")
        or command_name_from_pyproject(pyproject)
    )
    metadata_package_name = _extract_metadata_constant(metadata_text, "PACKAGE_NAME") or project_name

    return BrandState(
        app_name=app_name,
        command_name=command_name,
        env_prefix=env_prefix_from_pyproject(pyproject),
        metadata_package_name=metadata_package_name,
        project_package_name=package_name_from_pyproject(pyproject),
        script_name=script_name,
        tool_metadata_section=tool_metadata_section_name(pyproject),
    )


def _discover_script_name(scripts: dict[object, object], pyproject_path: Path) -> str:
    matching = [
        name
        for name, target in scripts.items()
        if isinstance(name, str) and isinstance(target, str) and target.strip() == CONSOLE_SCRIPT_TARGET
    ]
    if len(matching) == 1:
        return matching[0]
    if len(scripts) == 1:
        script_name = next(iter(scripts))
        if isinstance(script_name, str):
            return script_name
    raise click.ClickException(
        f"Expected exactly one console script targeting '{CONSOLE_SCRIPT_TARGET}' in {pyproject_path}."
    )


def _extract_metadata_constant(text: str, constant: str) -> str | None:
    pattern = re.compile(rf'(?m)^\s*{re.escape(constant)}\s*=\s*"([^"]*)".*$')
    match = pattern.search(text)
    if match is None:
        return None
    value = match.group(1).strip()
    return value or None


def _extract_tool_metadata_value(tool_metadata: object, key: str) -> str | None:
    if not isinstance(tool_metadata, dict):
        return None
    value = tool_metadata.get(key)
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _user_config_dir_paths(
    current: BrandState, new_command_name: str, skip_user: bool
) -> tuple[Path, Path] | None:
    if skip_user:
        return None

    current_user_config_dir = user_config_dir(current.project_package_name)
    new_user_config_dir = user_config_dir(new_command_name)
    if current_user_config_dir == new_user_config_dir:
        return None
    return current_user_config_dir, new_user_config_dir


def _echo_plan(
    current: BrandState,
    new_app_name: str,
    new_command_name: str,
    user_config_dir_paths: tuple[Path, Path] | None,
) -> None:
    click.echo(f"Display name: {current.app_name} -> {new_app_name}")
    click.echo(f"CLI command: {current.script_name} -> {new_command_name}")
    click.echo(f"Package name: {current.project_package_name} -> {new_command_name}")
    click.echo(f"Env prefix: {current.env_prefix} -> {env_prefix_from_command_name(new_command_name)}")
    if user_config_dir_paths is not None:
        current_user_config_dir, new_user_config_dir = user_config_dir_paths
        click.echo(f"User config dir: {_display_path(current_user_config_dir)} -> {_display_path(new_user_config_dir)}")


def _is_noop(current: BrandState, new_app_name: str, new_command_name: str) -> bool:
    return (
        current.app_name == new_app_name
        and current.command_name == new_command_name
        and current.env_prefix == env_prefix_from_command_name(new_command_name)
        and current.metadata_package_name == new_command_name
        and current.project_package_name == new_command_name
        and current.script_name == new_command_name
    )


def _apply_rebrand(project_root: Path, current: BrandState, new_app_name: str, new_command_name: str) -> list[Path]:
    touched_paths: list[Path] = []

    pyproject_path = project_root / "pyproject.toml"
    pyproject_text = _read_text(pyproject_path)
    rewritten_pyproject = _rewrite_pyproject(pyproject_text, current, new_app_name, new_command_name)
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

    for path in _iter_text_rewrite_paths(project_root):
        text = _read_optional_text(path)
        if text is None:
            continue
        rewritten = _rewrite_text_branding(text, current, new_app_name, new_command_name)
        if rewritten != text:
            path.write_text(rewritten, encoding="utf-8")
            touched_paths.append(path)

    return touched_paths


def _iter_text_rewrite_paths(project_root: Path) -> list[Path]:
    excluded_paths = {project_root / relative_path for relative_path in DIRECTLY_REWRITTEN_PATHS}
    candidates: list[Path] = []

    for root, dirnames, filenames in os.walk(project_root):
        dirnames[:] = [name for name in dirnames if name not in TEXT_REWRITE_EXCLUDED_DIR_NAMES]
        root_path = Path(root)
        for filename in filenames:
            path = root_path / filename
            if path in excluded_paths:
                continue
            candidates.append(path)

    return sorted(candidates, key=lambda path: path.relative_to(project_root).as_posix())


def _validate_user_config_dir_rebrand(source_dir: Path, target_dir: Path) -> None:
    if target_dir.exists():
        raise click.ClickException(f"Cannot rename user config directory because target already exists: {target_dir}")

    if source_dir.exists() and not source_dir.is_dir():
        raise click.ClickException(f"User config path is not a directory: {source_dir}")

    if not _has_directory_rename_permissions(source_dir, target_dir):
        raise click.ClickException(f"Cannot rename user config directory due to insufficient permissions: {source_dir}")


def _has_directory_rename_permissions(source_dir: Path, target_dir: Path) -> bool:
    for parent in (source_dir.parent, target_dir.parent):
        if not parent.is_dir():
            return False
        if not os.access(parent, os.W_OK | os.X_OK):
            return False
    return True


def _rename_user_config_dir(source_dir: Path, target_dir: Path) -> tuple[Path, Path] | None:
    if not source_dir.exists():
        return None

    try:
        source_dir.rename(target_dir)
    except OSError as exc:
        raise click.ClickException(
            f"Failed to rename user config directory '{source_dir}' to '{target_dir}': {exc.strerror or exc}"
        ) from exc
    return source_dir, target_dir


def _display_path(path: Path) -> str:
    home_dir = Path.home()
    try:
        relative_path = path.relative_to(home_dir)
    except ValueError:
        return str(path)

    return "~" if not relative_path.parts else f"~/{relative_path.as_posix()}"


def _rewrite_pyproject(text: str, current: BrandState, new_app_name: str, new_command_name: str) -> str:
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
        f'{new_command_name} = "{CONSOLE_SCRIPT_TARGET}"',
    )
    return _rewrite_tool_metadata_section(rewritten, current.tool_metadata_section, new_app_name, new_command_name)


def _rewrite_tool_metadata_section(
    text: str,
    current_section_name: str | None,
    new_app_name: str,
    new_command_name: str,
) -> str:
    rewritten = text
    target_section_name = PREFERRED_TOOL_METADATA_SECTION

    if (
        current_section_name
        and current_section_name != target_section_name
        and not _has_tool_section(rewritten, target_section_name)
    ):
        rewritten = _rename_tool_section(rewritten, current_section_name, target_section_name)

    rewritten = _upsert_tool_metadata_value(rewritten, target_section_name, "name", new_app_name)
    rewritten = _upsert_tool_metadata_value(rewritten, target_section_name, "cli_name", new_command_name)
    rewritten = _upsert_tool_metadata_value(
        rewritten,
        target_section_name,
        "env_prefix",
        env_prefix_from_command_name(new_command_name),
    )

    for legacy_section_name in LEGACY_TOOL_METADATA_SECTIONS:
        if legacy_section_name != target_section_name:
            rewritten = _remove_tool_section(rewritten, legacy_section_name)

    return rewritten


def _has_tool_section(text: str, section_name: str) -> bool:
    return _tool_section_pattern(section_name).search(text) is not None


def _rename_tool_section(text: str, old_section_name: str, new_section_name: str) -> str:
    pattern = re.compile(rf"(?m)^\[tool\.{re.escape(old_section_name)}\]$")
    rewritten, count = pattern.subn(f"[tool.{new_section_name}]", text, count=1)
    if count == 0:
        return text
    return rewritten


def _remove_tool_section(text: str, section_name: str) -> str:
    rewritten, count = _tool_section_pattern(section_name).subn("", text, count=1)
    if count == 0:
        return text
    rewritten = re.sub(r"\n{3,}", "\n\n", rewritten.rstrip())
    return f"{rewritten}\n"


def _tool_section_pattern(section_name: str) -> re.Pattern[str]:
    return re.compile(rf"(?ms)(^\[tool\.{re.escape(section_name)}\]\n)(.*?)(?=^\[|\Z)")


def _upsert_tool_metadata_value(text: str, section_name: str, key: str, value: str) -> str:
    section_pattern = _tool_section_pattern(section_name)
    section_match = section_pattern.search(text)
    rendered = f'{key} = "{_escape_toml(value)}"'

    if section_match is None:
        return f"{text.rstrip()}\n\n[tool.{section_name}]\n{rendered}\n"

    body = section_match.group(2)
    key_pattern = re.compile(rf'(?m)^{re.escape(key)}[ \t]*=[ \t]*"[^"]*"[ \t]*$')
    rewritten_body, count = key_pattern.subn(rendered, body, count=1)
    if count == 0:
        if rewritten_body and not rewritten_body.endswith("\n"):
            rewritten_body = f"{rewritten_body}\n"
        rewritten_body = f"{rewritten_body}{rendered}\n"

    return f"{text[: section_match.start(2)]}{rewritten_body}{text[section_match.end(2) :]}"


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
    new_env_prefix = env_prefix_from_command_name(new_command_name)

    if current.tool_metadata_section and current.tool_metadata_section != PREFERRED_TOOL_METADATA_SECTION:
        rewritten = rewritten.replace(
            f"[tool.{current.tool_metadata_section}]",
            f"[tool.{PREFERRED_TOOL_METADATA_SECTION}]",
        )

    if current.app_name != new_app_name:
        rewritten = rewritten.replace(current.app_name, new_app_name)

    if current.env_prefix != new_env_prefix:
        rewritten = rewritten.replace(current.env_prefix, new_env_prefix)

    rewritten = _replace_metadata_constant(rewritten, "PACKAGE_NAME", new_command_name)
    rewritten = _replace_metadata_constant(rewritten, "COMMAND_NAME", new_command_name)
    rewritten = _replace_metadata_constant(rewritten, "APP_NAME", new_app_name)

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
    for old_value in sorted(
        (value for value in old_values if value and value != new_command_name), key=len, reverse=True
    ):
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

    return f"{text[: section_match.start(2)]}{rewritten_body}{text[section_match.end(2) :]}"


def _read_text(path: Path) -> str:
    if not path.is_file():
        raise click.ClickException(f"Missing required file: {path}")
    return path.read_text(encoding="utf-8")


def _read_optional_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _escape_python(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _escape_toml(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
