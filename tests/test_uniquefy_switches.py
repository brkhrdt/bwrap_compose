"""Tests for switch uniquification and organization in the composer."""

from bwrap_compose.composer import compose_profiles, _group_args, _organize_args


class TestTwoArgGrouping:
    """Test that two-arg flags are properly grouped for dedup."""

    def test_symlink_grouped_as_triple(self):
        args = ["--symlink", "/usr/lib/x86_64-linux-gnu/libc.so.6", "/lib/libc.so.6"]
        groups = _group_args(args)
        assert groups == [
            ("--symlink", "/usr/lib/x86_64-linux-gnu/libc.so.6", "/lib/libc.so.6"),
        ]

    def test_bind_grouped_as_triple(self):
        args = ["--ro-bind", "/usr/bin/grep", "/usr/bin/grep"]
        groups = _group_args(args)
        assert groups == [("--ro-bind", "/usr/bin/grep", "/usr/bin/grep")]

    def test_duplicate_symlinks_deduplicated(self):
        p1 = {"args": ["--symlink", "/a", "/b"]}
        p2 = {"args": ["--symlink", "/a", "/b"]}
        merged = compose_profiles([p1, p2])
        assert merged["args"].count("--symlink") == 1

    def test_different_symlinks_preserved(self):
        p1 = {"args": ["--symlink", "/a", "/b"]}
        p2 = {"args": ["--symlink", "/c", "/d"]}
        merged = compose_profiles([p1, p2])
        assert merged["args"].count("--symlink") == 2

    def test_duplicate_ro_bind_in_args_deduplicated(self):
        p1 = {"args": ["--ro-bind", "/usr/bin/grep", "/usr/bin/grep"]}
        p2 = {"args": ["--ro-bind", "/usr/bin/grep", "/usr/bin/grep"]}
        merged = compose_profiles([p1, p2])
        assert merged["args"].count("--ro-bind") == 1

    def test_mixed_two_arg_and_one_arg_grouping(self):
        args = [
            "--symlink", "/a", "/b",
            "--dir", "/tmp",
            "--ro-bind", "/x", "/y",
        ]
        groups = _group_args(args)
        assert groups == [
            ("--symlink", "/a", "/b"),
            ("--dir", "/tmp"),
            ("--ro-bind", "/x", "/y"),
        ]


class TestArgsOrganization:
    """Test that merged args are organized by category."""

    def test_namespace_flags_come_first(self):
        p1 = {"args": ["--dir", "/bin", "--unshare-all"]}
        p2 = {"args": ["--chdir", "/tmp", "--die-with-parent"]}
        merged = compose_profiles([p1, p2])
        args = merged["args"]
        # Namespace flags should be before dir and late flags
        ns_end = max(args.index("--die-with-parent"), args.index("--unshare-all"))
        dir_start = args.index("--dir")
        assert ns_end < dir_start

    def test_late_flags_come_last(self):
        p1 = {"args": ["--chdir", "/home", "--unshare-pid", "--dir", "/bin"]}
        merged = compose_profiles([p1])
        args = merged["args"]
        # --chdir should be after --dir and --unshare-pid
        chdir_idx = args.index("--chdir")
        assert chdir_idx == len(args) - 2  # --chdir /home at end

    def test_namespace_flags_sorted(self):
        p1 = {"args": ["--unshare-pid", "--die-with-parent", "--as-pid-1"]}
        merged = compose_profiles([p1])
        ns_flags = [a for a in merged["args"] if a.startswith("--")]
        assert ns_flags == sorted(ns_flags)

    def test_organize_preserves_all_args(self):
        original = [
            "--chdir", "/home",
            "--dir", "/bin",
            "--unshare-all",
            "--symlink", "/a", "/b",
            "--uid", "1000",
        ]
        organized = _organize_args(original)
        # All tokens are preserved
        assert sorted(organized) == sorted(original)

    def test_full_merge_organized(self):
        p1 = {
            "args": ["--chdir", "/work", "--dir", "/bin"],
        }
        p2 = {
            "args": ["--unshare-all", "--dir", "/lib", "--die-with-parent"],
        }
        merged = compose_profiles([p1, p2])
        args = merged["args"]
        # Check order: namespace, dirs, late
        assert args.index("--unshare-all") < args.index("--dir")
        assert args.index("--die-with-parent") < args.index("--dir")
        assert args.index("--chdir") > args.index("--dir")

    def test_dedup_and_organize_combined(self):
        """Dedup should work with organization."""
        p1 = {"args": ["--unshare-all", "--dir", "/bin", "--chdir", "/home"]}
        p2 = {"args": ["--dir", "/bin", "--unshare-all", "--chdir", "/home"]}
        merged = compose_profiles([p1, p2])
        args = merged["args"]
        assert args.count("--unshare-all") == 1
        assert args.count("--dir") == 1
        assert args.count("--chdir") == 1
        # Organized: namespace first, dir middle, chdir last
        assert args.index("--unshare-all") < args.index("--dir")
        assert args.index("--dir") < args.index("--chdir")
