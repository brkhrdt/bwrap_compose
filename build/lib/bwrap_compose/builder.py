from typing import Dict, Any, List, Optional, Set
import os

# Modes recognised as read-only in profile YAML.
_RO_MODES = {"ro", "readonly"}

# Zero-arg flags emitted early (namespace setup).
_NAMESPACE_FLAGS: Set[str] = {
    "--unshare-user", "--unshare-user-try", "--unshare-ipc",
    "--unshare-pid", "--unshare-net", "--unshare-uts",
    "--unshare-cgroup", "--unshare-cgroup-try", "--unshare-all",
    "--share-net", "--die-with-parent", "--as-pid-1",
    "--new-session", "--clearenv",
}

# One-arg flags that create directories (emitted after tmpfs, before mounts).
_DIR_FLAGS: Set[str] = {"--dir"}

# One-arg flags emitted late (after mounts).
_LATE_FLAGS: Set[str] = {"--chdir"}

# One-arg flags (for parsing purposes).
_ONE_ARG_FLAGS: Set[str] = {
    "--unsetenv", "--chdir", "--tmpfs", "--dir", "--proc", "--dev",
    "--remount-ro", "--uid", "--gid", "--hostname", "--lock-file",
    "--file", "--bind-data", "--ro-bind-data", "--perms", "--size", "--chmod",
}


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


def _categorise_args(args: List[str]):
    """Split raw args into (namespace, dir, late, other) groups."""
    namespace = []
    dirs = []
    late = []
    other = []

    i = 0
    while i < len(args):
        tok = args[i]
        if tok in _NAMESPACE_FLAGS:
            namespace.append(tok)
            i += 1
        elif tok in _DIR_FLAGS and i + 1 < len(args):
            dirs += [tok, args[i + 1]]
            i += 2
        elif tok in _LATE_FLAGS and i + 1 < len(args):
            late += [tok, args[i + 1]]
            i += 2
        elif tok in _ONE_ARG_FLAGS and i + 1 < len(args):
            other += [tok, args[i + 1]]
            i += 2
        else:
            other.append(tok)
            i += 1

    return namespace, dirs, late, other


def build_bwrap_command(
    config: Dict[str, Any],
    run_cmd: Optional[List[str]] = None,
) -> List[str]:
    """Convert a merged profile dict into a bwrap argv list.

    The arguments are ordered so that bwrap processes them correctly:
      1. Namespace / session flags (``--unshare-all``, etc.)
      2. Base filesystem (``--tmpfs``)
      3. Directory creation (``--dir``)
      4. Bind mounts (``--ro-bind``, ``--bind``)
      5. Special filesystems (``--dev``, ``--proc``)
      6. Environment variables (``--setenv``)
      7. Other args, then late args (``--chdir``)
      8. ``-- <command>``

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

    namespace, dirs, late, other = _categorise_args(config.get("args") or [])

    # 1. Namespace flags
    cmd += namespace

    # 2. Base filesystem mounts (tmpfs)
    for path in _as_list(config.get("tmpfs")):
        cmd += ["--tmpfs", path]

    # 3. Directory creation
    cmd += dirs

    # 4. Bind mounts
    for mount in config.get("mounts") or []:
        host = _expand_path(mount.get("host") or "")
        container = _expand_path(mount.get("container") or "")
        if not host or not container:
            continue
        mode = str(mount.get("mode", "rw")).lower()
        flag = "--ro-bind" if mode in _RO_MODES else "--bind"
        cmd += [flag, host, container]

    # 5. Special filesystems (dev, proc)
    for path in _as_list(config.get("dev")):
        cmd += ["--dev", path]
    for path in _as_list(config.get("proc")):
        cmd += ["--proc", path]

    # 6. Environment variables
    for key, value in (config.get("env") or {}).items():
        cmd += ["--setenv", key, str(value)]

    # 7. Other args, then late args
    cmd += other
    cmd += late

    cmd += ["--"] + run_cmd
    return cmd
