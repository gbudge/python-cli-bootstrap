"""Metadata and derived configuration for the CLI."""

from __future__ import annotations

import re
import sys
from collections.abc import Mapping
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import click
import tomllib

PREFERRED_TOOL_METADATA_SECTION = "cli"
LEGACY_TOOL_METADATA_SECTIONS = ("foxy",)
METADATA_TOOL_FIELDS = frozenset({"name", "cli_name", "env_prefix"})

DEFAULT_PACKAGE_NAME = "cli"
DEFAULT_APP_NAME = "CLI"
DEFAULT_COMMAND_NAME = "cli"
DEFAULT_ENV_PREFIX = "CLI_"
ENV_PREFIX_SUFFIX = "_"
CONSOLE_SCRIPT_TARGET = "cli.main:main"
PyprojectTable = Mapping[str, object]


def _pyproject_path() -> Path:
    return Path(__file__).resolve().parents[3] / "pyproject.toml"


def _normalized_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _load_pyproject(pyproject_path: Path | None = None) -> dict[str, object]:
    path = pyproject_path or _pyproject_path()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    if isinstance(data, dict) and all(isinstance(key, str) for key in data):
        return data
    return {}


PYPROJECT = _load_pyproject()


def project_table(pyproject: PyprojectTable = PYPROJECT) -> PyprojectTable:
    project = pyproject.get("project")
    if not isinstance(project, dict):
        return {}
    return project


def tool_tables(pyproject: PyprojectTable = PYPROJECT) -> dict[str, PyprojectTable]:
    tool = pyproject.get("tool")
    if not isinstance(tool, dict):
        return {}

    tables: dict[str, PyprojectTable] = {}
    for key, value in tool.items():
        if isinstance(key, str) and isinstance(value, dict):
            tables[key] = value
    return tables


def tool_metadata_section_name(pyproject: PyprojectTable = PYPROJECT) -> str | None:
    tables = tool_tables(pyproject)
    if PREFERRED_TOOL_METADATA_SECTION in tables:
        return PREFERRED_TOOL_METADATA_SECTION

    for section_name in LEGACY_TOOL_METADATA_SECTIONS:
        if section_name in tables:
            return section_name

    for section_name, table in tables.items():
        if any(field in table for field in METADATA_TOOL_FIELDS):
            return section_name

    return None


def tool_metadata_table(pyproject: PyprojectTable = PYPROJECT) -> PyprojectTable:
    section_name = tool_metadata_section_name(pyproject)
    if section_name is None:
        return {}
    return tool_tables(pyproject).get(section_name, {})


def _configured_tool_metadata_value(key: str, pyproject: PyprojectTable = PYPROJECT) -> str | None:
    return _normalized_string(tool_metadata_table(pyproject).get(key))


def script_name_from_pyproject(pyproject: PyprojectTable = PYPROJECT) -> str | None:
    scripts = project_table(pyproject).get("scripts")
    if not isinstance(scripts, dict) or not scripts:
        return None

    matching = [
        name
        for name, target in scripts.items()
        if isinstance(name, str) and isinstance(target, str) and target.strip() == CONSOLE_SCRIPT_TARGET
    ]
    if len(matching) == 1:
        return _normalized_string(matching[0])

    if len(scripts) == 1:
        return _normalized_string(next(iter(scripts)))

    return None


def package_name_from_pyproject(pyproject: PyprojectTable = PYPROJECT) -> str:
    return _normalized_string(project_table(pyproject).get("name")) or DEFAULT_PACKAGE_NAME


def app_name_from_pyproject(pyproject: PyprojectTable = PYPROJECT) -> str:
    return (
        _configured_tool_metadata_value("name", pyproject) or package_name_from_pyproject(pyproject) or DEFAULT_APP_NAME
    )


def command_name_from_pyproject(pyproject: PyprojectTable = PYPROJECT) -> str:
    return (
        _configured_tool_metadata_value("cli_name", pyproject)
        or script_name_from_pyproject(pyproject)
        or package_name_from_pyproject(pyproject)
        or DEFAULT_COMMAND_NAME
    )


def _normalize_env_prefix(prefix: str) -> str:
    normalized = prefix.strip().upper()
    if not normalized:
        return DEFAULT_ENV_PREFIX
    if not normalized.endswith(ENV_PREFIX_SUFFIX):
        normalized = f"{normalized}{ENV_PREFIX_SUFFIX}"
    return normalized


def env_prefix_from_command_name(command_name: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", command_name.strip()).strip("_").upper()
    if not normalized:
        return DEFAULT_ENV_PREFIX
    return f"{normalized}{ENV_PREFIX_SUFFIX}"


def env_prefix_from_pyproject(pyproject: PyprojectTable = PYPROJECT) -> str:
    env_prefix = _configured_tool_metadata_value("env_prefix", pyproject)
    if env_prefix is not None:
        return _normalize_env_prefix(env_prefix)
    return env_prefix_from_command_name(command_name_from_pyproject(pyproject))


def user_config_dir(package_name: str) -> Path:
    normalized = package_name.strip() or DEFAULT_PACKAGE_NAME
    return Path.home() / f".{normalized}"


class Metadata:
    """Centralized metadata and constants for the application."""

    PACKAGE_NAME = package_name_from_pyproject()
    APP_NAME = app_name_from_pyproject()
    COMMAND_NAME = command_name_from_pyproject()
    ENV_PREFIX = env_prefix_from_pyproject()
    TOOL_METADATA_SECTION = tool_metadata_section_name() or PREFERRED_TOOL_METADATA_SECTION

    try:
        VERSION = version(PACKAGE_NAME)
    except PackageNotFoundError:
        raise click.ClickException(f"Package '{PACKAGE_NAME}' not found. Ensure it is installed correctly.") from None

    PACKAGE_ROOT_DIR = Path(__file__).resolve().parent.parent
    COMMANDS_DIR = PACKAGE_ROOT_DIR / "commands"
    USER_CONFIG_DIR = user_config_dir(PACKAGE_NAME)
    USER_COMMANDS_DIR = USER_CONFIG_DIR / "commands"

    PYTHON_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    IS_TTY = sys.stdout.isatty()

    @classmethod
    def banner(cls) -> str:
        """Generate application banner."""
        return f"{cls.APP_NAME} v{cls.VERSION}"

    @classmethod
    def full_version(cls) -> str:
        """Detailed version information."""
        return f"{cls.APP_NAME} {cls.VERSION}\nPython {cls.PYTHON_VERSION}\nPackage: {cls.PACKAGE_NAME}"

    @classmethod
    def env_var(cls, name: str) -> str:
        """Build an environment variable name using the configured prefix."""
        return f"{cls.ENV_PREFIX}{name}"
