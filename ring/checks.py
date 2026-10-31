"""Grading: run test cases in the emulator and check results and constraints."""

from __future__ import annotations

import ast
import difflib
import random
import struct
import re
from dataclasses import dataclass, field

from capstone import CS_ARCH_X86, CS_MODE_16, CS_MODE_64, Cs
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
    note: str = ""            # shown next to the test's name, e.g. its cycle count


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
    if build.mode == "boot":                # 16-bit code: the listing's instruction lines
        md = Cs(CS_ARCH_X86, CS_MODE_16)
        image = build.elf.read_bytes()
        out = []
        for m in re.finditer(r"^\s*\d+\s+([0-9A-F]{8})\s+[0-9A-F\[\]()]+-?\s+(?:[\w.]+:)?\s*(\w+)",
                             build.listing, re.M):
            offset, first = int(m.group(1), 16), m.group(2).lower()
            if first in ("db", "dw", "dd", "dq", "times", "resb", "resw", "incbin"):
                continue
            ins = next(md.disasm(image[offset:offset + 15], 0x7C00 + offset), None)
            if ins is not None:
                out.append((ins.address, ins.mnemonic, ins.op_str))
        return out
    if build.mode == "native":
        if build.player_object is None:   # a flat file written with `nasm -f bin`
            return []
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
                    poison: bool = False, perf: bool = False) -> Machine:
    kernel = Kernel(test.stdin, files=test.files,
                    inject=Injection.from_dict(test.inject, seed=test.name))
    if test.userland:
        install_userland(kernel)
    m = Machine(build, record=record, kernel=kernel, argv=test.argv, env=test.env)
    if "cpu" in test.inject:                       # which CPU: what cpuid reports (ring/simd.py)
        m.set_cpu(test.inject["cpu"])
    for spec in test.inject.get("unmap", []):      # {"sym": ..., "size": ...}: a hole in memory
        m.unmap_region(resolve(build, spec), spec["size"])
    if test.inject.get("tso"):
        m.enable_tso()
    if perf or "max_cycles" in test.expect or "noise" in test.inject:
        m.enable_perf(noise=test.inject.get("noise"))
        for spec in test.inject.get("warm", []):   # {"sym": ..., "size": ...}: already in L2
            m.perf.warm(resolve(build, spec), spec["size"])
        if test.inject.get("warm_all"):               # every data section starts in L2
            for name, (addr, size) in build.sections.items():
                if name in (".data", ".bss", ".rodata"):
                    m.perf.warm(addr, size)
        if "max_cycles" in test.expect:               # far past the budget: stop there
            m.cycle_limit = 3 * test.expect["max_cycles"]
    if poison:
        # Real callers leave junk behind: registers the test doesn't set, and the
        # stack below rsp, start with garbage (deterministic per test, for replay).
        rng = random.Random(f"poison:{test.name}")
        for name in GPRS:
            if name != "rsp":
                m.set_reg(name, rng.getrandbits(64))
        for n in range(16):                        # (the upper halves are clean, as the ABI says)
            m.set_reg(f"xmm{n}", rng.getrandbits(128))
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
    if r.error:
        return TestResult(test.name, test.hidden, False, [r.error], 0)
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


