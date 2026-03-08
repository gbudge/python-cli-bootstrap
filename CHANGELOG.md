# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog], and this project adheres to [Semantic Versioning].

## 1.3.0 - 2026-03-08

### Added
- New admin command templates for plugin scaffolding under `src/your_cli/commands/admin/new_command/.template/`.
- Support for `no_args_is_help` metadata in command/group loading and command registration.

### Changed
- Bumped project version to `1.3.0` in `pyproject.toml`.
- Refactored `admin new-command` generation flow to require `--short-help`, support hierarchical parent paths via `--parent`, and create safer/clearer plugin skeleton output.
- Standardized command metadata keys to snake_case (`short_help`, `help_group`) while keeping compatibility with legacy aliases.
- Updated command metadata defaults and visibility behavior across admin/sample command specs.
- Improved command discovery to ignore dot-prefixed support directories in addition to interpreter artifact directories.
- Expanded CLI/loader test coverage for nested generation, metadata validation, ignored directories, and new command options.
- Regenerated lockfile content and package source metadata in `uv.lock`.

## 1.2.0 - 2026-02-12

### Changed
- Various fixes/improvements and shuffling of directory layout.

## 1.1.0 - 2026-02-09

### Added
- New [Makefile] stage `install` for local editable developer install
- Additional [tests], improving code coverage to >90%

### Changed
- Numerous linting and formatting fixes
- Documentation in the [README.md] file
- Modified [Makefile] stage `clean` to also remove the `.venv` directory

## 1.0.0 - 2026-02-08

### Added
- Initial project structure with `src/` and `test/` directories
- Hello World example script (`src/hello-world.py`)
- Comprehensive Makefile with common development tasks
- uv-based dependency management
- Code quality tooling: Ruff (linting + formatting) and Pyright (type checking)
- Testing framework with pytest and pytest-cov
- Security scanning with pip-audit and bandit
- Environment-based configuration support (.env files)
- Test suite for hello-world module
- Project documentation (README.md)
- MIT License
- .gitignore for Python projects

## References
- [README.md]
- [CHANGELOG.md]
- [Makefile]
- [Source Code][src]
- [Test Cases][tests]

<!-- Markdown Links -->
[Keep a Changelog]: https://keepachangelog.com/en/1.1.0/
[Semantic Versioning]: https://semver.org/spec/v2.0.0.html
[Makefile]: Makefile
[README.md]: README.md
[CHANGELOG.md]: CHANGELOG.md
[tests]: tests/
[src]: src/
