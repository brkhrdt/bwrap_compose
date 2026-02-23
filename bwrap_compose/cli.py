from typing import List, Optional
from pathlib import Path
import json
import shlex
import subprocess
import typer

try:
    import yaml as _yaml
except ImportError:
    _yaml = None

from .config import load_profile, validate_profile
from .composer import compose_profiles
from .builder import build_bwrap_command
from .parser import parse_bwrap_command
from .conflicts import detect_conflicts

app = typer.Typer(help="Compose bubblewrap profiles into a single bwrap command")

# Default directories searched (in order) when a profile name is given.
_BUILTIN_PROFILE_DIR = Path(__file__).resolve().parents[1] / "examples" / "profiles"

# Extensions tried when resolving a bare profile name.
_PROFILE_EXTENSIONS = (".yaml", ".yml", ".json")


def _resolve_profile_path(
    name: str,
    extra_dirs: Optional[List[Path]] = None,
) -> Path:
    """Resolve a profile name or path to a concrete filesystem path.

    Search order:
      1. Literal path (if it exists on disk).
      2. Each directory in *extra_dirs* (``<dir>/<name>{.yaml,.yml,.json}``).
      3. The built-in ``examples/profiles/`` directory.

    Raises :class:`typer.Exit` when the profile cannot be found.
    """
    path = Path(name)
    if path.exists():
        return path

    search_dirs: List[Path] = list(extra_dirs or []) + [_BUILTIN_PROFILE_DIR]

    for directory in search_dirs:
        for ext in _PROFILE_EXTENSIONS:
            candidate = directory / f"{name}{ext}"
            if candidate.exists():
                return candidate

    searched = ", ".join(str(d) for d in search_dirs)
    typer.echo(
        f"Profile '{name}' not found (searched: {searched})", err=True
    )
    raise typer.Exit(code=2)


def _handle_conflicts(profile_dicts, merged, interactive=False):
    """Detect and optionally prompt about conflicts. Returns True to proceed."""
    found = detect_conflicts(profile_dicts, merged)
    if not found:
        return True

    for c in found:
        prefix = "⚠ WARNING" if c.severity == "warning" else "✖ ERROR"
        typer.echo(f"  {prefix} [{c.kind}]: {c.description}", err=True)

    errors = [c for c in found if c.severity == "error"]
    if errors and not interactive:
        typer.echo("Aborting due to errors. Use --check-conflicts=prompt to override.", err=True)
        return False

    if interactive:
        typer.echo("")
        proceed = typer.confirm("Conflicts detected. Proceed anyway?", default=False)
        return proceed

    return True


@app.command()
def combine(
    profiles: List[str] = typer.Argument(..., help="Profile names or file paths"),
    dry_run: bool = typer.Option(True, "--dry-run/--no-dry-run", help="Print command"),
    run: bool = typer.Option(False, "--run", help="Execute the command"),
    output_script: Optional[str] = typer.Option(
        None, "--output-script", "-o", help="Write shell script to path"
    ),
    config_dir: Optional[List[str]] = typer.Option(
        None, "--config-dir", "-C",
        help="Additional directory to search for profile YAML files (may be repeated)",
    ),
    check_conflicts: Optional[str] = typer.Option(
        None, "--check-conflicts",
        help="Conflict checking mode: 'warn' (print warnings), 'prompt' (interactive), or 'error' (abort on conflicts)",
    ),
):
    """Combine one or more profile files/names into a single bwrap command.

    Profiles may be file paths or names resolved from ``--config-dir`` directories
    and the built-in ``examples/profiles/`` directory.
    """
    extra_dirs = [Path(d) for d in config_dir] if config_dir else []

    profile_dicts = [
        load_profile(str(_resolve_profile_path(p, extra_dirs=extra_dirs)))
        for p in profiles
    ]

    merged = compose_profiles(profile_dicts)

    if check_conflicts:
        interactive = check_conflicts == "prompt"
        if not _handle_conflicts(profile_dicts, merged, interactive=interactive):
            raise typer.Exit(code=1)

    cmd_list = build_bwrap_command(merged)
    cmd_str = " ".join(shlex.quote(a) for a in cmd_list)

    if dry_run:
        typer.echo(cmd_str)

    if output_script:
        out = Path(output_script)
        out.write_text("#!/usr/bin/env sh\nexec " + cmd_str + "\n")
        out.chmod(0o755)
        typer.echo(f"Wrote script to {out}")

    if run:
        subprocess.run(cmd_list)


