bwrap_compose — compose bubblewrap (bwrap) profiles into a single bwrap command

This is a small Python CLI prototype that composes named profiles (YAML) into a single bwrap command.

Quickstart

1. Install dependencies:

   pip install -r requirements.txt

2. Run an example (dry run):

   python -m bwrap_compose combine github-copilot python-uv --dry-run

See examples/profiles for sample profile YAML files.
