# Python CLI Bootstrap

A small reference project that demonstrates a Click-based Python CLI with a simple *plugin-style* command discovery mechanism and modern tooling.

## Features

- **CLI framework**: [Click](https://click.palletsprojects.com/)
- **Dynamic command loading**: commands are discovered from the `src/cli/commands/` tree and loaded lazily at runtime
- **Package management**: [uv](https://docs.astral.sh/uv/) for fast dependency management
- **Code quality**: Ruff (lint + format) and Pyright (type checking)
- **Testing**: pytest (with coverage support)
- **Security**: pip-audit and bandit
- **Automation**: a Makefile with common tasks

## Quick start

### Prerequisites

Install [uv](https://docs.astral.sh/uv/).

### Setup

Create / sync the project environment (this installs the project in editable mode, including the `mycli` console script):

```bash
make setup
```

### Run the CLI

```bash
uv run mycli --help
uv run mycli compute add 1 2
uv run mycli net ping 1.1.1.1 --count 1
```

Notes:
- If you skip `make setup`, you can run `uv sync --locked --all-extras --dev` directly.
- To install explicitly (editable) and see post-install hints, run `make install`.
- The Python-module equivalent of `mycli --help` is: `uv run python -m cli.main --help`.

## Commands

This repository includes example commands:

- `compute add <a> <b>`
- `compute sub <a> <b>`
- `net ping <host> [--count N]`

## Plugin contract (command discovery)

Commands are discovered from:

```
src/cli/commands/<...nested command path...>/
```

Each plugin directory must contain:

- `entry.py` (required): exports `cli`, a `click.Command` (typically created with `@click.command()`)
- `meta.yaml` (required): a YAML mapping containing a non-empty `short_help` string

Supported `meta.yaml` keys:

- `short_help` (required)
- `help_group` (optional, default: `Commands`)
- `enabled` (optional, default: `true`)
- `hidden` (optional, default: `false`; forced to `true` when `enabled: false`)
- `packaged` (optional; used for packaging workflows)
- `no_args_is_help` (optional, default: `false`)

Compatibility note: legacy aliases (`shortHelp`, `HelpSummary`, `HelpGroup`) are still accepted by the loader.

At runtime, the root command lists available command groups and loads subcommands only when invoked.

Dot-prefixed and `__`-prefixed directories are ignored during command discovery.

### Developer utility: create a new command skeleton

```bash
uv run mycli admin new-command mul --short-help "Multiply two integers."
uv run mycli admin new-command mul --parent compute --short-help "Multiply two integers."
uv run mycli admin new-command issue --parent github.repo --short-help "Manage repository issues."
```

`--parent` uses dot-notation to create nested command paths (`github.repo` => `github/repo`).
Any missing parent groups are scaffolded automatically.

If you want to generate plugins into a different directory during development, set:

- `<ENV_PREFIX>COMMANDS_DIR` (used by the `admin new-command` helper)
- `<ENV_PREFIX>REBRAND_PROJECT_ROOT` (used by the `admin rebrand` helper)

The environment variable prefix is configurable in [`pyproject.toml`](pyproject.toml):

```toml
[tool.mycli]
env_prefix = "mycli_"
name = "mycli"
cli_name = "mycli"
```

With the default prefix this resolves to `mycli_COMMANDS_DIR`.

- `name`: branded display name used in CLI metadata output (for example, banner/version text)
- `cli_name`: command name used as the CLI program name

With the default prefix, supported override variables are:

- `mycli_COMMANDS_DIR`
- `mycli_REBRAND_PROJECT_ROOT`

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
│   └── cli/
│       ├── commands/           # Dynamic command plugins
│       ├── dev.py              # Developer utilities ("mycli dev …")
│       ├── loader.py           # Command discovery + lazy loader
│       └── main.py             # Console entry point
├── tests/
├── pyproject.toml
├── Makefile
└── README.md
```

## License

MIT
