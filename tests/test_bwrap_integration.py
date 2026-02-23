"""Integration tests that actually execute bwrap to verify composed commands."""

import os
import shutil
import subprocess
import tempfile

import pytest

from bwrap_compose.builder import build_bwrap_command
from bwrap_compose.composer import compose_profiles

# Skip the entire module when bwrap is not available.
pytestmark = pytest.mark.skipif(
    shutil.which("bwrap") is None, reason="bwrap not installed"
)


def _run_bwrap(cmd, **kwargs):
    """Run a bwrap command list and return the CompletedProcess."""
    return subprocess.run(cmd, capture_output=True, text=True, timeout=10, **kwargs)


# ── basic sanity ─────────────────────────────────────────────────────────

class TestBasicBwrapExecution:
    def test_echo_inside_sandbox(self):
        """A trivial command should succeed inside bwrap."""
        config = {
            "mounts": [{"host": "/", "container": "/", "mode": "ro"}],
            "env": {},
            "args": [],
            "run": ["/usr/bin/echo", "hello"],
        }
        cmd = build_bwrap_command(config)
        result = _run_bwrap(cmd)
        assert result.returncode == 0
        assert result.stdout.strip() == "hello"

    def test_env_variable_is_set(self):
        """Environment variables from the profile should be visible."""
        config = {
            "mounts": [{"host": "/", "container": "/", "mode": "ro"}],
            "env": {"MY_TEST_VAR": "42"},
            "args": [],
            "run": ["/usr/bin/env"],
        }
        cmd = build_bwrap_command(config)
        result = _run_bwrap(cmd)
        assert result.returncode == 0
        assert "MY_TEST_VAR=42" in result.stdout


# ── ro with writable sub-directory ───────────────────────────────────────

class TestRoWithWritableSubdir:
    """Verify that a writable sub-directory inside a ro-bind tree works."""

    def test_ro_parent_writable_child(self, tmp_path):
        """Mount parent ro, but a child dir rw — writes to child should succeed."""
        parent = tmp_path / "parent"
        child = parent / "child"
        child.mkdir(parents=True)

        # Use tmp_path as a writable root so bwrap can create mount points
        config = {
            "mounts": [
                {"host": "/", "container": "/", "mode": "ro"},
                {"host": str(tmp_path), "container": str(tmp_path), "mode": "rw"},
                {"host": str(parent), "container": str(parent), "mode": "ro"},
                {"host": str(child), "container": str(child), "mode": "rw"},
            ],
            "env": {},
            "args": [],
            "run": ["/usr/bin/touch", str(child / "testfile")],
        }
        cmd = build_bwrap_command(config)
        result = _run_bwrap(cmd)
        assert result.returncode == 0

    def test_ro_parent_write_fails(self, tmp_path):
        """Writing to the ro-bound parent (outside writable child) should fail."""
        parent = tmp_path / "parent"
        child = parent / "child"
        child.mkdir(parents=True)

        config = {
            "mounts": [
                {"host": "/", "container": "/", "mode": "ro"},
                {"host": str(tmp_path), "container": str(tmp_path), "mode": "rw"},
                {"host": str(parent), "container": str(parent), "mode": "ro"},
                {"host": str(child), "container": str(child), "mode": "rw"},
            ],
            "env": {},
            "args": [],
            "run": ["/usr/bin/touch", str(parent / "cannot_write_here")],
        }
        cmd = build_bwrap_command(config)
        result = _run_bwrap(cmd)
        assert result.returncode != 0


# ── --bind takes priority over --ro-bind for same dir ────────────────────

