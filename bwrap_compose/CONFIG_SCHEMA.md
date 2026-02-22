bwrap_compose profile schema

Fields:

- mounts: sequence of mappings (host: string, container: string, mode: optional string 'ro' or 'rw' (default 'rw'))
- env: mapping of environment variables to string values
- args: sequence of extra bwrap arguments (strings)
- run: optional command to run inside the bwrap container; can be a string or a list (recommended: list)
- description: optional string

Merging semantics:

- mounts: union of mounts; duplicates removed by exact match (host+container)
- env: later profiles override earlier keys
- args: appended in order, duplicates removed
- run: if multiple profiles specify `run`, the last profile's `run` takes precedence

Examples are available in examples/profiles/ (github-copilot.yaml, python-uv.yaml)
