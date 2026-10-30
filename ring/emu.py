"""Unicorn-based x86-64 machine: loads a static ELF, emulates a small set of Linux
syscalls, and supports single-stepping with full reverse execution."""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

from elftools.elf.elffile import ELFFile
from unicorn import (UC_ARCH_X86, UC_HOOK_CODE, UC_HOOK_INSN, UC_HOOK_MEM_INVALID,
                     UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_MODE_64, UC_PROT_EXEC, UC_PROT_READ,
                     UC_PROT_WRITE, Uc, UcError)
from unicorn import x86_const as X

from .build import Build
from . import kernel as K
from .kernel import ERRNO_NAMES, NAMES as SYSCALL_NAMES, SIGNAL_NAMES, Block, Exec, Exit, Kernel

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
SYS_RT_SIGRETURN = 15
UCONTEXT_SIZE, SIGINFO_SIZE = 304, 128
# struct sigcontext register order (also glibc's REG_* indexes into gregs)
SIGCONTEXT_REGS = ["r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15", "rdi", "rsi", "rbp",
                   "rbx", "rdx", "rax", "rcx", "rsp", "rip", "rflags"]
AT_PAGESZ, AT_RANDOM, AT_NULL = 6, 25, 0


@dataclass
class Image:
    """A program started by execve (not the player's build): what Machine needs of a Build."""
    elf_bytes: bytes
    path: str
    entry: int = 0
    mode: str = "program"
    done_addr: int | None = None
    addr_to_line: dict = field(default_factory=dict)
    code_range: tuple[int, int] = (0, 0)
    symbols: dict = field(default_factory=dict)


def align_down(x: int) -> int:
    return x & ~(PAGE - 1)


def align_up(x: int) -> int:
    return (x + PAGE - 1) & ~(PAGE - 1)


