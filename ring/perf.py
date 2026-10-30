"""The game's CPU cost model: how many cycles a program would take on a simple,
documented out-of-order x86-64 core. It replaces wall-clock timing for Arc VII, so
results are the same on every machine (and on ARM, and in a browser), and the game can
say *why* something is slow.

The core (roughly a 2015-2020 desktop CPU, simplified):
  - in-order front end: 4 uops per cycle; cmp/test/add/sub/and/inc/dec + jcc fuse to 1
  - out of order: an instruction starts when its inputs are ready and an execution unit
    of its kind is free; a 224-entry reorder buffer limits how far ahead it can run
  - branch prediction: 2-bit counters indexed by address and global history, a target
    buffer for indirect jumps, a return stack; a misprediction costs 15 cycles
  - caches: L1 32 KiB (8-way), L2 1 MiB (16-way), 64-byte lines, LRU; memory 200 cycles,
    one line per 4 cycles; a stride prefetcher (16 lines ahead, within a 4 KiB page);
    prefetcht0/1/2/nta
  - TLB: 64 entries (4 KiB pages; 2 MiB huge pages); a miss needs the one page walker
    for 20 cycles
  - stores: a 56-entry store buffer; a store leaves it once its line is in L1 (in order),
    and when it's full, the front end waits. L2 moves one line per 2 cycles, and a
    written (dirty) line pushed out of L1 costs one more such transfer (the write-back).
  - stores are forwarded to later loads (5 cycles), a 15-cycle stall when a load only
    partly overlaps a store, 5 cycles for 4K aliasing (same low 12 address bits)
  - line-split accesses +2 cycles, page splits +20; denormal float results +100 (unless
    MXCSR has FTZ/DAZ); partial registers: writing al/ax depends on the old rax
  - lfence and rdtscp wait for all earlier instructions; rdtsc reads the cycle counter
"""

from __future__ import annotations

import math
from collections import Counter, OrderedDict, deque
from dataclasses import dataclass, field

from capstone import CS_ARCH_X86, CS_MODE_64, CS_OP_MEM, CS_OP_REG, Cs

WIDTH = 4
ROB_SIZE = 224
MISPREDICT = 15
MEM_LATENCY = 200
LINE = 64

# (latency, unit, uops) by mnemonic; loads add the memory latency on top
_INT1 = {"mov", "movzx", "movsx", "movsxd", "add", "sub", "and", "or", "xor", "cmp", "test",
         "inc", "dec", "neg", "not", "lea", "adc", "sbb", "xchg", "bswap", "sete", "setne",
         "rol", "ror", "shl", "shr", "sar", "sal", "andn", "nop", "cdq", "cqo", "cdqe", "cwde",
         "push", "pop", "bt", "bts", "btr", "btc", "movbe", "shlx", "shrx", "sarx", "rorx"}
_TABLE = {
    "imul": (3, "mul", 1), "mul": (4, "mul", 2), "div": (40, "div", 36), "idiv": (42, "div", 57),
    # (a 32-bit div/idiv: 26 cycles; the divider is busy for 24 cycles per division)
    "popcnt": (3, "mul", 1), "lzcnt": (3, "mul", 1), "tzcnt": (3, "mul", 1), "bsf": (3, "mul", 1),
    "bsr": (3, "mul", 1), "pdep": (3, "mul", 1), "pext": (3, "mul", 1), "crc32": (3, "mul", 1),
    "addsd": (4, "fp", 1), "addss": (4, "fp", 1), "subsd": (4, "fp", 1), "subss": (4, "fp", 1),
    "mulsd": (4, "fp", 1), "mulss": (4, "fp", 1), "addpd": (4, "fp", 1), "addps": (4, "fp", 1),
    "mulpd": (4, "fp", 1), "mulps": (4, "fp", 1), "subpd": (4, "fp", 1), "subps": (4, "fp", 1),
    "vaddsd": (4, "fp", 1), "vaddpd": (4, "fp", 1), "vaddps": (4, "fp", 1), "vmulpd": (4, "fp", 1),
    "vmulps": (4, "fp", 1), "vfmadd231sd": (4, "fp", 1), "vfmadd231pd": (4, "fp", 1),
    "vfmadd231ps": (4, "fp", 1), "divsd": (14, "fdiv", 1), "divss": (11, "fdiv", 1),
    "divpd": (14, "fdiv", 1), "sqrtsd": (18, "fdiv", 1), "sqrtss": (12, "fdiv", 1),
    "cvtsi2sd": (5, "fp", 2), "cvttsd2si": (6, "fp", 2), "cvtsd2si": (6, "fp", 2),
    "pmulld": (10, "fp", 2), "pmuludq": (5, "fp", 1), "lfence": (4, "serial", 2),
    "mfence": (33, "serial", 3), "sfence": (6, "serial", 2), "rdtsc": (25, "serial", 20),
    "rdtscp": (32, "serial", 22), "cpuid": (100, "serial", 30), "syscall": (150, "serial", 30),
    "pause": (140, "alu", 4), "shld": (3, "mul", 1), "shrd": (3, "mul", 1),
}
_UNITS = {"alu": 4, "branch": 2, "load": 2, "store": 1, "mul": 1, "div": 1 / 24, "fp": 2,
          "fdiv": 1 / 4, "vec": 3, "serial": 1, "mem": 1 / 4, "l2": 1 / 2, "walk": 1 / 20}
