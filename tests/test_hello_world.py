"""Tests for the hello-world module."""

import importlib.util
from pathlib import Path

# Load the hello-world module from src/ (has hyphen in name)
src_path = Path(__file__).parent.parent / "src" / "hello-world.py"
spec = importlib.util.spec_from_file_location("hello_world", src_path)
assert spec is not None, f"Failed to create module spec for {src_path}"
assert spec.loader is not None, f"Module spec has no loader for {src_path}"
hello_world = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hello_world)

main = hello_world.main


def test_main_prints_hello_world(capsys):
    """Test that main() prints 'Hello, World!' with version to stdout."""
    main()
    captured = capsys.readouterr()
    # Output should be in format "Hello, World! (v1.0.0)\n"
    assert captured.out.startswith("Hello, World! (v")
    assert captured.out.endswith(")\n")


def test_main_output_contains_version(capsys):
    """Test that main() output contains the correct version."""
    expected_version = hello_world.get_version()
    main()
    captured = capsys.readouterr()
    assert f"(v{expected_version})" in captured.out


def test_main_returns_none():
    """Test that main() returns None."""
    result = main()
    assert result is None