def run_boot_test(level: Level, build: Build, test: TestCase) -> TestResult:
    """A test on the whole emulated PC (ring/qemu.py)."""
    from . import qemu
    image = build.elf.read_bytes()
    exp, inj = test.expect, test.inject
    if len(image) < 512 or image[510:512] != b"\x55\xAA":
        got = image[510:512].hex(" ") if len(image) >= 512 else f"only {len(image)} bytes"
        return TestResult(test.name, test.hidden, False, [
            "the BIOS won't boot this: a boot sector is 512 bytes and ends with the bytes "
            f"55 AA (dw 0xAA55); yours: {got}. End it with `times 510 - ($ - $$) db 0` and "
            "`dw 0xAA55`"], 0)
    if "max_size" in exp and len(image) > exp["max_size"]:
        return TestResult(test.name, test.hidden, False, [
            f"the image is {len(image)} bytes; at most {exp['max_size']}"], 0)
    problems: list[str] = []
    note = inj.get("note")                    # {"seg", "off", "text"}: left in memory for you
    if "append" in inj:                       # the game's sectors after your boot sector
        if len(image) > 512:
            return TestResult(test.name, test.hidden, False, [
                f"your image is {len(image)} bytes: this level's disk has the game's code from "
                "sector 2 on, so yours must be exactly one sector (512 bytes)"], 0)
        image = image + bytes.fromhex(inj["append"])
    with qemu.Run(image, profile=inj.get("bios", "seabios"), disk_size=inj.get("disk_size", 0),
                  memory=inj.get("memory", qemu.MEMORY), rtc=inj.get("rtc", "2025-01-01T00:00:00"),
                  note=(note["seg"], note["off"], note["text"].encode("latin-1") + b"\0")
                  if note else None) as run:
        if "keys" in inj:
            if "ready" in inj:                # wait until the program says it's listening
                run.wait("serial", timeout=qemu.TIMEOUT_S, serial=inj["ready"].encode())
            else:
                run.wait("time", timeout=inj.get("key_delay", 0.5))
            run.send_keys(inj["keys"])
        until = exp.get("until", "halt")
        why = run.wait(until, timeout=exp.get("timeout", qemu.TIMEOUT_S),
                       serial=exp.get("serial_until", "").encode() or None)
        regs = run.registers() if run.alive else None
        screen = run.screen() if run.alive else []
        serial = run.serial()
        if why == "reset":
            problems.append("the machine reset: a triple fault (an exception while the CPU "
                            "couldn't deliver one, e.g. no valid interrupt table) or a jump "
                            "to the reset vector" + _boot_where(build, run))
        elif why == "timeout" and until == "halt":
            where = f" (it's at {regs['cs']:04x}:{regs['eip']:04x}" + (
                f", line {build.addr_to_line[regs['cs'] * 16 + regs['eip']]}"
                if regs and regs["cs"] * 16 + regs["eip"] in build.addr_to_line else "") + ")" \
                if regs else ""
            problems.append(f"didn't halt within {exp.get('timeout', qemu.TIMEOUT_S):g} seconds"
                            f"{where}: end with cli and hlt")
        elif why == "exit" and "exit" not in exp:
            problems.append(f"the program wrote {run.exit_code} to port 0xF4 (the game's exit "
                            "port) before finishing")
        elif until == "serial" and why != "serial":
            problems.append(f"the serial port never said {exp['serial_until']!r} "
                            f"({'it halted' if why == 'halt' else why} first)")
        if not problems:
            for name, want in exp.get("regs", {}).items():
                got = regs[name] if regs else None
                if got != want:
                    problems.append(f"{name}: expected {want:#x}, got "
                                    + (f"{got:#x}" if got is not None else "nothing"))
            if "exit" in exp and run.exit_code != exp["exit"]:
                problems.append(f"exit port 0xF4: expected {exp['exit']}, got {run.exit_code}")
            if "serial" in exp:
                want = exp["serial"].encode() if isinstance(exp["serial"], str) else exp["serial"]
                if serial != want:
                    problems.append(_compare("serial port", want, serial))
            for text in exp.get("screen_contains", []):
                if not any(text in row for row in screen):
                    problems.append(f"the screen doesn't show {text!r}")
            for spec in exp.get("mem", []):
                want = bytes.fromhex(spec["hex"])
                got = run.read(spec["addr"], len(want)) if run.alive else b""
                if got != want:
                    problems.append(f"memory at {spec['addr']:#x}: expected {want.hex(' ')}, "
                                    f"got {got.hex(' ')}")
            if exp.get("check"):
                problems += level._gen_module().check(test, run, regs, screen, serial)
        if problems and screen and exp.get("show_screen", True):
            shown = [r for r in screen]
            while shown and not shown[-1]:
                shown.pop()
            problems.append("the screen:\n" + "\n".join("    |" + r for r in shown[-12:]))
        if problems and serial and "serial" not in exp:
            problems.append(f"serial output: {_show(serial)}")
    return TestResult(test.name, test.hidden, not problems, problems, 0)


def _boot_where(build: Build, run) -> str:
    log = (run.dir / "qemu.log").read_text(errors="replace") if (run.dir / "qemu.log").exists() else ""
    dumps = log.split("CPU Reset")
    if len(dumps) < 3:
        return ""
    from .qemu import parse_registers
    r = parse_registers(dumps[-1])
    addr = r.values.get("cs_base", 0) + r.values.get("eip", 0)
    line = build.addr_to_line.get(addr)
    return f"; last at {r['cs']:04x}:{r['eip']:04x}" + (f" (line {line})" if line else "")


def run_test(level: Level, build: Build, test: TestCase) -> tuple[TestResult, Machine]:
    if level.mode == "boot":
        return run_boot_test(level, build, test), None
    if level.mode == "native":
        return run_native_test(level, build, test), None
    if "signal_sweep" in test.inject:
        return _signal_sweep(level, build, test)
    if "fs_sweep" in test.inject:
        return _fs_sweep(level, build, test)
    if "schedule_sweep" in test.inject:
        return _schedule_sweep(level, build, test)
    if "cancel_sweep" in test.inject:
        return _cancel_sweep(level, build, test)
    return _run_one(level, build, test)


