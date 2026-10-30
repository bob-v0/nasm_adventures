"""x86-TSO for the game's threads: every thread has a store buffer.

Real x86 cores don't write stores to memory (to the cache) right away: they queue them
in a store buffer and drain it in order, a little later. Meanwhile the core's own loads
see its queued stores (store forwarding), but other cores don't. That's the one
reordering x86 allows (a load can complete before an earlier store becomes visible),
and the reason `inc [mem]` without `lock` loses updates between cores.

Model (Unicorn itself is sequentially consistent):
  - memory holds the committed values plus the RUNNING thread's pending stores;
    switching threads takes one thread's pending stores out and puts the other's in;
  - a store goes into the running thread's buffer (Unicorn has already written it to
    memory, which is that thread's view);
  - stores commit oldest first, at points the schedule chooses (thread switches), or
    when a buffer is full (56 entries);
  - `lock`-prefixed instructions, `xchg` with memory, `mfence`, `cpuid` and syscalls
    first drain the thread's buffer, and their own stores commit at once;
  - non-temporal stores (`movnti`, `movntdq`, ...) are weakly ordered: they may commit
    after later ordinary stores, until an `sfence` (or `mfence`, or a locked
    instruction) drains them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

CAPACITY = 56
_DRAINS = {"mfence", "cpuid", "syscall", "xchg", "lfence"}   # (lfence: not on x86, but harmless)
_NONTEMPORAL = {"movnti", "movntdq", "movntps", "movntpd", "movntq", "vmovntdq", "vmovntps",
                "vmovntpd"}


@dataclass
class Buffer:
    stores: list = field(default_factory=list)      # [(addr, bytes)] oldest first
    weak: list = field(default_factory=list)        # non-temporal stores, any order
    saved: dict = field(default_factory=dict)       # byte address -> committed byte (while running)


class TSO:
    def __init__(self, machine):
        self.m = machine
        self.buffers: dict[int, Buffer] = {}
        self.running: int | None = None             # tid whose stores are in memory
        self.mode = "normal"                        # how the current instruction's stores go

    def buffer(self, tid: int) -> Buffer:
        b = self.buffers.get(tid)
        if b is None:
            b = self.buffers[tid] = Buffer()
        return b

    # ---- the instruction about to run (from the code hook) --------------------------------

    def before_insn(self, tid: int, mnemonic: str, locked: bool, mem_operand: bool) -> None:
        if locked or mnemonic in ("mfence", "cpuid", "syscall") or \
                (mnemonic == "xchg" and mem_operand):
            self.drain(tid)                         # everything earlier becomes visible first
            self.mode = "atomic"
        elif mnemonic == "sfence":
            self.drain_weak(tid)
            self.mode = "normal"
        elif mnemonic in _NONTEMPORAL:
            self.mode = "weak"
        else:
            self.mode = "normal"

    # ---- stores (from the memory-write hook, before Unicorn writes) -----------------------

    def on_store(self, tid: int, addr: int, size: int, value: int) -> None:
        if self.mode == "atomic":
            return                                  # locked: straight to memory (buffer is empty)
        b = self.buffer(tid)
        mem = self.m.uc
        for a in range(addr, addr + size):
            if a not in b.saved:
                b.saved[a] = bytes(mem.mem_read(a, 1))[0]
        data = (value & ((1 << (8 * size)) - 1)).to_bytes(size, "little")
        (b.weak if self.mode == "weak" else b.stores).append((addr, data))
        if len(b.stores) + len(b.weak) > CAPACITY:
            self.commit(tid, 1)

    # ---- commits ----------------------------------------------------------------------

    def _commit_one(self, tid: int, addr: int, data: bytes) -> None:
        """Make one store globally visible: it becomes the committed value."""
        if tid == self.running:
            b = self.buffer(tid)
            for i, byte in enumerate(data):         # memory already shows it (or a later one)
                b.saved[addr + i] = byte
            self._forget(b)
            return
        run = self.buffers.get(self.running) if self.running is not None else None
        for i, byte in enumerate(data):
            a = addr + i
            if run is not None and a in run.saved:  # hidden under the running thread's store
                run.saved[a] = byte
            else:
                self.m.uc.mem_write(a, bytes([byte]))

    def _forget(self, b: Buffer) -> None:
        """Drop saved bytes that no pending store covers any more."""
        pending = {a + i for a, d in b.stores + b.weak for i in range(len(d))}
        for a in [a for a in b.saved if a not in pending]:
            del b.saved[a]

    def commit(self, tid: int, n: int) -> None:
        b = self.buffer(tid)
        for _ in range(min(n, len(b.stores))):
            addr, data = b.stores.pop(0)
            self._commit_one(tid, addr, data)
        if tid == self.running:
            self._forget(b)

    def commit_weak(self, tid: int, rng) -> None:
        """Non-temporal stores commit in any order, independently of ordinary ones."""
        b = self.buffer(tid)
        if b.weak and rng.random() < 0.03:         # write-combining buffers flush lazily
            addr, data = b.weak.pop(rng.randrange(len(b.weak)))
            self._commit_one(tid, addr, data)
            if tid == self.running:
                self._forget(b)

    def drain(self, tid: int) -> None:
        self.drain_weak(tid)
        self.commit(tid, len(self.buffer(tid).stores))

    def drain_weak(self, tid: int) -> None:
        b = self.buffer(tid)
        while b.weak:
            addr, data = b.weak.pop(0)
            self._commit_one(tid, addr, data)
        if tid == self.running:
            self._forget(b)

    def drain_all(self) -> None:
        for tid in list(self.buffers):
            self.drain(tid)

    # ---- thread switches ----------------------------------------------------------------

    def switch(self, old: int | None, new: int) -> None:
        """Take old's pending stores out of memory, put new's in."""
        mem = self.m.uc
        if old is not None and old in self.buffers:
            b = self.buffers[old]
            for a, byte in b.saved.items():
                mem.mem_write(a, bytes([byte]))
            b.saved = {}
        self.running = new
        b = self.buffer(new)
        for addr, data in b.stores + b.weak:        # first remember what's committed...
            for i in range(len(data)):
                if addr + i not in b.saved:
                    b.saved[addr + i] = bytes(mem.mem_read(addr + i, 1))[0]
        for addr, data in b.stores + b.weak:        # ...then lay the stores over it, oldest first
            mem.mem_write(addr, data)

    def pending(self, tid: int) -> int:
        b = self.buffers.get(tid)
        return len(b.stores) + len(b.weak) if b else 0
