"""Grading: run test cases in the emulator and check results and constraints."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

from capstone import CS_ARCH_X86, CS_MODE_64, Cs

from .build import Build
from .emu import GPRS, Machine
from .level import Level, TestCase, encode_mem, to_int

DEFAULT_MAX_STEPS = 1_000_000

# Capstone spells some instructions differently from NASM.
_MNEMONIC_ALIASES = {"movabs": "mov"}


@dataclass
class TestResult:
    name: str
    hidden: bool
    passed: bool
    problems: list[str] = field(default_factory=list)
    steps: int = 0


@dataclass
class Check:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class Report:
    tests: list[TestResult] = field(default_factory=list)
    checks: list[Check] = field(default_factory=list)
    stretch: list[Check] = field(default_factory=list)
    instructions: list[tuple[int, str]] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(t.passed for t in self.tests) and all(c.passed for c in self.checks)

    @property
    def max_steps(self) -> int:
        return max((t.steps for t in self.tests), default=0)


def disassemble(build: Build) -> list[tuple[int, str, str]]:
    """(address, mnemonic, operands) for the player's code."""
    start, end = build.code_range
    m = Machine(build)
    code = m.read(start, end - start) if end > start else b""
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.skipdata = True
    out = []
    for ins in md.disasm(code, start):
        out.append((ins.address, _MNEMONIC_ALIASES.get(ins.mnemonic, ins.mnemonic), ins.op_str))
    return out


def resolve(build: Build, spec: dict) -> int:
    if "sym" in spec:
        if spec["sym"] not in build.symbols:
            raise KeyError(f"label `{spec['sym']}` is not defined")
        return build.symbols[spec["sym"]] + spec.get("offset", 0)
    return to_int(spec["addr"])


def prepare_machine(build: Build, test: TestCase, record: bool = False) -> Machine:
    m = Machine(build, stdin=test.stdin, record=record)
    for name, value in test.regs.items():
        m.set_reg(name, value)
    for spec in test.mem:
        m.write(resolve(build, spec), encode_mem(spec))
    return m


def _show(b: bytes, limit: int = 64) -> str:
    if len(b) > limit:
        return f"{_show(b[:limit], limit)}… ({len(b)} bytes)"
    try:
        s = b.decode()
        if s.isprintable() or all(c.isprintable() or c in "\n\t" for c in s):
            return repr(s)
    except UnicodeDecodeError:
        pass
    return b.hex(" ")


