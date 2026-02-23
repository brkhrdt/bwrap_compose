bwrap_compose — compose bubblewrap (bwrap) profiles into a single bwrap command

This is a small Python CLI prototype that composes named profiles (YAML) into a single bwrap command.

Quickstart

1. Install dependencies (using uv):

   uv sync

2. Run tests (using uv):

   uv run pytest

3. Run an example (dry run) via uv (runs the console script installed from pyproject.toml):

   uv run bwrap-compose -- python-uv --dry-run

See examples/profiles for sample profile YAML files.
