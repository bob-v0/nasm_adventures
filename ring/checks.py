"""Grading: run test cases in the emulator and check results and constraints."""

from __future__ import annotations

import ast
import difflib
import random
import struct
import re
from dataclasses import dataclass, field

from capstone import CS_ARCH_X86, CS_MODE_64, Cs
from elftools.elf.elffile import ELFFile

from .build import Build
from .emu import FLAG_BITS, GPRS, Machine
from .kernel import Injection, Kernel
from .userland import install_userland
from .level import Context, Level, TestCase, encode_mem, to_int

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
    warnings: str = ""

    @property
    def passed(self) -> bool:
        return all(t.passed for t in self.tests) and all(c.passed for c in self.checks)

    @property
    def max_steps(self) -> int:
        return max((t.steps for t in self.tests), default=0)


def disassemble(build: Build) -> list[tuple[int, str, str]]:
    """(address, mnemonic, operands) for the player's code."""
    if build.mode == "native":
        with open(build.player_object, "rb") as fh:  # dynamically linked: read the object
            sec = ELFFile(fh).get_section_by_name(".text")
            code, start = (sec.data() if sec else b""), 0
    else:
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


def prepare_machine(build: Build, test: TestCase, record: bool = False,
                    poison: bool = False) -> Machine:
    kernel = Kernel(test.stdin, files=test.files,
                    inject=Injection.from_dict(test.inject, seed=test.name))
    if test.userland:
        install_userland(kernel)
    m = Machine(build, record=record, kernel=kernel, argv=test.argv, env=test.env)
    if poison:
        # Real callers leave junk behind: registers the test doesn't set, and the
        # stack below rsp, start with garbage (deterministic per test, for replay).
        rng = random.Random(f"poison:{test.name}")
        for name in GPRS:
            if name != "rsp":
                m.set_reg(name, rng.getrandbits(64))
        rsp = m.reg("rsp")
        m.write(rsp - 4096, rng.randbytes(4096))
    for name, value in test.regs.items():
        m.set_reg(name, symbol_value(build, value[1:]) if isinstance(value, str) else value)
    for spec in test.mem:
        if "ptr" in spec:  # an address: "label", "label+off", or a number (0 = null)
            data = struct.pack("<Q", symbol_value(build, spec["ptr"]))
        else:
            data = encode_mem(spec)
        m.write(resolve(build, spec), data)
    return m


def symbol_value(build: Build, ref) -> int:
    if isinstance(ref, int):
        return ref
    sym, _, off = str(ref).partition("+")
    if sym not in build.symbols:
        raise KeyError(f"label `{sym}` is not defined")
    return build.symbols[sym] + (int(off, 0) if off else 0)


def _compare(stream: str, want: bytes, got: bytes) -> str:
    """Describe a stream mismatch; for long outputs, say where they diverge."""
    if len(want) <= 64 and len(got) <= 64:
        return f"{stream}: expected {_show(want)}, got {_show(got)}"
    i = next((k for k, (a, b) in enumerate(zip(want, got)) if a != b), min(len(want), len(got)))
    return (f"{stream}: expected {len(want)} bytes, got {len(got)}; they first differ at byte {i} "
            f"(expected {_show(want[i:i + 24])}, got {_show(got[i:i + 24]) if i < len(got) else 'the end'})")


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


def _undefined_symbols(build: Build) -> set[str]:
    """Functions the player's object uses from elsewhere (libc, the game's helpers)."""
    if build.player_object is None:
        return set()
    with open(build.player_object, "rb") as fh:
        symtab = ELFFile(fh).get_section_by_name(".symtab")
        return {s.name for s in symtab.iter_symbols() if s["st_shndx"] == "SHN_UNDEF" and s.name}


def _register_diff_hint(name: str, want: int, got: int) -> str:
    """Point out the classic width mistakes when only the upper bits differ."""
    low32 = 0xFFFF_FFFF
    if got & low32 == want & low32 and got >> 32 == 0:
        reg32 = f"{name}d" if name[1:].isdigit() else f"e{name[1:]}"
        return (f" (the low 32 bits are right, but bits 63..32 are 0: writing a 32-bit register "
                f"like {reg32} clears them; produce the full 64-bit value instead)")
    for bits in (16, 8):
        mask = (1 << bits) - 1
        if got & mask == want & mask and got >> bits != want >> bits:
            return f" (the low {bits} bits are right; the upper bits differ)"
    return ""


