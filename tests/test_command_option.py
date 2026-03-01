"""Tests for the --command CLI option on combine and merge-commands."""

import shlex

from typer.testing import CliRunner

from bwrap_compose.builder import build_bwrap_command
from bwrap_compose.cli import app

runner = CliRunner()


class TestBuildCommandOverride:
    """Unit tests for build_bwrap_command with run_cmd override."""

    def test_run_cmd_overrides_profile_run(self):
        cfg = {
            "mounts": [{"host": "/", "container": "/", "mode": "ro"}],
            "run": ["/original/cmd"],
        }
        cmd = build_bwrap_command(cfg, run_cmd=["/custom/cmd", "--flag"])
        assert cmd[-3] == "--"
        assert cmd[-2:] == ["/custom/cmd", "--flag"]

    def test_run_cmd_none_uses_profile_run(self):
        cfg = {
            "mounts": [],
            "run": ["/bin/echo", "hello"],
        }
        cmd = build_bwrap_command(cfg, run_cmd=None)
        assert cmd[-2:] == ["/bin/echo", "hello"]

    def test_run_cmd_none_no_profile_run_uses_default(self):
        cfg = {"mounts": []}
        cmd = build_bwrap_command(cfg, run_cmd=None)
        assert cmd[-2:] == ["/usr/bin/env", "uv"]


class TestCombineCommandOption:
    """CLI tests for combine --command."""

    def test_combine_with_command_override(self, tmp_path):
        profile = tmp_path / "test.yaml"
        profile.write_text(
            "mounts:\n"
            "  - host: /usr\n"
            "    container: /usr\n"
            "    mode: ro\n"
            "run:\n"
            "  - /original\n"
        )
        result = runner.invoke(app, [
            "combine", str(profile),
            "--command", "/bin/grep pattern",
            "--dry-run",
        ])
        assert result.exit_code == 0
        assert "/bin/grep" in result.output
        assert "pattern" in result.output
        assert "/original" not in result.output

    def test_combine_without_command_uses_profile_run(self, tmp_path):
        profile = tmp_path / "test.yaml"
        profile.write_text(
            "mounts:\n"
            "  - host: /usr\n"
            "    container: /usr\n"
            "    mode: ro\n"
            "run:\n"
            "  - /bin/echo\n"
            "  - hello\n"
        )
        result = runner.invoke(app, [
            "combine", str(profile), "--dry-run",
        ])
        assert result.exit_code == 0
        assert "/bin/echo" in result.output
        assert "hello" in result.output


class TestMergeCommandsCommandOption:
    """CLI tests for merge-commands --command."""

    def test_merge_commands_with_command_override(self):
        result = runner.invoke(app, [
            "merge-commands",
            "bwrap --ro-bind / / -- /bin/sh",
            "bwrap --bind /tmp /tmp -- /bin/sh",
            "--command", "/bin/ls -la",
            "--dry-run",
        ])
        assert result.exit_code == 0
        assert "/bin/ls" in result.output
        assert "-la" in result.output
        # Original /bin/sh should not be the run command
        output_parts = shlex.split(result.output.strip())
        sep_idx = output_parts.index("--")
        run_part = output_parts[sep_idx + 1:]
        assert run_part == ["/bin/ls", "-la"]

    def test_merge_commands_without_command_uses_last_run(self):
        result = runner.invoke(app, [
            "merge-commands",
            "bwrap --ro-bind / / -- /bin/first",
            "bwrap --bind /tmp /tmp -- /bin/second",
            "--dry-run",
        ])
        assert result.exit_code == 0
        output_parts = shlex.split(result.output.strip())
        sep_idx = output_parts.index("--")
        run_part = output_parts[sep_idx + 1:]
        assert run_part == ["/bin/second"]