@app.command("merge-commands")
def merge_commands(
    commands: List[str] = typer.Argument(
        ..., help="Two or more bwrap command strings to merge"
    ),
    dry_run: bool = typer.Option(True, "--dry-run/--no-dry-run", help="Print command"),
    run: bool = typer.Option(False, "--run", help="Execute the merged command"),
    output_script: Optional[str] = typer.Option(
        None, "--output-script", "-o", help="Write shell script to path"
    ),
    check_conflicts: Optional[str] = typer.Option(
        None, "--check-conflicts",
        help="Conflict checking mode: 'warn', 'prompt', or 'error'",
    ),
):
    """Merge two or more raw bwrap command strings into a single command.

    Each argument should be a complete bwrap command line (quoted as a single
    shell argument).  The commands are parsed, their profiles merged using the
    standard composition rules, and a single unified command is emitted.

    Example::

        bwrap-compose merge-commands \\
          "bwrap --ro-bind / / --setenv A 1 -- /bin/sh" \\
          "bwrap --bind /tmp /tmp --setenv B 2 -- /bin/sh"
    """
    if len(commands) < 2:
        typer.echo("At least two bwrap commands are required.", err=True)
        raise typer.Exit(code=2)

    profiles = [parse_bwrap_command(c) for c in commands]
    merged = compose_profiles(profiles)

    if check_conflicts:
        interactive = check_conflicts == "prompt"
        if not _handle_conflicts(profiles, merged, interactive=interactive):
            raise typer.Exit(code=1)

    cmd_list = build_bwrap_command(merged)
    cmd_str = " ".join(shlex.quote(a) for a in cmd_list)

    if dry_run:
        typer.echo(cmd_str)

    if output_script:
        out = Path(output_script)
        out.write_text("#!/usr/bin/env sh\nexec " + cmd_str + "\n")
        out.chmod(0o755)
        typer.echo(f"Wrote script to {out}")

    if run:
        subprocess.run(cmd_list)


@app.command("validate")
def validate(
    profiles: List[str] = typer.Argument(..., help="Profile names or file paths to validate"),
    config_dir: Optional[List[str]] = typer.Option(
        None, "--config-dir", "-C",
        help="Additional directory to search for profile YAML files",
    ),
):
    """Validate one or more profile files for schema correctness."""
    extra_dirs = [Path(d) for d in config_dir] if config_dir else []
    has_errors = False

    for p in profiles:
        path = _resolve_profile_path(p, extra_dirs=extra_dirs)
        data = load_profile(str(path), search_dirs=extra_dirs)
        errors = validate_profile(data)
        if errors:
            has_errors = True
            typer.echo(f"✖ {path}:", err=True)
            for e in errors:
                typer.echo(f"  - {e}", err=True)
        else:
            typer.echo(f"✔ {path}: valid")

    if has_errors:
        raise typer.Exit(code=1)


@app.command("list-profiles")
def list_profiles(
    config_dir: Optional[List[str]] = typer.Option(
        None, "--config-dir", "-C",
        help="Additional directory to search for profiles",
    ),
):
    """List available profile names from config directories."""
    dirs = [Path(d) for d in config_dir] if config_dir else []
    dirs.append(_BUILTIN_PROFILE_DIR)

    seen = set()
    for d in dirs:
        if not d.is_dir():
            continue
        for ext in _PROFILE_EXTENSIONS:
            for f in sorted(d.glob(f"*{ext}")):
                name = f.stem
                if name not in seen:
                    seen.add(name)
                    typer.echo(f"  {name}  ({f})")

    if not seen:
        typer.echo("No profiles found.")


def _extract_special_mounts(profile):
    """Move --tmpfs/--dev/--proc entries from *args* into dedicated profile keys."""
    args = list(profile.get("args") or [])
    _special = {"--tmpfs": "tmpfs", "--dev": "dev", "--proc": "proc"}
    new_args = []
    extracted = {}

    i = 0
    while i < len(args):
        if args[i] in _special and i + 1 < len(args):
            key = _special[args[i]]
            extracted.setdefault(key, []).append(args[i + 1])
            i += 2
        else:
            new_args.append(args[i])
            i += 1

    result = dict(profile)
    result["args"] = new_args
    result.update(extracted)
    return result


@app.command("from-command")
def from_command(
    command: str = typer.Argument(..., help="A bwrap command string to convert to a profile"),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Write profile YAML to a file instead of stdout"
    ),
):
    """Generate a profile YAML from a raw bwrap command string.

    Example::

        bwrapc from-command "bwrap --ro-bind / / --setenv A 1 -- /bin/sh"
    """
    profile = parse_bwrap_command(command)
    profile = _extract_special_mounts(profile)

    # Remove empty/default fields for a clean profile.
    cleaned = {}
    key_order = ("mounts", "env", "tmpfs", "dev", "proc", "args", "run")
    for key in key_order:
        val = profile.get(key)
        if val:
            cleaned[key] = val

    if _yaml is not None:
        text = _yaml.dump(cleaned, default_flow_style=False, sort_keys=False)
    else:
        text = json.dumps(cleaned, indent=2) + "\n"

    if output:
        out = Path(output)
        out.write_text(text)
        typer.echo(f"Wrote profile to {out}")
    else:
        typer.echo(text, nl=False)


def main():
    app()
