from typing import Dict, Any, List, Tuple, Set

# Flags that take exactly one argument — must be kept as (flag, value) pairs.
_ONE_ARG_FLAGS: Set[str] = {
    "--unsetenv", "--chdir", "--tmpfs", "--dir", "--proc", "--dev",
    "--remount-ro", "--uid", "--gid", "--hostname", "--lock-file",
    "--file", "--bind-data", "--ro-bind-data", "--perms", "--size", "--chmod",
}

# Flags that take exactly two arguments (key+value or src+dest style).
_TWO_ARG_FLAGS: Set[str] = {
    "--setenv", "--symlink",
    "--bind", "--bind-try", "--dev-bind", "--dev-bind-try",
    "--ro-bind", "--ro-bind-try",
}

# Zero-arg namespace / session flags.
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


def _group_args(args: List[str]) -> List[Tuple[str, ...]]:
    """Group raw bwrap args into logical tuples for deduplication.

    Zero-arg flags become 1-tuples, one-arg flags become 2-tuples,
    two-arg flags become 3-tuples, and unrecognised tokens become 1-tuples.
    """
    groups: List[Tuple[str, ...]] = []
    i = 0
    while i < len(args):
        if args[i] in _TWO_ARG_FLAGS and i + 2 < len(args):
            groups.append((args[i], args[i + 1], args[i + 2]))
            i += 3
        elif args[i] in _ONE_ARG_FLAGS and i + 1 < len(args):
            groups.append((args[i], args[i + 1]))
            i += 2
        else:
            groups.append((args[i],))
            i += 1
    return groups


def _organize_args(args: List[str]) -> List[str]:
    """Sort merged args into a consistent order by category.

    Order: namespace flags, dir flags, other flags, late flags.
    """
    namespace: List[str] = []
    dirs: List[Tuple[str, str]] = []
    late: List[Tuple[str, str]] = []
    other: List[str] = []

    i = 0
    while i < len(args):
        tok = args[i]
        if tok in _NAMESPACE_FLAGS:
            namespace.append(tok)
            i += 1
        elif tok in _DIR_FLAGS and i + 1 < len(args):
            dirs.append((tok, args[i + 1]))
            i += 2
        elif tok in _LATE_FLAGS and i + 1 < len(args):
            late.append((tok, args[i + 1]))
            i += 2
        elif tok in _TWO_ARG_FLAGS and i + 2 < len(args):
            other += [tok, args[i + 1], args[i + 2]]
            i += 3
        elif tok in _ONE_ARG_FLAGS and i + 1 < len(args):
            other += [tok, args[i + 1]]
            i += 2
        else:
            other.append(tok)
            i += 1

    result: List[str] = []
    result += sorted(namespace)
    for flag, val in dirs:
        result += [flag, val]
    result += other
    for flag, val in late:
        result += [flag, val]
    return result


def compose_profiles(profile_dicts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge multiple profile dicts into a single configuration.

    Merge rules:
      - **mounts** – union, de-duplicated by exact dict equality.
      - **env** – later profiles override earlier keys.
      - **args** – appended in order, duplicates skipped (flag+value pairs
        are treated as units).
      - **run** – last profile with a ``run`` key wins.
      - **tmpfs/dev/proc** – union of unique paths.
    """
    merged: Dict[str, Any] = {
        "mounts": [],
        "env": {},
        "args": [],
        "run": None,
        "tmpfs": [],
        "dev": [],
        "proc": [],
    }
    seen_arg_groups: list[Tuple[str, ...]] = []

    for profile in profile_dicts:
        for mount in profile.get("mounts") or []:
            if mount not in merged["mounts"]:
                merged["mounts"].append(mount)

        merged["env"].update(profile.get("env") or {})

        for group in _group_args(profile.get("args") or []):
            if group not in seen_arg_groups:
                seen_arg_groups.append(group)
                merged["args"].extend(group)

        if "run" in profile:
            merged["run"] = profile["run"]

        for key in ("tmpfs", "dev", "proc"):
            val = profile.get(key)
            if val is not None:
                items = [val] if isinstance(val, str) else (val or [])
                for item in items:
                    if item not in merged[key]:
                        merged[key].append(item)

    merged["args"] = _organize_args(merged["args"])
    return merged
