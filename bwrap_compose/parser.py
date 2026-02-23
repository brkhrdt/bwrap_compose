"""Parse a bwrap command line back into a profile dict."""

from typing import Any, Dict, List, Optional
import shlex


# bwrap flags that take exactly two arguments (src, dest).
_BIND_FLAGS = {
    "--bind",
    "--bind-try",
    "--dev-bind",
    "--dev-bind-try",
    "--ro-bind",
    "--ro-bind-try",
}

# Flags that take exactly two arguments (key, value style).
_TWO_ARG_FLAGS = {
    "--setenv",
    "--symlink",
}

# Flags that take exactly one argument.
_ONE_ARG_FLAGS = {
    "--unsetenv",
    "--chdir",
    "--tmpfs",
    "--dir",
    "--proc",
    "--dev",
    "--remount-ro",
    "--uid",
    "--gid",
    "--hostname",
    "--lock-file",
    "--file",
    "--bind-data",
    "--ro-bind-data",
    "--perms",
    "--size",
    "--chmod",
}

# Flags that take zero extra arguments.
_ZERO_ARG_FLAGS = {
    "--unshare-user",
    "--unshare-user-try",
    "--unshare-ipc",
    "--unshare-pid",
    "--unshare-net",
    "--unshare-uts",
    "--unshare-cgroup",
    "--unshare-cgroup-try",
    "--unshare-all",
    "--share-net",
    "--die-with-parent",
    "--as-pid-1",
    "--new-session",
    "--clearenv",
}

_RW_BIND_FLAGS = {"--bind", "--bind-try", "--dev-bind", "--dev-bind-try"}
_RO_BIND_FLAGS = {"--ro-bind", "--ro-bind-try"}


def parse_bwrap_command(cmd: str) -> Dict[str, Any]:
    """Parse a bwrap command string into a profile dict.

    Returns a dict with keys: ``mounts``, ``env``, ``args``, ``run``.
    """
    tokens = shlex.split(cmd)

    # Skip leading 'bwrap' if present.
    if tokens and tokens[0] in ("bwrap", "/usr/bin/bwrap"):
        tokens = tokens[1:]

    mounts: List[Dict[str, str]] = []
    env: Dict[str, str] = {}
    args: List[str] = []
    run: Optional[List[str]] = None

    i = 0
    while i < len(tokens):
        tok = tokens[i]

        if tok == "--":
            run = tokens[i + 1:]
            break

        if tok in _BIND_FLAGS and i + 2 < len(tokens):
            host = tokens[i + 1]
            container = tokens[i + 2]
            mode = "ro" if tok in _RO_BIND_FLAGS else "rw"
            mounts.append({"host": host, "container": container, "mode": mode})
            i += 3
            continue

        if tok == "--setenv" and i + 2 < len(tokens):
            env[tokens[i + 1]] = tokens[i + 2]
            i += 3
            continue

        if tok in _TWO_ARG_FLAGS and i + 2 < len(tokens):
            args += [tok, tokens[i + 1], tokens[i + 2]]
            i += 3
            continue

        if tok in _ONE_ARG_FLAGS and i + 1 < len(tokens):
            args += [tok, tokens[i + 1]]
            i += 2
            continue

        if tok in _ZERO_ARG_FLAGS:
            args.append(tok)
            i += 1
            continue

        # Unknown token – keep it as a raw arg.
        args.append(tok)
        i += 1

    result: Dict[str, Any] = {
        "mounts": mounts,
        "env": env,
        "args": args,
    }
    if run is not None:
        result["run"] = run
    return result
