"""Tests for task-6 additional features: validate, list-profiles, extends, tmpfs/dev/proc."""

import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from bwrap_compose.config import load_profile, validate_profile
from bwrap_compose.composer import compose_profiles
from bwrap_compose.builder import build_bwrap_command
from bwrap_compose.cli import app

runner = CliRunner()


# ── Profile validation ───────────────────────────────────────────────────

class TestValidateProfile:
    def test_valid_profile(self):
        data = {"mounts": [{"host": "/a", "container": "/a"}], "env": {"X": "1"}}
        assert validate_profile(data) == []

    def test_unknown_keys(self):
        data = {"mounts": [], "bogus": True}
        errors = validate_profile(data)
        assert any("Unknown" in e for e in errors)

    def test_mounts_must_be_list(self):
        data = {"mounts": "not-a-list"}
        errors = validate_profile(data)
        assert any("list" in e for e in errors)

    def test_mount_missing_host(self):
        data = {"mounts": [{"container": "/a"}]}
        errors = validate_profile(data)
        assert any("host" in e for e in errors)

    def test_mount_missing_container(self):
        data = {"mounts": [{"host": "/a"}]}
        errors = validate_profile(data)
        assert any("container" in e for e in errors)

    def test_env_must_be_dict(self):
        data = {"env": "bad"}
        errors = validate_profile(data)
        assert any("mapping" in e for e in errors)

    def test_args_must_be_list(self):
        data = {"args": "bad"}
        errors = validate_profile(data)
        assert any("list" in e for e in errors)

    def test_run_can_be_string(self):
        data = {"run": "echo hello"}
        assert validate_profile(data) == []

    def test_run_can_be_list(self):
        data = {"run": ["/bin/echo", "hello"]}
        assert validate_profile(data) == []

    def test_run_bad_type(self):
        data = {"run": 123}
        errors = validate_profile(data)
        assert any("run" in e for e in errors)

    def test_tmpfs_string(self):
        assert validate_profile({"tmpfs": "/tmp"}) == []

    def test_tmpfs_list(self):
        assert validate_profile({"tmpfs": ["/tmp", "/var"]}) == []

    def test_tmpfs_bad_type(self):
        errors = validate_profile({"tmpfs": 123})
        assert len(errors) > 0


class TestValidateCLI:
    def test_validate_valid_file(self, tmp_path):
        f = tmp_path / "good.json"
        f.write_text(json.dumps({"env": {"A": "1"}}))
        result = runner.invoke(app, ["validate", str(f)])
        assert result.exit_code == 0
        assert "valid" in result.output

    def test_validate_invalid_file(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text(json.dumps({"mounts": "not-a-list"}))
        result = runner.invoke(app, ["validate", str(f)])
        assert result.exit_code == 1


# ── Profile inheritance (extends) ────────────────────────────────────────

class TestExtends:
    def test_simple_extends(self, tmp_path):
        base = {"mounts": [{"host": "/", "container": "/", "mode": "ro"}], "env": {"A": "1"}}
        child = {"extends": "base", "env": {"B": "2"}, "run": ["/bin/echo"]}
        (tmp_path / "base.yaml").write_text(yaml.dump(base))
        (tmp_path / "child.yaml").write_text(yaml.dump(child))

        data = load_profile(str(tmp_path / "child.yaml"))
        assert data["env"]["A"] == "1"
        assert data["env"]["B"] == "2"
        assert len(data["mounts"]) == 1

    def test_extends_list(self, tmp_path):
        p1 = {"env": {"X": "1"}}
        p2 = {"env": {"Y": "2"}}
        child = {"extends": ["p1", "p2"], "env": {"Z": "3"}}
        (tmp_path / "p1.yaml").write_text(yaml.dump(p1))
        (tmp_path / "p2.yaml").write_text(yaml.dump(p2))
        (tmp_path / "child.yaml").write_text(yaml.dump(child))

        data = load_profile(str(tmp_path / "child.yaml"))
        assert data["env"] == {"X": "1", "Y": "2", "Z": "3"}

    def test_extends_circular_detected(self, tmp_path):
        a = {"extends": "b", "env": {"A": "1"}}
        b = {"extends": "a", "env": {"B": "2"}}
        (tmp_path / "a.yaml").write_text(yaml.dump(a))
        (tmp_path / "b.yaml").write_text(yaml.dump(b))

        import pytest
        with pytest.raises(ValueError, match="Circular"):
            load_profile(str(tmp_path / "a.yaml"))

    def test_extends_child_overrides_parent(self, tmp_path):
        base = {"env": {"A": "old", "B": "keep"}}
        child = {"extends": "base", "env": {"A": "new"}}
        (tmp_path / "base.yaml").write_text(yaml.dump(base))
        (tmp_path / "child.yaml").write_text(yaml.dump(child))

        data = load_profile(str(tmp_path / "child.yaml"))
        assert data["env"]["A"] == "new"
        assert data["env"]["B"] == "keep"


# ── tmpfs/dev/proc in profiles ───────────────────────────────────────────

class TestSpecialMounts:
    def test_tmpfs_in_builder(self):
        config = {
            "mounts": [{"host": "/", "container": "/", "mode": "ro"}],
            "tmpfs": ["/tmp"],
            "run": ["/bin/echo"],
        }
        cmd = build_bwrap_command(config)
        assert "--tmpfs" in cmd
        idx = cmd.index("--tmpfs")
        assert cmd[idx + 1] == "/tmp"

    def test_dev_in_builder(self):
        config = {
            "mounts": [{"host": "/", "container": "/", "mode": "ro"}],
            "dev": "/dev",
            "run": ["/bin/echo"],
        }
        cmd = build_bwrap_command(config)
        assert "--dev" in cmd

    def test_proc_in_builder(self):
        config = {
            "mounts": [{"host": "/", "container": "/", "mode": "ro"}],
            "proc": "/proc",
            "run": ["/bin/echo"],
        }
        cmd = build_bwrap_command(config)
        assert "--proc" in cmd

    def test_compose_merges_tmpfs(self):
        p1 = {"tmpfs": ["/tmp"]}
        p2 = {"tmpfs": ["/var"]}
        merged = compose_profiles([p1, p2])
        assert "/tmp" in merged["tmpfs"]
        assert "/var" in merged["tmpfs"]

    def test_compose_deduplicates_tmpfs(self):
        p1 = {"tmpfs": ["/tmp"]}
        p2 = {"tmpfs": ["/tmp"]}
        merged = compose_profiles([p1, p2])
        assert merged["tmpfs"].count("/tmp") == 1


# ── list-profiles command ────────────────────────────────────────────────

class TestListProfiles:
    def test_list_builtin_profiles(self):
        result = runner.invoke(app, ["list-profiles"])
        assert result.exit_code == 0
        assert "python-uv" in result.output

    def test_list_with_custom_dir(self, tmp_path):
        (tmp_path / "custom.yaml").write_text(yaml.dump({"env": {}}))
        result = runner.invoke(app, ["list-profiles", "--config-dir", str(tmp_path)])
        assert result.exit_code == 0
        assert "custom" in result.output
