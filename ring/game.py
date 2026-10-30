"""Game actions shared by the CLI and the web UI."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .build import Build, BuildError, build
from .checks import Report
from .level import Context, Level, all_levels
from .progress import Progress, level_dir, workspace


def solution_path(level: Level) -> Path:
    return level_dir(level.number) / "solution.asm"


def context(prog: Progress) -> Context:
    return Context(seed=prog.seed)


def setup_level(level: Level, prog: Progress, force: bool = False) -> list[str]:
    """Create the player's files for a level. Returns a log of what was created."""
    d = level_dir(level.number)
    d.mkdir(parents=True, exist_ok=True)
    log = []
    sol = solution_path(level)
    if force or not sol.exists():
        shutil.copy(level.starter, sol)
        log.append(f"created {sol}")
    if level.include_dir:
        for f in level.include_dir.iterdir():
            shutil.copy(f, d / f.name)
            log.append(f"copied {d / f.name}")
    level.prepare(d, context(prog))
    return log


def build_solution(level: Level, src: Path) -> Build:
    if not src.exists():
        raise BuildError(f"{src} does not exist. Start the level first.")
    b = build(src, src.parent / ".build", level.mode, **level.build_options())
    if level.mode == "program":
        # Whole programs are real Linux executables: put one next to the source so the
        # player can run, strace and gdb it.
        exe = src.parent / src.stem
        shutil.copy(b.elf, exe)
        exe.chmod(0o755)
    return b


@dataclass
class PassResult:
    badges: list[str] = field(default_factory=list)
    first_time: bool = False
    next_level: Level | None = None


def library_dir() -> Path:
    return workspace() / "library"


def library_entries() -> dict[str, tuple[Path, int]]:
    """name -> (file, level it came from), for routines the player has proven."""
    out = {}
    for f in sorted(library_dir().glob("*.asm")) if library_dir().exists() else []:
        first = f.read_text().splitlines()[:1]
        number = int(first[0].split()[-1]) if first and first[0].startswith("; from level") else 0
        out[f.stem] = (f, number)
    return out


def record_pass(prog: Progress, level: Level, report: Report) -> PassResult:
    """Record a successful submission and open the next level."""
    provides = level.data.get("library")
    if provides:
        # The proven solution joins the player's library (used from Arc IV on).
        library_dir().mkdir(parents=True, exist_ok=True)
        (library_dir() / f"{provides}.asm").write_text(
            f"; from level {level.number}\n" + solution_path(level).read_text())
    badges = []
    if report.stretch and all(s.passed for s in report.stretch):
        badges.append(level.stretch.get("label", "stretch goal"))
    first_time = not prog.completed(level.number)
    prog.complete(level.number, len(report.instructions),
                  [f"{level.number}:{b}" for b in badges], next_level=level.number - 1)
    return PassResult(badges, first_time, all_levels().get(level.number - 1))
