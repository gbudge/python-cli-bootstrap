# Makefile for Python projects using uv (VS Code–first)
#
# Environment loading:
# - Loads (later overrides earlier):
#     .env-build
#     .env-build.local
#     .env-build.$(ENV)
#
# Help text convention (required):
# - Each target MUST have:
#     <target>: <deps><space><space>## <help text>
# - Exactly two spaces before `##`
# - Only matching lines appear in `make help`

SHELL := /bin/bash
.DEFAULT_GOAL := help

# ----------------------------------------------------------------------------
# Environment (.env-build support)
# ----------------------------------------------------------------------------

ENV ?= local

ENV_FILES := \
	.env-build \
	.env-build.local \
	.env-build.$(ENV)

-include $(ENV_FILES)

export $(shell sed -n 's/^\([A-Za-z_][A-Za-z0-9_]*\)=.*/\1/p' $(ENV_FILES) 2>/dev/null)

# ----------------------------------------------------------------------------
# Tooling defaults (override in .env-build)
# ----------------------------------------------------------------------------

UV            ?= uv
PYTHON        ?= python3
PYTEST        ?= pytest
RUFF          ?= ruff
PYRIGHT       ?= pyright
TWINE         ?= twine
PIP_AUDIT     ?= pip-audit
BANDIT        ?= bandit
BUMP          ?= bump

UV_SYNC_ARGS  ?= --all-extras --dev --locked
BUILD_ARGS    ?=
TEST_ARGS     ?=
COV_ARGS      ?= --cov --cov-report=term-missing --cov-report=xml --cov-report=html
PUBLISH_REPO  ?= pypi

# pip-audit args:
PIP_AUDIT_ARGS ?=

#
# Bandit args:
#  --configfile <file>        : specify config file (default: pyproject.toml)
#  --severity-level <level>   : report only issues at or above this severity (low, medium, high)
#  --confidence-level <level> : report only issues at or above this confidence level (low, medium, high)
#  --recursive <path>         : recursively scan directories from the path
#
BANDIT_ARGS ?= --configfile ./pyproject.toml --severity-level medium --confidence-level medium --recursive .

#
# Other
#
PACKAGE ?= $(shell $(PYTHON) -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['name'])" 2>/dev/null || echo .)
# Python import module name is typically the distribution name with '-' replaced by '_'
PACKAGE_MODULE ?= $(subst -,_,$(PACKAGE))

# ----------------------------------------------------------------------------
# Colors
# ----------------------------------------------------------------------------