def run_native_test(level: Level, build: Build, test: TestCase) -> TestResult:
    from . import native
    r = native.run(build.elf, test.stdin, test.expect.get("args", []))
    problems: list[str] = []
    if r.timed_out:
        problems.append(f"did not finish within {native.TIMEOUT_S} seconds")
    elif r.signal:
        names = {11: "segmentation fault (SIGSEGV)", 6: "aborted (SIGABRT)",
                 4: "illegal instruction (SIGILL)", 8: "arithmetic error (SIGFPE)",
                 7: "bus error (SIGBUS)", 24: "CPU time limit exceeded"}
        problems.append(f"crashed: {names.get(r.signal, f'signal {r.signal}')}")
    exp = test.expect
    for stream in ("stdout", "stderr"):
        want = exp.get(stream)
        if isinstance(want, str):
            want = want.encode()
        got = getattr(r, stream)
        if want is not None and got != want:
            problems.append(_compare(stream, want, got))
    if "exit" in exp and not r.signal and r.exit_code != exp["exit"]:
        problems.append(f"exit status: expected {exp['exit']}, got {r.exit_code}")
    return TestResult(test.name, test.hidden, not problems, problems, 0)


def run_test(level: Level, build: Build, test: TestCase) -> tuple[TestResult, Machine]:
    if level.mode == "native":
        return run_native_test(level, build, test), None
    if "signal_sweep" in test.inject:
        return _signal_sweep(level, build, test)
    if "fs_sweep" in test.inject:
        return _fs_sweep(level, build, test)
    return _run_one(level, build, test)


def _fs_sweep(level: Level, build: Build, test: TestCase):
    """Another process changes the filesystem (the kernel's fs_event): run once without
    it, then once per syscall the program made, with the change right after that call.
    The first point where the program goes wrong is reported."""
    from .kernel import NAMES
    event = test.inject["fs_sweep"]
    base = TestCase(**{**test.__dict__, "inject": {k: v for k, v in test.inject.items()
                                                   if k != "fs_sweep"}})
    result, m = _run_one(level, build, base)
    if not result.passed:
        result.problems.insert(0, "(with no other process interfering)")
        return result, m
    seen: dict[str, int] = {}
    points = []
    for rec in m.syscalls:
        name = NAMES.get(rec.number)
        if name and name not in ("exit", "exit_group", "rt_sigreturn"):
            seen[name] = seen.get(name, 0) + 1
            points.append((name, seen[name]))
    for name, nth in points[:200]:
        t = TestCase(**{**base.__dict__, "inject": {
            **base.inject, "fs_events": [{**event, "after": name, "nth": nth}]}})
        r, mm = _run_one(level, build, t)
        if not r.passed:
            r.problems.insert(0, f"when another process strikes right after your call #{nth} "
                                 f"of {name}:")
            return r, mm
    return TestResult(test.name, test.hidden, True, [], m.steps), m


