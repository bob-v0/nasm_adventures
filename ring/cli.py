"""`ring` — the NASM Adventures command line."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import briefs, docs
from .build import BuildError, _inspect
from .checks import Report, grade
from .level import Context, Level, all_levels
from .game import (build_solution, context, library_entries, record_pass, setup_level,
                   solution_path)
from .progress import Progress, SaveError, dev_mode, workspace

COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if COLOR else text


OK, FAIL, NOTE = c("32", "✔"), c("31", "✘"), c("2", "─")


class CliError(Exception):
    pass


# ---- helpers ------------------------------------------------------------------------

def get_level(number: int | None, prog: Progress) -> Level:
    levels = all_levels()
    number = prog.current if number is None else number
    if number not in levels:
        raise CliError(f"level {number} does not exist yet." if number >= 0 else "no such level")
    if not prog.unlocked(number):
        raise CliError(f"level {number} is sealed. You are at level {prog.current}.")
    return levels[number]


def print_report(level: Level, report: Report, show_hidden_names: bool) -> None:
    public = [t for t in report.tests if not t.hidden]
    hidden = [t for t in report.tests if t.hidden]
    print(c("1", f"Level {level.number} — {level.title}"))
    if report.warnings:
        print(c("33", "  assembler warnings:"))
        for line in report.warnings.splitlines():
            print(f"    {line}")
    for t in public:
        print(f"  {OK if t.passed else FAIL} {t.name}")
        for p in t.problems:
            print(f"      {p}")
    if hidden:
        failed = [t for t in hidden if not t.passed]
        print(f"  {OK if not failed else FAIL} hidden tests  {len(hidden) - len(failed)}/{len(hidden)}")
        if failed:
            first = failed[0]
            name = first.name if show_hidden_names else "a hidden test"
            print(f"      first failure ({name}): {first.problems[0]}")
    for ch in report.checks:
        detail = f"   ({ch.detail})" if ch.detail else ""
        print(f"  {OK if ch.passed else FAIL} {ch.name}{detail}")
    for ch in report.stretch if report.passed else []:
        detail = f"   ({ch.detail})" if ch.detail else ""
        print(f"  {OK if ch.passed else NOTE} stretch: {ch.name}{detail}")


def show_build_error(e: BuildError) -> None:
    print(c("31", "build failed:"))
    for line in str(e).splitlines():
        print(f"  {line}")


# ---- commands -----------------------------------------------------------------------

def cmd_status(args, prog: Progress) -> None:
    levels = all_levels()
    lv = levels.get(prog.current)
    done = len(prog.data["completed"])
    if prog.current < 0 or lv is None:
        print(c("1", "You have reached the deepest level that exists so far."))
    else:
        print(f"  {c('1', f'Level {lv.number}')} — \"{lv.title}\"    Arc {lv.arc}")
    print(f"  Levels cleared: {done}   Heat: {prog.heat}   Badges: {len(prog.data['badges'])}")
    print(f"  Workspace: {workspace()}")
    if lv is not None:
        sol = solution_path(lv)
        nxt = "ring brief, then ring start" if not sol.exists() else f"edit {sol}, then ring test"
        print(f"  Next: {nxt}")


def cmd_list(args, prog: Progress) -> None:
    for number, lv in sorted(all_levels().items(), reverse=True):
        if prog.completed(number):
            mark = OK
        elif number == prog.current:
            mark = c("33", "▶")
        elif prog.unlocked(number):
            mark = " "
        else:
            mark = c("2", "·")
        title = lv.title if prog.unlocked(number) or prog.completed(number) else c("2", "sealed")
        print(f"  {mark} {number:>3}  {title:<28} Arc {lv.arc}")


def cmd_brief(args, prog: Progress) -> None:
    lv = get_level(args.level, prog)
    for line in briefs.render(lv.brief, "cli").splitlines():
        if line.startswith("#"):
            print(c("1;36", line))
        elif line.startswith("```"):
            print(c("2", line))
        else:
            print(line)
    print(c("2", f"\n(introduces: {', '.join(lv.introduces)})"))


def cmd_start(args, prog: Progress) -> None:
    lv = get_level(args.level, prog)
    sol = solution_path(lv)
    if sol.exists() and not args.force:
        print(f"  {sol} already exists (use --force to overwrite with the starter).")
    for line in setup_level(lv, prog, force=args.force):
        print(f"  {line}")
    print("  Read the brief with `ring brief`, edit the file, then `ring test`.")


def cmd_test(args, prog: Progress, submit: bool = False) -> int:
    lv = get_level(args.level, prog)
    src = Path(args.file) if getattr(args, "file", None) else solution_path(lv)
    if not src.exists():
        raise CliError(f"{src} does not exist. Run `ring start {lv.number}` first.")
    try:
        b = build_solution(lv, src)
    except BuildError as e:
        show_build_error(e)
        return 1
    tests = lv.all_tests(context(prog), include_hidden=submit)
    report = grade(lv, b, tests, context(prog))
    print_report(lv, report, show_hidden_names=dev_mode())
    if not submit:
        if report.passed:
            print(c("32", "\n  Public tests pass. `ring submit` runs the hidden tests too."))
        return 0 if report.passed else 1
    if not report.passed:
        print(c("31", "\n  The gate holds. Fix the failures above and submit again."))
        return 1
    result = record_pass(prog, lv, report)
    print(c("1;32", f"\n  Level {lv.number} is open."))
    for b in result.badges:
        print(c("33", f"  Badge earned: {b}"))
    if result.first_time and result.next_level:
        nxt = result.next_level
        print(f"  Descending to level {nxt.number}: \"{nxt.title}\". Run `ring brief`.")
    elif result.first_time:
        print("  You have cleared every level that exists so far. More are being forged.")
    return 0


def cmd_hint(args, prog: Progress) -> None:
    lv = get_level(args.level, prog)
    n = args.n or (max(prog.hints_used(lv.number), default=0) + 1)
    if not 1 <= n <= len(lv.hints):
        raise CliError(f"level {lv.number} has hints 1–{len(lv.hints)}.")
    heat = prog.use_hint(lv.number, n)
    print(c("33", f"Hint {n}/{len(lv.hints)}") + (f"  (+{heat} heat)" if heat else ""))
    print(briefs.render(lv.hints[n - 1], "cli"))


def cmd_docs(args, prog: Progress) -> None:
    print(docs.lookup(args.term) if args.term else docs.index())


def cmd_listing(args, prog: Progress) -> int:
    lv = get_level(args.level, prog)
    try:
        b = build_solution(lv, solution_path(lv))
    except BuildError as e:
        show_build_error(e)
        return 1
    if lv.mode == "fragment":
        print(c("2", "; lines 1-4 are the wrapper the game puts around your code\n"))
    print(b.listing)
    return 0


def _session_for(lv: Level, prog: Progress, test_name: str | None, src: Path | None):
    from .debugger import Session
    b = build_solution(lv, src or solution_path(lv))
    tests = lv.all_tests(context(prog), include_hidden=False)
    test = None
    if test_name:
        matches = [t for t in tests if t.name == test_name]
        if not matches:
            raise CliError(f"no public test named {test_name!r}. Tests: "
                           + ", ".join(t.name for t in tests))
        test = matches[0]
    elif tests:
        test = tests[0]
    return Session(b, test, poison=lv.poison)


def cmd_debug(args, prog: Progress) -> int:
    from .debugger import Session, TerminalDebugger
    if args.binary:
        elf = Path(args.binary).resolve()
        b = _inspect(elf, elf, "program")
        b.source = Path(os.devnull)
        s = Session(b)
    else:
        lv = get_level(args.level, prog)
        try:
            s = _session_for(lv, prog, args.test, Path(args.file) if args.file else None)
        except BuildError as e:
            show_build_error(e)
            return 1
        if s.test.name != "debug":
            print(c("2", f"(running with the inputs of test {s.test.name!r}; --test NAME picks another)"))
    TerminalDebugger(s, color=COLOR).loop()
    return 0


def cmd_dap(args, prog: Progress) -> None:
    from .dap import serve_stdio

    def factory(launch: dict):
        lv = get_level(launch.get("level"), prog)
        prog_path = launch.get("program")
        return _session_for(lv, prog, launch.get("test"), Path(prog_path) if prog_path else None)

    serve_stdio(factory)


def cmd_ui(args, prog: Progress) -> None:
    from .web.server import serve
    terminal = not args.no_terminal and os.environ.get("RING_TERMINAL", "1") != "0"
    serve(args.host, args.port, open_browser=not args.no_browser, terminal=terminal)


def cmd_library(args, prog: Progress) -> None:
    entries = library_entries()
    if not entries:
        print("  Your library is empty. Routines you prove (starting with `itoa` in level 154)")
        print("  are collected here for reuse in later levels.")
    for name, (path, number) in sorted(entries.items()):
        print(f"  {name:<10} from level {number}   {path}")


def cmd_check_levels(args, prog: Progress) -> int:
    """For CI and level authors: every reference passes; every starter fails."""
    from .authoring import check_level
    ctx = Context(seed=args.seed)
    failures = 0
    for number, lv in sorted(all_levels().items(), reverse=True):
        if args.level is not None and number != args.level:
            continue
        problems = check_level(lv, ctx, Path(args.out) / f"level{number:03d}")
        print(f"  {OK if not problems else FAIL} {number:>3} {lv.title}")
        for p in problems:
            print(f"        {p}")
        failures += bool(problems)
    return 1 if failures else 0


# ---- entry point ----------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ring", description="NASM Adventures: descend to ring 0.")
    sub = p.add_subparsers(dest="cmd")

    def level_arg(sp):
        sp.add_argument("level", nargs="?", type=int, help="level number (default: current)")

    sub.add_parser("status", help="where you are")
    sub.add_parser("list", help="all levels")
    level_arg(sp := sub.add_parser("brief", help="lore, lesson and gate for a level"))
    level_arg(sp := sub.add_parser("start", help="create your solution file from the starter"))
    sp.add_argument("--force", action="store_true")
    level_arg(sp := sub.add_parser("test", help="build and run the public tests"))
    sp.add_argument("--file")
    level_arg(sp := sub.add_parser("submit", help="run all tests; opens the next level on success"))
    sp.add_argument("--file")
    sp = sub.add_parser("hint", help="progressive hints (adds heat)")
    sp.add_argument("n", nargs="?", type=int)
    sp.add_argument("--level", type=int)
    sp = sub.add_parser("docs", help="instruction and directive reference")
    sp.add_argument("term", nargs="?")
    level_arg(sub.add_parser("listing", help="show the NASM listing (bytes per line) of your code"))
    level_arg(sp := sub.add_parser("debug", help="step through your program (forwards and backwards)"))
    sp.add_argument("--test", help="use the inputs of this public test")
    sp.add_argument("--file")
    sp.add_argument("--binary", help="debug any static x86-64 ELF instead (no source view)")
    sub.add_parser("dap", help="Debug Adapter Protocol server on stdio (for editors)")
    sp = sub.add_parser("ui", help="play in your browser (local web front end)")
    sp.add_argument("--host", default="127.0.0.1")
    sp.add_argument("--port", type=int, default=8080)
    sp.add_argument("--no-browser", action="store_true", help="don't try to open a browser")
    sp.add_argument("--no-terminal", action="store_true",
                    help="disable the in-browser shell (also: RING_TERMINAL=0)")
    sub.add_parser("library", help="routines you have proven")
    sp = sub.add_parser("check-levels", help="(authors/CI) validate reference + starter of every level")
    sp.add_argument("level", nargs="?", type=int)
    sp.add_argument("--seed", type=int, default=1234)
    sp.add_argument("--out", default=str(Path(os.environ.get("TMPDIR", "/tmp")) / "ring-check"))

    args = p.parse_args(argv)
    if args.cmd is None:
        args.cmd = "status"
    try:
        prog = None if args.cmd in ("check-levels", "docs") else Progress.load()
        handlers = {"status": cmd_status, "list": cmd_list, "brief": cmd_brief,
                    "start": cmd_start, "test": cmd_test, "hint": cmd_hint, "docs": cmd_docs,
                    "listing": cmd_listing, "debug": cmd_debug, "dap": cmd_dap, "ui": cmd_ui,
                    "library": cmd_library, "check-levels": cmd_check_levels,
                    "submit": lambda a, pr: cmd_test(a, pr, submit=True)}
        rc = handlers[args.cmd](args, prog)
        return rc or 0
    except (CliError, SaveError) as e:
        print(c("31", f"ring: {e}"), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
