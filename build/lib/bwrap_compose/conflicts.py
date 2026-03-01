"""Detect and report conflicts in a merged bwrap profile.

Conflicts include:
  - Same container path mounted with different modes (ro vs rw).
  - A read-only directory with a writable sub-directory.
  - Duplicate environment variable keys with different values across profiles.
  - Contradictory namespace flags (e.g. --unshare-net and --share-net).
"""

from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any, Dict, List, Optional


@dataclass
class Conflict:
    """A single detected conflict."""

    kind: str  # e.g. "mount-mode", "ro-writable-subdir", "env-override", "ns-contradiction"
    description: str
    severity: str = "warning"  # "warning" or "error"


def detect_conflicts(
    profiles: List[Dict[str, Any]],
    merged: Optional[Dict[str, Any]] = None,
) -> List[Conflict]:
    """Analyse *profiles* (and optionally the *merged* result) for conflicts.

    Returns a list of :class:`Conflict` objects.  An empty list means no
    conflicts were found.
    """
    conflicts: List[Conflict] = []
    conflicts.extend(_check_mount_mode_conflicts(profiles))
    conflicts.extend(_check_ro_writable_subdir(merged or _quick_merge(profiles)))
    conflicts.extend(_check_env_overrides(profiles))
    conflicts.extend(_check_namespace_contradictions(merged or _quick_merge(profiles)))
    return conflicts


# ── helpers ──────────────────────────────────────────────────────────────

def _normalise_mode(mode: str) -> str:
    m = str(mode).lower()
    return "ro" if m in ("ro", "readonly") else "rw"


def _quick_merge(profiles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Lightweight merge for conflict detection (avoids circular import)."""
    mounts: List[Dict[str, str]] = []
    env: Dict[str, str] = {}
    args: List[str] = []
    for p in profiles:
        mounts.extend(p.get("mounts") or [])
        env.update(p.get("env") or {})
        args.extend(p.get("args") or [])
    return {"mounts": mounts, "env": env, "args": args}


def _check_mount_mode_conflicts(profiles: List[Dict[str, Any]]) -> List[Conflict]:
    """Flag container paths that appear with both ro and rw modes."""
    # Collect (container_path → set of modes) across all profiles.
    path_modes: Dict[str, set] = {}
    for p in profiles:
        for m in p.get("mounts") or []:
            cp = m.get("container", "")
            mode = _normalise_mode(m.get("mode", "rw"))
            path_modes.setdefault(cp, set()).add(mode)

    conflicts: List[Conflict] = []
    for cp, modes in path_modes.items():
        if len(modes) > 1:
            conflicts.append(Conflict(
                kind="mount-mode",
                description=(
                    f"Container path '{cp}' is mounted with conflicting modes: "
                    f"{', '.join(sorted(modes))}. The last mount will take effect."
                ),
            ))
    return conflicts


def _check_ro_writable_subdir(merged: Dict[str, Any]) -> List[Conflict]:
    """Flag writable mount points nested under a read-only parent."""
    mounts = merged.get("mounts") or []
    ro_paths = set()
    rw_paths = set()
    for m in mounts:
        cp = m.get("container", "")
        mode = _normalise_mode(m.get("mode", "rw"))
        if mode == "ro":
            ro_paths.add(cp)
        else:
            rw_paths.add(cp)

    conflicts: List[Conflict] = []
    for rw in rw_paths:
        rw_posix = PurePosixPath(rw)
        for ro in ro_paths:
            ro_posix = PurePosixPath(ro)
            if rw_posix != ro_posix and _is_subpath(rw_posix, ro_posix):
                conflicts.append(Conflict(
                    kind="ro-writable-subdir",
                    description=(
                        f"Writable mount '{rw}' is nested under read-only mount '{ro}'. "
                        f"Ensure this is intentional."
                    ),
                ))
    return conflicts


def _is_subpath(child: PurePosixPath, parent: PurePosixPath) -> bool:
    """Return True if *child* is a strict sub-path of *parent*."""
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _check_env_overrides(profiles: List[Dict[str, Any]]) -> List[Conflict]:
    """Flag env vars set in multiple profiles with different values."""
    seen: Dict[str, str] = {}  # key → first value
    conflicts: List[Conflict] = []
    for p in profiles:
        for k, v in (p.get("env") or {}).items():
            v_str = str(v)
            if k in seen and seen[k] != v_str:
                conflicts.append(Conflict(
                    kind="env-override",
                    description=(
                        f"Environment variable '{k}' is set to '{seen[k]}' "
                        f"and later overridden to '{v_str}'."
                    ),
                    severity="warning",
                ))
            seen[k] = v_str
    return conflicts


_CONTRADICTING_NS_PAIRS = [
    ("--unshare-net", "--share-net"),
]


def _check_namespace_contradictions(merged: Dict[str, Any]) -> List[Conflict]:
    """Flag contradictory namespace flags (e.g. --unshare-net + --share-net)."""
    args = set(merged.get("args") or [])
    conflicts: List[Conflict] = []
    for a, b in _CONTRADICTING_NS_PAIRS:
        if a in args and b in args:
            conflicts.append(Conflict(
                kind="ns-contradiction",
                description=(
                    f"Contradictory namespace flags '{a}' and '{b}' are both present."
                ),
                severity="error",
            ))
    return conflicts