@dataclass
class SyscallRecord:
    number: int
    args: tuple[int, ...]
    result: int | None
    note: str = ""
    step: int = 0          # instruction count when it happened

    def __str__(self) -> str:
        if self.note:
            return self.note
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
    """One process. States: ready -> (running) -> done | exited | fault | limit | killed;
    "blocked" while it waits in a syscall for another process.

    The machine the game creates is the first process; fork() makes more, and run()
    then schedules them all, round-robin, `quantum` instructions at a time, until the
    first process ends. Everything is deterministic."""

    USER_LIMIT = USER_LIMIT

    def __init__(self, build: Build, stdin: bytes = b"", record: bool = False,
                 kernel: Kernel | None = None, argv: list[str] | None = None,
                 env: dict[str, str] | list[str] | None = None, _proc=None):
        self.build = build
        self.kernel = kernel or Kernel(stdin)
        self.proc = _proc or self.kernel.proc
        self.kernel.machines[self.proc.pid] = self
        self.argv = argv or ["./solution"]
        self.env = env or {}
        self.proc.command = self.proc.command or self.argv[0]
        self.blocked_on = ""
        self._yield = False
        self.syscalls: list[SyscallRecord] = []
        self.term_signal: int | None = None      # set when killed by a signal
        self.trace: list[int] | None = None      # addresses executed, when enabled
        self.perf = None                          # the CPU cost model, when enabled
        self._redirect: str | None = None        # "sigreturn" / "deliver", requested mid-slice
        self._bad_access: int | None = None
        self._checked_mapped = 0
        self.exit_code: int | None = None
        self.state = "ready"
        self.fault: str | None = None
        self.steps = 0
        self.record = record
        self.history: list[_Frame] = []
        self._frame: _Frame | None = None
        if _proc is None:
            self._new_cpu()
            self._load()

    def _new_cpu(self) -> None:
        self.uc = Uc(UC_ARCH_X86, UC_MODE_64)
        self.uc.hook_add(UC_HOOK_INSN, self._on_syscall, None, 1, 0, X.UC_X86_INS_SYSCALL)
        self.uc.hook_add(UC_HOOK_CODE, self._count)
        self.uc.hook_add(UC_HOOK_MEM_INVALID, self._on_invalid)
        if self.record:
            self.uc.hook_add(UC_HOOK_MEM_WRITE, self._on_write)
        self._checked_mapped = 0

    # ---- loading -------------------------------------------------------------------

    def _load(self) -> None:
        perms: dict[int, int] = {}
        blobs: list[tuple[int, bytes]] = []
        import io
        data = getattr(self.build, "elf_bytes", None)
        with (io.BytesIO(data) if data is not None else open(self.build.elf, "rb")) as fh:
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
        runs: list[list[int]] = []         # [start, size, prot]: adjacent pages, same rights
        for page in sorted(perms):
            if runs and runs[-1][0] + runs[-1][1] == page and runs[-1][2] == perms[page]:
                runs[-1][1] += PAGE
            else:
                runs.append([page, PAGE, perms[page]])
        for start, size, _ in runs:
            self.uc.mem_map(start, size, UC_PROT_READ | UC_PROT_WRITE | UC_PROT_EXEC)
        for addr, data in blobs:
            self.uc.mem_write(addr, data)
        for start, size, prot in runs:
            self.uc.mem_protect(start, size, prot)
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
        env = self.env if isinstance(self.env, list) else [f"{k}={v}" for k, v in self.env.items()]
        env_ptrs = [put(e.encode() + b"\0") for e in env]
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
        return self.state in ("done", "exited", "fault", "limit", "killed", "idle")

    # ---- syscalls -----------------------------------------------------------------

    def _on_syscall(self, uc: Uc, _user) -> None:
        rip = self.reg("rip")
        nr = self.reg("rax")
        if nr == SYS_RT_SIGRETURN:
            self.syscalls.append(SyscallRecord(nr, (), None))
            self._redirect = "sigreturn"
            uc.emu_stop()
            return
        args = tuple(self.reg(r) for r in ("rdi", "rsi", "rdx", "r10", "r8", "r9"))
        try:
            result = self.kernel.syscall(self, nr, args)
        except Exit as e:
            self.syscalls.append(SyscallRecord(nr, args[:1], None))
            self.exit_code = e.status
            self.state = "exited"
            uc.emu_stop()
            return
        except Block as b:
            self._on_block(rip, b.why)
            return
        except Exec as e:
            self.syscalls.append(SyscallRecord(nr, args[:3], 0, step=self.steps))
            self._exec(e)
            uc.emu_stop()
            return
        self.syscalls.append(SyscallRecord(nr, args[:3], result & MASK64, step=self.steps))
        # The kernel returns in rax and clobbers rcx (return rip) and r11 (rflags).
        self.set_reg("rax", result)
        self.set_reg("rcx", rip + 2)
        self.set_reg("r11", self.reg("rflags"))
        self.kernel.after_syscall(SYSCALL_NAMES.get(nr, ""))
        # (Unicorn moves rip past the `syscall` when the hook returns, even after a stop.)
        if self.kernel.pending and self.state == "running":
            self._redirect = "deliver"              # deliver right after this syscall
            uc.emu_stop()
        elif self._yield:
            uc.emu_stop()

    def _on_block(self, rip: int, why: str) -> None:
        """The syscall must wait. A signal that would be delivered interrupts it
        (EINTR, or a restart after the handler with SA_RESTART); otherwise the process
        is parked on the `syscall` instruction, which runs again when it's scheduled."""
        sig = self.kernel.deliverable_pending()
        restart = sig is not None and (self.kernel.disposition(sig) == "kill" or
                                       self.kernel.actions[sig][1] & K.SA_RESTART)
        if sig is not None and not restart:
            self.syscalls.append(SyscallRecord(self.reg("rax"), (), -K.EINTR & MASK64,
                                               step=self.steps))
            self.set_reg("rax", -K.EINTR)
            self.set_reg("rcx", rip + 2)
            self.set_reg("r11", self.reg("rflags"))
            self._redirect = "deliver"
        else:
            self.set_reg("rip", rip - 2)           # run the syscall again later (Unicorn adds 2)
            self.steps -= 1                        # ...and don't count it twice
            if sig is not None:
                self._redirect = "deliver"
            else:
                self.state = "blocked"
                self.blocked_on = why
        self.uc.emu_stop()

    def yield_cpu(self) -> None:
        self._yield = True

    # ---- processes ------------------------------------------------------------------

    def fork(self, child_proc) -> "Machine":
        """A copy of this process: same memory and registers; fork returns 0 in it."""
        child = Machine(self.build, kernel=self.kernel, argv=self.argv, env=self.env,
                        _proc=child_proc)
        child._new_cpu()
        for start, last, prot in self.uc.mem_regions():
            size = last + 1 - start
            child.uc.mem_map(start, size, UC_PROT_READ | UC_PROT_WRITE)
            child.uc.mem_write(start, bytes(self.uc.mem_read(start, size)))
            child.uc.mem_protect(start, size, prot)
        for name in REGS:
            child.set_reg(name, self.reg(name))
        for r in [X.UC_X86_REG_FS_BASE] + [getattr(X, f"UC_X86_REG_XMM{i}") for i in range(16)]:
            child.uc.reg_write(r, self.uc.reg_read(r))
        child.set_reg("rip", self.pc + 2)
        child.set_reg("rax", 0)
        child.set_reg("rcx", self.pc + 2)
        child.set_reg("r11", self.reg("rflags"))
        child._checked_mapped = self._checked_mapped
        if self._checked_mapped:
            child.uc.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE, child._on_heap_access, None,
                              K.CHECKED_HEAP, K.CHECKED_HEAP + (1 << 28))
        child.steps = 0
        child.state = "ready"
        self._yield = True              # let the scheduler decide who runs next
        self._end_history("fork")
        return child

    def _exec(self, e: Exec) -> None:
        """Replace this process's memory with a new program (execve succeeded)."""
        import io
        with io.BytesIO(e.image) as fh:
            entry = ELFFile(fh).header["e_entry"]
        self.build = Image(e.image, e.path, entry=entry)
        self.argv, self.env = e.argv, e.env
        self._end_history("execve")
        self._new_cpu()
        self._load()

    def _end_history(self, why: str) -> None:
        if self.record:
            self.record = False
            self.history.clear()
            self._frame = None
            self.syscalls.append(SyscallRecord(-1, (), None,
                                               f"--- {why}: stepping backwards stops here ---"))

    def wait_status(self) -> int:
        """How this process ended, as wait4 reports it."""
        if self.state == "exited":
            return (self.exit_code & 0xFF) << 8
        return self.term_signal or 11

    def _on_write(self, uc: Uc, _access, addr: int, size: int, _value, _user) -> None:
        if self._frame is not None:
            self._frame.writes.append((addr, bytes(uc.mem_read(addr, size))))

    # ---- execution ----------------------------------------------------------------

    def _count(self, _uc, addr, _size, _user) -> None:
        self.steps += 1
        if self.trace is not None:
            self.trace.append(addr)
        if self.perf is not None:
            p = self.perf
            info = p.decoded.get(addr) or p.decode(addr, self.read(addr, 16)
                                                    if self.readable(addr, 16) else b"")
            p.on_insn(info, addr)
            if p.tsc_fix is not None:               # rdtsc ran: it reads the model's clock
                tsc, rdtscp = p.tsc_fix
                p.tsc_fix = None
                self.set_reg("rax", tsc & 0xFFFFFFFF)
                self.set_reg("rdx", tsc >> 32)
                if rdtscp:
                    self.set_reg("rcx", 0)

    def enable_perf(self, noise: int | None = None) -> None:
        """Count cycles with the game's CPU model (ring/perf.py) from now on."""
        from .perf import CostModel
        self.perf = CostModel(huge=lambda a: self.kernel.is_huge(a),
                              mxcsr=lambda: self.uc.reg_read(X.UC_X86_REG_MXCSR), noise=noise)
        self.perf.read_reg = self.reg_any
        self.perf.read_xmm = lambda name: self.uc.reg_read(getattr(X, f"UC_X86_REG_{name.upper()}"))
        self.uc.hook_add(UC_HOOK_MEM_READ, lambda uc, a, addr, size, v, d:
                         self.perf.on_mem("r", addr, size))
        self.uc.hook_add(UC_HOOK_MEM_WRITE, lambda uc, a, addr, size, v, d:
                         self.perf.on_mem("w", addr, size))

    def reg_any(self, name: str) -> int:
        return self.uc.reg_read(getattr(X, f"UC_X86_REG_{name.upper()}")) & MASK64

    def _on_invalid(self, _uc, _access, addr, _size, _value, _user) -> bool:
        self._bad_access = addr
        return False

    def _next_injected(self) -> int | None:
        if self.proc.pid != K.FIRST_PID:
            return None
        due = [s["at"] for s in self.kernel.inject.signals if s["at"] > self.steps]
        return min(due) if due else None

    def _raise_injected(self) -> None:
        if self.proc.pid != K.FIRST_PID:
            return
        for s in self.kernel.inject.signals:
            if s["at"] == self.steps:
                self.kernel.raise_signal(s["sig"])

    def _between_slices(self) -> None:
        """Kernel work between instructions: sigreturn, injected and pending signals."""
        if self._redirect == "sigreturn":
            self._sigreturn()
        self._redirect = None
        self._raise_injected()
        while self.state == "running":
            sig = self.kernel.next_deliverable()
            if sig is None:
                break
            self._deliver(sig)

    def _slice(self, until: int, count: int) -> None:
        try:
            self.uc.emu_start(self.pc, until, count=count)
        except UcError as e:
            self._fault(e)

    def _advance(self, budget: int) -> None:
        """Run this process for up to `budget` instructions; stop early when it ends,
        blocks, or yields (after fork, sched_yield)."""
        done = self.build.done_addr
        end = self.steps + budget
        self._yield = False
        while self.state == "running" and self.steps < end and not self._yield:
            nxt = self._next_injected()
            count = min(end, nxt if nxt is not None else end) - self.steps
            self._slice(done or 0, count)
            if self.state != "running":
                break
            stopped_for_kernel = self._redirect is not None or self._yield
            self._between_slices()
            if self.state == "running" and not stopped_for_kernel and done is not None \
                    and self.pc == done:
                self.state = "done"
        self._yield = False

    def _activate(self) -> None:
        self.kernel.proc = self.proc

    def run(self, max_steps: int = 1_000_000) -> str:
        """Run to completion (or until max_steps instructions in all processes),
        without recording history."""
        if self.finished:
            return self.state
        if self.state == "blocked":
            self.state = "running"
        self._schedule(max_steps, until=lambda: self.finished)
        if self.perf is not None and self.finished:
            self.perf.finish()
        return self.state

    def _schedule(self, max_steps: int, until) -> None:
        """Round-robin over all live processes until `until()` holds."""
        used, turn = 0, 0
        while not until():
            live = [m for m in self.kernel.machines.values() if not m.finished]
            n = turn % len(live)
            progress, used = self._round(live[n:] + live[:n], max_steps, used, until)
            turn += 1
            if self.state == "ready":
                self.state = "running"
            if used >= max_steps and not until():
                self.state, self.fault = "limit", None
                return
            if not progress and not until():
                if self._all_waiting():
                    return
                continue
        self._activate()

    def _round(self, machines: list["Machine"], max_steps: int, used: int,
               until=lambda: False) -> tuple[bool, int]:
        """Give each process one turn. Returns (did anyone make progress, steps used)."""
        k = self.kernel
        progress = False
        for m in machines:
            if until() or m.finished or used >= max_steps:
                continue
            before, was_blocked, pc_before = m.steps, m.state == "blocked", m.pc
            m.state = "running"
            m._activate()
            alone = len(k.machines) == 1
            m._advance(max_steps - used if alone else min(max_steps - used, k.inject.quantum))
            used += m.steps - before
            if m.state == "running":
                m.state = "ready"
            if not (was_blocked and m.state == "blocked" and m.steps == before
                    and m.pc == pc_before):
                progress = True
            if m.finished and m is not self:
                k.process_exit(m.proc, m.wait_status())
                del k.machines[m.proc.pid]
        return progress, used

    def _all_waiting(self) -> bool:
        """Nobody can run. If time can move on to the next event, do that (False: go on).
        Otherwise the run ends: "idle" when a server has served all its clients, else a
        deadlock (True)."""
        k = self.kernel
        if k.peers_done:
            self.state = "idle"
            return True
        if k.advance_time():
            return False
        self._deadlock()
        return True

    def _deadlock(self) -> None:
        blocked = [m for m in self.kernel.machines.values() if m.state == "blocked"]
        waiting = [f"pid {m.proc.pid}" + (f" ({m.proc.command})" if m.proc.command else "")
                   + f": {m.blocked_on}" for m in blocked]
        why = []
        if any("empty pipe" in m.blocked_on for m in blocked):
            why.append("A pipe read waits while ANY write end is still open, including copies "
                       "inherited through fork: close the ends you don't use.")
        if any("full pipe" in m.blocked_on for m in blocked):
            why.append("A pipe write waits for room while ANY read end is still open, even if "
                       "nobody will read it again; with no read end left it gets SIGPIPE.")
        self.state = "fault"
        if self.kernel.peers:
            self.fault = ("everything stopped: the program waits ("
                          + "; ".join(waiting) + ") and so do the clients: "
                          + "; ".join(self.kernel.peer_report()))
            return
        self.fault = ("deadlock: every process is waiting for another one, forever ("
                      + "; ".join(waiting) + ")." + "".join(" " + w for w in why))

    def step(self) -> bool:
        """Execute one instruction. Returns False if the machine had already finished.
        (Other processes run only while this one waits for them.)"""
        if self.finished:
            return False
        if self.record:
            at_syscall = self.readable(self.pc, 2) and self.read(self.pc, 2) == SYSCALL_INSN
            k = self.kernel
            snap = at_syscall or k.actions or k.pending or k.inject.signals or k.blocks
            self._frame = _Frame(self.uc.context_save(), [], [],
                                 k.snapshot() if snap else None,
                                 len(self.syscalls), self.state, self.exit_code)
        used = 0
        while True:
            self.state = "running"
            self._activate()
            self._slice(0, 1)
            if self.state != "blocked":
                break
            # Let the others run until this one can go on (or nobody can).
            others = [m for m in self.kernel.machines.values() if m is not self and not m.finished]
            progress, used = self._round(others, 1_000_000, used)
            if not progress and self._all_waiting():
                break
            if used >= 1_000_000:
                self.state = "limit"
                break
        self._activate()
        if self.state == "running":
            self._between_slices()
        if self.state == "running":
            self.state = "done" if self.pc == self.build.done_addr else "ready"
        if self._frame is not None:
            self.history.append(self._frame)
            self._frame = None
        return True

    # ---- signals ----------------------------------------------------------------------

    def _deliver(self, sig: int) -> None:
        what = self.kernel.disposition(sig)
        if what == "ignore":
            return
        name = SIGNAL_NAMES.get(sig, f"signal {sig}")
        if what == "kill":
            self.state = "killed"
            self.term_signal = sig
            self.fault = f"killed by {name} (no handler installed)"
            return
        handler, flags, restorer, mask = self.kernel.actions[sig]
        regs = self.regs()
        sp = regs["rsp"] - 128                                  # skip the red zone
        sp = ((sp - 8 - UCONTEXT_SIZE - SIGINFO_SIZE) & ~15) - 8
        uc, info = sp + 8, sp + 8 + UCONTEXT_SIZE
        if not self.writable(sp, 8 + UCONTEXT_SIZE + SIGINFO_SIZE):
            self.state = "killed"
            self.term_signal = 11
            self.fault = f"killed by SIGSEGV: no room on the stack to deliver {name}"
            return
        gregs = [regs[r] for r in SIGCONTEXT_REGS] + [0x33, 0, 14 if sig == 11 else 0,
                                                      self.kernel.blocked, self._bad_access or 0]
        ctx = struct.pack("<QQ24x", 0, 0) + struct.pack(f"<{len(gregs)}Q", *gregs)
        ctx += bytes(256 - 23 * 8) + struct.pack("<Q", self.kernel.blocked)
        self.kernel_write(sp, struct.pack("<Q", restorer if flags & K.SA_RESTORER else 0))
        self.kernel_write(uc, ctx)
        self.kernel_write(info, struct.pack("<iii4xQ", sig, 0, 0, self._bad_access or 0)
                          + bytes(SIGINFO_SIZE - 24))
        if not flags & K.SA_NODEFER:
            self.kernel.blocked |= 1 << (sig - 1)
        self.kernel.blocked |= mask
        if flags & K.SA_RESETHAND:
            self.kernel.actions[sig] = (K.SIG_DFL, 0, 0, 0)
        self.set_reg("rsp", sp)
        self.set_reg("rip", handler)
        self.set_reg("rdi", sig)
        self.set_reg("rsi", info)
        self.set_reg("rdx", uc)
        self.set_reg("rax", 0)
        self.set_reg("rflags", regs["rflags"] & ~(1 << 10))   # DF clear in handlers
        self.syscalls.append(SyscallRecord(-1, (sig,), None, f"--- {name} delivered ---"))

    def _sigreturn(self) -> None:
        uc = self.reg("rsp")       # the handler's `ret` popped pretcode: rsp is at the ucontext
        if not self.readable(uc, UCONTEXT_SIZE):
            self.state = "killed"
            self.term_signal = 11
            self.fault = "killed by SIGSEGV: rt_sigreturn found no signal frame on the stack"
            return
        gregs = struct.unpack(f"<{len(SIGCONTEXT_REGS)}Q", self.read(uc + 40, 8 * len(SIGCONTEXT_REGS)))
        for name, value in zip(SIGCONTEXT_REGS, gregs):
            self.set_reg(name, value)
        self.kernel.blocked = struct.unpack("<Q", self.read(uc + 40 + 256, 8))[0]

    # ---- faults ----------------------------------------------------------------------

    def _fault(self, e: UcError) -> None:
        msg = str(e).upper()
        sig = 4 if "INSN_INVALID" in msg else 8 if "EXCEPTION" in msg else 11
        if self.kernel.disposition(sig) == "handle" and not self.kernel.blocked >> (sig - 1) & 1:
            self._deliver(sig)          # the faulting instruction is re-run after sigreturn
            self._bad_access = None
            return
        self._set_fault(e)
        self.fault += f" [{SIGNAL_NAMES[sig]}]"

    def memory_error(self, message: str) -> None:
        """Called by the checked allocator / heap watch: stop at the bad access."""
        self.state = "fault"
        self.fault = f"memory error: {message}"
        self.uc.emu_stop()

    def caller_line(self) -> str:
        """Where the game's malloc/free was called from (its return address)."""
        ret = int.from_bytes(self.read(self.reg("rsp"), 8), "little") if self.readable(self.reg("rsp"), 8) else 0
        lines = [(a, ln) for a, ln in self.build.addr_to_line.items() if a < ret]
        return f"line {max(lines)[1]}" if lines else f"{ret:#x}"

    def ensure_checked_heap(self, top: int) -> None:
        if not self._checked_mapped:
            self._checked_mapped = K.CHECKED_HEAP
            self.uc.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE, self._on_heap_access, None,
                             K.CHECKED_HEAP, K.CHECKED_HEAP + (1 << 28))
        if top > self._checked_mapped:
            new_top = align_up(top)
            self.map_region(self._checked_mapped, new_top - self._checked_mapped,
                            UC_PROT_READ | UC_PROT_WRITE)
            self._checked_mapped = new_top

    def _on_heap_access(self, uc, access, addr, size, _value, _user) -> None:
        found = self.kernel.checked_block(addr)
        if found is not None:                        # the common case: a fine access
            start, b = found
            if not b["freed"] and start <= addr and addr + size <= start + b["size"]:
                return
        kind = "write" if access == 17 or access == 0x11 else "read"   # UC_MEM_WRITE = 17
        line = self.build.addr_to_line.get(self.pc)
        where = f" at line {line}" if line else f" at rip={self.pc:#x}"
        if found is None:
            self.memory_error(f"{kind} of {size} bytes at {addr:#x}, outside any heap block{where}")
            return
        start, b = found
        if b["freed"]:
            self.memory_error(f"use after free: {kind} of {size} bytes{where}, inside a block "
                              f"allocated at {b['alloc']} and freed at {b['free']}")
        elif addr < start or addr + size > start + b["size"]:
            self.memory_error(f"heap overflow: {kind} of {size} bytes{where}, "
                              f"{'before' if addr < start else 'past'} the {b['size']}-byte block "
                              f"allocated at {b['alloc']}")

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
        self.term_signal = None
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
