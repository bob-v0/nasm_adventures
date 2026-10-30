"""Unicorn-based x86-64 machine: loads a static ELF, emulates a small set of Linux
syscalls, and supports single-stepping with full reverse execution."""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

from elftools.elf.elffile import ELFFile
from unicorn import (UC_ARCH_X86, UC_HOOK_CODE, UC_HOOK_INSN, UC_HOOK_MEM_WRITE, UC_MODE_64,
                     UC_PROT_EXEC, UC_PROT_READ, UC_PROT_WRITE, Uc, UcError)
from unicorn import x86_const as X

from .build import Build
from .kernel import ERRNO_NAMES, NAMES as SYSCALL_NAMES, Exit, Kernel

PAGE = 0x1000
STACK_TOP = 0x7FFFFFFFF000
STACK_SIZE = 0x100000
MASK64 = (1 << 64) - 1
USER_LIMIT = 0x7FFFFFFFF000  # end of the user address space on Linux x86-64

GPRS = ["rax", "rbx", "rcx", "rdx", "rsi", "rdi", "rbp", "rsp",
        "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15"]
REGS = {name: getattr(X, f"UC_X86_REG_{name.upper()}") for name in GPRS + ["rip", "rflags"]}

FLAG_BITS = [("CF", 0), ("PF", 2), ("AF", 4), ("ZF", 6), ("SF", 7), ("TF", 8),
             ("IF", 9), ("DF", 10), ("OF", 11)]

SYSCALL_INSN = b"\x0f\x05"
AT_PAGESZ, AT_RANDOM, AT_NULL = 6, 25, 0


def align_down(x: int) -> int:
    return x & ~(PAGE - 1)


def align_up(x: int) -> int:
    return (x + PAGE - 1) & ~(PAGE - 1)


@dataclass
class SyscallRecord:
    number: int
    args: tuple[int, ...]
    result: int | None

    def __str__(self) -> str:
        name = SYSCALL_NAMES.get(self.number, f"syscall_{self.number}")
        res = "" if self.result is None else f" = {_signed(self.result)}"
        if self.result is not None and -4096 < _signed(self.result) < 0:
            res += f" ({ERRNO_NAMES.get(-_signed(self.result), 'error')})"
        return f"{name}({', '.join(hex(a) for a in self.args)}){res}"


def _signed(v: int) -> int:
    return v - (1 << 64) if v & (1 << 63) else v


@dataclass
class _Frame:
    """Undo record for one executed instruction."""
    context: object
    writes: list[tuple[int, bytes]] = field(default_factory=list)
    undo: list = field(default_factory=list)     # callables undoing memory-map changes
    kernel: dict | None = None                   # kernel snapshot, taken before a syscall
    syscalls_len: int = 0
    state: str = "ready"
    exit_code: int | None = None


