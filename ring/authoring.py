"""Level validation used by `ring check-levels` and the test suite."""

from __future__ import annotations

import shutil
from pathlib import Path

from .build import Build, BuildError, build
from .checks import Report, grade
from .level import Context, Level


def build_copy(level: Level, src: Path, workdir: Path) -> Build:
    """Build a copy of `src` as if it were a player's solution.asm."""
    workdir.mkdir(parents=True, exist_ok=True)
    copy = workdir / "solution.asm"
    shutil.copy(src, copy)
    return build(copy, workdir / ".build", level.mode,
                 [level.include_dir] if level.include_dir else [], level.prelude)


def check_level(level: Level, ctx: Context, workdir: Path) -> list[str]:
    """Problems with a level: its reference must pass every test, its starter must not."""
    problems = []
    tests = level.all_tests(ctx)
    if not tests:
        problems.append("level has no tests")
    for kind, src in (("reference", level.reference), ("starter", level.starter)):
        try:
            report: Report = grade(level, build_copy(level, src, workdir / kind), tests)
            ok = report.passed
            why = [f"{t.name}: {t.problems}" for t in report.tests if not t.passed][:3]
            why += [ch.name for ch in report.checks if not ch.passed]
        except BuildError as e:
            ok, why = False, [str(e)]
        if kind == "reference" and not ok:
            problems.append(f"reference fails: {why}")
        if kind == "starter" and ok:
            problems.append("starter already passes")
    return problems