def _signal_sweep(level: Level, build: Build, test: TestCase):
    """Run once without the signal, then once per sampled instruction with the signal
    delivered right after it. The first failing delivery point is reported."""
    sweep = test.inject["signal_sweep"]
    base = TestCase(**{**test.__dict__, "inject": {k: v for k, v in test.inject.items()
                                                   if k != "signal_sweep"}})
    result, m = _run_one(level, build, base, trace=True)
    if not result.passed:
        result.problems.insert(0, "(without any signal)")
        return result, m
    trace = m.trace or []
    last = max(1, len(trace) - sweep.get("tail", 0))
    first = 1
    if "after_syscall" in sweep:   # e.g. only once the handler is installed
        first = next((r.step + 1 for r in m.syscalls if str(r).startswith(sweep["after_syscall"] + "(")), 1)
    points = list(range(first, last + 1))
    if len(points) > 400:
        points = sorted({first + i * (last - first) // 399 for i in range(400)})
    for k in points:
        t = TestCase(**{**base.__dict__,
                        "inject": {**base.inject, "signals": [{"at": k, "sig": sweep["sig"]}]}})
        r, mm = _run_one(level, build, t)
        if not r.passed:
            addr = trace[k - 1]
            line = build.addr_to_line.get(addr)
            where = f"line {line}" if line else f"{addr:#x}"
            r.problems.insert(0, f"with the signal delivered right after instruction {k} ({where}):")
            return r, mm
    return TestResult(test.name, test.hidden, True, [], m.steps), m


def _run_one(level: Level, build: Build, test: TestCase,
             trace: bool = False) -> tuple[TestResult, Machine]:
    c = level.constraints
    try:
        m = prepare_machine(build, test, poison=level.poison)
    except KeyError as e:
        return TestResult(test.name, test.hidden, False, [str(e.args[0])]), None
    initial = {n: m.reg(n) for n in GPRS}
    if trace:
        m.trace = []
    state = m.run(c.get("max_steps", DEFAULT_MAX_STEPS))
    problems: list[str] = []
    want_state = "exited" if level.mode == "program" else "done"
    exp = test.expect
    if "killed" in exp:                      # the test expects death by a signal
        want_state = "killed"
        if state == "killed" and m.term_signal != exp["killed"]:
            problems.append(f"expected to be killed by signal {exp['killed']}, "
                            f"but was killed by {m.term_signal}")
    if state == "killed" and want_state != "killed":
        problems.append(m.fault)
    elif state == "exited" and level.mode == "function":
        problems.append("your function ended the program (exit syscall) instead of returning")
    elif state == "fault":
        problems.append(m.fault)
    elif state == "limit":
        problems.append(f"did not finish within {c.get('max_steps', DEFAULT_MAX_STEPS)} executed "
                        "instructions (an infinite loop, or too slow for this level's budget)")
    elif state != want_state:
        problems.append(f"ended in state {state}, expected {want_state}")
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
                problems.append(f"{name}: expected {want:#x}, got {got:#x}"
                                + _register_diff_hint(name, want, got))
        flags = m.reg("rflags")
        for name, want in exp.get("flags", {}).items():
            bit = dict(FLAG_BITS)[name.upper()]
            got = flags >> bit & 1
            if got != int(want):
                problems.append(f"flag {name.upper()}: expected {int(want)}, got {got}")
        if level.mode == "function":
            # The System V contract: callee-saved registers come back unchanged, `ret`
            # pops the return address, and the direction flag is clear.
            if m.reg("rsp") != initial["rsp"] + 8:
                problems.append(f"rsp must be back where it started: expected "
                                f"{initial['rsp'] + 8:#x} after ret, got {m.reg('rsp'):#x}")
            if m.reg("rflags") >> 10 & 1:
                problems.append("the direction flag must be clear (cld) when you return")
        default_preserve = {"fragment": ["rsp"], "program": [],
                            "function": ["rbx", "rbp", "r12", "r13", "r14", "r15"]}[level.mode]
        for name in c.get("preserve", default_preserve):
            if m.reg(name) != initial[name]:
                problems.append(f"{name} must be preserved: started {initial[name]:#x}, "
                                f"ended {m.reg(name):#x}")
        for spec in exp.get("mem", []):
            try:
                addr = resolve(build, spec)
            except KeyError as e:
                problems.append(str(e.args[0]))
                continue
            try:
                want = (struct.pack("<Q", symbol_value(build, spec["ptr"])) if "ptr" in spec
                        else encode_mem(spec))
            except KeyError as e:
                problems.append(str(e.args[0]))
                continue
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
                problems.append(_compare(stream, want, got))
        for name, want in exp.get("symbols", {}).items():
            got = build.symbols.get(name)
            if got is None:
                problems.append(f"`{name}` is not defined")
            elif got != to_int(want):
                problems.append(f"`{name}`: expected {to_int(want)}, got {got}")
        if "exit" in exp and m.exit_code != exp["exit"]:
            problems.append(f"exit status: expected {exp['exit']}, got {m.exit_code}")
        for path, want in exp.get("files", {}).items():
            got = m.kernel.file_text(path)
            if want is None:
                if got is not None:
                    problems.append(f"{path} should not exist")
            elif got != (want.encode() if isinstance(want, str) else bytes.fromhex(want["hex"])):
                problems.append(f"{path}: expected {_show(want.encode() if isinstance(want, str) else bytes.fromhex(want['hex']))}, "
                                + (f"got {_show(got)}" if got is not None else "but it doesn't exist"))
        if "fds_open" in exp and sorted(m.kernel.fds) != sorted(exp["fds_open"]):
            leaked = sorted(set(m.kernel.fds) - set(exp["fds_open"]))
            problems.append(f"file descriptors still open at exit: {sorted(m.kernel.fds)}"
                            + (f" (leaked: {leaked}; close what you open)" if leaked else ""))
        if "heap_max" in exp:
            used = (m.kernel.brk - m.kernel.brk_start) + sum(m.kernel.mmaps.values())
            if used > exp["heap_max"]:
                problems.append(f"the heap grew to {used} bytes; this workload must fit in "
                                f"{exp['heap_max']} (reuse freed blocks)")
    if exp.get("check") and not problems:   # the level's own checker (gen.check)
        problems += level._gen_module().check(test, m)
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
    prefixes = tuple(rules.get("banned_prefixes", []))
    banned = sorted({mn for mn in mnemonics if mn in set(rules.get("banned", []))
                     or (prefixes and mn.startswith(prefixes))})
    if rules.get("banned") or prefixes:
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


_WITNESS_LINE = re.compile(r"^\s*;!\s*witness\b(.*)$", re.M | re.I)
_WITNESS_PAIR = re.compile(r"""(\w+)\s*=\s*("(?:[^"\\]|\\.)*"|[^,\s]+)""")


def parse_witness(text: str) -> dict | None:
    """Collect `;! witness key = value, ...` lines from a solution. Values are
    integers (any base Python/NASM-style prefix, `_` allowed) or "strings"."""
    pairs = {}
    for line in _WITNESS_LINE.findall(text):
        for key, raw in _WITNESS_PAIR.findall(line):
            if raw.startswith('"'):
                pairs[key] = ast.literal_eval(raw)
            else:
                pairs[key] = int(raw.replace("_", ""), 0)
    return pairs or None


def _witness_checks(level: Level, build: Build, ctx: Context) -> list[Check]:
    """A bug level with a witness: the player's input must make the ORIGINAL program
    fail, and their fixed program must handle it."""
    from .build import build as assemble  # local: avoid a name clash with `build`

    try:
        w = parse_witness(build.source.read_text())
    except (ValueError, SyntaxError) as e:
        return [Check("witness", False, f"can't read the witness line: {e}")]
    if w is None:
        return [Check("witness", False, "add a line like `;! witness rdi = 5, rsi = 7` "
                      "with an input that makes the original program fail")]
    try:
        test = TestCase.from_dict(level._gen_module().witness_test(w, ctx))
    except (ValueError, KeyError) as e:
        return [Check("witness", False, str(e))]
    orig_dir = build.elf.parent / "original"
    orig_dir.mkdir(parents=True, exist_ok=True)
    (orig_dir / "solution.asm").write_text(level.starter.read_text())
    original = assemble(orig_dir / "solution.asm", orig_dir / ".build", level.mode,
                        **level.build_options())
    before, _ = run_test(level, original, test)
    after, _ = run_test(level, build, test)
    shown = ", ".join(f"{k} = {v:#x}" if isinstance(v, int) else f"{k} = {v!r}" for k, v in w.items())
    return [
        Check(f"witness ({shown}) breaks the original program", not before.passed,
              "the original handles this input correctly" if before.passed else before.problems[0]),
        Check("your fix handles the witness", after.passed, "" if after.passed else after.problems[0]),
    ]


def grade(level: Level, build: Build, tests: list[TestCase], ctx: Context | None = None) -> Report:
    r = Report(warnings=build.warnings)
    for t in tests:
        result, _ = run_test(level, build, t)
        r.tests.append(result)
    ins = disassemble(build)
    r.instructions = [(a, f"{mn} {ops}".strip()) for a, mn, ops in ins]
    r.checks = _static_checks(level.constraints, ins, r.max_steps)
    if level.constraints.get("source_patterns"):
        text = re.sub(r";.*", "", build.source.read_text())  # ignore comments
        for rule in level.constraints["source_patterns"]:
            n = len(re.findall(rule["pattern"], text, re.M | re.I))
            want = rule.get("min", 1)
            r.checks.append(Check(rule["label"], n >= want, f"found {n}" if n < want else ""))
    for fn in level.constraints.get("must_call", []):
        r.checks.append(Check(f"calls `{fn}`", fn in _undefined_symbols(build)))
    if "max_changed_lines" in level.constraints:
        n = level.constraints["max_changed_lines"]
        used = changed_lines(level.starter.read_text(), build.source.read_text())
        r.checks.append(Check(f"≤ {n} changed lines (vs. the original)", used <= n, f"you: {used}"))
    if level.data.get("witness"):
        r.checks += _witness_checks(level, build, ctx or Context())
    r.stretch = _static_checks(level.stretch, ins, r.max_steps)
    return r