class TestBindPriorityOverRoBind:
    """When the same container path has both ro and rw mounts, bwrap uses the last one."""

    def test_rw_after_ro_allows_write(self, tmp_path):
        """If --bind comes after --ro-bind for the same path, writes succeed."""
        d = tmp_path / "data"
        d.mkdir()

        # Mount the parent tmp_path rw so bwrap can access the mount point,
        # then overlay with ro → rw for the same dir.
        config = {
            "mounts": [
                {"host": "/", "container": "/", "mode": "ro"},
                {"host": str(tmp_path), "container": str(tmp_path), "mode": "rw"},
                {"host": str(d), "container": str(d), "mode": "ro"},
                {"host": str(d), "container": str(d), "mode": "rw"},
            ],
            "env": {},
            "args": [],
            "run": ["/usr/bin/touch", str(d / "writable_test")],
        }
        cmd = build_bwrap_command(config)
        result = _run_bwrap(cmd)
        assert result.returncode == 0, f"Expected write to succeed: {result.stderr}"

    def test_ro_after_rw_blocks_write(self, tmp_path):
        """If --ro-bind comes after --bind for the same path, writes should fail."""
        d = tmp_path / "data"
        d.mkdir()

        config = {
            "mounts": [
                {"host": "/", "container": "/", "mode": "ro"},
                {"host": str(tmp_path), "container": str(tmp_path), "mode": "rw"},
                {"host": str(d), "container": str(d), "mode": "rw"},
                {"host": str(d), "container": str(d), "mode": "ro"},
            ],
            "env": {},
            "args": [],
            "run": ["/usr/bin/touch", str(d / "should_fail")],
        }
        cmd = build_bwrap_command(config)
        result = _run_bwrap(cmd)
        assert result.returncode != 0, "Expected write to fail with ro override"


# ── composed profiles produce working commands ───────────────────────────

class TestComposedProfilesRun:
    def test_compose_two_profiles_and_run(self, tmp_path):
        """Two profiles merged together should produce a working bwrap invocation."""
        p1 = {
            "mounts": [{"host": "/", "container": "/", "mode": "ro"}],
            "env": {"PROFILE": "one"},
            "args": [],
        }
        p2 = {
            "mounts": [],
            "env": {"EXTRA": "two"},
            "args": [],
            "run": ["/usr/bin/env"],
        }
        merged = compose_profiles([p1, p2])
        cmd = build_bwrap_command(merged)
        result = _run_bwrap(cmd)
        assert result.returncode == 0
        assert "PROFILE=one" in result.stdout
        assert "EXTRA=two" in result.stdout


# ── additional edge-case checks ──────────────────────────────────────────

class TestAdditionalChecks:
    def test_unshare_pid(self):
        """--unshare-pid with --proc should give PID 1 to the child."""
        config = {
            "mounts": [{"host": "/", "container": "/", "mode": "ro"}],
            "env": {},
            "args": ["--unshare-pid", "--proc", "/proc"],
            "run": ["/usr/bin/cat", "/proc/self/status"],
        }
        cmd = build_bwrap_command(config)
        result = _run_bwrap(cmd)
        assert result.returncode == 0
        for line in result.stdout.splitlines():
            if line.startswith("Pid:"):
                pid = int(line.split()[1])
                assert pid <= 2, f"Expected PID ≤ 2 in new PID ns, got {pid}"
                break

    def test_empty_config_still_runs(self):
        """An empty profile (no mounts/env/args) with explicit run should work."""
        config = {
            "mounts": [{"host": "/", "container": "/", "mode": "ro"}],
            "env": {},
            "args": [],
            "run": ["/usr/bin/echo", "ok"],
        }
        cmd = build_bwrap_command(config)
        result = _run_bwrap(cmd)
        assert result.returncode == 0
        assert result.stdout.strip() == "ok"

    def test_multiple_env_vars(self):
        """Multiple env vars should all be visible inside the sandbox."""
        config = {
            "mounts": [{"host": "/", "container": "/", "mode": "ro"}],
            "env": {"A": "1", "B": "2", "C": "3"},
            "args": [],
            "run": ["/usr/bin/env"],
        }
        cmd = build_bwrap_command(config)
        result = _run_bwrap(cmd)
        assert result.returncode == 0
        assert "A=1" in result.stdout
        assert "B=2" in result.stdout
        assert "C=3" in result.stdout

    def test_nonexistent_command_fails(self):
        """Running a nonexistent command should fail gracefully."""
        config = {
            "mounts": [{"host": "/", "container": "/", "mode": "ro"}],
            "env": {},
            "args": [],
            "run": ["/nonexistent_binary_xyz"],
        }
        cmd = build_bwrap_command(config)
        result = _run_bwrap(cmd)
        assert result.returncode != 0
