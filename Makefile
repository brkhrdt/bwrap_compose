.PHONY: install test run-example

install:
	uv sync

test:
	uv run pytest -v

run-example:
	uv run bwrap-compose -- python-uv --dry-run
