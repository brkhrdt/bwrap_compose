import json
from bwrap_compose.config import load_profile


def test_load_profile_single_profile_mapping(tmp_path):
    data = {"profiles": {"p": {"env": {"A": "1"}}}}
    p = tmp_path / "p.json"
    p.write_text(json.dumps(data))
    out = load_profile(str(p))
    assert out == {"env": {"A": "1"}}


def test_load_profile_plain(tmp_path):
    data = {"env": {"B": "2"}}
    p = tmp_path / "plain.json"
    p.write_text(json.dumps(data))
    out = load_profile(str(p))
    assert out == data
