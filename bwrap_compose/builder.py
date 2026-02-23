from typing import Dict, Any, List, Optional
import os

# Modes recognised as read-only in profile YAML.
_RO_MODES = {"ro", "readonly"}


def _as_list(val):
    """Normalise a string-or-list value to a list."""
    if val is None:
        return []
    if isinstance(val, str):
        return [val]
    return list(val)


def _expand_path(path: str) -> str:
    """Expand ``~`` and ``$VAR`` references in *path*.

    If the path is wrapped in literal single quotes (e.g. ``'$HOME/foo'``),
    the quotes are stripped and no expansion is performed so that the value
    is kept as-is for use in generated shell scripts.
    """
    if len(path) >= 2 and path.startswith("'") and path.endswith("'"):
        return path[1:-1]
    path = os.path.expanduser(path)
    path = os.path.expandvars(path)
    return path


def build_bwrap_command(
    config: Dict[str, Any],
    run_cmd: Optional[List[str]] = None,
) -> List[str]:
    """Convert a merged profile dict into a bwrap argv list.

    Parameters
    ----------
    config:
        Merged profile dictionary (as returned by :func:`compose_profiles`).
    run_cmd:
        Override the command to execute inside the sandbox.  When *None*,
        the ``run`` key from *config* is used; if that is also absent the
        default is ``['/usr/bin/env', 'uv']``.
    """
    if run_cmd is None:
        run_spec = config.get("run")
        if isinstance(run_spec, str):
            run_cmd = ["/bin/sh", "-lc", "exec " + run_spec]
        elif isinstance(run_spec, list):
            run_cmd = run_spec
        else:
            run_cmd = ["/usr/bin/env", "uv"]

    cmd: List[str] = ["bwrap"]

    for mount in config.get("mounts") or []:
        host = _expand_path(mount.get("host") or "")
        container = _expand_path(mount.get("container") or "")
        if not host or not container:
            continue
        mode = str(mount.get("mode", "rw")).lower()
        flag = "--ro-bind" if mode in _RO_MODES else "--bind"
        cmd += [flag, host, container]

    # Special filesystem mounts
    for path in _as_list(config.get("tmpfs")):
        cmd += ["--tmpfs", path]
    for path in _as_list(config.get("dev")):
        cmd += ["--dev", path]
    for path in _as_list(config.get("proc")):
        cmd += ["--proc", path]

    for key, value in (config.get("env") or {}).items():
        cmd += ["--setenv", key, str(value)]

    cmd += config.get("args") or []

    cmd += ["--"] + run_cmd
    return cmd
