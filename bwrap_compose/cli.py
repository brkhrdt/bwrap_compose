from typing import List, Optional
from pathlib import Path
import shlex
import subprocess
import typer

from .config import load_profile
from .composer import compose_profiles
from .builder import build_bwrap_command

app = typer.Typer(help="Compose bubblewrap profiles into a single bwrap command")

# Default directories searched (in order) when a profile name is given.
_BUILTIN_PROFILE_DIR = Path(__file__).resolve().parents[1] / "examples" / "profiles"


def _resolve_profile_path(name: str) -> Path:
    """Resolve a profile name or path to a concrete filesystem path.

    Raises :class:`typer.Exit` when the profile cannot be found.
    """
    path = Path(name)
    if path.exists():
        return path

    alt = _BUILTIN_PROFILE_DIR / f"{name}.yaml"
    if alt.exists():
        return alt

    typer.echo(f"Profile '{name}' not found at {name} or {alt}", err=True)
    raise typer.Exit(code=2)


@app.command()
def combine(
    profiles: List[str] = typer.Argument(..., help="Profile names or file paths"),
    dry_run: bool = typer.Option(True, "--dry-run/--no-dry-run", help="Print command"),
    run: bool = typer.Option(False, "--run", help="Execute the command"),
    output_script: Optional[str] = typer.Option(
        None, "--output-script", "-o", help="Write shell script to path"
    ),
):
    """Combine one or more profile files/names into a single bwrap command.

    Profiles may be file paths or names that match ``examples/profiles/<name>.yaml``.
    """
    profile_dicts = [load_profile(str(_resolve_profile_path(p))) for p in profiles]

    merged = compose_profiles(profile_dicts)
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


def main():
    app()
