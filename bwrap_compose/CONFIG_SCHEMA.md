# bwrap_compose profile schema

## Fields

- **mounts**: sequence of mappings (`host`: string, `container`: string, `mode`: optional string `'ro'` or `'rw'` (default `'rw'`))
- **env**: mapping of environment variables to string values
- **args**: sequence of extra bwrap arguments (strings)
- **run**: optional command to run inside the sandbox; can be a string or a list (recommended: list). If omitted, defaults to `uv`.
- **description**: optional string
- **extends**: optional string or list of strings – names of parent profiles to inherit from. The child profile's values overlay the parent(s).
- **tmpfs**: optional string or list of paths to mount as tmpfs inside the sandbox
- **dev**: optional string or list of paths to mount a devtmpfs
- **proc**: optional string or list of paths to mount procfs

## Merging semantics

- **mounts**: union of mounts; duplicates removed by exact match
- **env**: later profiles override earlier keys
- **args**: appended in order, duplicates removed
- **run**: if multiple profiles specify `run`, the last profile's `run` takes precedence
- **tmpfs/dev/proc**: union of unique paths

## Profile inheritance

Use the `extends` key to inherit from one or more parent profiles:

```yaml
extends: base-sandbox
env:
  MY_VAR: "1"
run:
  - /bin/sh
```

Parent profiles are resolved from the same directory as the child and from any `--config-dir` directories.

## Examples

See `examples/profiles/` for sample profile YAML files.
