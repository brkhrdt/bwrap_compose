"""Tests for conflict detection and the --check-conflicts CLI option."""

import json
from pathlib import Path

from typer.testing import CliRunner

from bwrap_compose.conflicts import detect_conflicts, Conflict
from bwrap_compose.cli import app

runner = CliRunner()


class TestMountModeConflicts:
    def test_same_path_different_modes(self):
        profiles = [
            {"mounts": [{"host": "/data", "container": "/data", "mode": "ro"}]},
            {"mounts": [{"host": "/data", "container": "/data", "mode": "rw"}]},
        ]
        conflicts = detect_conflicts(profiles)
        kinds = [c.kind for c in conflicts]
        assert "mount-mode" in kinds

    def test_no_conflict_same_mode(self):
        profiles = [
            {"mounts": [{"host": "/data", "container": "/data", "mode": "ro"}]},
            {"mounts": [{"host": "/data", "container": "/data", "mode": "ro"}]},
        ]
        conflicts = detect_conflicts(profiles)
        assert not any(c.kind == "mount-mode" for c in conflicts)


class TestRoWritableSubdir:
    def test_writable_under_ro(self):
        profiles = [
            {"mounts": [
                {"host": "/", "container": "/", "mode": "ro"},
                {"host": "/tmp", "container": "/home/user", "mode": "rw"},
            ]},
        ]
        conflicts = detect_conflicts(profiles)
        kinds = [c.kind for c in conflicts]
        assert "ro-writable-subdir" in kinds

    def test_no_conflict_sibling_paths(self):
        profiles = [
            {"mounts": [
                {"host": "/a", "container": "/a", "mode": "ro"},
                {"host": "/b", "container": "/b", "mode": "rw"},
            ]},
        ]
        conflicts = detect_conflicts(profiles)
        assert not any(c.kind == "ro-writable-subdir" for c in conflicts)


class TestEnvOverrides:
    def test_env_override_detected(self):
        profiles = [
            {"env": {"PATH": "/usr/bin"}},
            {"env": {"PATH": "/usr/local/bin"}},
        ]
        conflicts = detect_conflicts(profiles)
        kinds = [c.kind for c in conflicts]
        assert "env-override" in kinds

    def test_env_same_value_no_conflict(self):
        profiles = [
            {"env": {"A": "1"}},
            {"env": {"A": "1"}},
        ]
        conflicts = detect_conflicts(profiles)
        assert not any(c.kind == "env-override" for c in conflicts)


class TestNamespaceContradictions:
    def test_unshare_and_share_net(self):
        profiles = [
            {"args": ["--unshare-net"]},
            {"args": ["--share-net"]},
        ]
        conflicts = detect_conflicts(profiles)
        kinds = [c.kind for c in conflicts]
        assert "ns-contradiction" in kinds

    def test_no_contradiction(self):
        profiles = [
            {"args": ["--unshare-net"]},
            {"args": ["--unshare-pid"]},
        ]
        conflicts = detect_conflicts(profiles)
        assert not any(c.kind == "ns-contradiction" for c in conflicts)


class TestNoConflicts:
    def test_clean_profiles(self):
        profiles = [
            {"mounts": [{"host": "/a", "container": "/a", "mode": "ro"}], "env": {"X": "1"}},
            {"mounts": [{"host": "/b", "container": "/b", "mode": "rw"}], "env": {"Y": "2"}},
        ]
        assert detect_conflicts(profiles) == []


class TestCheckConflictsCLI:
    def test_warn_mode_prints_conflicts(self, tmp_path):
        d = tmp_path / "profiles"
        d.mkdir()
        p1 = {"mounts": [{"host": "/data", "container": "/data", "mode": "ro"}],
               "run": ["/bin/echo"]}
        p2 = {"mounts": [{"host": "/data", "container": "/data", "mode": "rw"}],
               "run": ["/bin/echo"]}
        (d / "a.json").write_text(json.dumps(p1))
        (d / "b.json").write_text(json.dumps(p2))

        result = runner.invoke(app, [
            "combine",
            "--config-dir", str(d),
            "--check-conflicts", "warn",
            "a", "b",
            "--dry-run",
        ])
        # warn mode still succeeds
        assert result.exit_code == 0
        assert "mount-mode" in result.output

    def test_error_mode_aborts(self, tmp_path):
        d = tmp_path / "profiles"
        d.mkdir()
        p1 = {"args": ["--unshare-net"], "run": ["/bin/echo"]}
        p2 = {"args": ["--share-net"], "run": ["/bin/echo"]}
        (d / "a.json").write_text(json.dumps(p1))
        (d / "b.json").write_text(json.dumps(p2))

        result = runner.invoke(app, [
            "combine",
            "--config-dir", str(d),
            "--check-conflicts", "error",
            "a", "b",
            "--dry-run",
        ])
        assert result.exit_code == 1

    def test_no_conflicts_proceeds(self, tmp_path):
        d = tmp_path / "profiles"
        d.mkdir()
        p1 = {"mounts": [{"host": "/a", "container": "/a", "mode": "ro"}],
               "run": ["/bin/echo"]}
        (d / "a.json").write_text(json.dumps(p1))

        result = runner.invoke(app, [
            "combine",
            "--config-dir", str(d),
            "--check-conflicts", "warn",
            "a",
            "--dry-run",
        ])
        assert result.exit_code == 0

    def test_merge_commands_check_conflicts(self):
        result = runner.invoke(app, [
            "merge-commands",
            "--check-conflicts", "warn",
            "bwrap --ro-bind / / --setenv A 1 -- /bin/sh",
            "bwrap --ro-bind / / --setenv A 2 -- /bin/sh",
            "--dry-run",
        ])
        assert result.exit_code == 0
        assert "env-override" in result.output
