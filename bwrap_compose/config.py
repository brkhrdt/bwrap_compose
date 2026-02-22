from pathlib import Path
from typing import Any, Dict
import json

try:
    import yaml  # type: ignore
    _yaml_safe_load = getattr(yaml, "safe_load")
except Exception:
    yaml = None
    _yaml_safe_load = None


def _safe_load_text(text: str):
    if _yaml_safe_load:
        return _yaml_safe_load(text)
    # fallback to JSON parsing for environments without PyYAML
    return json.loads(text)


def load_profile(path: str) -> Dict[str, Any]:
    """Load a profile YAML/JSON file.

    If the document contains a top-level `profiles` mapping with a single key, return that inner profile.
    Otherwise return the parsed document.
    """
    p = Path(path)
    with p.open() as f:
        text = f.read()
        data = _safe_load_text(text) or {}

    if isinstance(data, dict) and 'profiles' in data and isinstance(data['profiles'], dict):
        if len(data['profiles']) == 1:
            return next(iter(data['profiles'].values()))

    return data
