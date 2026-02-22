install:
	pip install -r requirements.txt

run-example:
	python -m bwrap_compose combine github-copilot --dry-run
