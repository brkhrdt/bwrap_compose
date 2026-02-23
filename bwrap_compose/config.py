from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import json

try:
    import yaml  # type: ignore
    _yaml_safe_load = yaml.safe_load
    _yaml_dump = yaml.dump
except ImportError:
    _yaml_safe_load = None
    _yaml_dump = None


def _parse_text(text: str) -> Any:
    """Parse YAML or JSON text, preferring YAML when available."""
    if _yaml_safe_load:
        return _yaml_safe_load(text)
    return json.loads(text)


def _unwrap_profiles(data: Dict[str, Any]) -> Dict[str, Any]:
    """If *data* has a single-entry ``profiles`` wrapper, unwrap it."""
    if isinstance(data, dict) and isinstance(data.get("profiles"), dict):
        profiles = data["profiles"]
        if len(profiles) == 1:
            return next(iter(profiles.values()))
    return data


def load_profile(
    path: str,
    *,
    search_dirs: Optional[List[Path]] = None,
    _visited: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """Load a profile YAML/JSON file.

    Supports an ``extends`` key (string or list of strings) that names parent
    profiles to inherit from.  Parent profiles are resolved relative to the
    same directory as *path* and any directories in *search_dirs*.

    Raises:
        FileNotFoundError: If *path* does not exist.
        ValueError: If the file cannot be parsed or a cycle is detected.
    """
    if _visited is None:
        _visited = set()

    real = str(Path(path).resolve())
    if real in _visited:
        raise ValueError(f"Circular extends detected: {real}")
    _visited.add(real)

    p = Path(path)
    text = p.read_text()
    data = _parse_text(text) or {}
    data = _unwrap_profiles(data)

    extends = data.pop("extends", None)
    if extends:
        if isinstance(extends, str):
            extends = [extends]
        parent_dicts = []
        for parent_name in extends:
            parent_path = _resolve_extends(parent_name, p.parent, search_dirs)
            if parent_path is None:
                raise FileNotFoundError(
                    f"Extended profile '{parent_name}' not found from {path}"
                )
            parent_dicts.append(
                load_profile(str(parent_path), search_dirs=search_dirs, _visited=_visited)
            )
        # Merge parents first, then overlay current profile.
        from .composer import compose_profiles
        base = compose_profiles(parent_dicts)
        data = compose_profiles([base, data])

    return data


def _resolve_extends(
    name: str,
    base_dir: Path,
    search_dirs: Optional[List[Path]] = None,
) -> Optional[Path]:
    """Resolve a profile name referenced in ``extends``."""
    exts = (".yaml", ".yml", ".json")
    dirs = [base_dir] + list(search_dirs or [])
    for d in dirs:
        for ext in exts:
            candidate = d / f"{name}{ext}"
            if candidate.exists():
                return candidate
        # Also try as literal filename
        literal = d / name
        if literal.exists():
            return literal
    return None


def validate_profile(data: Dict[str, Any]) -> List[str]:
    """Return a list of validation error messages (empty = valid)."""
    errors: List[str] = []
    if not isinstance(data, dict):
        return ["Profile must be a mapping"]

    valid_keys = {
        "mounts", "env", "args", "run", "description", "extends",
        "tmpfs", "dev", "proc", "profiles",
    }
    unknown = set(data.keys()) - valid_keys
    if unknown:
        errors.append(f"Unknown keys: {', '.join(sorted(unknown))}")

    mounts = data.get("mounts")
    if mounts is not None:
        if not isinstance(mounts, list):
            errors.append("'mounts' must be a list")
        else:
            for i, m in enumerate(mounts):
                if not isinstance(m, dict):
                    errors.append(f"mounts[{i}] must be a mapping")
                    continue
                if "host" not in m:
                    errors.append(f"mounts[{i}] missing 'host'")
                if "container" not in m:
                    errors.append(f"mounts[{i}] missing 'container'")

    env = data.get("env")
    if env is not None and not isinstance(env, dict):
        errors.append("'env' must be a mapping")

    args = data.get("args")
    if args is not None and not isinstance(args, list):
        errors.append("'args' must be a list")

    run = data.get("run")
    if run is not None and not isinstance(run, (str, list)):
        errors.append("'run' must be a string or list")

    for key in ("tmpfs", "dev", "proc"):
        val = data.get(key)
        if val is not None and not isinstance(val, (str, list)):
            errors.append(f"'{key}' must be a string or list of paths")

    return errors
