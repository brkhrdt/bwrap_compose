from typing import Dict, Any, List, Tuple

# Flags that take exactly one argument — must be kept as (flag, value) pairs.
_ONE_ARG_FLAGS = {
    "--unsetenv", "--chdir", "--tmpfs", "--dir", "--proc", "--dev",
    "--remount-ro", "--uid", "--gid", "--hostname", "--lock-file",
    "--file", "--bind-data", "--ro-bind-data", "--perms", "--size", "--chmod",
}


def _group_args(args: List[str]) -> List[Tuple[str, ...]]:
    """Group raw bwrap args into logical tuples for deduplication.

    Zero-arg flags become 1-tuples, one-arg flags become 2-tuples,
    and unrecognised tokens become 1-tuples.
    """
    groups: List[Tuple[str, ...]] = []
    i = 0
    while i < len(args):
        if args[i] in _ONE_ARG_FLAGS and i + 1 < len(args):
            groups.append((args[i], args[i + 1]))
            i += 2
        else:
            groups.append((args[i],))
            i += 1
    return groups


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

    return merged
