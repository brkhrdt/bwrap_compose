from typing import Dict, Any, List


def compose_profiles(profile_dicts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge multiple profile dicts into a single configuration.

    Rules (simple prototype):
    - mounts: union of mounts, de-duplicated by full dict equality
    - env: later profiles override earlier ones
    - args: append unique args in order
    """
    merged = {
        'mounts': [],
        'env': {},
        'args': [],
    }

    for p in profile_dicts:
        mounts = p.get('mounts', []) or []
        for m in mounts:
            if m not in merged['mounts']:
                merged['mounts'].append(m)

        env = p.get('env', {}) or {}
        merged['env'].update(env)

        args = p.get('args', []) or []
        for a in args:
            if a not in merged['args']:
                merged['args'].append(a)

    return merged
