from bwrap_compose.composer import compose_profiles


def test_compose_merges_mounts_and_env_and_args():
    p1 = {"mounts":[{"host":"/a","container":"/a","mode":"ro"}],"env":{"X":"1"},"args":["--foo"]}
    p2 = {"mounts":[{"host":"/b","container":"/b","mode":"rw"}],"env":{"X":"2","Y":"y"},"args":["--bar"]}
    merged = compose_profiles([p1,p2])
    assert {"host":"/a","container":"/a","mode":"ro"} in merged['mounts']
    assert {"host":"/b","container":"/b","mode":"rw"} in merged['mounts']
    assert merged['env']['X'] == "2"
    assert merged['env']['Y'] == "y"
    assert "--foo" in merged['args'] and "--bar" in merged['args']
