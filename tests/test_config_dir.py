"""Tests for the --config-dir CLI option and profile resolution."""

import json
from pathlib import Path

from typer.testing import CliRunner

from bwrap_compose.cli import app, _resolve_profile_path

runner = CliRunner()


class TestResolveProfilePath:
    """Unit tests for _resolve_profile_path."""

    def test_resolves_literal_path(self, tmp_path):
        f = tmp_path / "my.yaml"
        f.write_text("env: {}")
        assert _resolve_profile_path(str(f)) == f

    def test_resolves_from_extra_dir(self, tmp_path):
        d = tmp_path / "cfgs"
        d.mkdir()
        f = d / "foo.yaml"
        f.write_text("env: {}")
        result = _resolve_profile_path("foo", extra_dirs=[d])
        assert result == f

    def test_resolves_yml_extension(self, tmp_path):
        d = tmp_path / "cfgs"
        d.mkdir()
        f = d / "bar.yml"
        f.write_text("env: {}")
        result = _resolve_profile_path("bar", extra_dirs=[d])
        assert result == f

    def test_resolves_json_extension(self, tmp_path):
        d = tmp_path / "cfgs"
        d.mkdir()
        f = d / "baz.json"
        f.write_text('{"env": {}}')
        result = _resolve_profile_path("baz", extra_dirs=[d])
        assert result == f

    def test_extra_dir_takes_priority_over_builtin(self, tmp_path):
        """Extra dirs are searched before the built-in profiles dir."""
        d = tmp_path / "custom"
        d.mkdir()
        f = d / "python-uv.yaml"
        f.write_text("env: {CUSTOM: '1'}")
        result = _resolve_profile_path("python-uv", extra_dirs=[d])
        assert result == f

    def test_falls_back_to_builtin(self):
        """Built-in profiles should still be found without extra dirs."""
        result = _resolve_profile_path("python-uv")
        assert result.name == "python-uv.yaml"


class TestCombineWithConfigDir:
    """CLI-level tests for --config-dir."""

    def test_config_dir_option(self, tmp_path):
        d = tmp_path / "profiles"
        d.mkdir()
        profile = {"env": {"HELLO": "world"}, "run": ["/usr/bin/echo", "hi"]}
        (d / "test-profile.json").write_text(json.dumps(profile))

        result = runner.invoke(app, [
            "combine",
            "--config-dir", str(d),
            "test-profile",
            "--dry-run",
        ])
        assert result.exit_code == 0
        assert "HELLO" in result.output

    def test_multiple_config_dirs(self, tmp_path):
        d1 = tmp_path / "dir1"
        d2 = tmp_path / "dir2"
        d1.mkdir()
        d2.mkdir()
        (d1 / "p1.json").write_text(json.dumps({"env": {"A": "1"}, "run": ["/usr/bin/echo"]}))
        (d2 / "p2.json").write_text(json.dumps({"env": {"B": "2"}, "run": ["/usr/bin/echo"]}))

        result = runner.invoke(app, [
            "combine",
            "--config-dir", str(d1),
            "--config-dir", str(d2),
            "p1", "p2",
            "--dry-run",
        ])
        assert result.exit_code == 0
        assert "A" in result.output
        assert "B" in result.output

    def test_missing_profile_shows_error(self, tmp_path):
        result = runner.invoke(app, [
            "combine",
            "--config-dir", str(tmp_path),
            "nonexistent",
            "--dry-run",
        ])
        assert result.exit_code != 0
