"""Tests for bwrap command parsing and the merge-commands CLI."""

import shlex

from typer.testing import CliRunner

from bwrap_compose.parser import parse_bwrap_command
from bwrap_compose.composer import compose_profiles
from bwrap_compose.builder import build_bwrap_command
from bwrap_compose.cli import app

runner = CliRunner()


class TestParseBwrapCommand:
    def test_basic_parse(self):
        cmd = "bwrap --ro-bind / / --setenv A 1 -- /bin/sh"
        result = parse_bwrap_command(cmd)
        assert result["mounts"] == [{"host": "/", "container": "/", "mode": "ro"}]
        assert result["env"] == {"A": "1"}
        assert result["run"] == ["/bin/sh"]

    def test_rw_bind(self):
        cmd = "bwrap --bind /tmp /tmp -- /bin/echo"
        result = parse_bwrap_command(cmd)
        assert result["mounts"] == [{"host": "/tmp", "container": "/tmp", "mode": "rw"}]

    def test_multiple_mounts_and_env(self):
        cmd = "bwrap --ro-bind / / --bind /home /home --setenv X 1 --setenv Y 2 -- /usr/bin/env"
        result = parse_bwrap_command(cmd)
        assert len(result["mounts"]) == 2
        assert result["env"] == {"X": "1", "Y": "2"}
        assert result["run"] == ["/usr/bin/env"]

    def test_extra_args_preserved(self):
        cmd = "bwrap --ro-bind / / --unshare-pid --unshare-net -- /bin/sh"
        result = parse_bwrap_command(cmd)
        assert "--unshare-pid" in result["args"]
        assert "--unshare-net" in result["args"]

    def test_no_run_command(self):
        cmd = "bwrap --ro-bind / /"
        result = parse_bwrap_command(cmd)
        assert "run" not in result

    def test_without_bwrap_prefix(self):
        cmd = "--ro-bind / / -- /bin/echo hello"
        result = parse_bwrap_command(cmd)
        assert result["mounts"] == [{"host": "/", "container": "/", "mode": "ro"}]
        assert result["run"] == ["/bin/echo", "hello"]

    def test_tmpfs_and_proc_as_args(self):
        cmd = "bwrap --ro-bind / / --tmpfs /tmp --proc /proc -- /bin/sh"
        result = parse_bwrap_command(cmd)
        assert "--tmpfs" in result["args"]
        assert "/tmp" in result["args"]
        assert "--proc" in result["args"]
        assert "/proc" in result["args"]


class TestMergeRoundTrip:
    """Parse two commands, merge, and verify the result."""

    def test_merge_two_commands(self):
        cmd1 = "bwrap --ro-bind / / --setenv A 1 -- /bin/sh"
        cmd2 = "bwrap --bind /tmp /tmp --setenv B 2 -- /usr/bin/env"

        p1 = parse_bwrap_command(cmd1)
        p2 = parse_bwrap_command(cmd2)
        merged = compose_profiles([p1, p2])
        result = build_bwrap_command(merged)

        assert "bwrap" == result[0]
        assert "--ro-bind" in result
        assert "--bind" in result
        # Both env vars present
        idx_a = result.index("A")
        assert result[idx_a + 1] == "1"
        idx_b = result.index("B")
        assert result[idx_b + 1] == "2"
        # Last run wins
        assert result[-1] == "/usr/bin/env"

    def test_merge_preserves_args(self):
        cmd1 = "bwrap --ro-bind / / --unshare-pid -- /bin/sh"
        cmd2 = "bwrap --ro-bind / / --unshare-net -- /bin/sh"

        p1 = parse_bwrap_command(cmd1)
        p2 = parse_bwrap_command(cmd2)
        merged = compose_profiles([p1, p2])
        result = build_bwrap_command(merged)

        assert "--unshare-pid" in result
        assert "--unshare-net" in result


class TestMergeCommandsCLI:
    def test_merge_commands_dry_run(self):
        result = runner.invoke(app, [
            "merge-commands",
            "bwrap --ro-bind / / --setenv A 1 -- /bin/sh",
            "bwrap --bind /tmp /tmp --setenv B 2 -- /usr/bin/env",
            "--dry-run",
        ])
        assert result.exit_code == 0
        assert "--ro-bind" in result.output
        assert "--bind" in result.output
        assert "A" in result.output
        assert "B" in result.output

    def test_merge_commands_requires_two(self):
        result = runner.invoke(app, [
            "merge-commands",
            "bwrap --ro-bind / / -- /bin/sh",
        ])
        assert result.exit_code != 0

    def test_merge_commands_output_script(self, tmp_path):
        script = tmp_path / "merged.sh"
        result = runner.invoke(app, [
            "merge-commands",
            "bwrap --ro-bind / / -- /bin/sh",
            "bwrap --bind /tmp /tmp -- /bin/sh",
            "--output-script", str(script),
        ])
        assert result.exit_code == 0
        assert script.exists()
        content = script.read_text()
        assert content.startswith("#!/usr/bin/env sh")
        assert "--ro-bind" in content
