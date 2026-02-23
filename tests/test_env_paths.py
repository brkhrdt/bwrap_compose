"""Tests for environment variable and tilde expansion in mount paths."""

import os
from unittest import mock

from bwrap_compose.builder import build_bwrap_command, _expand_path


class TestExpandPath:
    def test_tilde_expanded(self):
        result = _expand_path("~/Documents")
        assert result == os.path.expanduser("~/Documents")
        assert "~" not in result

    def test_env_var_expanded(self):
        with mock.patch.dict(os.environ, {"MY_VAR": "/custom/path"}):
            result = _expand_path("$MY_VAR/sub")
        assert result == "/custom/path/sub"

    def test_home_env_expanded(self):
        home = os.environ.get("HOME", "/home/test")
        result = _expand_path("$HOME/.config")
        assert result == f"{home}/.config"

    def test_single_quoted_not_expanded(self):
        result = _expand_path("'$HOME/.config'")
        assert result == "$HOME/.config"

    def test_single_quoted_tilde_not_expanded(self):
        result = _expand_path("'~/Documents'")
        assert result == "~/Documents"

    def test_plain_path_unchanged(self):
        result = _expand_path("/usr/bin")
        assert result == "/usr/bin"

    def test_empty_string(self):
        result = _expand_path("")
        assert result == ""

    def test_single_quote_char_alone(self):
        result = _expand_path("'")
        # A single quote alone is not a quoted pair; treat as literal.
        assert "'" in result or result == "'"


class TestBuildWithEnvPaths:
    def test_tilde_in_mount_expanded(self):
        home = os.path.expanduser("~")
        cfg = {
            "mounts": [{"host": "~/.config", "container": "~/.config", "mode": "ro"}],
            "run": ["/bin/echo"],
        }
        cmd = build_bwrap_command(cfg)
        assert f"{home}/.config" in cmd

    def test_env_var_in_mount_expanded(self):
        home = os.environ.get("HOME", "/home/test")
        cfg = {
            "mounts": [{"host": "$HOME/.config", "container": "$HOME/.config", "mode": "ro"}],
            "run": ["/bin/echo"],
        }
        cmd = build_bwrap_command(cfg)
        assert f"{home}/.config" in cmd

    def test_single_quoted_mount_not_expanded(self):
        cfg = {
            "mounts": [{"host": "'$HOME/.config'", "container": "'$HOME/.config'", "mode": "ro"}],
            "run": ["/bin/echo"],
        }
        cmd = build_bwrap_command(cfg)
        assert "$HOME/.config" in cmd
        # The literal $HOME should be in the command, not expanded
        home = os.environ.get("HOME", "/home/test")
        idx = cmd.index("--ro-bind")
        assert cmd[idx + 1] == "$HOME/.config"
        assert cmd[idx + 2] == "$HOME/.config"

    def test_mixed_mounts(self):
        """One mount expanded, one kept literal."""
        home = os.path.expanduser("~")
        cfg = {
            "mounts": [
                {"host": "~/.config", "container": "/config", "mode": "ro"},
                {"host": "'$HOME/data'", "container": "/data", "mode": "rw"},
            ],
            "run": ["/bin/echo"],
        }
        cmd = build_bwrap_command(cfg)
        ro_idx = cmd.index("--ro-bind")
        assert cmd[ro_idx + 1] == f"{home}/.config"
        bind_idx = cmd.index("--bind")
        assert cmd[bind_idx + 1] == "$HOME/data"

    def test_custom_env_var_in_mount(self):
        with mock.patch.dict(os.environ, {"APP_DIR": "/opt/myapp"}):
            cfg = {
                "mounts": [{"host": "$APP_DIR/lib", "container": "/lib", "mode": "ro"}],
                "run": ["/bin/echo"],
            }
            cmd = build_bwrap_command(cfg)
            assert "/opt/myapp/lib" in cmd
