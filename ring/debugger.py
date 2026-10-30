"""Debugger session (shared by the terminal debugger and the DAP server) and the
interactive terminal debugger used by `ring debug`."""

from __future__ import annotations

import re
import shlex

from capstone import CS_ARCH_X86, CS_MODE_64, Cs

from .build import Build
from .checks import prepare_machine
from .emu import GPRS, Machine, flags_str
from .level import TestCase

MAX_RUN = 1_000_000


class Session:
    def __init__(self, build: Build, test: TestCase | None = None, poison: bool = False):
        self.build = build
        self.test = test or TestCase(name="debug")
        self.poison = poison
        self.breakpoints: set[int] = set()
        self.md = Cs(CS_ARCH_X86, CS_MODE_64)
        self.restart()

    def restart(self) -> None:
        self.m: Machine = prepare_machine(self.build, self.test, record=True, poison=self.poison)

    # -- execution ------------------------------------------------------------------

    def step(self, n: int = 1) -> int:
        done = 0
        while done < n and self.m.step():
            done += 1
        return done

    def back(self, n: int = 1) -> int:
        done = 0
        while done < n and self.m.step_back():
            done += 1
        return done

    def cont(self) -> str:
        """Run until a breakpoint, the end of the program, or MAX_RUN steps."""
        for _ in range(MAX_RUN):
            if not self.m.step():
                return "end"
            if self.m.finished:
                return "end"
            if self.m.pc in self.breakpoints:
                return "breakpoint"
        return "limit"

    def reverse_cont(self) -> str:
        while self.m.step_back():
            if self.m.pc in self.breakpoints:
                return "breakpoint"
        return "start"

    def step_line(self) -> int:
        """Step until the source line changes (one line may be several instructions)."""
        start = self.line()
        n = 0
        while self.m.step():
            n += 1
            if self.m.finished or self.line() != start:
                break
        return n

    # -- inspection -----------------------------------------------------------------

    def line(self, addr: int | None = None) -> int | None:
        return self.build.addr_to_line.get(self.m.pc if addr is None else addr)

    def disasm(self, addr: int, count: int = 1) -> list[tuple[int, bytes, str]]:
        if not self.m.readable(addr, 1):
            return []
        size = 16 * count
        while size > 0 and not self.m.readable(addr, size):
            size -= 1
        out = []
        for ins in self.md.disasm(self.m.read(addr, size), addr):
            out.append((ins.address, bytes(ins.bytes), f"{ins.mnemonic} {ins.op_str}".strip()))
            if len(out) == count:
                break
        return out

    def eval_address(self, expr: str) -> int:
        """Resolve 'label', 'label+8', '0x401000', 'rsp', 'rsp+16'."""
        total = 0
        for sign, term in re.findall(r"([+-]?)\s*([^+\-\s]+)", expr.strip()):
            term = term.strip()
            if term in self.m.regs():
                v = self.m.reg(term)
            elif term in self.build.symbols:
                v = self.build.symbols[term]
            else:
                v = int(term, 0)
            total += -v if sign == "-" else v
        return total & ((1 << 64) - 1)

    def resolve_breakpoint(self, spec: str) -> int:
        if spec.startswith("*"):
            return self.eval_address(spec[1:])
        if spec.isdigit():
            line = int(spec)
            for ln in sorted(self.build.line_to_addr):
                if ln >= line:
                    return self.build.line_to_addr[ln]
            raise ValueError(f"no code at or after line {line}")
        return self.eval_address(spec)


# ---- terminal debugger -------------------------------------------------------------

HELP = """\
  s, si [n]       step n instructions (default 1)
  n               step one source line
  b, back [n]     step BACKWARDS n instructions
  c               continue to breakpoint / end        rc   reverse-continue
  break <spec>    breakpoint at a line number, label, or *address
  delete [spec]   delete a breakpoint (or all)
  regs            registers (changed ones marked *)
  vregs [f|d|b]   vector registers in use: hex dwords, or floats/doubles/bytes
  x <addr> [n]    hex dump n bytes (addr: label, register, number, label+off)
  q8 <addr> [n]   dump n qwords        str <addr>   show a 0-terminated string
  dis [n]         disassemble n instructions from rip
  stack [n]       show n qwords at rsp
  out             program output so far
  restart         start over            q, quit   leave
"""


