"""Additional tests for composer arg grouping and tool manifest validation."""

import os

import pytest

from bwrap_compose.composer import compose_profiles, _group_args
from bwrap_compose.config import validate_profile, load_profile

TOOLS_DIR = os.path.join(os.path.dirname(__file__), "..", "examples", "tools")


class TestArgGrouping:
    """Tests for the arg grouping logic used in deduplication."""

    def test_groups_zero_arg_flags(self):
        args = ["--unshare-all", "--die-with-parent"]
        groups = _group_args(args)
        assert groups == [("--unshare-all",), ("--die-with-parent",)]

    def test_groups_one_arg_flags(self):
        args = ["--dir", "/bin", "--dir", "/lib"]
        groups = _group_args(args)
        assert groups == [("--dir", "/bin"), ("--dir", "/lib")]

    def test_groups_mixed_flags(self):
        args = ["--unshare-all", "--dir", "/bin", "--die-with-parent", "--chdir", "/tmp"]
        groups = _group_args(args)
        assert groups == [
            ("--unshare-all",),
            ("--dir", "/bin"),
            ("--die-with-parent",),
            ("--chdir", "/tmp"),
        ]

    def test_unknown_token_becomes_single_tuple(self):
        args = ["--unknown-flag"]
        groups = _group_args(args)
        assert groups == [("--unknown-flag",)]

    def test_dedup_preserves_different_dir_values(self):
        p1 = {"args": ["--dir", "/bin", "--dir", "/lib"]}
        p2 = {"args": ["--dir", "/bin", "--dir", "/usr"]}
        merged = compose_profiles([p1, p2])
        # /bin appears once, /lib and /usr each appear once
        assert merged["args"].count("--dir") == 3
        assert "/bin" in merged["args"]
        assert "/lib" in merged["args"]
        assert "/usr" in merged["args"]

    def test_dedup_removes_duplicate_dir_pairs(self):
        p1 = {"args": ["--dir", "/bin"]}
        p2 = {"args": ["--dir", "/bin"]}
        merged = compose_profiles([p1, p2])
        assert merged["args"].count("--dir") == 1
        assert merged["args"].count("/bin") == 1

    def test_zero_arg_flags_deduplicated(self):
        p1 = {"args": ["--unshare-all", "--new-session"]}
        p2 = {"args": ["--unshare-all", "--die-with-parent"]}
        merged = compose_profiles([p1, p2])
        assert merged["args"].count("--unshare-all") == 1
        assert "--new-session" in merged["args"]
        assert "--die-with-parent" in merged["args"]


class TestToolManifestValidation:
    """Validate tool manifests against the profile schema."""

    def test_grep_manifest_is_valid(self):
        profile = load_profile(os.path.join(TOOLS_DIR, "grep.yaml"))
        errors = validate_profile(profile)
        assert errors == []

    def test_ls_manifest_is_valid(self):
        profile = load_profile(os.path.join(TOOLS_DIR, "ls.yaml"))
        errors = validate_profile(profile)
        assert errors == []

    def test_merged_profiles_are_valid(self):
        grep = load_profile(os.path.join(TOOLS_DIR, "grep.yaml"))
        ls = load_profile(os.path.join(TOOLS_DIR, "ls.yaml"))
        merged = compose_profiles([grep, ls])
        errors = validate_profile(merged)
        assert errors == []
