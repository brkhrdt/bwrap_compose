from bwrap_compose.builder import build_bwrap_command


def test_build_bwrap_command_basic():
    cfg = {"mounts":[{"host":"/a","container":"/a","mode":"ro"}],"env":{"A":"1"},"args":["--custom"]}
    cmd = build_bwrap_command(cfg, run_cmd=["/bin/echo","hello"])
    assert cmd[0] == 'bwrap'
    assert '--ro-bind' in cmd
    assert '--setenv' in cmd
    assert '--' in cmd
    assert cmd[-2:] == ["/bin/echo","hello"]