class TerminalDebugger:
    def __init__(self, session: Session, color: bool = True):
        self.s = session
        self.color = color
        self.prev_regs = session.m.regs()
        self.prev_vregs = session.m.vregs()
        self.source = session.build.source.read_text().splitlines()

    def _c(self, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.color else text

    def where(self) -> None:
        m = self.s.m
        if m.finished:
            what = {"done": ("the function returned (rax = "f"{m.reg('rax'):#x})"
                             if m.build.mode == "function" else "reached the end of your code"),
                    "exited": f"exited with status {m.exit_code}",
                    "fault": m.fault, "limit": "step limit reached"}[m.state]
            print(self._c("33", f"-- program finished: {what}  (use `back` to rewind)"))
        line = self.s.line()
        ins = self.s.disasm(m.pc)
        ins_text = f"{ins[0][2]:<32} ; {ins[0][1].hex(' ')}" if ins else "??"
        sym = self.s.build.symbol_at(m.pc) or ""
        loc = f"line {line}: {self.source[line - 1].strip()}" if line and line <= len(self.source) else sym
        print(f"{self._c('36', f'{m.pc:#014x}')}  {ins_text}   {self._c('2', loc)}")

    def regs(self) -> None:
        now = self.s.m.regs()
        cells = []
        for name in GPRS + ["rip"]:
            changed = now[name] != self.prev_regs.get(name)
            text = f"{name:>3}={now[name]:016x}"
            cells.append(self._c("1;33", text + "*") if changed else text + " ")
        for i in range(0, len(cells), 4):
            print("  " + "  ".join(cells[i:i + 4]))
        print(f"  rflags={now['rflags']:#x}  [{flags_str(now['rflags'])}]")

    def vregs(self, fmt: str = "") -> None:
        """Non-zero vector registers: as hex dwords (highest first), or as floats (f),
        doubles (d), or bytes (b), lane 0 first."""
        import struct
        now = self.s.m.vregs()
        if not now:
            print("  (all vector registers are zero)")
        for name, v in now.items():
            mark = "*" if v != self.prev_vregs.get(name) else " "
            if name[1:3] != "mm":
                print(f"  {name:>6}{mark} {v:#x}")
                continue
            size = {"x": 16, "y": 32, "z": 64}[name[0]]
            raw = v.to_bytes(size, "little")
            if fmt == "f":
                text = " ".join(f"{x:.7g}" for x in struct.unpack(f"<{size // 4}f", raw))
            elif fmt == "d":
                text = " ".join(f"{x:.15g}" for x in struct.unpack(f"<{size // 8}d", raw))
            elif fmt == "b":
                text = raw.hex(" ")
            else:
                text = " ".join(f"{v >> (32 * i) & 0xFFFFFFFF:08x}" for i in reversed(range(size // 4)))
            print(self._c("1;33", f"  {name:>6}*") + f" {text}" if mark == "*" else f"  {name:>6}  {text}")

    def dump(self, addr: int, n: int) -> None:
        for off in range(0, n, 16):
            a = addr + off
            size = min(16, n - off)
            if not self.s.m.readable(a, size):
                print(f"  {a:#x}: <unmapped>")
                return
            data = self.s.m.read(a, size)
            asc = "".join(chr(c) if 32 <= c < 127 else "." for c in data)
            label = self.s.build.symbol_at(a) or ""
            print(f"  {a:#014x}  {data.hex(' '):<48} {asc:<16} {self._c('2', label)}")

    def loop(self) -> None:
        print(self._c("1", "ring debugger") + " — type `help` for commands. Nothing has run yet.")
        self.where()
        while True:
            try:
                line = input(self._c("35", "(ring) "))
            except (EOFError, KeyboardInterrupt):
                print()
                return
            try:
                if self.command(line) == "quit":
                    return
            except Exception as e:  # keep the session alive on bad input
                print(self._c("31", f"error: {e}"))

    def command(self, line: str) -> str | None:
        args = shlex.split(line)
        if not args:
            return None
        cmd, rest = args[0], args[1:]
        n = int(rest[0], 0) if rest and rest[0].lstrip("-").isdigit() else 1
        before = self.s.m.regs()
        before_v = self.s.m.vregs()
        moved = False
        if cmd in ("s", "si", "step", "stepi"):
            moved = self.s.step(n) > 0
        elif cmd in ("n", "next"):
            moved = self.s.step_line() > 0
        elif cmd in ("b", "back"):
            moved = self.s.back(n) > 0
            if not moved:
                print("  already at the start")
        elif cmd in ("c", "continue"):
            print(f"  stopped: {self.s.cont()}")
            moved = True
        elif cmd in ("rc", "reverse-continue"):
            print(f"  stopped: {self.s.reverse_cont()}")
            moved = True
        elif cmd == "break":
            addr = self.s.resolve_breakpoint(rest[0])
            self.s.breakpoints.add(addr)
            print(f"  breakpoint at {addr:#x} (line {self.s.line(addr)})")
        elif cmd == "delete":
            if rest:
                self.s.breakpoints.discard(self.s.resolve_breakpoint(rest[0]))
            else:
                self.s.breakpoints.clear()
        elif cmd in ("regs", "r", "info"):
            self.regs()
        elif cmd in ("vregs", "v"):
            self.vregs(rest[0] if rest else "")
        elif cmd == "x":
            self.dump(self.s.eval_address(rest[0]), int(rest[1], 0) if len(rest) > 1 else 32)
        elif cmd == "q8":
            addr = self.s.eval_address(rest[0])
            for i in range(int(rest[1], 0) if len(rest) > 1 else 4):
                a = addr + 8 * i
                v = int.from_bytes(self.s.m.read(a, 8), "little") if self.s.m.readable(a, 8) else None
                print(f"  {a:#014x}: " + (f"{v:#018x}  ({v})" if v is not None else "<unmapped>"))
        elif cmd == "str":
            addr = self.s.eval_address(rest[0])
            raw = bytearray()
            while len(raw) < 256 and self.s.m.readable(addr + len(raw), 1):
                c = self.s.m.read(addr + len(raw), 1)
                if c == b"\0":
                    break
                raw += c
            print(f"  {bytes(raw)!r}")
        elif cmd == "dis":
            for a, raw, text in self.s.disasm(self.s.m.pc, n if rest else 8):
                ln = self.s.line(a)
                marker = "=>" if a == self.s.m.pc else "  "
                print(f"  {marker} {a:#014x}  {raw.hex(' '):<30} {text:<32} {f'line {ln}' if ln else ''}")
        elif cmd == "stack":
            self.command(f"q8 rsp {n if rest else 6}")
        elif cmd == "out":
            print(f"  stdout: {bytes(self.s.m.stdout)!r}\n  stderr: {bytes(self.s.m.stderr)!r}")
            for sc in self.s.m.syscalls:
                print(f"  {sc}")
        elif cmd == "restart":
            self.s.restart()
            moved = True
        elif cmd in ("q", "quit", "exit"):
            return "quit"
        elif cmd in ("h", "help", "?"):
            print(HELP)
        else:
            print(f"  unknown command `{cmd}` (try `help`)")
        if moved:
            self.prev_regs = before
            self.prev_vregs = before_v
            self.where()
        return None
