# bwrap_compose

Compose [bubblewrap](https://github.com/containers/bubblewrap) (`bwrap`) profiles into a single `bwrap` command.

## Quickstart

1. Install dependencies (using [uv](https://docs.astral.sh/uv/)):

   ```sh
   uv sync
   ```

2. Run tests:

   ```sh
   uv run pytest
   ```

3. Run an example (dry run):

   ```sh
   uv run bwrap-compose -- python-uv --dry-run
   ```

See `examples/profiles/` for sample profile YAML files and
`bwrap_compose/CONFIG_SCHEMA.md` for the profile format reference.
