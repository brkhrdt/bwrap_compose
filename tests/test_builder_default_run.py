from bwrap_compose.builder import build_bwrap_command


def test_default_run_is_uv():
    cfg = {}
    cmd = build_bwrap_command(cfg)
    assert '--' in cmd
    assert cmd[-2:] == ['/usr/bin/env', 'uv']
