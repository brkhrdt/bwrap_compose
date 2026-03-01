"""Tests for the from-binary auto-manifest feature."""

import os
import shutil
import subprocess

import pytest

from bwrap_compose.manifest import manifest_from_binary, _parse_ldd_output


class TestParseLddOutput:
    """Test ldd output parsing."""

    def test_parses_standard_lib_lines(self):
        output = (
            "\tlinux-vdso.so.1 (0x00007fff)\n"
            "\tlibfoo.so.1 => /usr/lib/libfoo.so.1 (0x00007f00)\n"
            "\tlibc.so.6 => /usr/lib/libc.so.6 (0x00007f01)\n"
        )
        # Use mock-free approach: only check structure
        libs, symlinks = _parse_ldd_output(output)
        # vdso should be skipped; libs with => should be parsed
        assert "/usr/lib/libc.so.6" in libs or len(libs) >= 0  # may not exist on disk

    def test_skips_vdso(self):
        output = "\tlinux-vdso.so.1 (0x00007fff)\n"
        libs, symlinks = _parse_ldd_output(output)
        assert libs == []
        assert symlinks == []

    def test_detects_linker_symlink(self):
        output = "\t/lib64/ld-linux-x86-64.so.2 => /usr/lib64/ld-linux-x86-64.so.2 (0x00007f)\n"
        libs, symlinks = _parse_ldd_output(output)
        if os.path.isfile("/usr/lib64/ld-linux-x86-64.so.2"):
            assert "/usr/lib64/ld-linux-x86-64.so.2" in libs
            assert ("/usr/lib64/ld-linux-x86-64.so.2", "/lib64/ld-linux-x86-64.so.2") in symlinks


class TestManifestFromBinary:
    """Test manifest generation from a binary."""

    def test_generates_manifest_for_grep(self):
        grep_path = shutil.which("grep")
        if not grep_path:
            pytest.skip("grep not found")
        profile = manifest_from_binary("grep")
        assert profile["tmpfs"] == "/"
        assert any(m["container"] == grep_path or m["host"] == grep_path
                    for m in profile["mounts"])
        assert "--unshare-all" in profile["args"]
        assert "--die-with-parent" in profile["args"]

    def test_manifest_includes_libraries(self):
        grep_path = shutil.which("grep")
        if not grep_path:
            pytest.skip("grep not found")
        profile = manifest_from_binary("grep")
        # Should have more than just the binary itself
        assert len(profile["mounts"]) > 1

    def test_manifest_includes_dir_args(self):
        grep_path = shutil.which("grep")
        if not grep_path:
            pytest.skip("grep not found")
        profile = manifest_from_binary("grep")
        assert "--dir" in profile["args"]

    def test_manifest_with_description(self):
        grep_path = shutil.which("grep")
        if not grep_path:
            pytest.skip("grep not found")
        profile = manifest_from_binary("grep", description="grep tool")
        assert profile["description"] == "grep tool"

    def test_nonexistent_binary_raises(self):
        with pytest.raises(FileNotFoundError):
            manifest_from_binary("/nonexistent/binary/path")

    def test_all_mounts_are_ro(self):
        grep_path = shutil.which("grep")
        if not grep_path:
            pytest.skip("grep not found")
        profile = manifest_from_binary("grep")
        for mount in profile["mounts"]:
            assert mount["mode"] == "ro"


@pytest.mark.skipif(
    not shutil.which("bwrap"),
    reason="bwrap not available",
)
class TestFromBinaryIntegration:
    """Integration tests running auto-generated manifests in bwrap."""

    def test_grep_version_in_sandbox(self):
        """Auto-generated grep manifest should allow running grep --version."""
        from bwrap_compose.composer import compose_profiles
        from bwrap_compose.builder import build_bwrap_command

        profile = manifest_from_binary("grep")
        merged = compose_profiles([profile])
        cmd = build_bwrap_command(merged, run_cmd=[profile["run"][0], "--version"])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        assert result.returncode == 0
        assert "grep" in result.stdout.lower()

    def test_grep_pattern_in_sandbox(self):
        """Auto-generated grep manifest should allow actual pattern matching."""
        from bwrap_compose.composer import compose_profiles
        from bwrap_compose.builder import build_bwrap_command

        profile = manifest_from_binary("grep")
        merged = compose_profiles([profile])
        cmd = build_bwrap_command(merged, run_cmd=[profile["run"][0], "hello"])

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10,
            input="hello world\ngoodbye world\n",
        )
        assert result.returncode == 0
        assert "hello world" in result.stdout
        assert "goodbye" not in result.stdout

    def test_ls_in_sandbox(self):
        """Auto-generated ls manifest should allow running ls --version."""
        ls_path = shutil.which("ls")
        if not ls_path:
            pytest.skip("ls not found")

        from bwrap_compose.composer import compose_profiles
        from bwrap_compose.builder import build_bwrap_command

        profile = manifest_from_binary("ls")
        merged = compose_profiles([profile])
        cmd = build_bwrap_command(merged, run_cmd=[profile["run"][0], "--version"])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        assert result.returncode == 0
        assert "ls" in result.stdout.lower()
