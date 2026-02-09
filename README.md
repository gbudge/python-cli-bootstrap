# your-cli

A small reference project that demonstrates a Click-based Python CLI with a simple *plugin-style* command discovery mechanism and modern tooling.

## Features

- **CLI framework**: [Click](https://click.palletsprojects.com/)
- **Dynamic command loading**: commands are discovered from the `src/your_cli/commands/` tree and loaded lazily at runtime
- **Package management**: [uv](https://docs.astral.sh/uv/) for fast dependency management
- **Code quality**: Ruff (lint + format) and Pyright (type checking)
- **Testing**: pytest (with coverage support)
- **Security**: pip-audit and bandit
- **Automation**: a Makefile with common tasks

## Quick start

### Prerequisites

Install [uv](https://docs.astral.sh/uv/).

### Setup

Create / sync the project environment (this installs the project in editable mode, including the `your-cli` console script):

```bash
make setup
```

### Run the CLI

```bash
uv run your-cli --help
uv run your-cli compute add 1 2
uv run your-cli net ping 1.1.1.1 --count 1
```

Notes:
- If you skip `make setup`, you can run `uv sync --locked --all-extras --dev` directly.
- To install explicitly (editable) and see post-install hints, run `make install`.
- The Python-module equivalent of `your-cli --help` is: `uv run python -m your_cli.main --help`.

## Commands

This repository includes example commands:

- `compute add <a> <b>`
- `compute sub <a> <b>`
- `net ping <host> [--count N]`

## Plugin contract (command discovery)

Commands are discovered from:

```
src/your_cli/commands/<command>/<subcommand>/
```

Each plugin directory must contain:

- `entry.py` (required): exports `cli`, a `click.Command` (typically created with `@click.command()`)
- `meta.yaml` (required): a YAML mapping containing a non-empty `shortHelp` string

At runtime, the root command lists available command groups and loads subcommands only when invoked.

### Developer utility: create a new plugin skeleton

```bash
uv run your-cli dev new-plugin compute mul --short-help "Multiply two integers."
```

If you want to generate plugins into a different directory during development, set:

- `YOUR_CLI_COMMANDS_DIR` (used by the `dev new-plugin` helper)

## Development tasks

```bash
make format
make lint
make test
make coverage
make scan
```

## Environment configuration

The Makefile supports environment-specific configuration via `.env` files:

- `.env` (base)
- `.env.local` (local overrides, gitignored)
- `.env.$(ENV)` (environment-specific; e.g. `.env.dev`, `.env.prod`)

Example:

```bash
ENV=prod make lint
```

## Project structure

```
.
├── src/
│   └── your_cli/
│       ├── commands/           # Dynamic command plugins
│       ├── dev.py              # Developer utilities ("your-cli dev …")
│       ├── loader.py           # Command discovery + lazy loader
│       └── main.py             # Console entry point
├── tests/
├── pyproject.toml
├── Makefile
└── README.md
```

## License

MIT