STORE_BUFFER = 56
_FUSES = {"cmp", "test", "add", "sub", "and", "inc", "dec"}
_ZERO_IDIOMS = {"xor", "sub", "pxor", "xorps", "xorpd", "vpxor", "vxorps", "psubd"}
_FP = {"addsd", "addss", "subsd", "subss", "mulsd", "mulss", "divsd", "divss", "addpd", "addps",
       "mulpd", "mulps", "subpd", "subps", "divpd", "sqrtsd", "sqrtss", "vaddsd", "vaddpd",
       "vaddps", "vmulpd", "vmulps", "vfmadd231sd", "vfmadd231pd", "vfmadd231ps"}


def _family(name: str) -> str:
    """al/ax/eax/rax -> rax; r8b/r8w/r8d -> r8; xmm3/ymm3 -> xmm3."""
    n = name.lower()
    if n in ("rip", "eip"):
        return "rip"
    if n.startswith(("xmm", "ymm", "zmm")):
        return "xmm" + n[3:]
    if n.startswith("r") and n[1:2].isdigit():
        return n.rstrip("bwd")
    table = {"a": "rax", "b": "rbx", "c": "rcx", "d": "rdx"}
    if len(n) in (2, 3) and n[-1] in "lhx" and n[-2] in "abcd":
        return table[n[-2]]
    if n in ("eax", "ebx", "ecx", "edx"):
        return table[n[1]]
    for full in ("rsi", "rdi", "rbp", "rsp"):
        if n in (full, "e" + full[1:], full[1:], full[1:] + "l"):
            return full
    if n in ("rflags", "eflags", "flags"):
        return "flags"
    return n


@dataclass
class Info:
    addr: int
    size: int
    mnemonic: str
    reads: frozenset
    writes: frozenset
    addr_regs: frozenset          # registers used to compute a memory address
    mem: tuple | None             # (base, index, scale, disp) of the memory operand
    latency: int
    unit: str
    uops: int
    cond_branch: bool
    indirect: bool                # jmp/call through a register or memory
    is_call: bool
    is_ret: bool
    partial: frozenset            # 8/16-bit destinations (they merge with the old value)
    zero_idiom: bool
    fusable: bool
    fp_dest: str | None           # an SSE register whose result may be denormal
    elem: int                     # 4 (ps/ss) or 8 (pd/sd)


@dataclass
class Cache:
    sets: int
    ways: int
    lines: dict = field(default_factory=dict)        # set -> OrderedDict(line -> None)

    evicted: int | None = None      # the line the last fill pushed out, if any

    def lookup(self, line: int, fill: bool = True) -> bool:
        s = self.lines.setdefault(line % self.sets, OrderedDict())
        self.evicted = None
        if line in s:
            s.move_to_end(line)
            return True
        if fill:
            s[line] = None
            if len(s) > self.ways:
                self.evicted = s.popitem(last=False)[0]
        return False


