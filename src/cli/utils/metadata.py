"""
Metadata and constants for the application.

Not fully used yet.
"""

from __future__ import annotations

import sys
import tomllib
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import click

DEFAULT_PACKAGE_NAME = "foxy"
DEFAULT_APP_NAME = "Foxy"
DEFAULT_COMMAND_NAME = "foxy"
DEFAULT_ENV_PREFIX = "FOXY_"
ENV_PREFIX_SUFFIX = "_"


def _load_pyproject() -> dict[object, object]:
    pyproject_path = Path(__file__).resolve().parents[3] / "pyproject.toml"
    try:
        data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    if isinstance(data, dict):
        return data
    return {}


PYPROJECT = _load_pyproject()


def _tool_foxy_table() -> dict[object, object]:
    tool = PYPROJECT.get("tool")
    if not isinstance(tool, dict):
        return {}
    foxy = tool.get("foxy")
    if not isinstance(foxy, dict):
        return {}
    return foxy


def _project_table() -> dict[object, object]:
    project = PYPROJECT.get("project")
    if not isinstance(project, dict):
        return {}
    return project


def _normalize_env_prefix(prefix: str) -> str:
    normalized = prefix.strip().upper()
    if not normalized:
        return DEFAULT_ENV_PREFIX
    if not normalized.endswith(ENV_PREFIX_SUFFIX):
        normalized = f"{normalized}{ENV_PREFIX_SUFFIX}"
    return normalized


def _load_env_prefix() -> str:
    env_prefix = _tool_foxy_table().get("env_prefix")
    if not isinstance(env_prefix, str):
        return DEFAULT_ENV_PREFIX
    return _normalize_env_prefix(env_prefix)


def _load_app_name() -> str:
    app_name = _tool_foxy_table().get("name")
    if not isinstance(app_name, str):
        return DEFAULT_APP_NAME
    normalized = app_name.strip()
    if not normalized:
        return DEFAULT_APP_NAME
    return normalized


def _load_command_name() -> str:
    command_name = _tool_foxy_table().get("cli_name")
    if not isinstance(command_name, str):
        return DEFAULT_COMMAND_NAME
    normalized = command_name.strip()
    if not normalized:
        return DEFAULT_COMMAND_NAME
    return normalized


def _load_package_name() -> str:
    project_name = _project_table().get("name")
    if not isinstance(project_name, str):
        return DEFAULT_PACKAGE_NAME
    normalized = project_name.strip()
    if not normalized:
        return DEFAULT_PACKAGE_NAME
    return normalized


class Metadata:
    """Centralized metadata and constants for the application."""

    # Core identifiers
    PACKAGE_NAME = _load_package_name()  # pip package name (kebab-case)
    APP_NAME = _load_app_name()  # Branded display name
    COMMAND_NAME = _load_command_name()  # CLI command (lowercase, no spaces)

    # Derived at runtime
    try:
        VERSION = version(PACKAGE_NAME)
    except PackageNotFoundError:
        # Raise a click exception. Something is wrong.
        raise click.ClickException(f"Package '{PACKAGE_NAME}' not found. Ensure it is installed correctly.") from None

    # Paths
    PACKAGE_ROOT_DIR = Path(__file__).resolve().parent.parent
    COMMANDS_DIR = PACKAGE_ROOT_DIR / "commands"
    ENV_PREFIX = _load_env_prefix()

    # Runtime
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
