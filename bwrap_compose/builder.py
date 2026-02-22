from typing import Dict, Any, List


def build_bwrap_command(config: Dict[str, Any], run_cmd: List[str] = None) -> List[str]:
    """Convert a merged profile dict into a bwrap command (argv list).

    This is a conservative, minimal builder for the prototype.
    """
    if run_cmd is None:
        run_cmd = ['/bin/sh', '-lc', 'exec /bin/bash --login']

    cmd: List[str] = ['bwrap']

    # mounts: list of {host, container, mode?}
    for m in config.get('mounts', []) or []:
        host = m.get('host')
        container = m.get('container')
        mode = m.get('mode', 'rw')
        if not host or not container:
            continue
        if str(mode).lower() in ('ro', 'readonly'):
            cmd += ['--ro-bind', host, container]
        else:
            cmd += ['--bind', host, container]

    # environment
    for k, v in (config.get('env', {}) or {}).items():
        cmd += ['--setenv', k, str(v)]

    # extra args
    extra = config.get('args', []) or []
    cmd += extra

    # separator and command
    cmd += ['--'] + run_cmd
    return cmd
