# python-bootstrap

A simple Python project template with modern tooling and best practices.

## Features

- **Package Management**: [uv](https://docs.astral.sh/uv/) for fast, reliable dependency management
- **Code Quality**: Ruff for linting and formatting, Pyright for type checking
- **Testing**: pytest with coverage support
- **Security**: pip-audit and bandit for vulnerability scanning
- **Automation**: Makefile with common development tasks
- **Versioning**: bump for easily version increments

## Quick Start

### Prerequisites

Install [uv](https://docs.astral.sh/uv/):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Setup

```bash
# Install dependencies
make setup

# Run the full pipeline (clean, setup, format, lint, test, scan)
make all
```

## Development

### Install

```bash
pip install -e .
```

### Usage

```bash
your-cli --help
your-cli compute add 1 2
your-cli dev new-plugin compute mul --short-help "Multiply two integers."
```

### Plugin contract

Plugins are discovered from `src/your_cli/commands/<command>/<subcommand>/`:

- `entry.py` (required) exports `cli`, a `click.Command` instance.
- `meta.yaml` (required) must be a YAML mapping with a non-empty `shortHelp`.

### Available Commands

```bash
  all              Run build & test pipeline
  build            Build sdist and wheel
  bump             Bump Z patch version (X.Y.Z -> X.Y.Z+1)
  bump-major       Bump X major version (X.Y.Z -> X+1.0.0)
  bump-minor       Bump Y minor version (X.Y.Z -> X.Y+1.0)
  check-uv         Check uv exists and print version
  clean            Remove build, cache and temp files
  format           Format code and apply fixes
  help             Show available make targets
  lint             Lint code and type-check
  package          Clean and build artifacts
  publish          Upload artifacts to PyPI
  scan             Scan for security issues
  setup            Install dependencies
  tests            Run test suite
  version          Show current version
```

### Environment Configuration

The project supports environment-specific configuration via `.env` files:

- `.env` - Base configuration
- `.env.local` - Local overrides (gitignored)
- `.env.$(ENV)` - Environment-specific (e.g., `.env.dev`, `.env.prod`)

Use `ENV=prod make <target>` to load environment-specific settings.

## Project Structure

```
.
├── src/                    # Source code
│   └── your_cli/           # CLI package
├── tests/                  # Test files
├── pyproject.toml          # Project configuration
├── Makefile                # Development automation
└── README.md
```

## License

MIT
