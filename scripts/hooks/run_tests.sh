#!/bin/sh
# Pre-commit gate: run the test suite through the project environment.
# UV_PROJECT_ENVIRONMENT defaults to a per-user venv so the repo can live
# on a filesystem without symlink support.
: "${UV_PROJECT_ENVIRONMENT:=$HOME/.venvs/aneup}"
export UV_PROJECT_ENVIRONMENT
exec uv run --group test pytest -q
