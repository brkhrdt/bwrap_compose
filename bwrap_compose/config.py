from pathlib import Path
from typing import Any, Dict
import json

try:
    import yaml  # type: ignore
    _yaml_safe_load = yaml.safe_load
except ImportError:
    _yaml_safe_load = None


def _parse_text(text: str) -> Any:
    """Parse YAML or JSON text, preferring YAML when available."""
    if _yaml_safe_load:
        return _yaml_safe_load(text)
    return json.loads(text)


def load_profile(path: str) -> Dict[str, Any]:
    """Load a profile YAML/JSON file.

    If the document contains a top-level ``profiles`` mapping with a single
    key, the inner profile dict is returned.  Otherwise the parsed document
    is returned as-is.

    Raises:
        FileNotFoundError: If *path* does not exist.
        ValueError: If the file cannot be parsed.
    """
    p = Path(path)
    text = p.read_text()
    data = _parse_text(text) or {}

    if isinstance(data, dict) and isinstance(data.get("profiles"), dict):
        profiles = data["profiles"]
        if len(profiles) == 1:
            return next(iter(profiles.values()))

    return data
