from typing import Dict, Any, List


def compose_profiles(profile_dicts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge multiple profile dicts into a single configuration.

    Merge rules:
      - **mounts** – union, de-duplicated by exact dict equality.
      - **env** – later profiles override earlier keys.
      - **args** – appended in order, duplicates skipped.
      - **run** – last profile with a ``run`` key wins.
    """
    merged: Dict[str, Any] = {
        "mounts": [],
        "env": {},
        "args": [],
        "run": None,
    }

    for profile in profile_dicts:
        for mount in profile.get("mounts") or []:
            if mount not in merged["mounts"]:
                merged["mounts"].append(mount)

        merged["env"].update(profile.get("env") or {})

        for arg in profile.get("args") or []:
            if arg not in merged["args"]:
                merged["args"].append(arg)

        if "run" in profile:
            merged["run"] = profile["run"]

    return merged
