"""Integration tests for tool manifests (grep, ls) with real bwrap."""

import os
import shlex
import shutil
import subprocess

import pytest
import yaml

from bwrap_compose.composer import compose_profiles
from bwrap_compose.builder import build_bwrap_command
from bwrap_compose.config import load_profile

TOOLS_DIR = os.path.join(os.path.dirname(__file__), "..", "examples", "tools")

# Skip all tests if bwrap is not available
pytestmark = pytest.mark.skipif(
    shutil.which("bwrap") is None,
    reason="bwrap not installed",
)


def _workdir_profile(workdir: str) -> dict:
    """Create a profile that binds *workdir* read-write and sets --chdir."""
    return {
        "mounts": [{"host": workdir, "container": workdir, "mode": "rw"}],
        "args": ["--chdir", workdir],
    }


class TestGrepManifest:
    def test_dry_run_has_correct_structure(self):
        profile = load_profile(os.path.join(TOOLS_DIR, "grep.yaml"))
        cmd = build_bwrap_command(profile)
        cmd_str = " ".join(cmd)
        assert "--tmpfs /" in cmd_str
        assert "--ro-bind /bin/grep /bin/grep" in cmd_str
        assert "--unshare-all" in cmd_str
        assert cmd[-1] == "/bin/grep"

    def test_grep_finds_pattern(self, tmp_path):
        (tmp_path / "data.txt").write_text("hello world\nfoo bar\n")
        profile = load_profile(os.path.join(TOOLS_DIR, "grep.yaml"))
        merged = compose_profiles([profile, _workdir_profile(str(tmp_path))])
        cmd = build_bwrap_command(merged, run_cmd=["/bin/grep", "hello", str(tmp_path / "data.txt")])
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        assert result.returncode == 0
        assert "hello world" in result.stdout

    def test_grep_no_match_returns_nonzero(self, tmp_path):
        (tmp_path / "data.txt").write_text("foo bar\n")
        profile = load_profile(os.path.join(TOOLS_DIR, "grep.yaml"))
        merged = compose_profiles([profile, _workdir_profile(str(tmp_path))])
        cmd = build_bwrap_command(merged, run_cmd=["/bin/grep", "nomatch", str(tmp_path / "data.txt")])
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        assert result.returncode != 0