YELLOW := \033[33m
CYAN   := \033[36m
GREEN  := \033[32m
RED    := \033[31m
BLUE   := \033[34m
RESET  := \033[0m

# ----------------------------------------------------------------------------
# Logging levels
# ----------------------------------------------------------------------------
INFO := [$(GREEN)INFO$(RESET)]
WARN := [$(YELLOW)WARN$(RESET)]
ERROR := [$(RED)ERROR$(RESET)]

# ----------------------------------------------------------------------------
# Guards
# ----------------------------------------------------------------------------

.PHONY: check-uv
check-uv:  ## Check uv exists and print version
	@command -v $(UV) >/dev/null 2>&1 || { \
		printf "$(ERROR) '$(UV)' command not found. Install from: $(BLUE)https://docs.astral.sh/uv/$(RESET)\n"; \
		exit 1; \
	}

	@printf "$(INFO) Using %s\n" "$$($(UV) --version)"

# ----------------------------------------------------------------------------
# Targets
# ----------------------------------------------------------------------------

.PHONY: help
help:  ## Show available make targets
	@printf "$(CYAN)Usage:$(RESET) make <target>\n\n"
	@printf "$(CYAN)Environment:$(RESET) ENV=$(ENV)\n"
	@printf "$(CYAN)Env files:$(RESET) $(ENV_FILES)\n\n"
	@printf "$(CYAN)Targets:$(RESET)\n"
	@awk 'BEGIN {FS=":.*  ## "} /^[a-zA-Z0-9_.-]+:.*  ## / {printf "  $(YELLOW)%-16s$(RESET) %s\n", $$1, $$2}' $(MAKEFILE_LIST) | sort

.PHONY: all
all: clean setup format lint coverage scan  ## Run build & test pipeline

.PHONY: clean
clean:  ## Remove build, cache and temp files
	@printf "$(INFO) Cleaning project artifacts and caches...\n"

	@rm -rf \
		.venv/ \
		.build/ \
		.build_excluded/ \
		.coverage \
		.dist/ \
		.mypy_cache/ \
		.pytest_cache/ \
		.ruff_cache/ \
		.tox/ \
		build/ \
		dist/ \
		htmlcov/ \
		site/ \
		coverage.xml \
		junit.xml \
		*.egg-info \
		**/*.egg-info
	@find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	@find . -type f -name "*.pyc" -delete
	@find . -type f -name "*.pyo" -delete
	@printf "$(INFO) Clean complete.\n\n"

.PHONY: setup
setup: check-uv  ## Install dependencies
	@printf "$(INFO) Upgrading pip in uv environment...\n"
	@$(UV) run pip install --upgrade pip

	@printf "$(INFO) Syncing uv environment with dependencies...\n"
	@$(UV) sync $(UV_SYNC_ARGS)

.PHONY: build
build: check-uv  ## Build sdist and wheel
	@printf "$(INFO) Building distribution artifacts...\n"
	@printf "$(INFO) Filtering commands for packaging...\n"
	@$(PYTHON) scripts/filter_commands.py prepare || { \
		printf "$(ERROR) Failed to filter commands\n"; \
		exit 1; \
	}
	@$(UV) build $(BUILD_ARGS) || { \
		printf "$(ERROR) Build failed, restoring commands...\n"; \
		$(PYTHON) scripts/filter_commands.py restore; \
		exit 1; \
	}
	@printf "$(INFO) Restoring excluded commands...\n"
	@$(PYTHON) scripts/filter_commands.py restore
	@printf "$(INFO) Build complete. Artifacts in 'dist/' directory.\n\n"

.PHONY: format
format: check-uv  ## Format code and apply fixes
	@printf "$(INFO) Formatting code...\n"
	@$(UV) run $(RUFF) format .
	@$(UV) run $(RUFF) check . --fix
	@printf "$(INFO) Formatting complete.\n\n"

.PHONY: lint
lint: check-uv  ## Lint code and type-check
	@printf "$(INFO) Linting code using ruff...\n"
	@$(UV) run $(RUFF) check .
	@printf "\n"

	@printf "$(INFO) Type-checking code using pyright...\n"
	@$(UV) run $(PYRIGHT)
	@printf "$(INFO) Type-checking complete.\n\n"

.PHONY: test
test: check-uv  ## Run test suite
	@printf "$(INFO) Running test suite...\n"
	@$(UV) run $(PYTEST) $(TEST_ARGS)
	@printf "$(INFO) Test suite complete.\n\n"

.PHONY: coverage
coverage: check-uv  ## Run tests with coverage reports
	@printf "$(INFO) Running tests with coverage reports...\n"
	@$(UV) run $(PYTEST) $(TEST_ARGS) $(COV_ARGS)
	@printf "$(INFO) Coverage reports complete.\n\n"

.PHONY: scan
scan: check-uv  ## Scan for security issues
# 	@printf "$(INFO) Scanning for security issues...\n"
# 	@$(UV) run $(PIP_AUDIT) --version >/dev/null 2>&1 || { \
# 		printf "$(ERROR) '$(PIP_AUDIT)' not installed in uv env.\n"; \
# 		printf "Fix: make setup  (or: $(UV) sync $(UV_SYNC_ARGS))\n"; \
# 		exit 1; \
# 	}
# 	@$(UV) run $(PIP_AUDIT) $(PIP_AUDIT_ARGS)

	@$(UV) run $(BANDIT) --version >/dev/null 2>&1 || { \
		printf "$(ERROR) '$(BANDIT)' not installed in uv env.\n"; \
		printf "Fix: make setup  (or: $(UV) sync $(UV_SYNC_ARGS))\n"; \
		exit 1; \
	}
	@$(UV) run $(BANDIT) $(BANDIT_ARGS)

.PHONY: version
version:  ## Show current version
	@$(PYTHON) -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])"

.PHONY: bump
bump: check-uv  ## Bump patch version (X.Y.Z -> X.Y.Z+1)
	@printf "$(INFO) Bumping patch version...\n"
	@old_version=$$($(PYTHON) -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])"); \
	$(UV) run $(BUMP) >/dev/null 2>&1; \
	new_version=$$($(PYTHON) -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])"); \
	printf "$(INFO) $$old_version$(RESET) --> $(GREEN)$$new_version$(RESET)\n"

.PHONY: bump-minor
bump-minor: check-uv  ## Bump minor version (X.Y.Z -> X.Y+1.0)
	@printf "$(INFO) Bumping minor version...\n"
	@old_version=$$($(PYTHON) -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])"); \
	$(UV) run $(BUMP) --minor --reset >/dev/null 2>&1; \
	new_version=$$($(PYTHON) -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])"); \
	printf "$(INFO) $$old_version$(RESET) --> $(GREEN)$$new_version$(RESET)\n"

.PHONY: bump-major
bump-major: check-uv  ## Bump major version (X.Y.Z -> X+1.0.0)
	@printf "$(INFO) Bumping major version...\n"
	@old_version=$$($(PYTHON) -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])"); \
	$(UV) run $(BUMP) --major --reset >/dev/null 2>&1; \
	new_version=$$($(PYTHON) -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])"); \
	printf "$(INFO) $$old_version$(RESET) --> $(GREEN)$$new_version$(RESET)\n"

.PHONY: package
package: check-uv  ## Clean and build artifacts
	@printf "$(INFO) Packaging project...\n"
	@$(MAKE) clean
	@$(MAKE) build
	@printf "$(INFO) Packaging complete.\n\n"

.PHONY: publish
publish: check-uv  ## Upload artifacts to PyPI
	@printf "$(INFO) Publishing package to repository '$(PUBLISH_REPO)'...\n"
	@test -d dist || (printf "$(ERROR) dist/ missing; run make build\n" && exit 1)
	@$(UV) run $(TWINE) check dist/*
	@$(UV) run $(TWINE) upload $(PYPI_BASE_URL)/$(PUBLISH_REPO) dist/*
	@printf "$(INFO) Publishing complete.\n\n"

.PHONY: install
install: check-uv  ## Install package in editable mode
	@printf "$(INFO) Installing package in editable mode...\n"
	@$(UV) run pip install -e .
	@printf "$(INFO) Installation complete.\n\n"
	@printf "$(INFO) You can now run help via Python: $(YELLOW)uv run python -m %s.main --help$(RESET)\n" "$(PACKAGE_MODULE)"
	@printf "$(INFO) You can now execute the package in the terminal: $(YELLOW)uv run $(PACKAGE) --help$(RESET)\n"
