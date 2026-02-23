install:
	uv install -r requirements.txt

run-example:
	uv run bwrap-compose -- python-uv --dry-run
