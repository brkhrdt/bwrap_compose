"""Generate a bwrap profile from a binary by inspecting its linked libraries."""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _parse_ldd_output(output: str) -> Tuple[List[str], List[Tuple[str, str]]]:
    """Extract resolved library paths from ldd output.

    Skips virtual DSOs (linux-vdso) and entries without a resolved path.
    Returns (libs, symlink_pairs) where libs is a list of absolute paths
    and symlink_pairs is a list of (target, link_name) for cases where
    the expected path differs from the resolved path (e.g. dynamic linker).
    """
    libs: List[str] = []
    symlinks: List[Tuple[str, str]] = []
    for line in output.strip().splitlines():
        line = line.strip()
        if not line or "linux-vdso" in line:
            continue
        if "=>" in line:
            parts = line.split("=>")
            expected = parts[0].strip()
            resolved = parts[1].strip().split("(")[0].strip()
            if resolved and os.path.isfile(resolved):
                libs.append(resolved)
                # If the expected path is absolute and differs, we need a symlink
                if expected.startswith("/") and expected != resolved:
                    symlinks.append((resolved, expected))
        elif line.startswith("/"):
            path = line.split("(")[0].strip()
            if path and os.path.isfile(path):
                libs.append(path)
    return libs, symlinks


def _collect_dirs(paths: List[str]) -> List[str]:
    """Collect the unique parent directories needed for a list of paths."""
    dirs = set()
    for p in paths:
        parent = str(Path(p).parent)
        while parent and parent != "/":
            dirs.add(parent)
            parent = str(Path(parent).parent)
    return sorted(dirs)


def manifest_from_binary(
    binary: str,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a minimal bwrap profile for *binary* using ``ldd`` to discover deps.

    The resulting profile uses ``tmpfs /`` as a base, read-only binds the
    binary and all its shared libraries, creates necessary directories, and
    sets ``--unshare-all --die-with-parent --new-session``.
    """
    binary_path = shutil.which(binary) or binary
    binary_path = str(Path(binary_path).resolve())

    if not os.path.isfile(binary_path):
        raise FileNotFoundError(f"Binary not found: {binary}")

    result = subprocess.run(
        ["ldd", binary_path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ldd failed: {result.stderr.strip()}")

    libs, symlink_pairs = _parse_ldd_output(result.stdout)

    # All files that need to be bind-mounted
    all_files = [binary_path] + libs

    # Build mounts, resolving symlinks to real files
    mounts = []
    seen_paths = set()
    for fpath in all_files:
        if fpath in seen_paths:
            continue
        seen_paths.add(fpath)
        mounts.append({"host": fpath, "container": fpath, "mode": "ro"})
        # If it's a symlink, also mount the real file
        real = str(Path(fpath).resolve())
        if real != fpath and real not in seen_paths:
            seen_paths.add(real)
            mounts.append({"host": real, "container": real, "mode": "ro"})

    # Collect all paths including symlink targets for directory creation
    all_paths = list(seen_paths) + [link for _, link in symlink_pairs]
    dirs = _collect_dirs(all_paths)

    # Build args: namespace flags, dir creation, symlinks
    args: List[str] = ["--unshare-all", "--die-with-parent", "--new-session"]
    for d in dirs:
        args += ["--dir", d]
    for target, link_name in symlink_pairs:
        args += ["--symlink", target, link_name]

    profile: Dict[str, Any] = {
        "mounts": mounts,
        "tmpfs": "/",
        "args": args,
        "run": [binary_path],
    }

    if description:
        profile["description"] = description

    return profile