def run_test(level: Level, build: Build, test: TestCase) -> tuple[TestResult, Machine]:
    c = level.constraints
    initial = {n: test.regs.get(n, 0) for n in GPRS}
    try:
        m = prepare_machine(build, test)
    except KeyError as e:
        return TestResult(test.name, test.hidden, False, [str(e.args[0])]), None
    initial["rsp"] = m.reg("rsp")
    state = m.run(c.get("max_steps", DEFAULT_MAX_STEPS))
    problems: list[str] = []
    want_state = "done" if level.mode == "fragment" else "exited"
    if state == "fault":
        problems.append(m.fault)
    elif state == "limit":
        problems.append(f"did not finish within {c.get('max_steps', DEFAULT_MAX_STEPS)} "
                        "instructions (infinite loop?)")
    elif state != want_state:
        problems.append(f"ended in state {state}, expected {want_state}")

    exp = test.expect
    if not problems:
        for name, want in exp.get("regs", {}).items():
            if isinstance(want, str) and want.startswith("@"):  # "@label" or "@label+off"
                sym, _, off = want[1:].partition("+")
                if sym not in build.symbols:
                    problems.append(f"label `{sym}` is not defined")
                    continue
                want = build.symbols[sym] + (int(off, 0) if off else 0)
            got, want = m.reg(name), to_int(want)
            if got != want:
                problems.append(f"{name}: expected {want:#x}, got {got:#x}")
        for name in c.get("preserve", ["rsp"] if level.mode == "fragment" else []):
            if m.reg(name) != initial[name]:
                problems.append(f"{name} must be preserved: started {initial[name]:#x}, "
                                f"ended {m.reg(name):#x}")
        for spec in exp.get("mem", []):
            try:
                addr = resolve(build, spec)
            except KeyError as e:
                problems.append(str(e.args[0]))
                continue
            want = encode_mem(spec)
            got = m.read(addr, len(want)) if m.readable(addr, len(want)) else b""
            if got != want:
                label = spec.get("sym", hex(addr)) + (f"+{spec['offset']}" if spec.get("offset") else "")
                problems.append(f"memory at {label}: expected {want.hex(' ')}, got {got.hex(' ')}")
        for stream in ("stdout", "stderr"):
            want = exp.get(stream)
            if f"{stream}_hex" in exp:
                want = bytes.fromhex(exp[f"{stream}_hex"])
            elif isinstance(want, str):
                want = want.encode()
            got = bytes(getattr(m, stream))
            if want is not None and got != want:
                problems.append(f"{stream}: expected {_show(want)}, got {_show(got)}")
        if "exit" in exp and m.exit_code != exp["exit"]:
            problems.append(f"exit status: expected {exp['exit']}, got {m.exit_code}")
    if "syscalls" in exp:
        names = [str(s).split("(")[0] for s in m.syscalls]
        if names != exp["syscalls"]:
            problems.append(f"syscalls: expected {exp['syscalls']}, got {names}")
    return TestResult(test.name, test.hidden, not problems, problems, m.steps), m


def _static_checks(rules: dict, ins: list[tuple[int, str, str]], report_steps: int) -> list[Check]:
    out = []
    mnemonics = {mn for _, mn, _ in ins}
    if "max_instructions" in rules:
        n = rules["max_instructions"]
        out.append(Check(f"≤ {n} instructions", len(ins) <= n, f"you: {len(ins)}"))
    if "max_steps_used" in rules:
        n = rules["max_steps_used"]
        out.append(Check(f"≤ {n} executed instructions", report_steps <= n,
                         f"you: {report_steps}"))
    for mn in rules.get("must_use", []):
        out.append(Check(f"uses `{mn}`", mn in mnemonics))
    banned = sorted(mnemonics & set(rules.get("banned", [])))
    if rules.get("banned"):
        out.append(Check("no banned instructions", not banned,
                         f"found: {', '.join(banned)}" if banned else ""))
    return out


def _code_lines(text: str) -> list[str]:
    """Source lines with comments and whitespace removed (for change budgets)."""
    out = []
    for line in text.splitlines():
        if ";" in line and not re.search(r"[\"'`]", line.split(";")[0]):
            line = line.split(";")[0]
        line = " ".join(line.split())
        if line:
            out.append(line)
    return out


def changed_lines(original: str, edited: str) -> int:
    """How many code lines differ (replaced, added or removed), ignoring comments,
    blank lines and spacing."""
    a, b = _code_lines(original), _code_lines(edited)
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    return sum(max(i2 - i1, j2 - j1) for op, i1, i2, j1, j2 in sm.get_opcodes() if op != "equal")


def grade(level: Level, build: Build, tests: list[TestCase]) -> Report:
    r = Report()
    for t in tests:
        result, _ = run_test(level, build, t)
        r.tests.append(result)
    ins = disassemble(build)
    r.instructions = [(a, f"{mn} {ops}".strip()) for a, mn, ops in ins]
    r.checks = _static_checks(level.constraints, ins, r.max_steps)
    if "max_changed_lines" in level.constraints:
        n = level.constraints["max_changed_lines"]
        used = changed_lines(level.starter.read_text(), build.source.read_text())
        r.checks.append(Check(f"≤ {n} changed lines (vs. the original)", used <= n, f"you: {used}"))
    r.stretch = _static_checks(level.stretch, ins, r.max_steps)
    return r
