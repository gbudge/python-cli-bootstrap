#!/usr/bin/env python3
"""A simple "Hello, World!" script."""

from pathlib import Path

import tomllib


def get_version() -> str:
    """Read version from pyproject.toml."""
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)
    return data["project"]["version"]


def main() -> None:
    """Prints "Hello, World!" and version to the console."""
    version = get_version()
    print(f"Hello, World! (v{version})")


if __name__ == "__main__":  # pragma: no cover
    main()