def _without(test: TestCase, key: str, **inject) -> TestCase:
    rest = {k: v for k, v in test.inject.items() if k != key}
    return TestCase(**{**test.__dict__, "inject": {**rest, **inject}})


def _schedule_sweep(level: Level, build: Build, test: TestCase):
    """The task runtime asks the game which ready task runs next: try the plain order
    (schedule 0), then `count` shuffled ones. The first that fails is reported, by
    number, so it can be replayed (and used as a witness)."""
    count = test.inject["schedule_sweep"].get("count", 100)
    m = None
    for s in range(count + 1):
        r, m = _run_one(level, build, _without(test, "schedule_sweep", schedule=s))
        if not r.passed:
            r.problems.insert(0, "with the plain schedule (threads/tasks take turns in order):"
                              if s == 0 else f"with schedule {s} (one of {count} interleavings "
                              "the game tried):")
            return r, m
    return TestResult(test.name, test.hidden, True, [], m.steps if m else 0), m


def _cancel_sweep(level: Level, build: Build, test: TestCase):
    """Run once, then once per await point of that run, cancelling the task that makes
    it right there (only tasks in `tasks`, if given)."""
    sweep = test.inject["cancel_sweep"]
    base = _without(test, "cancel_sweep")
    result, m = _run_one(level, build, base)
    if not result.passed:
        result.problems.insert(0, "(without any cancellation)")
        return result, m
    awaits, fns = list(m.kernel.awaits), list(m.kernel.await_fns)
    only = sweep.get("tasks")
    by_fn = {build.symbols[f] for f in sweep.get("functions", []) if f in build.symbols}
    for k, task in enumerate(awaits[:400], 1):
        if only and task not in only:
            continue
        if sweep.get("functions") and fns[k - 1] not in by_fn:
            continue
        r, mm = _run_one(level, build, _without(test, "cancel_sweep", cancel_at=k))
        if not r.passed:
            nth = awaits[:k].count(task)
            suffix = "th" if 10 <= nth % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(nth % 10, "th")
            r.problems.insert(0, f"with task {task} cancelled at its {nth}{suffix} await "
                                 f"(await #{k} of the run):")
            return r, mm
    return TestResult(test.name, test.hidden, True, [], m.steps), m


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
        m = prepare_machine(build, test, poison=level.poison, perf=level.data.get("perf", False))
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
    if m.kernel.peers and "killed" not in exp:   # a server: it runs until its clients are done
        want_state = exp.get("end", "idle")
        if state in ("idle", "exited"):
            problems += m.kernel.peer_report()
        if state == "exited" and want_state == "idle" and not m.kernel.peers_done:
            problems.append(f"the server exited (status {m.exit_code}) while clients were "
                            "still talking to it")
            state = want_state
    if state == "killed" and want_state != "killed":
        problems.append(m.fault)
    elif state == "exited" and level.mode == "function":
        problems.append("your function ended the program (exit syscall) instead of returning")
    elif state == "fault":
        problems.append(m.fault)
    elif state == "limit" and m.perf is not None and m.cycle_limit \
            and m.perf.max_done > m.cycle_limit:
        problems.append(f"stopped after {int(m.perf.max_done)} cycles, three times the budget of "
                        f"{exp['max_cycles']}, without finishing")
        problems += m.perf.report(where=build.addr_to_line.get).splitlines()[1:]
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
    note = ""
    if m.perf is not None:
        cycles = m.cycles
        per = exp.get("per")                 # [count, "element"]: also show cycles per item
        note = f"{cycles} cycles" + (f", {cycles / per[0]:.2f} per {per[1]}" if per else "")
        budget = exp.get("max_cycles")
        if budget is not None and cycles > budget and not problems:
            each = f" ({budget / per[0]:.2f} per {per[1]})" if per else ""
            problems.append(f"too slow: {note} on the game's CPU model; the budget is "
                            f"{budget} cycles{each}")
            slowest = max(m.cores.values(), key=lambda core: core.cycles)
            problems += slowest.report(where=build.addr_to_line.get).splitlines()[1:]
    if exp.get("check") and not problems:   # the level's own checker (gen.check)
        problems += level._gen_module().check(test, m)
    if "syscalls" in exp:
        names = [str(s).split("(")[0] for s in m.syscalls]
        if names != exp["syscalls"]:
            problems.append(f"syscalls: expected {exp['syscalls']}, got {names}")
    return TestResult(test.name, test.hidden, not problems, problems, m.steps, note), m


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
    gen = level._gen_module()
    if gen is not None and hasattr(gen, "audit"):   # the level's own checks of the binary
        import inspect
        args = (build, level) if len(inspect.signature(gen.audit).parameters) > 1 else (build,)
        r.checks += [Check(*c) for c in gen.audit(*args)]
    r.stretch = _static_checks(level.stretch, ins, r.max_steps)
    return r