class Machine:
    """States: ready -> (running) -> done | exited | fault | limit."""

    USER_LIMIT = USER_LIMIT

    def __init__(self, build: Build, stdin: bytes = b"", record: bool = False,
                 kernel: Kernel | None = None, argv: list[str] | None = None,
                 env: dict[str, str] | None = None):
        self.build = build
        self.kernel = kernel or Kernel(stdin)
        self.argv = argv or ["./solution"]
        self.env = env or {}
        self.syscalls: list[SyscallRecord] = []
        self.exit_code: int | None = None
        self.state = "ready"
        self.fault: str | None = None
        self.steps = 0
        self.record = record
        self.history: list[_Frame] = []
        self._frame: _Frame | None = None
        self.uc = Uc(UC_ARCH_X86, UC_MODE_64)
        self._load()
        self.uc.hook_add(UC_HOOK_INSN, self._on_syscall, None, 1, 0, X.UC_X86_INS_SYSCALL)
        if record:
            self.uc.hook_add(UC_HOOK_MEM_WRITE, self._on_write)

    # ---- loading -------------------------------------------------------------------

    def _load(self) -> None:
        perms: dict[int, int] = {}
        blobs: list[tuple[int, bytes]] = []
        with open(self.build.elf, "rb") as fh:
            elf = ELFFile(fh)
            for seg in elf.iter_segments():
                if seg["p_type"] != "PT_LOAD":
                    continue
                prot = 0
                flags = seg["p_flags"]
                prot |= UC_PROT_READ if flags & 4 else 0
                prot |= UC_PROT_WRITE if flags & 2 else 0
                prot |= UC_PROT_EXEC if flags & 1 else 0
                start, end = seg["p_vaddr"], seg["p_vaddr"] + seg["p_memsz"]
                for page in range(align_down(start), align_up(end), PAGE):
                    perms[page] = perms.get(page, 0) | prot
                blobs.append((start, seg.data()))
        for page in sorted(perms):
            self.uc.mem_map(page, PAGE, UC_PROT_READ | UC_PROT_WRITE | UC_PROT_EXEC)
        for addr, data in blobs:
            self.uc.mem_write(addr, data)
        for page, prot in perms.items():
            self.uc.mem_protect(page, PAGE, prot)
        if perms:   # the heap (brk) starts right after the program's last page
            self.kernel.brk_start = self.kernel.brk = max(perms) + PAGE

        self.uc.mem_map(STACK_TOP - STACK_SIZE, STACK_SIZE, UC_PROT_READ | UC_PROT_WRITE)
        if self.build.mode == "program":
            rsp = self._linux_initial_stack()
        elif self.build.mode == "function":
            # As if called: rsp is 16-byte aligned before the call, and the call pushed
            # the return address (the game's trap) so the function sees rsp % 16 == 8.
            rsp = STACK_TOP - PAGE - 8
            self.uc.mem_write(rsp, struct.pack("<Q", self.build.done_addr))
        else:
            rsp = STACK_TOP - PAGE
        self.uc.reg_write(REGS["rsp"], rsp)
        self.uc.reg_write(REGS["rip"], self.build.entry)
        self.uc.reg_write(REGS["rflags"], 0x202)

    def _linux_initial_stack(self) -> int:
        """The stack Linux builds for a new program: strings at the top, then (from rsp
        upwards) argc, argv[] + NULL, envp[] + NULL, auxv pairs ending with AT_NULL."""
        pos = STACK_TOP - 16
        def put(data: bytes) -> int:
            nonlocal pos
            pos -= len(data)
            self.uc.mem_write(pos, data)
            return pos
        rand = put(bytes(range(16)))                      # AT_RANDOM points at 16 bytes
        env_ptrs = [put(f"{k}={v}".encode() + b"\0") for k, v in self.env.items()]
        arg_ptrs = [put(a.encode() + b"\0") for a in self.argv]
        words = [len(self.argv), *arg_ptrs, 0, *env_ptrs, 0,
                 AT_PAGESZ, PAGE, AT_RANDOM, rand, AT_NULL, 0]
        rsp = (pos - 8 * len(words) - 64) & ~0xF          # argc is 16-byte aligned
        self.uc.mem_write(rsp, struct.pack(f"<{len(words)}Q", *words))
        return rsp

    # ---- registers & memory -------------------------------------------------------

    def reg(self, name: str) -> int:
        return self.uc.reg_read(REGS[name]) & MASK64

    def set_reg(self, name: str, value: int) -> None:
        self.uc.reg_write(REGS[name], value & MASK64)

    def regs(self) -> dict[str, int]:
        return {n: self.reg(n) for n in REGS}

    def read(self, addr: int, size: int) -> bytes:
        return bytes(self.uc.mem_read(addr, size))

    def write(self, addr: int, data: bytes) -> None:
        self.uc.mem_write(addr, data)

    def readable(self, addr: int, size: int) -> bool:
        return self._covered(addr, size, UC_PROT_READ)

    def _readable_prefix(self, addr: int, size: int) -> int:
        """Number of bytes readable from addr onwards, up to size."""
        n = 0
        for start, last, p in sorted(self.uc.mem_regions()):
            if n < size and start <= addr + n <= last and p & UC_PROT_READ:
                n = min(size, last + 1 - addr)
        return n

    def _covered(self, addr: int, size: int, prot: int) -> bool:
        """Is [addr, addr+size) entirely mapped with `prot`? (Checks the memory map
        rather than reading, so absurd sizes from buggy programs are cheap.)"""
        if size <= 0:
            return True
        end = addr + size - 1
        if end > MASK64:
            return False
        for start, last, p in sorted(self.uc.mem_regions()):
            if start <= addr <= last:
                if not p & prot:
                    return False
                if end <= last:
                    return True
                addr = last + 1
        return False

    def readable_prefix(self, addr: int, size: int) -> int:
        return self._readable_prefix(addr, size)

    def writable(self, addr: int, size: int) -> bool:
        return self._covered(addr, size, UC_PROT_WRITE)

    def kernel_write(self, addr: int, data: bytes) -> None:
        """A write done by the kernel on the program's behalf (recorded for undo)."""
        if self._frame is not None:
            self._frame.writes.append((addr, self.read(addr, len(data))))
        self.write(addr, data)

    def map_region(self, start: int, length: int, prot: int, data: bytes = b"") -> None:
        self.uc.mem_map(start, length, UC_PROT_READ | UC_PROT_WRITE)
        if data:
            self.uc.mem_write(start, data)
        self.uc.mem_protect(start, length, prot & 7)
        if self._frame is not None:
            self._frame.undo.append(lambda: self.uc.mem_unmap(start, length))

    def unmap_region(self, start: int, length: int) -> None:
        for page in range(start, start + length, PAGE):
            prot = next((p for a, b, p in self.uc.mem_regions() if a <= page <= b), None)
            if prot is None:
                continue
            data = self.read(page, PAGE) if prot & UC_PROT_READ else bytes(PAGE)
            self.uc.mem_unmap(page, PAGE)
            if self._frame is not None:
                self._frame.undo.append(lambda page=page, prot=prot, data=data: (
                    self.uc.mem_map(page, PAGE, UC_PROT_READ | UC_PROT_WRITE),
                    self.uc.mem_write(page, data), self.uc.mem_protect(page, PAGE, prot)))

    def protect_region(self, start: int, length: int, prot: int) -> None:
        old = [(page, p) for page in range(start, start + length, PAGE)
               for a, b, p in self.uc.mem_regions() if a <= page <= b]
        self.uc.mem_protect(start, length, prot & 7)
        if self._frame is not None:
            self._frame.undo.append(lambda: [self.uc.mem_protect(pg, PAGE, p) for pg, p in old])

    def resize_region(self, start: int, old_end: int, new_end: int) -> None:
        old_top, new_top = align_up(old_end), align_up(new_end)
        if new_top > old_top:
            self.map_region(old_top, new_top - old_top, UC_PROT_READ | UC_PROT_WRITE)
        elif new_top < old_top:
            self.unmap_region(new_top, old_top - new_top)

    def set_fs_base(self, addr: int) -> None:
        self.uc.reg_write(X.UC_X86_REG_FS_BASE, addr)

    @property
    def stdout(self) -> bytearray:
        return self.kernel.stdout

    @property
    def stderr(self) -> bytearray:
        return self.kernel.stderr

    @property
    def pc(self) -> int:
        return self.reg("rip")

    @property
    def finished(self) -> bool:
        return self.state in ("done", "exited", "fault", "limit")

    # ---- syscalls -----------------------------------------------------------------

    def _on_syscall(self, uc: Uc, _user) -> None:
        rip = self.reg("rip")
        nr = self.reg("rax")
        args = tuple(self.reg(r) for r in ("rdi", "rsi", "rdx", "r10", "r8", "r9"))
        try:
            result = self.kernel.syscall(self, nr, args)
        except Exit as e:
            self.syscalls.append(SyscallRecord(nr, args[:1], None))
            self.exit_code = e.status
            self.state = "exited"
            self.set_reg("rip", rip + 2)
            uc.emu_stop()
            return
        self.syscalls.append(SyscallRecord(nr, args[:3], result & MASK64))
        # The kernel returns in rax and clobbers rcx (return rip) and r11 (rflags).
        self.set_reg("rax", result)
        self.set_reg("rcx", rip + 2)
        self.set_reg("r11", self.reg("rflags"))

    def _on_write(self, uc: Uc, _access, addr: int, size: int, _value, _user) -> None:
        if self._frame is not None:
            self._frame.writes.append((addr, bytes(uc.mem_read(addr, size))))

    # ---- execution ----------------------------------------------------------------

    def run(self, max_steps: int = 1_000_000) -> str:
        """Run to completion (or until max_steps), without recording history."""
        if self.finished:
            return self.state
        counter = {"n": 0}

        def count(_uc, _addr, _size, _user):
            counter["n"] += 1

        h = self.uc.hook_add(UC_HOOK_CODE, count)
        self.state = "running"
        done = self.build.done_addr
        try:
            self.uc.emu_start(self.pc, done or 0, count=max_steps)
        except UcError as e:
            self._set_fault(e)
        finally:
            self.uc.hook_del(h)
        self.steps += counter["n"]
        if self.state == "running":
            if done is not None and self.pc == done:
                self.state = "done"
            else:
                self.state = "limit"
        return self.state

    def step(self) -> bool:
        """Execute one instruction. Returns False if the machine had already finished."""
        if self.finished:
            return False
        if self.record:
            at_syscall = self.readable(self.pc, 2) and self.read(self.pc, 2) == SYSCALL_INSN
            self._frame = _Frame(self.uc.context_save(), [], [],
                                 self.kernel.snapshot() if at_syscall else None,
                                 len(self.syscalls), self.state, self.exit_code)
        self.state = "running"
        try:
            self.uc.emu_start(self.pc, 0, count=1)
        except UcError as e:
            self._set_fault(e)
        self.steps += 1
        if self.state == "running":
            self.state = "done" if self.pc == self.build.done_addr else "ready"
        if self._frame is not None:
            self.history.append(self._frame)
            self._frame = None
        return True

    def step_back(self) -> bool:
        if not self.history:
            return False
        f = self.history.pop()
        for undo in reversed(f.undo):
            undo()
        for addr, old in reversed(f.writes):
            self.uc.mem_write(addr, old)
        self.uc.context_restore(f.context)
        if f.kernel is not None:
            self.kernel.restore(f.kernel)
        del self.syscalls[f.syscalls_len:]
        self.state = f.state
        self.exit_code = f.exit_code
        self.fault = None
        self.steps -= 1
        return True

    def _set_fault(self, e: UcError) -> None:
        self.state = "fault"
        pc = self.pc
        where = self.build.addr_to_line.get(pc)
        loc = f" (solution line {where})" if where else ""
        end = self.build.code_range[1]
        if not where and end <= pc < align_up(end + 1):
            missing = "`ret`" if self.build.mode == "function" else "to exit"
            loc = f" (past the end of your code: did you forget {missing}?)"
        self.fault = f"{_describe(e)} at rip={pc:#x}{loc}"


def _describe(e: UcError) -> str:
    msg = str(e)
    table = {
        "UNMAPPED": "segmentation fault: access to unmapped memory",
        "WRITE_PROT": "segmentation fault: write to read-only memory",
        "READ_PROT": "segmentation fault: read from protected memory",
        "FETCH_PROT": "segmentation fault: executing non-executable memory",
        "INSN_INVALID": "illegal instruction (#UD)",
        "EXCEPTION": "CPU exception (e.g. #DE divide error or privileged instruction)",
    }
    for key, text in table.items():
        if key in msg.upper().replace(" ", "_"):
            return text
    return f"CPU fault: {msg}"


def flags_str(rflags: int) -> str:
    return " ".join(name if rflags >> bit & 1 else name.lower() for name, bit in FLAG_BITS
                    if name not in ("TF", "IF"))