class CostModel:
    def __init__(self, huge=lambda addr: False, mxcsr=lambda: 0x1F80, noise: int | None = None):
        self.md = Cs(CS_ARCH_X86, CS_MODE_64)
        self.md.detail = True
        self.decoded: dict[int, Info] = {}
        self.huge, self.mxcsr = huge, mxcsr
        self.ready: dict[str, float] = {}
        self.dispatch = 0.0
        self.front = 0.0
        self.busy: dict[str, dict[int, int]] = {}    # unit -> cycle -> units in use
        self.retire: deque[float] = deque()
        self.last_retire = 0.0
        self.max_done = 0.0
        self.pending: Info | None = None
        self.accesses: list[tuple[str, int, int]] = []
        self.prev: Info | None = None
        self.bp: dict[int, int] = {}
        self.history = 0
        self.btb: dict[int, int] = {}
        self.rsb: list[int] = []
        self.l1, self.l2 = Cache(64, 8), Cache(1024, 16)
        self.tlb: OrderedDict = OrderedDict()
        self.fill_ready: dict[int, float] = {}      # line -> when its fill arrives
        self.streams: dict[int, tuple[int, int]] = {}  # page -> (last line, stride)
        self.stores: deque = deque(maxlen=56)        # (addr, size, done)
        self.counts: Counter = Counter()
        self.lost: Counter = Counter()               # cycles lost, by reason
        self.by_addr: Counter = Counter()            # cycles lost, by instruction address
        self.tsc_fix: tuple[int, int] | None = None  # (rdtsc value, 1 if rdtscp)
        self.read_reg = None                         # set by the Machine
        self.store_buffer: deque[float] = deque()    # when each pending store leaves it
        self.cp_ready: dict[str, float] = {}         # for the critical path
        self.dirty: set[int] = set()                 # L1 lines written since they came in
        self.critical = 0.0
        self.last_commit = 0.0
        self.noise = None                            # "interrupts": a deterministic rng
        if noise is not None:
            import random
            self.noise = random.Random(f"interrupts:{noise}")
        self.read_xmm = None

    # ---- decoding ----------------------------------------------------------------------

    def decode(self, addr: int, code: bytes) -> Info:
        info = self.decoded.get(addr)
        if info is not None:
            return info
        ins = next(self.md.disasm(code, addr), None)
        if ins is None:
            info = Info(addr, 1, "?", frozenset(), frozenset(), frozenset(), None, 1,
                        "alu", 1, False, False, False, False, frozenset(), False, False, None, 8)
            self.decoded[addr] = info
            return info
        mn = ins.mnemonic
        regs_r, regs_w = ins.regs_access()
        reads = {_family(ins.reg_name(r)) for r in regs_r}
        writes = {_family(ins.reg_name(r)) for r in regs_w}
        addr_regs, partial, fp_dest, mem = set(), set(), None, None
        for i, op in enumerate(ins.operands):
            if op.type == CS_OP_MEM:
                for r in (op.mem.base, op.mem.index):
                    if r:
                        addr_regs.add(_family(ins.reg_name(r)))
                mem = (ins.reg_name(op.mem.base) if op.mem.base else None,
                       ins.reg_name(op.mem.index) if op.mem.index else None,
                       op.mem.scale, op.mem.disp)
            elif op.type == CS_OP_REG and i == 0:
                name = ins.reg_name(op.reg)
                if name in ("al", "ah", "bl", "bh", "cl", "ch", "dl", "dh", "sil", "dil", "bpl",
                            "spl", "ax", "bx", "cx", "dx", "si", "di", "bp", "sp") or \
                        (name.startswith("r") and name[-1] in "bw" and name[1:2].isdigit()):
                    partial.add(_family(name))
                if mn in _FP:
                    fp_dest = name
        reads.discard("rip")
        writes.discard("rip")
        ops = ins.operands
        zero = (mn in _ZERO_IDIOMS and len(ops) == 2 and ops[0].type == CS_OP_REG
                and ops[1].type == CS_OP_REG and ops[0].reg == ops[1].reg)
        if mn in _TABLE:
            lat, unit, uops = _TABLE[mn]
        elif mn.startswith("cmov") or mn.startswith("set") or mn in _INT1:
            lat, unit, uops = 1, "alu", 1
        elif mn.startswith("j") or mn in ("call", "ret", "loop"):
            lat, unit, uops = 1, "branch", 2 if mn in ("call", "ret") else 1
        elif mn.startswith("prefetch"):
            lat, unit, uops = 1, "load", 1
        elif mn.startswith(("v", "p", "mov")) or mn.endswith(("ps", "pd", "sd", "ss")):
            lat, unit, uops = 1, "vec", 1
        else:
            lat, unit, uops = 2, "alu", 2
        if mn in ("shl", "shr", "sar", "rol", "ror") and "rcx" in reads:
            lat, uops = 2, 2
        if mn in ("div", "idiv") and ins.operands and ins.operands[0].size <= 4:
            lat, uops = (26, 10) if mn == "div" else (26, 10)      # 32-bit: cheaper
        if mn == "loop":
            lat, unit, uops = 1, "branch", 7                       # slower than dec + jnz
        cond = mn.startswith("j") and mn != "jmp" or mn == "loop"
        indirect = mn in ("jmp", "call") and bool(ops) and ops[0].type != 2   # not an immediate
        info = Info(addr, ins.size, mn, frozenset(reads), frozenset(writes), frozenset(addr_regs),
                    mem, lat, unit, uops, cond, indirect, mn == "call", mn == "ret",
                    frozenset(partial), zero, mn in _FUSES and not (mem and len(ops) == 2
                                                                    and ops[1].type == 2),
                    fp_dest, 4 if mn.endswith(("ss", "ps")) else 8)
        self.decoded[addr] = info
        return info

    def warm(self, addr: int, size: int) -> None:
        """Start with [addr, addr+size) in L2 (as if just written by the caller)."""
        for ln in range(addr // LINE, (addr + size + LINE - 1) // LINE):
            self.l2.lookup(ln)

    # ---- events from the emulator ----------------------------------------------------------

    def on_insn(self, info: Info, next_pc: int | None) -> None:
        """Account for the instruction executed before this one."""
        if self.pending is not None:
            self._account(self.pending, self.accesses, next_pc)
        self.pending, self.accesses = info, []

    def on_mem(self, kind: str, addr: int, size: int) -> None:
        self.accesses.append((kind, addr, size))

    def finish(self) -> None:
        if self.pending is not None:
            self._account(self.pending, self.accesses, None)
            self.pending, self.accesses = None, []

    @property
    def cycles(self) -> int:
        return int(max(self.max_done, self.dispatch) + 0.999)

    # ---- the core ------------------------------------------------------------------------

    def _unit(self, unit: str, earliest: float) -> float:
        """Book the earliest cycle >= earliest with a free unit of this kind (units of
        throughput < 1, like the divider, stay busy for several cycles)."""
        cap = _UNITS[unit]
        busy = self.busy.setdefault(unit, {})
        c = math.ceil(earliest - 1e-9)
        if cap >= 1:
            while busy.get(c, 0) >= cap:
                c += 1
            busy[c] = busy.get(c, 0) + 1
            return c
        occupy = round(1 / cap)
        while any(busy.get(c + k) for k in range(occupy)):
            c += 1
        for k in range(occupy):
            busy[c + k] = 1
        return c

    def _prune(self) -> None:
        """Forget unit bookings far in the past (they can't matter any more)."""
        horizon = self.dispatch - 2000
        for unit, busy in self.busy.items():
            if len(busy) > 4096:
                self.busy[unit] = {c: n for c, n in busy.items() if c >= horizon}

    def _lose(self, info: Info, why: str, cycles: float) -> None:
        self.lost[why] += cycles
        self.by_addr[info.addr] += cycles

    def _account(self, info: Info, accesses, next_pc) -> None:
        c = self.counts
        c["instructions"] += 1
        if c["instructions"] % 4096 == 0:
            self._prune()
        fused = (info.cond_branch and self.prev is not None and self.prev.fusable
                 and self.prev.addr + self.prev.size == info.addr)
        uops = 0 if fused else info.uops
        c["uops"] += uops
        # front end: in order, WIDTH uops per cycle, after any misprediction
        start = max(self.dispatch, self.front)
        if len(self.retire) >= ROB_SIZE:          # the reorder buffer is full
            oldest = self.retire.popleft()
            if oldest > start:
                self._lose(info, "reorder buffer full (the oldest instruction hasn't finished: "
                           "a cache miss, or a long dependency chain)", oldest - start)
                start = oldest
        if info.unit == "serial" and info.mnemonic in ("lfence", "rdtscp", "mfence", "cpuid",
                                                        "syscall"):
            start = max(start, self.max_done)     # waits for everything before it
        if self.noise is not None and self.noise.random() < 1 / 2500:
            gap = self.noise.randrange(500, 3000)  # an interrupt: the program just stops a while
            start += gap
            c["interrupts"] += 1
            self._lose(info, "interrupts", gap)
        if any(k == "w" for k, _, _ in accesses):
            while self.store_buffer and self.store_buffer[0] <= start:
                self.store_buffer.popleft()
            if len(self.store_buffer) >= STORE_BUFFER:
                oldest = self.store_buffer.popleft()
                self._lose(info, "store buffer full (stores waiting for their cache lines)",
                           oldest - start)
                start = max(start, oldest)
        self.dispatch = start + uops / WIDTH
        rd = self.ready
        # operands
        src = 0.0 if info.zero_idiom else max((rd.get(r, 0.0) for r in info.reads
                                                if r not in ("rsp", "flags")), default=0.0)
        if info.reads & {"flags"} and not info.zero_idiom:
            src = max(src, rd.get("flags", 0.0))
        src = max(src, max((rd.get(r, 0.0) for r in info.partial), default=0.0))
        addr_ready = max((rd.get(r, 0.0) for r in info.addr_regs if r != "rsp"), default=0.0)
        data = start
        loads = [(a, s) for k, a, s in accesses if k == "r"]
        stores = [(a, s) for k, a, s in accesses if k == "w"]
        load_lat = 0.0
        for a, s in loads:
            t = self._unit("load", max(start, addr_ready))
            lat = self._load_latency(info, a, s, t)
            load_lat = max(load_lat, lat)
            data = max(data, t + lat)
        if info.mnemonic.startswith("prefetch") and info.mem and self.read_reg:
            ea = self._address(info)
            self._tlb(info, ea, start)
            self._line_latency(info, ea // LINE, self._unit("load", max(start, addr_ready)))
        begin = max(start, src, data if loads else start)
        begin = self._unit(info.unit, begin)
        done = begin + (0 if info.zero_idiom else info.latency)
        if info.fp_dest and not self.mxcsr() & 0x8040 and self._denormal(info):
            done += 100
            c["denormal assists"] += 1
            self._lose(info, "denormal float results (microcode assists)", 100)
        for a, s in stores:
            st = self._unit("store", max(start, addr_ready, src))
            self._store(info, a, s, st)
        # the critical path: the same dataflow with unlimited units and a perfect front end
        cp = self.cp_ready
        values = (info.reads - info.addr_regs) | info.partial
        cp_src = 0.0 if info.zero_idiom else max(
            (cp.get(r, 0.0) for r in values if r != "rsp"), default=0.0)
        if loads:     # a load waits for its address, not for the value chain
            cp_addr = max((cp.get(r, 0.0) for r in info.addr_regs if r != "rsp"), default=0.0)
            cp_src = max(cp_src, cp_addr + load_lat)
        cp_done = cp_src + (0 if info.zero_idiom else info.latency)
        for r in info.writes:
            if r != "rip":
                cp[r] = cp_done
        self.critical = max(self.critical, cp_done)
        for r in info.writes:
            if r not in ("rip",):
                rd[r] = done
        if info.mnemonic == "pop" or info.mnemonic == "push" or info.is_call or info.is_ret:
            rd["rsp"] = start                      # the stack engine: rsp updates are free
        # branches
        if info.cond_branch or info.indirect or info.is_ret:
            self._branch(info, next_pc, done)
        if info.mnemonic in ("rdtsc", "rdtscp"):
            self.tsc_fix = (int(start), info.mnemonic == "rdtscp")
        self.max_done = max(self.max_done, done)
        self.last_retire = max(self.last_retire, done)
        self.retire.append(self.last_retire)
        self.prev = info

    def _branch(self, info: Info, next_pc, done) -> None:
        c = self.counts
        c["branches"] += 1
        if next_pc is None:
            return
        if info.cond_branch:
            taken = next_pc != info.addr + info.size
            key = (info.addr ^ (self.history * 0x9E37)) & 0x3FFF
            ctr = self.bp.get(key, 1)
            predicted = ctr >= 2
            self.bp[key] = min(ctr + 1, 3) if taken else max(ctr - 1, 0)
            self.history = ((self.history << 1) | taken) & 0xFFF
            miss = predicted != taken
        elif info.is_ret:
            miss = not self.rsb or self.rsb.pop() != next_pc
        else:
            miss = self.btb.get(info.addr) != next_pc
            self.btb[info.addr] = next_pc
        if info.is_call:
            self.rsb.append(info.addr + info.size)
        if miss:
            c["branch mispredictions"] += 1
            self.front = max(self.front, done + MISPREDICT)
            self._lose(info, "branch mispredictions", MISPREDICT)

    def _tlb(self, info: Info, addr: int, now: float = 0.0) -> float:
        page = addr >> (21 if self.huge(addr) else 12) << 1 | self.huge(addr)
        if page in self.tlb:
            self.tlb.move_to_end(page)
            return 0
        self.tlb[page] = None
        if len(self.tlb) > 64:
            self.tlb.popitem(last=False)
        self.counts["TLB misses"] += 1
        walk = self._unit("walk", now) - now + 20     # one walker: walks queue up
        self._lose(info, "TLB misses", walk)
        return walk

    def _l1(self, line: int, now: float) -> bool:
        """Look up (and fill) a line in L1; writing back the dirty line it evicts."""
        hit = self.l1.lookup(line)
        victim = self.l1.evicted
        if victim is not None and victim in self.dirty:
            self.dirty.discard(victim)
            self._unit("l2", now)
            self.counts["write-backs"] += 1
        return hit

    def _line_latency(self, info: Info, line: int, now: float) -> float:
        self._train_prefetcher(line, now)
        arriving = self.fill_ready.get(line)
        if self._l1(line, now):
            if arriving is not None and arriving > now:   # a prefetch still on its way
                return max(4, arriving - now)
            return 4
        self.counts["L1 misses"] += 1
        if self.l2.lookup(line):
            if arriving is not None and arriving > now:
                return max(14, arriving - now)
            self._lose(info, "L1 cache misses", 10)
            return self._unit("l2", now) - now + 14
        self.counts["L2 misses"] += 1
        t = self._unit("mem", now)
        lat = t - now + MEM_LATENCY
        self._lose(info, "cache misses to memory", lat - 4)
        self.fill_ready[line] = now + lat
        return lat

    def _train_prefetcher(self, line: int, now: float) -> None:
        """A stride prefetcher per 4 KiB page: when two steps between lines in a row have
        the same small stride, fetch up to 16 lines ahead along it (not past the page)."""
        page = line >> 6
        last = self.streams.get(page)
        if last is None:
            self.streams[page] = (line, 0)
            return
        if line == last[0]:
            return
        stride = line - last[0]
        if stride == last[1] and abs(stride) <= 8:
            for k in range(1, 17):
                ahead = line + k * stride
                if ahead >> 6 != page:
                    break
                if not self.l1.lookup(ahead, fill=False):
                    if not self.l2.lookup(ahead):
                        self.fill_ready[ahead] = self._unit("mem", now) + MEM_LATENCY
                    else:
                        self.fill_ready[ahead] = max(self.fill_ready.get(ahead, 0.0), now + 10)
                    self.l1.lookup(ahead)
                    self.counts["prefetched lines"] += 1
        self.streams[page] = (line, stride)

    def _address(self, info: Info) -> int:
        base, index, scale, disp = info.mem
        ea = disp
        if base == "rip":
            ea += info.addr + info.size
        elif base:
            ea += self.read_reg(base)
        if index:
            ea += self.read_reg(index) * scale
        return ea & (1 << 64) - 1

    def _load_latency(self, info: Info, addr: int, size: int, now: float) -> float:
        c = self.counts
        c["loads"] += 1
        extra = self._tlb(info, addr, now)
        first, last = addr // LINE, (addr + size - 1) // LINE
        lat = max(self._line_latency(info, ln, now) for ln in range(first, last + 1))
        if first != last:
            if addr >> 12 != (addr + size - 1) >> 12:
                extra += 20
                c["page-split accesses"] += 1
                self._lose(info, "accesses split across pages", 20)
            else:
                extra += 2
                c["line-split accesses"] += 1
                self._lose(info, "accesses split across cache lines", 2)
        for s_addr, s_size, s_done in reversed(self.stores):
            if s_done < now - 60:
                continue
            overlap = addr < s_addr + s_size and s_addr < addr + size
            if overlap:
                if s_addr <= addr and addr + size <= s_addr + s_size:
                    return max(lat, s_done - now + 5) + extra    # forwarded from the store
                c["failed store forwarding"] += 1
                self._lose(info, "loads that only partly overlap an earlier store", 15)
                return max(lat, s_done - now + 15) + extra
            if (s_addr ^ addr) & 0xFFF == 0:
                c["4K aliasing"] += 1
                self._lose(info, "4K aliasing (a load and an earlier store 4096 bytes apart)", 5)
                extra += 5
                break
        return lat + extra

    def _store(self, info: Info, addr: int, size: int, t: float) -> None:
        """A store executes at t, then waits in the store buffer until its line is in L1
        (fetched from L2 or memory: 'read for ownership'); stores leave in order."""
        self.counts["stores"] += 1
        self._tlb(info, addr, t)
        first, last = addr // LINE, (addr + size - 1) // LINE
        ready = t + 1
        for ln in range(first, last + 1):
            self._train_prefetcher(ln, t)               # the streamer sees stores too
            arriving = self.fill_ready.get(ln)
            hit = self._l1(ln, t)
            self.dirty.add(ln)
            if hit:
                if arriving is not None and arriving > ready:
                    ready = arriving
                continue
            self.counts["L1 misses"] += 1
            self._lose(info, "L1 cache misses", 2)
            if self.l2.lookup(ln):
                ready = max(ready, self._unit("l2", t) + 14)
            else:
                self.counts["L2 misses"] += 1
                ready = max(ready, self._unit("mem", t) + MEM_LATENCY)
                self.fill_ready[ln] = ready
        if first != last:
            self.counts["line-split accesses"] += 1
            self._lose(info, "accesses split across cache lines", 2)
        self.last_commit = max(self.last_commit, ready)
        self.store_buffer.append(self.last_commit)
        self.stores.append((addr, size, t + 1))

    def _denormal(self, info: Info) -> bool:
        value = self.read_xmm(info.fp_dest) if self.read_xmm else None
        if value is None:
            return False
        lanes = 1 if info.mnemonic.endswith(("sd", "ss")) else 16 // info.elem
        bits = info.elem * 8
        exp_bits, frac_bits = (11, 52) if bits == 64 else (8, 23)
        for i in range(lanes):
            lane = value >> (i * bits) & ((1 << bits) - 1)
            exp = lane >> frac_bits & ((1 << exp_bits) - 1)
            if exp == 0 and lane & ((1 << frac_bits) - 1):
                return True
        return False

    # ---- reports ---------------------------------------------------------------------------

    def report(self, where=lambda addr: None) -> str:
        """Cycles, then the costly events (out-of-order execution may have hidden part of
        each event's cost, so these are upper bounds), then the worst instructions."""
        c = self.counts
        lines = [f"{self.cycles} cycles, {c['instructions']} instructions "
                 f"({c['instructions'] / max(self.cycles, 1):.2f} per cycle)"]
        if self.critical >= 0.7 * self.cycles:
            lines.append(f"  a dependency chain sets the pace: its instructions, one waiting for "
                         f"the other, take ~{int(self.critical)} of the {self.cycles} cycles")
        events = [("branch mispredictions", "branch mispredictions"),
                  ("L2 misses", "cache misses to memory"), ("L1 misses", "L1 cache misses"),
                  ("interrupts", "interrupts"),
                  ("TLB misses", "TLB misses"), ("4K aliasing", "4K aliasing"),
                  ("failed store forwarding", "loads that only partly overlap an earlier store"),
                  ("line-split accesses", "accesses split across cache lines"),
                  ("page-split accesses", "accesses split across pages"),
                  ("denormal assists", "denormal float results (microcode assists)")]
        shown = []
        for key, why in events:
            lost = self.lost.get(why, 0)
            if c[key] and lost >= 0.03 * self.cycles:
                shown.append((lost, f"  {c[key]} {key} (up to ~{int(lost)} cycles)"))
        lines += [text for _, text in sorted(shown, reverse=True)]
        worst = self.by_addr.most_common(2)
        for a, v in worst:
            if v >= 0.1 * self.cycles:
                w = where(a)
                lines.append(f"  most of it at {'line ' + str(w) if w else hex(a)}")
        return "\n".join(lines)
