"""The game's vector unit: AVX, AVX2, FMA and AVX-512 on top of Unicorn.

Unicorn (QEMU 5's CPU) runs x87, SSE through SSE4.2 and the scalar VEX instructions
(BMI1/2), but not AVX: a VEX- or EVEX-encoded vector instruction is an invalid opcode
to it. Those land here. This module decodes them with Capstone and carries them out on
the same registers (Unicorn keeps the full 512-bit zmm0-31 state; the mask registers
k0-k7 live here) and the same memory, reporting every access to the machine's hooks
(the CPU model, the store buffers, the checked heap, reverse stepping) as if Unicorn
had made it.

It also decides what the CPU *is*: `cpuid` and `xgetbv` report the features of a CPU
profile, and an instruction the profile lacks raises #UD (SIGILL), exactly as on an
older machine. So a program that dispatches on `cpuid` can be tested on several
"machines" in one run.

Faithful in the ways the game's levels can observe: VEX/EVEX zero the bits above the
vector length; masks merge or zero; masked-off elements never fault; the aligned moves
fault on misaligned addresses; FMA rounds once. Not modelled: floating-point
exceptions and the MXCSR flags they set (results are those of the default, masked
exceptions); DAZ/FTZ for emulated instructions; `vrcpps`/`vrsqrtps` return the exact
value rounded to 12 bits.
"""

from __future__ import annotations

import math
import re
import struct
from fractions import Fraction

import numpy as np
from capstone import CS_ARCH_X86, CS_MODE_64, CS_OP_IMM, CS_OP_MEM, CS_OP_REG, Cs
from unicorn import x86_const as X

MASK64 = (1 << 64) - 1

# scalar VEX instructions Unicorn runs itself; every other VEX/EVEX instruction is ours
# (Unicorn rejects most of them, but decodes a few, like kmov, as something else)
UNICORN_VEX = {"andn", "bextr", "blsi", "blsmsk", "blsr", "bzhi", "mulx", "pdep", "pext", "rorx",
               "sarx", "shlx", "shrx"}

# ---- CPU profiles ---------------------------------------------------------------------

FEATURES = ["sse3", "ssse3", "sse4.1", "sse4.2", "popcnt", "avx", "f16c", "fma", "avx2", "bmi1",
            "bmi2", "lzcnt", "avx512f", "avx512dq", "avx512cd", "avx512bw", "avx512vl",
            "avx512vbmi", "avx512vpopcntdq", "avx512bitalg"]
_BASE = {"sse3", "ssse3", "sse4.1", "sse4.2", "popcnt", "bmi1", "bmi2", "lzcnt"}
PROFILES = {
    "sse4.2": _BASE,                                         # ~2008-2010: no AVX at all
    "avx": _BASE | {"avx"},                                  # ~2011 (Sandy Bridge)
    "avx2": _BASE | {"avx", "f16c", "fma", "avx2"},          # ~2013-today (Haswell...)
    "avx512": set(FEATURES) - {"f16c"},                      # servers, Ice Lake, Zen 4
}
DEFAULT_PROFILE = "avx512"


class _Fault(Exception):
    """The instruction faults: kind is "read", "write" or "gp" (misaligned)."""

    def __init__(self, kind: str, addr: int, message: str = ""):
        super().__init__(message)
        self.kind, self.addr, self.message = kind, addr, message


class Unsupported(Exception):
    pass


_DT = {1: np.uint8, 2: np.uint16, 4: np.uint32, 8: np.uint64}
_ST = {1: np.int8, 2: np.int16, 4: np.int32, 8: np.int64}
_FT = {4: np.float32, 8: np.float64}
_SUFFIX = {"b": 1, "w": 2, "d": 4, "q": 8}


def _bits(data: bytes, size: int, signed=False) -> np.ndarray:
    return np.frombuffer(data, (_ST if signed else _DT)[size]).copy()


def _floats(data: bytes, size: int) -> np.ndarray:
    return np.frombuffer(data, _FT[size]).copy()


def _sat(values, size: int, signed: bool) -> np.ndarray:
    lo, hi = ((-(1 << (8 * size - 1)), (1 << (8 * size - 1)) - 1) if signed
              else (0, (1 << (8 * size)) - 1))
    return np.clip(values, lo, hi).astype((_ST if signed else _DT)[size])


class Operand:
    __slots__ = ("kind", "reg", "size", "mem", "imm", "name")

    def __init__(self, kind, size, reg=None, mem=None, imm=None, name=""):
        self.kind, self.size, self.reg, self.mem, self.imm, self.name = kind, size, reg, mem, imm, name


class Decoded:
    """An instruction, decoded once per address."""
    __slots__ = ("mnemonic", "size", "ops", "mask", "zero", "bcast", "text", "addr", "evex", "vex")

    def __init__(self, ins):
        self.mnemonic, self.size, self.addr = ins.mnemonic, ins.size, ins.address
        self.text = f"{ins.mnemonic} {ins.op_str}".strip()
        raw = bytes(ins.bytes)
        i = 0
        while i < len(raw) and raw[i] in (0x66, 0xF2, 0xF3, 0x2E, 0x3E, 0x26, 0x64, 0x65, 0x36,
                                          0x67, 0xF0):
            i += 1
        self.evex = i < len(raw) and raw[i] == 0x62
        self.vex = i < len(raw) and raw[i] in (0xC4, 0xC5)
        self.zero = "{z}" in ins.op_str
        self.bcast = "{1to" in ins.op_str
        self.mask = None
        self.ops: list[Operand] = []
        for op in ins.operands:
            if op.type == CS_OP_REG:
                name = ins.reg_name(op.reg)
                if re.fullmatch(r"k[0-7]", name) and self.ops and len(self.ops) == 1 \
                        and f"{{{name}}}" in ins.op_str:
                    self.mask = int(name[1])            # the {kN} after the destination
                    continue
                self.ops.append(Operand("reg", op.size, reg=name, name=name))
            elif op.type == CS_OP_MEM:
                m = op.mem
                self.ops.append(Operand("mem", op.size, mem=(
                    ins.reg_name(m.base) if m.base else None,
                    ins.reg_name(m.index) if m.index else None, m.scale, m.disp,
                    ins.reg_name(op.mem.segment) if op.mem.segment else None)))
            elif op.type == CS_OP_IMM:
                self.ops.append(Operand("imm", op.size, imm=op.imm & MASK64))


def _vec_index(name: str) -> tuple[int, int] | None:
    """xmm3 -> (3, 16); ymm12 -> (12, 32); zmm30 -> (30, 64)."""
    m = re.fullmatch(r"([xyz])mm(\d+)", name)
    if not m:
        return None
    return int(m.group(2)), {"x": 16, "y": 32, "z": 64}[m.group(1)]


# vcmpps predicates (imm 0-31): name -> (relation, result when unordered)
_FCMP = {}
for _i, _n in enumerate(["eq", "lt", "le", "unord", "neq", "nlt", "nle", "ord", "eq_uq", "nge",
                         "ngt", "false", "neq_oq", "ge", "gt", "true", "eq_os", "lt_oq", "le_oq",
                         "unord_s", "neq_us", "nlt_uq", "nle_uq", "ord_s", "eq_us", "nge_uq",
                         "ngt_uq", "false_os", "neq_os", "ge_oq", "gt_oq", "true_us"]):
    _FCMP[_n] = _i
_FCMP.update({"eq_oq": 0, "lt_os": 1, "le_os": 2, "unord_q": 3, "neq_uq": 4, "nlt_us": 5,
              "nle_us": 6, "ord_q": 7, "nge_us": 9, "ngt_us": 10, "false_oq": 11, "ge_os": 13,
              "gt_os": 14, "true_uq": 15})
_FREL = ["eq", "lt", "le", "unord", "neq", "nlt", "nle", "ord"] * 2
_FREL[8:16] = ["eq", "nge", "ngt", "false", "neq", "ge", "gt", "true"]
_FUNORD = [False, False, False, True, True, True, True, False,
           True, True, True, False, False, False, False, True]
# vpcmp predicates (imm 0-7)
_ICMP = {"eq": 0, "lt": 1, "le": 2, "false": 3, "neq": 4, "nlt": 5, "nle": 6, "true": 7}


class Vector:
    """The vector unit of one Machine."""

    def __init__(self, machine, profile: str = DEFAULT_PROFILE):
        if profile not in PROFILES:
            raise ValueError(f"unknown CPU profile {profile!r} (one of {', '.join(PROFILES)})")
        self.m = machine
        self.profile = profile
        self.features = PROFILES[profile]
        self.md = Cs(CS_ARCH_X86, CS_MODE_64)
        self.md.detail = True
        self.cache: dict[int, Decoded | None] = {}
        self.kregs: dict[int, list[int]] = {}            # tid -> k0..k7
        self.dirty_upper = False                         # a VEX.256/EVEX op ran since vzeroupper
        self.emulated = 0

    # ---- registers ------------------------------------------------------------------

    @property
    def uc(self):
        return self.m.uc

    @property
    def k(self) -> list[int]:
        tid = self.m.thread.tid
        ks = self.kregs.get(tid)
        if ks is None:
            ks = self.kregs[tid] = [0] * 8
        return ks

    def set_k(self, n: int, value: int) -> None:
        ks = self.k
        old = ks[n]
        f = self.m._frame
        if f is not None:
            f.undo.append(lambda: ks.__setitem__(n, old))
        ks[n] = value & MASK64

    def vget(self, n: int) -> bytes:
        return (self.uc.reg_read(getattr(X, f"UC_X86_REG_ZMM{n}")) & ((1 << 512) - 1)).to_bytes(64, "little")

    def vset(self, n: int, data: bytes) -> None:
        self.uc.reg_write(getattr(X, f"UC_X86_REG_ZMM{n}"), int.from_bytes(data, "little"))

    def gpr(self, name: str) -> int:
        return self.uc.reg_read(getattr(X, f"UC_X86_REG_{name.upper()}")) & MASK64

    def set_gpr(self, name: str, value: int, size: int) -> None:
        from .perf import _family
        full = _family(name)
        if size == 4:
            value &= 0xFFFFFFFF                        # 32-bit writes zero the upper half
        elif size < 4:
            old = self.gpr(full)
            m = (1 << (8 * size)) - 1
            value = (old & ~m) | (value & m)
        self.uc.reg_write(getattr(X, f"UC_X86_REG_{full.upper()}"), value & MASK64)

    def set_flags(self, **bits: int) -> None:
        """Set ZF/CF/... and clear the arithmetic flags not named (as vptest & co. do)."""
        pos = {"CF": 0, "PF": 2, "AF": 4, "ZF": 6, "SF": 7, "OF": 11}
        f = self.gpr("rflags")
        for name, bit in pos.items():
            f &= ~(1 << bit)
            if bits.get(name):
                f |= 1 << bit
        self.uc.reg_write(X.UC_X86_REG_RFLAGS, f)

    # ---- memory ---------------------------------------------------------------------

    def address(self, d: Decoded, op: Operand) -> int:
        base, index, scale, disp, seg = op.mem
        a = disp
        if base == "rip":
            a += d.addr + d.size
        elif base:
            a += self.gpr(base)
        if index and not _vec_index(index):
            a += self.gpr(index) * scale
        if seg == "fs":
            a += self.uc.reg_read(X.UC_X86_REG_FS_BASE)
        elif seg == "gs":
            a += self.uc.reg_read(X.UC_X86_REG_GS_BASE)
        return a & MASK64

    def read(self, addr: int, size: int) -> bytes:
        m = self.m
        if not m.readable(addr, size):
            bad = addr + m.readable_prefix(addr, size)
            raise _Fault("read", bad)
        m.vector_access("r", addr, size)
        return m.read(addr, size)

    def write(self, addr: int, data: bytes) -> None:
        m = self.m
        if not m.writable(addr, len(data)):
            for i in range(len(data)):
                if not m.writable(addr + i, 1):
                    raise _Fault("write", addr + i)
        m.vector_access("w", addr, len(data), data)
        if m.state != "fault":
            m.write(addr, data)

    def check_writable(self, addr: int, size: int) -> None:
        if not self.m.writable(addr, size):
            for i in range(size):
                if not self.m.writable(addr + i, 1):
                    raise _Fault("write", addr + i)

    # ---- operands -------------------------------------------------------------------

    def vl(self, d: Decoded) -> int:
        """The vector length: the largest vector register (or memory) operand."""
        sizes = [op.size for op in d.ops if op.kind == "reg" and _vec_index(op.reg)]
        return max(sizes) if sizes else 16

    def active(self, d: Decoded, count: int) -> np.ndarray | None:
        """Which elements the {k} mask enables (None: no mask, all of them)."""
        if d.mask is None or d.mask == 0:
            return None
        k = self.k[d.mask]
        return np.array([(k >> i) & 1 == 1 for i in range(count)])

    def value(self, d: Decoded, op: Operand, size: int, esize: int = 0,
              act: np.ndarray | None = None) -> bytes:
        """`size` bytes of a source operand. Memory: a broadcast element when {1toN}; with
        a mask, only the enabled elements are read (masked-off ones can't fault)."""
        if op.kind == "reg":
            v = _vec_index(op.reg)
            if v:
                return self.vget(v[0])[:size]
            if re.fullmatch(r"k[0-7]", op.reg):
                return (self.k[int(op.reg[1])] & ((1 << (8 * size)) - 1)).to_bytes(size, "little")
            return (self.gpr(op.reg) & ((1 << (8 * min(size, 8))) - 1)).to_bytes(size, "little")
        if op.kind == "imm":
            return (op.imm & ((1 << (8 * size)) - 1)).to_bytes(size, "little")
        addr = self.address(d, op)
        if d.bcast and esize:
            return self.read(addr, esize) * (size // esize)
        if act is not None and esize and not act.all():
            out = bytearray(size)
            for i, on in enumerate(act):
                if on and i * esize < size:
                    out[i * esize:(i + 1) * esize] = self.read(addr + i * esize, esize)
            return bytes(out)
        return self.read(addr, size)

    def put(self, d: Decoded, op: Operand, data: bytes, esize: int = 0,
            act: np.ndarray | None = None, vl: int | None = None) -> None:
        """Write a result. Registers: masked-off elements keep their old value ({k}) or
        become 0 ({k}{z}); everything above the vector length becomes 0. Memory: only
        enabled elements are written."""
        if op.kind == "mem":
            addr = self.address(d, op)
            if act is not None and esize and not act.all():
                for i, on in enumerate(act):
                    if on and i * esize < len(data):
                        self.check_writable(addr + i * esize, esize)
                for i, on in enumerate(act):
                    if on and i * esize < len(data):
                        self.write(addr + i * esize, data[i * esize:(i + 1) * esize])
                return
            self.write(addr, data)
            return
        v = _vec_index(op.reg)
        if v is None:
            if re.fullmatch(r"k[0-7]", op.reg):
                self.set_k(int(op.reg[1]), int.from_bytes(data[:8], "little"))
                return
            self.set_gpr(op.reg, int.from_bytes(data[:8], "little"), op.size)
            return
        n, size = v
        vl = vl or size
        data = data[:vl]
        if act is not None and esize:
            old = self.vget(n)
            out = bytearray(data)
            for i, on in enumerate(act):
                if not on and i * esize < vl:
                    out[i * esize:(i + 1) * esize] = (bytes(esize) if d.zero
                                                      else old[i * esize:(i + 1) * esize])
            data = bytes(out)
        if vl > 16:
            self.dirty_upper = True
        self.vset(n, data + bytes(64 - len(data)))

    # ---- entry points ----------------------------------------------------------------

    def decode(self, addr: int) -> Decoded | None:
        if addr in self.cache:
            return self.cache[addr]
        code = self.m.read(addr, 15) if self.m.readable(addr, 15) else \
            self.m.read(addr, max(self.m.readable_prefix(addr, 15), 0))
        ins = next(self.md.disasm(code, addr), None)
        d = self.cache[addr] = Decoded(ins) if ins is not None else None
        return d

    def needs(self, d: Decoded) -> str | None:
        """The CPU feature this instruction needs, if the profile lacks it."""
        mn = d.mnemonic
        if d.evex or mn.startswith("k"):
            if "avx512f" not in self.features:
                return "AVX-512"
            return None
        if mn.startswith(("vfmadd", "vfmsub", "vfnmadd", "vfnmsub")):
            return None if "fma" in self.features else "FMA"
        if "avx" not in self.features:
            return "AVX"
        vl = self.vl(d)
        avx2_only = mn.startswith(("vpgather", "vgather", "vpbroadcast", "vperm2i128", "vpermd",
                                   "vpermq", "vpermps", "vpermpd", "vinserti128", "vextracti128",
                                   "vpsllv", "vpsrlv", "vpsrav", "vpmaskmov", "vpblendd",
                                   "vbroadcasti128"))
        integer_256 = vl == 32 and (mn.startswith("vp") or mn in ("vmovntdqa",))
        if (avx2_only or integer_256) and "avx2" not in self.features:
            return "AVX2"
        return None

    def on_invalid(self) -> bool:
        """Unicorn found an instruction it can't run at the current rip. Emulate it and
        return True, or return False for a genuine #UD."""
        d = self.decode(self.m.pc)
        if d is None:
            return False
        return self.emulate(d)

    def emulate(self, d: Decoded) -> bool:
        """Carry out d (at rip) and move rip past it; False if it faults (the fault is
        pending on the machine)."""
        m = self.m
        rip = d.addr
        lacking = self.needs(d) if (d.mnemonic.startswith(("v", "k")) or d.evex) else "?"
        if lacking == "?":
            return False
        if lacking:
            m._pending_fault = (4, f"illegal instruction (#UD): `{d.text}` needs {lacking}, and "
                                f"this CPU (profile {self.profile}) doesn't have it", None)
            return False
        try:
            self.execute(d)
        except _Fault as f:
            m.vector_fault(f.kind, f.addr, f.message)
            return False
        except Unsupported as e:
            m._pending_fault = (4, f"illegal instruction: `{d.text}`: {e}" if str(e) else
                                f"illegal instruction: `{d.text}` isn't implemented by the "
                                "game's vector emulator (ring/simd.py) yet; tell us, or use "
                                "another instruction", None)
            return False
        self.emulated += 1
        if m.state == "fault":                      # the checked heap stopped it
            return True
        m.uc.reg_write(X.UC_X86_REG_RIP, rip + d.size)
        return True

    # ---- cpuid / xgetbv --------------------------------------------------------------

    def cpuid(self, leaf: int, sub: int) -> tuple[int, int, int, int]:
        f = self.features
        bit = lambda name, n: (1 << n) if name in f else 0          # noqa: E731
        if leaf == 0:
            vendor = b"RingZeroCore"
            ebx, edx, ecx = struct.unpack("<III", vendor)
            return 0xD, ebx, ecx, edx
        if leaf == 1:
            ecx = (bit("sse3", 0) | (1 << 1) | bit("ssse3", 9) | bit("fma", 12) | (1 << 13)
                   | bit("sse4.1", 19) | bit("sse4.2", 20) | (1 << 22) | bit("popcnt", 23)
                   | (1 << 26) | (1 << 27) | bit("avx", 28) | bit("f16c", 29))
            edx = (1 << 0) | (1 << 4) | (1 << 8) | (1 << 15) | (1 << 23) | (1 << 24) \
                | (1 << 25) | (1 << 26)
            return 0x000906EA, 0x00000800, ecx, edx
        if leaf == 7 and sub == 0:
            ebx = (bit("bmi1", 3) | bit("avx2", 5) | bit("bmi2", 8) | bit("avx512f", 16)
                   | bit("avx512dq", 17) | bit("avx512cd", 28) | bit("avx512bw", 30)
                   | bit("avx512vl", 31))
            ecx = bit("avx512vbmi", 1) | bit("avx512bitalg", 12) | bit("avx512vpopcntdq", 14)
            return 0, ebx, ecx, 0
        if leaf == 0xD and sub == 0:
            xcr0 = self.xcr0()
            return xcr0, 2688 if xcr0 & 0xE0 else 832, 2688, 0
        if leaf == 0x80000000:
            return 0x80000004, 0, 0, 0
        if leaf == 0x80000001:
            return 0, 0, bit("lzcnt", 5) | 1, (1 << 29) | (1 << 11) | (1 << 20)
        if 0x80000002 <= leaf <= 0x80000004:
            brand = f"NASM Adventures model CPU ({self.profile})".encode().ljust(48, b"\0")
            chunk = brand[(leaf - 0x80000002) * 16:][:16]
            return struct.unpack("<IIII", chunk)
        return 0, 0, 0, 0

    def xcr0(self) -> int:
        """Which register state the OS saves: x87|SSE, +AVX, +AVX-512 (opmask, zmm)."""
        if "avx512f" in self.features:
            return 0xE7
        return 0x7 if "avx" in self.features else 0x3

    # ---- the instructions -------------------------------------------------------------

    def execute(self, d: Decoded) -> None:
        mn = d.mnemonic
        fn = _HANDLERS.get(mn)
        if fn is not None:
            fn(self, d)
            return
        for pattern, fn in _PATTERNS:
            mt = pattern.fullmatch(mn)
            if mt:
                fn(self, d, *mt.groups())
                return
        raise Unsupported("")


# =========================================================================================
# Handlers. Each takes (vector unit, decoded instruction[, regex groups]).

_HANDLERS: dict = {}
_PATTERNS: list = []


def handles(*names):
    def wrap(fn):
        for n in names:
            _HANDLERS[n] = fn
        return fn
    return wrap


def pattern(regex):
    def wrap(fn):
        _PATTERNS.append((re.compile(regex), fn))
        return fn
    return wrap


def _srcs(d: Decoded):
    """(destination, sources) with the mask removed."""
    return d.ops[0], d.ops[1:]


def _elementwise(v: Vector, d: Decoded, esize: int, fn, kind: str = "u") -> None:
    """dest = fn(src1, src2[, ...]) element by element; kind u/s/f picks the element type."""
    dst, srcs = _srcs(d)
    vl = v.vl(d)
    count = vl // esize
    act = v.active(d, count)
    conv = (lambda b: _floats(b, esize)) if kind == "f" else \
        (lambda b: _bits(b, esize, kind == "s"))
    args = [conv(v.value(d, s, vl, esize, act)) for s in srcs if s.kind != "imm"]
    imms = [s.imm for s in srcs if s.kind == "imm"]
    with np.errstate(all="ignore"):
        r = fn(*args, *imms)
    v.put(d, dst, np.asarray(r).astype(args[0].dtype if kind != "f" else _FT[esize]).tobytes(),
          esize, act, vl)


# ---- moves -----------------------------------------------------------------------------

def _move(v: Vector, d: Decoded, esize: int, aligned: bool) -> None:
    dst, (src,) = d.ops[0], d.ops[1:]
    vl = max(dst.size, src.size) if dst.kind == "reg" or src.kind == "reg" else 16
    vl = v.vl(d)
    act = v.active(d, vl // esize)
    for op in (dst, src):
        if aligned and op.kind == "mem":
            a = v.address(d, op)
            if a % vl:
                raise _Fault("gp", a, f"general protection fault: `{d.mnemonic}` needs a "
                             f"{vl}-byte aligned address, and {a:#x} isn't "
                             f"(use the unaligned form, or align the data)")
    v.put(d, dst, v.value(d, src, vl, esize, act), esize, act, vl)


@pattern(r"v(movdq|movap|movntdq|movntp|movntdqa)(a|u)?(8|16|32|64|s|d)?")
def _mov_vec(v, d, base, au, el):
    aligned = base in ("movap", "movntdq", "movntp", "movntdqa") or au == "a"
    esize = {"8": 1, "16": 2, "32": 4, "64": 8, "s": 4, "d": 8}.get(el or "", 4)
    _move(v, d, esize, aligned)


@handles("vmovups", "vmovupd", "vlddqu")
def _movu(v, d):
    _move(v, d, 4 if d.mnemonic.endswith("s") else 8, False)


@handles("vmovd", "vmovq")
def _movdq(v, d):
    size = 4 if d.mnemonic == "vmovd" else 8
    dst, src = d.ops
    data = v.value(d, src, size)
    if dst.kind == "reg" and _vec_index(dst.reg):
        v.put(d, dst, data + bytes(16 - size), vl=16)
    else:
        v.put(d, dst, data)


@handles("vmovss", "vmovsd")
def _movs(v, d):
    size = 4 if d.mnemonic == "vmovss" else 8
    act = v.active(d, 1)
    if len(d.ops) == 3:                         # reg, reg, reg: merge the low element
        dst, a, b = d.ops
        data = v.value(d, b, size) + v.value(d, a, 16)[size:]
        v.put(d, dst, data, size, act, 16)
        return
    dst, src = d.ops
    data = v.value(d, src, size, size, act)
    if dst.kind == "mem":
        v.put(d, dst, data, size, act)
    else:
        v.put(d, dst, data + bytes(16 - size), size, act, 16)


@handles("vzeroupper", "vzeroall")
def _vzero(v, d):
    for n in range(16):
        keep = v.vget(n)[:16] if d.mnemonic == "vzeroupper" else bytes(16)
        v.vset(n, keep + bytes(48))
    v.dirty_upper = False


# ---- broadcasts, inserts, extracts -----------------------------------------------------

@pattern(r"vp?broadcast(b|w|d|q|ss|sd|i128|f128|i32x4|f32x4|i64x4|f64x4|i32x8|f32x8|i64x2|f64x2)")
def _broadcast(v, d, what):
    dst, src = d.ops
    vl = dst.size
    esize = {"b": 1, "w": 2, "d": 4, "q": 8, "ss": 4, "sd": 8, "i128": 16, "f128": 16, "i32x4": 16,
             "f32x4": 16, "i64x2": 16, "f64x2": 16, "i64x4": 32, "f64x4": 32, "i32x8": 32,
             "f32x8": 32}[what]
    el = v.value(d, src, esize)
    mask_el = esize if esize <= 8 else 8 if "64" in what else 4
    v.put(d, dst, el * (vl // esize), mask_el, v.active(d, vl // mask_el), vl)


@pattern(r"vinsert[if](128|32x4|64x2|64x4|32x8)")
def _insert(v, d, what):
    dst, a, b, imm = d.ops
    vl, part = dst.size, b.size if b.kind == "reg" else {"128": 16, "32x4": 16, "64x2": 16,
                                                          "64x4": 32, "32x8": 32}[what]
    data = bytearray(v.value(d, a, vl))
    pos = (imm.imm % (vl // part)) * part
    data[pos:pos + part] = v.value(d, b, part)
    esize = 8 if "64" in what else 4
    v.put(d, dst, bytes(data), esize, v.active(d, vl // esize), vl)


@pattern(r"vextract[if](128|32x4|64x2|64x4|32x8)")
def _extract(v, d, what):
    dst, src, imm = d.ops
    part = 16 if what in ("128", "32x4", "64x2") else 32
    data = v.value(d, src, src.size)
    pos = (imm.imm % (src.size // part)) * part
    esize = 8 if "64" in what else 4
    v.put(d, dst, data[pos:pos + part], esize, v.active(d, part // esize), part)


@pattern(r"vperm2[if]128")
def _perm2x128(v, d):
    dst, a, b, imm = d.ops
    lanes = v.value(d, a, 32) + v.value(d, b, 32)
    out = b""
    for sel in (imm.imm & 0xF, imm.imm >> 4):
        out += bytes(16) if sel & 8 else lanes[(sel & 3) * 16:(sel & 3) * 16 + 16]
    v.put(d, dst, out, vl=32)


@pattern(r"vpinsr(b|w|d|q)")
def _pinsr(v, d, s):
    dst, a, b, imm = d.ops
    size = _SUFFIX[s]
    data = bytearray(v.value(d, a, 16))
    pos = (imm.imm % (16 // size)) * size
    data[pos:pos + size] = v.value(d, b, size)
    v.put(d, dst, bytes(data), vl=16)


@pattern(r"vpextr(b|w|d|q)|vextract(ps)")
def _pextr(v, d, s, ps):
    dst, src, imm = d.ops
    size = 4 if ps else _SUFFIX[s]
    data = v.value(d, src, 16)
    pos = (imm.imm % (16 // size)) * size
    val = data[pos:pos + size]
    if dst.kind == "reg":
        v.set_gpr(dst.reg, int.from_bytes(val, "little"), max(dst.size, 4))
    else:
        v.put(d, dst, val)


# ---- integer arithmetic ------------------------------------------------------------------

_INT_BIN = {
    "add": (lambda a, b: a + b, "u"), "sub": (lambda a, b: a - b, "u"),
    "mull": (lambda a, b: a * b, "u"),
    "and": (lambda a, b: a & b, "u"), "or": (lambda a, b: a | b, "u"),
    "xor": (lambda a, b: a ^ b, "u"), "andn": (lambda a, b: ~a & b, "u"),
    "minu": (np.minimum, "u"), "maxu": (np.maximum, "u"),
    "mins": (np.minimum, "s"), "maxs": (np.maximum, "s"),
    "avg": (lambda a, b: ((a.astype(np.uint64) + b + 1) >> 1), "u"),
    "sllv": (lambda a, b: np.where(b < a.dtype.itemsize * 8, a << (b % (a.dtype.itemsize * 8)), 0), "u"),
    "srlv": (lambda a, b: np.where(b < a.dtype.itemsize * 8, a >> (b % (a.dtype.itemsize * 8)), 0), "u"),
}


@pattern(r"vp(add|sub|mull|minu|maxu|mins|maxs|avg|sllv|srlv)(b|w|d|q)")
def _int_bin(v, d, op, s):
    fn, kind = _INT_BIN[op]
    _elementwise(v, d, _SUFFIX[s], fn, kind)


@pattern(r"vp(and|or|xor|andn)(d|q)?")
def _logic(v, d, op, s):
    _elementwise(v, d, _SUFFIX.get(s or "q", 8), _INT_BIN[op][0], "u")


@pattern(r"v(and|or|xor|andn)p(s|d)")
def _flogic(v, d, op, s):
    _elementwise(v, d, 4 if s == "s" else 8, _INT_BIN[op][0], "u")


@pattern(r"vpadd(u?)s(b|w)")
def _adds(v, d, u, s):
    size = _SUFFIX[s]
    _elementwise(v, d, size, lambda a, b: _sat(a.astype(np.int64) + b, size, not u), "u" if u else "s")


@pattern(r"vpsub(u?)s(b|w)")
def _subs(v, d, u, s):
    size = _SUFFIX[s]
    _elementwise(v, d, size, lambda a, b: _sat(a.astype(np.int64) - b, size, not u), "u" if u else "s")


@pattern(r"vpsrav(w|d|q)")
def _srav(v, d, s):
    size = _SUFFIX[s]
    bits = 8 * size
    _elementwise(v, d, size, lambda a, b: a >> np.minimum(b.astype(np.uint64), bits - 1).astype(a.dtype), "s")


@handles("vpmulhw", "vpmulhuw", "vpmulhrsw")
def _mulh(v, d):
    if d.mnemonic == "vpmulhrsw":
        _elementwise(v, d, 2, lambda a, b: ((a.astype(np.int32) * b >> 14) + 1) >> 1, "s")
    else:
        signed = d.mnemonic == "vpmulhw"
        _elementwise(v, d, 2, lambda a, b: (a.astype(np.int32 if signed else np.uint32) * b) >> 16,
                     "s" if signed else "u")


@handles("vpmuludq", "vpmuldq")
def _muldq(v, d):
    signed = d.mnemonic == "vpmuldq"

    def fn(a, b):
        lo = lambda x: (x & 0xFFFFFFFF).astype(np.int64) if not signed else \
            ((x & 0xFFFFFFFF).astype(np.int64) ^ 0x80000000) - 0x80000000  # noqa: E731
        return (lo(a) * lo(b)).astype(np.uint64)
    _elementwise(v, d, 8, fn, "u")


@handles("vpmullq")
def _mullq(v, d):
    _elementwise(v, d, 8, lambda a, b: a * b, "u")


@handles("vpmaddwd")
def _maddwd(v, d):
    dst, a, b = d.ops
    vl = v.vl(d)
    x = _bits(v.value(d, a, vl), 2, True).astype(np.int32)
    y = _bits(v.value(d, b, vl), 2, True).astype(np.int32)
    p = x * y
    v.put(d, dst, (p[0::2] + p[1::2]).astype(np.int32).tobytes(), 4, v.active(d, vl // 4), vl)


@handles("vpmaddubsw")
def _maddubsw(v, d):
    dst, a, b = d.ops
    vl = v.vl(d)
    x = _bits(v.value(d, a, vl), 1).astype(np.int32)
    y = _bits(v.value(d, b, vl), 1, True).astype(np.int32)
    p = x * y
    v.put(d, dst, _sat(p[0::2] + p[1::2], 2, True).tobytes(), 2, v.active(d, vl // 2), vl)


@handles("vpsadbw")
def _sadbw(v, d):
    dst, a, b = d.ops
    vl = v.vl(d)
    x = _bits(v.value(d, a, vl), 1).astype(np.int64)
    y = _bits(v.value(d, b, vl), 1).astype(np.int64)
    s = np.abs(x - y).reshape(-1, 8).sum(axis=1).astype(np.uint64)
    v.put(d, dst, s.tobytes(), vl=vl)


@pattern(r"vpabs(b|w|d|q)")
def _abs(v, d, s):
    size = _SUFFIX[s]
    _elementwise(v, d, size, lambda a: np.abs(a).astype(_DT[size]), "s")


@pattern(r"vpsign(b|w|d)")
def _psign(v, d, s):
    _elementwise(v, d, _SUFFIX[s], lambda a, b: np.where(b < 0, -a, np.where(b == 0, 0, a)), "s")


@pattern(r"vp(lzcnt|opcnt)(b|w|d|q)")
def _count(v, d, op, s):
    size = _SUFFIX[s]
    if op == "lzcnt":
        fn = lambda a: np.array([8 * size - int(x).bit_length() for x in a])  # noqa: E731
    else:
        fn = lambda a: np.array([int(x).bit_count() for x in a])          # noqa: E731
    _elementwise(v, d, size, fn, "u")


@pattern(r"vpconflict(d|q)")
def _conflict(v, d, s):
    def fn(a):
        return np.array([sum(1 << j for j in range(i) if a[j] == a[i]) for i in range(len(a))])
    _elementwise(v, d, _SUFFIX[s], fn, "u")


@pattern(r"vpternlog(d|q)")
def _ternlog(v, d, s):
    def fn(a, b, c, imm):
        out = np.zeros_like(a)
        for bit in range(8):
            if imm >> bit & 1:
                ta = a if bit & 4 else ~a
                tb = b if bit & 2 else ~b
                tc = c if bit & 1 else ~c
                out |= ta & tb & tc
        return out
    dst, srcs = _srcs(d)
    vl = v.vl(d)
    esize = _SUFFIX[s]
    act = v.active(d, vl // esize)
    a = _bits(v.value(d, dst, vl), esize)
    b = _bits(v.value(d, srcs[0], vl), esize)
    c = _bits(v.value(d, srcs[1], vl, esize, act), esize)
    v.put(d, dst, fn(a, b, c, srcs[2].imm).tobytes(), esize, act, vl)


# ---- compares --------------------------------------------------------------------------

def _icompare(a, b, pred: int):
    return [a == b, a < b, a <= b, np.zeros_like(a, bool), a != b, a >= b, a > b,
            np.ones_like(a, bool)][pred]


def _to_mask(v: Vector, d: Decoded, dst: Operand, cond: np.ndarray) -> None:
    k = 0
    for i, c in enumerate(cond):
        if c:
            k |= 1 << i
    if d.mask:                                  # vpcmp k1{k2}: only where k2 allows
        k &= v.k[d.mask]
    v.set_k(int(dst.reg[1]), k)


def _cmp_into(v, d, esize, signed, pred):
    dst, srcs = _srcs(d)
    vl = max(op.size for op in srcs if op.kind == "reg" and _vec_index(op.reg))
    a = _bits(v.value(d, srcs[0], vl), esize, signed)
    b = _bits(v.value(d, srcs[1], vl, esize), esize, signed)
    cond = _icompare(a, b, pred)
    if dst.reg.startswith("k"):
        _to_mask(v, d, dst, cond)
    else:
        v.put(d, dst, np.where(cond, _DT[esize](~0 & ((1 << 8 * esize) - 1)), 0)
              .astype(_DT[esize]).tobytes(), vl=vl)


@pattern(r"vpcmp(eq|gt)(b|w|d|q)")
def _pcmp(v, d, op, s):
    _cmp_into(v, d, _SUFFIX[s], True, 0 if op == "eq" else 6)


@pattern(r"vpcmp(eq|lt|le|false|neq|nlt|nle|true)?(u?)(b|w|d|q)")
def _pcmp512(v, d, op, u, s):
    pred = _ICMP[op] if op else d.ops[-1].imm & 7
    if not op:
        d = _drop_imm(d)
    _cmp_into(v, d, _SUFFIX[s], not u, pred)


def _drop_imm(d: Decoded) -> Decoded:
    c = object.__new__(Decoded)
    for f in Decoded.__slots__:
        setattr(c, f, getattr(d, f))
    c.ops = d.ops[:-1]
    return c


@pattern(r"vptestn?m(b|w|d|q)")
def _ptestm(v, d, s):
    dst, a, b = d.ops
    esize = _SUFFIX[s]
    vl = a.size
    x = _bits(v.value(d, a, vl), esize) & _bits(v.value(d, b, vl, esize), esize)
    _to_mask(v, d, dst, (x == 0) if "testnm" in d.mnemonic else (x != 0))


def _fcompare(a, b, pred: int):
    unord = np.isnan(a) | np.isnan(b)
    with np.errstate(all="ignore"):
        ordered = {"eq": a == b, "lt": a < b, "le": a <= b, "unord": np.zeros_like(unord),
                   "neq": a != b, "nlt": a >= b, "nle": a > b, "ord": np.ones_like(unord),
                   "nge": a < b, "ngt": a <= b, "false": np.zeros_like(unord), "ge": a >= b,
                   "gt": a > b, "true": np.ones_like(unord)}[_FREL[pred & 15]]
    return np.where(unord, _FUNORD[pred & 15], ordered)


@pattern(r"vcmp(\w*?)(ps|pd|ss|sd)")
def _fcmp(v, d, name, s):
    if name:
        if name not in _FCMP:
            raise Unsupported("")
        pred = _FCMP[name]
    else:
        pred = d.ops[-1].imm & 31
        d = _drop_imm(d)
    esize = 4 if s[1] == "s" else 8
    dst, srcs = _srcs(d)
    scalar = s[0] == "s"
    vl = 16 if scalar else max(op.size for op in srcs if op.kind == "reg")
    a = _floats(v.value(d, srcs[0], vl), esize)
    b = _floats(v.value(d, srcs[1], esize if scalar else vl, esize) + bytes(vl), esize)[:len(a)]
    cond = _fcompare(a, b, pred)
    if scalar:
        cond = cond[:1]
    if dst.reg.startswith("k"):
        _to_mask(v, d, dst, cond)
        return
    full = (1 << 8 * esize) - 1
    out = np.where(cond, _DT[esize](full), 0).astype(_DT[esize]).tobytes()
    if scalar:
        out = out[:esize] + v.value(d, srcs[0], 16)[esize:]
    v.put(d, dst, out, vl=vl)


@pattern(r"v(u?)comis(s|d)")
def _comis(v, d, u, s):
    esize = 4 if s == "s" else 8
    a, b = d.ops
    x = _floats(v.value(d, a, esize), esize)[0]
    y = _floats(v.value(d, b, esize), esize)[0]
    if np.isnan(x) or np.isnan(y):
        v.set_flags(ZF=1, PF=1, CF=1)
    elif x < y:
        v.set_flags(CF=1)
    elif x == y:
        v.set_flags(ZF=1)
    else:
        v.set_flags()


@pattern(r"vptest|vtestp(s|d)")
def _ptest(v, d, s=None):
    a, b = d.ops
    vl = a.size
    x = int.from_bytes(v.value(d, a, vl), "little")
    y = int.from_bytes(v.value(d, b, vl), "little")
    if s:                                        # vtestps/pd: only the sign bits
        esize = 4 if s == "s" else 8
        sign = sum(1 << (8 * esize * (i + 1) - 1) for i in range(vl // esize))
        x, y = x & sign, y & sign
    full = (1 << 8 * vl) - 1
    v.set_flags(ZF=int(x & y == 0), CF=int((~x & full) & y == 0))


@handles("vpmovmskb", "vmovmskps", "vmovmskpd")
def _movmsk(v, d):
    dst, src = d.ops
    esize = {"vpmovmskb": 1, "vmovmskps": 4, "vmovmskpd": 8}[d.mnemonic]
    data = v.value(d, src, src.size)
    bits = 0
    for i in range(src.size // esize):
        if data[(i + 1) * esize - 1] & 0x80:
            bits |= 1 << i
    v.set_gpr(dst.reg, bits, max(dst.size, 4))


@pattern(r"vpmov(b|w|d|q)2m")
def _mov2m(v, d, s):
    dst, src = d.ops
    esize = _SUFFIX[s]
    data = v.value(d, src, src.size)
    _to_mask(v, d, dst, np.array([data[(i + 1) * esize - 1] & 0x80 != 0
                                  for i in range(src.size // esize)]))


@pattern(r"vpmovm2(b|w|d|q)")
def _movm2(v, d, s):
    dst, src = d.ops
    esize = _SUFFIX[s]
    k = v.k[int(src.reg[1])]
    out = b"".join((b"\xff" if k >> i & 1 else b"\0") * esize for i in range(dst.size // esize))
    v.put(d, dst, out, vl=dst.size)


# ---- shifts ----------------------------------------------------------------------------

@pattern(r"vps(ll|rl|ra)(w|d|q)")
def _shift(v, d, kind, s):
    esize = _SUFFIX[s]
    bits = 8 * esize
    dst, srcs = _srcs(d)
    vl = dst.size
    act = v.active(d, vl // esize)
    a = _bits(v.value(d, srcs[0], vl, esize, act), esize, kind == "ra")
    if srcs[1].kind == "imm":
        n = srcs[1].imm & 0xFF
    else:                                       # the count is the low 64 bits of an xmm
        n = int.from_bytes(v.value(d, srcs[1], 16)[:8], "little")
    if n >= bits:
        r = (a >> (bits - 1)) if kind == "ra" else np.zeros_like(a)
    else:
        r = a << n if kind == "ll" else a >> n
    v.put(d, dst, r.astype(a.dtype).tobytes(), esize, act, vl)


@pattern(r"vp(s|b)(ll|rl)dq")
def _byteshift(v, d, _p, kind):
    dst, src, imm = d.ops
    vl = dst.size
    data = v.value(d, src, vl)
    n = min(imm.imm, 16)
    out = b""
    for lane in range(vl // 16):
        x = data[lane * 16:lane * 16 + 16]
        out += (bytes(n) + x)[:16] if kind == "ll" else (x + bytes(n))[n:n + 16]
    v.put(d, dst, out, vl=vl)


@pattern(r"vpro(l|r)(v?)(d|q)")
def _rotate(v, d, lr, var, s):
    esize = _SUFFIX[s]
    bits = 8 * esize

    def fn(a, b):
        n = (b % bits).astype(a.dtype) if var else a.dtype.type(b % bits)
        if lr == "r":
            n = (bits - n) % bits
        return (a << n) | (a >> ((bits - n) % bits)) if np.any(n) else a
    _elementwise(v, d, esize, fn, "u")


@pattern(r"v(p)?alignr|valign(d|q)")
def _alignr(v, d, p=None, s=None):
    dst, a, b, imm = d.ops
    vl = dst.size
    x, y = v.value(d, a, vl), v.value(d, b, vl)
    if s:                                       # valignd/q: across the whole vector
        esize = _SUFFIX[s]
        n = (imm.imm % (vl // esize)) * esize
        cat = y + x
        v.put(d, dst, cat[n:n + vl], esize, v.active(d, vl // esize), vl)
        return
    out = b""
    for lane in range(vl // 16):
        cat = y[lane * 16:lane * 16 + 16] + x[lane * 16:lane * 16 + 16] + bytes(32)
        out += cat[imm.imm:imm.imm + 16]
    v.put(d, dst, out, 1, v.active(d, vl), vl)


# ---- shuffles and permutes -------------------------------------------------------------

@handles("vpshufb")
def _pshufb(v, d):
    dst, a, b = d.ops
    vl = dst.size
    x, ctl = v.value(d, a, vl), v.value(d, b, vl)
    out = bytearray(vl)
    for i in range(vl):
        c = ctl[i]
        lane = i & ~15
        out[i] = 0 if c & 0x80 else x[lane + (c & 15)]
    v.put(d, dst, bytes(out), 1, v.active(d, vl), vl)


@pattern(r"vp?shuf(d|ps|pd|lw|hw)")
def _shuf(v, d, s):
    if s in ("ps", "pd"):
        dst, a, b, imm = d.ops
    else:
        dst, a, imm = d.ops
        b = a
    vl = dst.size
    esize = 8 if s == "pd" else 2 if s in ("lw", "hw") else 4
    act = v.active(d, vl // esize)
    x = _bits(v.value(d, a, vl, esize), esize)
    y = _bits(v.value(d, b, vl, esize), esize) if b is not a else x
    out = x.copy()
    k = imm.imm
    for lane in range(vl // 16):
        base = lane * 16 // esize
        if s == "d":
            for i in range(4):
                out[base + i] = x[base + (k >> 2 * i & 3)]
        elif s == "ps":
            for i in range(4):
                out[base + i] = (x if i < 2 else y)[base + (k >> 2 * i & 3)]
        elif s == "pd":
            for i in range(2):
                out[base + i] = (x if i < 1 else y)[base + (k >> (lane * 2 + i) & 1)]
        else:
            off = 0 if s == "lw" else 4
            for i in range(4):
                out[base + off + i] = x[base + off + (k >> 2 * i & 3)]
    v.put(d, dst, out.tobytes(), esize, act, vl)


@pattern(r"vpermilp(s|d)")
def _permil(v, d, s):
    dst, a, b = d.ops
    esize = 4 if s == "s" else 8
    vl = dst.size
    x = _bits(v.value(d, a, vl), esize)
    per = 16 // esize
    if b.kind == "imm":
        sel = [(b.imm >> (2 * (i % 4) if esize == 4 else (i % 8))) & (per - 1) for i in range(len(x))]
    else:
        ctl = _bits(v.value(d, b, vl), esize)
        sel = [int(c >> (1 if esize == 8 else 0)) & (per - 1) for c in ctl]
    out = np.array([x[(i // per) * per + sel[i]] for i in range(len(x))], dtype=x.dtype)
    v.put(d, dst, out.tobytes(), esize, v.active(d, len(x)), vl)


@pattern(r"vperm(d|q|ps|pd|b|w)")
def _perm(v, d, s):
    esize = {"d": 4, "ps": 4, "q": 8, "pd": 8, "b": 1, "w": 2}[s]
    dst, srcs = _srcs(d)
    vl = dst.size
    act = v.active(d, vl // esize)
    n = vl // esize
    if srcs[-1].kind == "imm":                  # vpermq/vpermpd ymm, ymm/m, imm
        x = _bits(v.value(d, srcs[0], vl, esize, None), esize)
        k = srcs[1].imm
        idx = [(k >> 2 * (i % 4) & 3) + (i // 4) * 4 for i in range(n)]
    else:                                       # vpermd dst, index, table
        idx = _bits(v.value(d, srcs[0], vl), esize) % n
        x = _bits(v.value(d, srcs[1], vl, esize, None), esize)
    out = np.array([x[int(i)] for i in idx], dtype=x.dtype)
    v.put(d, dst, out.tobytes(), esize, act, vl)


@pattern(r"vperm(t|i)2(b|w|d|q|ps|pd)")
def _perm2(v, d, ti, s):
    esize = {"d": 4, "ps": 4, "q": 8, "pd": 8, "b": 1, "w": 2}[s]
    dst, (b, c) = d.ops[0], d.ops[1:]
    vl = dst.size
    n = vl // esize
    act = v.active(d, n)
    a = _bits(v.value(d, dst, vl), esize)
    bb = _bits(v.value(d, b, vl), esize)
    cc = _bits(v.value(d, c, vl, esize), esize)
    if ti == "t":                               # dst = table 1, b = indexes, c = table 2
        idx, t1, t2 = bb, a, cc
    else:                                       # dst = indexes, b = table 1, c = table 2
        idx, t1, t2 = a, bb, cc
    out = np.array([(t2 if int(i) & n else t1)[int(i) % n] for i in idx], dtype=a.dtype)
    v.put(d, dst, out.tobytes(), esize, act, vl)


@pattern(r"vpunpck(l|h)(bw|wd|dq|qdq)")
def _unpck(v, d, lh, s):
    esize = {"bw": 1, "wd": 2, "dq": 4, "qdq": 8}[s]
    dst, a, b = d.ops
    vl = dst.size
    x, y = v.value(d, a, vl), v.value(d, b, vl)
    out = b""
    for lane in range(vl // 16):
        base = lane * 16 + (0 if lh == "l" else 8)
        for i in range(8 // esize):
            o = base + i * esize
            out += x[o:o + esize] + y[o:o + esize]
    v.put(d, dst, out, esize, v.active(d, vl // esize), vl)


@pattern(r"vunpck(l|h)p(s|d)")
def _unpckps(v, d, lh, s):
    esize = 4 if s == "s" else 8
    dst, a, b = d.ops
    vl = dst.size
    x, y = v.value(d, a, vl), v.value(d, b, vl)
    out = b""
    for lane in range(vl // 16):
        base = lane * 16 + (0 if lh == "l" else 8)
        for i in range(8 // esize):
            o = base + i * esize
            out += x[o:o + esize] + y[o:o + esize]
    v.put(d, dst, out, esize, v.active(d, vl // esize), vl)


@pattern(r"vpack(ss|us)(wb|dw)")
def _pack(v, d, su, s):
    esize = 2 if s == "wb" else 4
    dst, a, b = d.ops
    vl = dst.size
    x = _bits(v.value(d, a, vl), esize, True).astype(np.int64)
    y = _bits(v.value(d, b, vl), esize, True).astype(np.int64)
    out = b""
    per = 16 // esize
    for lane in range(vl // 16):
        for src in (x, y):
            out += _sat(src[lane * per:(lane + 1) * per], esize // 2, su == "ss").tobytes()
    v.put(d, dst, out, vl=vl)


@pattern(r"vpmov(z|s)x(bw|bd|bq|wd|wq|dq)")
def _movx(v, d, zs, s):
    src_size, dst_size = _SUFFIX[s[0]], _SUFFIX[s[1]]
    dst, src = d.ops
    vl = dst.size
    n = vl // dst_size
    x = _bits(v.value(d, src, n * src_size), src_size, zs == "s")
    v.put(d, dst, x.astype((_ST if zs == "s" else _DT)[dst_size]).tobytes(), dst_size,
          v.active(d, n), vl)


@pattern(r"vpmov(s|us)?(db|dw|qb|qw|qd|wb)")
def _movdown(v, d, sat, s):
    src_size, dst_size = _SUFFIX[s[0]], _SUFFIX[s[1]]
    dst, src = d.ops
    n = src.size // src_size
    x = _bits(v.value(d, src, src.size), src_size, sat == "s")
    if sat == "us":
        r = np.minimum(x, (1 << 8 * dst_size) - 1).astype(_DT[dst_size])
    elif sat:
        r = _sat(x.astype(np.int64), dst_size, True)
    else:
        r = (x & ((1 << 8 * dst_size) - 1)).astype(_DT[dst_size])
    data = r.tobytes()
    act = v.active(d, n)
    if dst.kind == "mem":
        v.put(d, dst, data, dst_size, act)
    else:
        v.put(d, dst, data, dst_size, act, 16 if n * dst_size <= 16 else 32)


@pattern(r"vp?blend(d|w|ps|pd|vb|vps|vpd)")
def _blend(v, d, s):
    if s in ("vb", "vps", "vpd"):               # variable: the sign bit of each element
        dst, a, b, c = d.ops
        esize = {"vb": 1, "vps": 4, "vpd": 8}[s]
        vl = dst.size
        x, y, m = v.value(d, a, vl), v.value(d, b, vl), v.value(d, c, vl)
        out = b"".join(y[i:i + esize] if m[i + esize - 1] & 0x80 else x[i:i + esize]
                       for i in range(0, vl, esize))
        v.put(d, dst, out, vl=vl)
        return
    dst, a, b, imm = d.ops
    esize = {"d": 4, "w": 2, "ps": 4, "pd": 8}[s]
    vl = dst.size
    x, y = v.value(d, a, vl), v.value(d, b, vl)
    per = 8 if esize == 2 else 32
    out = b"".join(y[i * esize:(i + 1) * esize] if imm.imm >> (i % per) & 1 else
                   x[i * esize:(i + 1) * esize] for i in range(vl // esize))
    v.put(d, dst, out, vl=vl)


@pattern(r"vp?blendm(b|w|d|q|ps|pd)")
def _blendm(v, d, s):
    esize = {"b": 1, "w": 2, "d": 4, "q": 8, "ps": 4, "pd": 8}[s]
    dst, a, b = d.ops
    vl = dst.size
    n = vl // esize
    k = v.k[d.mask] if d.mask else (1 << n) - 1
    x, y = v.value(d, a, vl), v.value(d, b, vl, esize)
    out = b"".join(y[i * esize:(i + 1) * esize] if k >> i & 1 else
                   (bytes(esize) if d.zero else x[i * esize:(i + 1) * esize]) for i in range(n))
    v.vset(int(dst.reg[3:]), out + bytes(64 - vl))


@pattern(r"v(p?)compress(b|w|d|q|ps|pd)")
def _compress(v, d, _p, s):
    esize = {"b": 1, "w": 2, "d": 4, "q": 8, "ps": 4, "pd": 8}[s]
    dst, src = d.ops
    vl = src.size
    n = vl // esize
    k = v.k[d.mask] if d.mask else (1 << n) - 1
    data = v.value(d, src, vl)
    picked = b"".join(data[i * esize:(i + 1) * esize] for i in range(n) if k >> i & 1)
    if dst.kind == "mem":                       # only the picked elements are stored
        if picked:
            v.write(v.address(d, dst), picked)
        return
    old = v.vget(int(dst.reg[3:]))
    rest = bytes(vl - len(picked)) if d.zero else old[len(picked):vl]
    v.vset(int(dst.reg[3:]), picked + rest + bytes(64 - vl))


@pattern(r"v(p?)expand(b|w|d|q|ps|pd)")
def _expand(v, d, _p, s):
    esize = {"b": 1, "w": 2, "d": 4, "q": 8, "ps": 4, "pd": 8}[s]
    dst, src = d.ops
    vl = dst.size
    n = vl // esize
    k = v.k[d.mask] if d.mask else (1 << n) - 1
    count = bin(k & ((1 << n) - 1)).count("1")
    data = (v.read(v.address(d, src), count * esize) if src.kind == "mem"
            else v.value(d, src, vl))
    old = v.vget(int(dst.reg[3:]))
    out, j = bytearray(), 0
    for i in range(n):
        if k >> i & 1:
            out += data[j * esize:(j + 1) * esize]
            j += 1
        else:
            out += bytes(esize) if d.zero else old[i * esize:(i + 1) * esize]
    v.vset(int(dst.reg[3:]), bytes(out) + bytes(64 - vl))


# ---- gathers, scatters, masked moves -----------------------------------------------------

@pattern(r"v(p?)gather(d|q)(d|q|ps|pd)")
def _gather(v, d, _p, ix, el):
    isize = 4 if ix == "d" else 8
    esize = {"d": 4, "q": 8, "ps": 4, "pd": 8}[el]
    evex = d.mask is not None
    dst, mem = d.ops[0], d.ops[1]
    base, index, scale, disp, seg = mem.mem
    vidx, ivl = _vec_index(index)
    n = min(dst.size // esize, ivl // isize)
    idx = _bits(v.vget(vidx)[:n * isize], isize, True)
    if evex:
        k = v.k[d.mask]
        enabled = [k >> i & 1 for i in range(n)]
    else:
        mreg = _vec_index(d.ops[2].reg)[0]
        mbytes = v.vget(mreg)
        enabled = [mbytes[(i + 1) * esize - 1] >> 7 for i in range(n)]
    start = v.address(d, mem)
    out = bytearray(v.vget(_vec_index(dst.reg)[0])[:dst.size])
    for i in range(n):
        if enabled[i]:
            addr = (start + int(idx[i]) * scale) & MASK64
            out[i * esize:(i + 1) * esize] = v.read(addr, esize)
    vl = dst.size
    out[n * esize:] = bytes(vl - n * esize)
    v.vset(_vec_index(dst.reg)[0], bytes(out) + bytes(64 - vl))
    if vl > 16:
        v.dirty_upper = True
    if evex:
        v.set_k(d.mask, 0)                      # the mask is consumed
    else:
        v.vset(mreg, bytes(64))


@pattern(r"v(p?)scatter(d|q)(d|q|ps|pd)")
def _scatter(v, d, _p, ix, el):
    isize = 4 if ix == "d" else 8
    esize = {"d": 4, "q": 8, "ps": 4, "pd": 8}[el]
    mem, src = d.ops
    _b, index, scale, _disp, _seg = mem.mem
    vidx, ivl = _vec_index(index)
    n = min(src.size // esize, ivl // isize)
    idx = _bits(v.vget(vidx)[:n * isize], isize, True)
    data = v.value(d, src, src.size)
    k = v.k[d.mask] if d.mask else 0
    start = v.address(d, mem)
    for i in range(n):
        if k >> i & 1:
            v.write((start + int(idx[i]) * scale) & MASK64, data[i * esize:(i + 1) * esize])
    v.set_k(d.mask, 0)


@pattern(r"v(p?)maskmov(d|q|ps|pd)")
def _maskmov(v, d, _p, s):
    esize = {"d": 4, "q": 8, "ps": 4, "pd": 8}[s]
    a, b, c = d.ops
    if a.kind == "mem":                         # store: [mem], mask, data
        vl = c.size
        m = v.value(d, b, vl)
        act = np.array([m[(i + 1) * esize - 1] >> 7 == 1 for i in range(vl // esize)])
        v.put(d, a, v.value(d, c, vl), esize, act)
        return
    vl = a.size                                 # load: dst, mask, [mem]
    m = v.value(d, b, vl)
    act = np.array([m[(i + 1) * esize - 1] >> 7 == 1 for i in range(vl // esize)])
    data = v.value(d, c, vl, esize, act) if act.any() else bytes(vl)
    out = b"".join(data[i * esize:(i + 1) * esize] if act[i] else bytes(esize)
                   for i in range(vl // esize))
    v.put(d, a, out, vl=vl)


# ---- floating point --------------------------------------------------------------------

def _round_mode(v: Vector) -> int:
    return (v.uc.reg_read(X.UC_X86_REG_MXCSR) >> 13) & 3


def _round(x: np.ndarray, mode: int) -> np.ndarray:
    return [np.rint, np.floor, np.ceil, np.trunc][mode](x)


def _fop(name):
    return {"add": np.add, "sub": np.subtract, "mul": np.multiply, "div": np.divide,
            "min": lambda a, b: np.where(a < b, a, b), "max": lambda a, b: np.where(a > b, a, b),
            }[name]


@pattern(r"v(add|sub|mul|div|min|max)(ps|pd|ss|sd)")
def _farith(v, d, op, s):
    esize = 4 if s[1] == "s" else 8
    fn = _fop(op)
    if s[0] == "p":
        _elementwise(v, d, esize, fn, "f")
        return
    dst, a, b = d.ops                           # scalar: low element; the rest from a
    act = v.active(d, 1)
    x = _floats(v.value(d, a, 16), esize)
    y = _floats(v.value(d, b, esize), esize)
    with np.errstate(all="ignore"):
        x[0] = fn(x[:1], y[:1])[0]
    v.put(d, dst, x.tobytes(), esize, act, 16)


@pattern(r"vsqrt(ps|pd|ss|sd)")
def _sqrt(v, d, s):
    esize = 4 if s[1] == "s" else 8
    if s[0] == "p":
        _elementwise(v, d, esize, np.sqrt, "f")
        return
    dst, a, b = d.ops
    x = _floats(v.value(d, a, 16), esize)
    with np.errstate(all="ignore"):
        x[0] = np.sqrt(_floats(v.value(d, b, esize), esize))[0]
    v.put(d, dst, x.tobytes(), esize, v.active(d, 1), 16)


@pattern(r"v(rcp|rsqrt)(14)?(ps|ss)")
def _approx(v, d, op, _14, s):
    def fn(a):
        with np.errstate(all="ignore"):
            r = (1 / a) if op == "rcp" else 1 / np.sqrt(a)
        bits = r.astype(np.float32).view(np.uint32) & np.uint32(0xFFFFE000)   # ~12 bits
        return bits.view(np.float32)
    if s == "ps":
        _elementwise(v, d, 4, fn, "f")
        return
    dst, a, b = d.ops
    x = _floats(v.value(d, a, 16), 4)
    x[0] = fn(_floats(v.value(d, b, 4), 4))[0]
    v.put(d, dst, x.tobytes(), vl=16)


@pattern(r"vh(add|sub)p(s|d)")
def _hadd(v, d, op, s):
    esize = 4 if s == "s" else 8
    dst, a, b = d.ops
    vl = dst.size
    x, y = _floats(v.value(d, a, vl), esize), _floats(v.value(d, b, vl), esize)
    per = 16 // esize
    out = []
    f = np.add if op == "add" else np.subtract
    for lane in range(vl // 16):
        for src in (x, y):
            p = src[lane * per:(lane + 1) * per]
            out += list(f(p[0::2], p[1::2]))
    v.put(d, dst, np.array(out, _FT[esize]).tobytes(), vl=vl)


@pattern(r"vph(add|sub)(w|d)")
def _phadd(v, d, op, s):
    esize = _SUFFIX[s]
    dst, a, b = d.ops
    vl = dst.size
    x, y = _bits(v.value(d, a, vl), esize), _bits(v.value(d, b, vl), esize)
    per = 16 // esize
    out = []
    for lane in range(vl // 16):
        for src in (x, y):
            p = src[lane * per:(lane + 1) * per]
            out += list(p[0::2] + p[1::2] if op == "add" else p[0::2] - p[1::2])
    v.put(d, dst, np.array(out, _DT[esize]).tobytes(), vl=vl)


@pattern(r"vround(ps|pd|ss|sd)|vrndscale(ps|pd|ss|sd)")
def _vround(v, d, s1, s2=None):
    s = s1 or s2
    esize = 4 if s[1] == "s" else 8
    imm = d.ops[-1].imm
    mode = _round_mode(v) if imm & 4 else imm & 3
    if s[0] == "p":
        dst, src, _ = d.ops
        vl = dst.size
        x = _floats(v.value(d, src, vl, esize), esize)
        v.put(d, dst, _round(x, mode).astype(_FT[esize]).tobytes(), esize, v.active(d, vl // esize), vl)
        return
    dst, a, b, _ = d.ops
    x = _floats(v.value(d, a, 16), esize)
    x[0] = _round(_floats(v.value(d, b, esize), esize), mode)[0]
    v.put(d, dst, x.tobytes(), vl=16)


# FMA: one rounding of the exact a*b+c.
_DEFAULT_NAN = struct.unpack("<d", struct.pack("<Q", 0xFFF8000000000000))[0]   # -QNaN
def _fma1(a: float, b: float, c: float, f32: bool) -> float:
    if not all(math.isfinite(t) for t in (a, b, c)):
        r = a * b + c                           # infinities: no rounding question
        if math.isnan(r):
            return _DEFAULT_NAN                 # inf*0, inf-inf: the "default NaN"
        return float(np.float32(r)) if f32 else r
    exact = Fraction(a) * Fraction(b) + Fraction(c)
    if exact == 0:
        prod_neg = (math.copysign(1, a) * math.copysign(1, b)) < 0
        if c == 0 and prod_neg and math.copysign(1, c) < 0:
            return -0.0
        return 0.0
    if not f32:
        try:
            return float(exact)                 # (Fraction -> float rounds correctly)
        except OverflowError:
            return math.copysign(math.inf, exact)
    return _f32(exact)


_F32_OVER = Fraction(float(np.finfo(np.float32).max)) + Fraction(2) ** 103   # halfway to 2^128


def _f32(exact: Fraction) -> float:
    """The float32 nearest to an exact value (ties to even)."""
    if abs(exact) >= _F32_OVER:
        return math.copysign(math.inf, exact)
    guess = np.float32(float(exact))
    best = None
    for cand in (np.nextafter(guess, np.float32(-np.inf)), guess,
                 np.nextafter(guess, np.float32(np.inf))):
        if not np.isfinite(cand):
            continue
        key = (abs(Fraction(float(cand)) - exact), int(np.array(cand).view(np.uint32)) & 1)
        if best is None or key < best[0]:
            best = (key, float(cand))
    r = best[1]
    return math.copysign(0.0, exact) if r == 0 else r


@pattern(r"vf(n?)m(add|sub)(132|213|231)(ps|pd|ss|sd)")
def _fma(v, d, neg, op, order, s):
    esize = 4 if s[1] == "s" else 8
    dst, b, c = d.ops
    scalar = s[0] == "s"
    vl = 16 if scalar else dst.size
    n = 1 if scalar else vl // esize
    act = v.active(d, n)
    x1 = _floats(v.value(d, dst, vl), esize)
    x2 = _floats(v.value(d, b, vl), esize)
    x3 = _floats(v.value(d, c, esize if scalar else vl, esize, act) + bytes(vl), esize)[:len(x1)]
    roles = {"132": (x1, x3, x2), "213": (x2, x1, x3), "231": (x2, x3, x1)}[order]
    out = x1.copy()
    quiet = np.array(1 << (8 * esize - 10), _DT[esize])          # the quiet-NaN bit
    for i in range(n):
        nans = [t[i:i + 1] for t in roles if np.isnan(t[i])]
        if nans:                                # the first NaN of a, b, c in a*b+c
            out[i:i + 1] = (nans[0].view(_DT[esize]) | quiet).view(_FT[esize])
            continue
        p, q, r = (float(t[i]) for t in roles)
        if neg:
            p = -p
        if op == "sub":
            r = -r
        out[i] = _fma1(p, q, r, esize == 4)
    v.put(d, dst, out.tobytes(), esize, act, vl)


@pattern(r"vcvt(t?)(dq2ps|ps2dq|dq2pd|pd2dq|ps2pd|pd2ps|ss2sd|sd2ss|si2ss|si2sd|ss2si|sd2si|udq2ps|ps2udq)")
def _cvt(v, d, trunc, what):
    dst = d.ops[0]
    act = None
    if what in ("si2ss", "si2sd"):
        dst, a, b = d.ops
        esize = 4 if what == "si2ss" else 8
        x = _floats(v.value(d, a, 16), esize)
        n = int.from_bytes(v.value(d, b, b.size), "little", signed=True)
        x[0] = float(n) if esize == 8 else _f32(Fraction(n))
        v.put(d, dst, x.tobytes(), vl=16)
        return
    if what in ("ss2si", "sd2si"):
        dst, src = d.ops
        esize = 4 if what == "ss2si" else 8
        x = float(_floats(v.value(d, src, esize), esize)[0])
        bits = 8 * dst.size
        r = _to_int(x, 0 if not trunc else 3, bits, v)
        v.set_gpr(dst.reg, r, dst.size)
        return
    if what in ("ss2sd", "sd2ss"):
        dst, a, b = d.ops
        to = 8 if what == "ss2sd" else 4
        x = _floats(v.value(d, a, 16), to)
        y = _floats(v.value(d, b, 4 if to == 8 else 8), 4 if to == 8 else 8)
        x[0] = y[0]
        v.put(d, dst, x.tobytes(), vl=16)
        return
    dst, src = d.ops
    src_el = {"dq2ps": 4, "ps2dq": 4, "dq2pd": 4, "pd2dq": 8, "ps2pd": 4, "pd2ps": 8,
              "udq2ps": 4, "ps2udq": 4}[what]
    dst_el = {"dq2ps": 4, "ps2dq": 4, "dq2pd": 8, "pd2dq": 4, "ps2pd": 8, "pd2ps": 4,
              "udq2ps": 4, "ps2udq": 4}[what]
    if dst_el > src_el:
        n = dst.size // dst_el                  # widening: half as many source bytes
    elif dst_el < src_el:
        n = src.size // src_el                  # narrowing: the source decides
    else:
        n = dst.size // dst_el
    act = v.active(d, n)
    raw = v.value(d, src, n * src_el, src_el, act)
    if what in ("dq2ps", "dq2pd", "udq2ps"):
        x = _bits(raw, 4, what != "udq2ps").astype(np.float64)
        out = x.astype(_FT[dst_el])
    elif what in ("ps2dq", "pd2dq", "ps2udq"):
        x = _floats(raw, src_el)
        mode = 3 if trunc else _round_mode(v)
        out = np.array([_to_int(float(t), mode, 32, v) for t in x], np.uint32)
    else:
        out = _floats(raw, src_el).astype(_FT[dst_el])
    data = out.tobytes()
    vl = max(16, len(data))
    v.put(d, dst, data + bytes(vl - len(data)), dst_el, act, vl)


def _to_int(x: float, mode: int, bits: int, v: Vector) -> int:
    """Float -> integer as cvt(t)ss2si & co. do: out-of-range and NaN give the
    'integer indefinite' value, 1 followed by zeros."""
    if not math.isfinite(x):
        return 1 << (bits - 1)
    r = [_rint, math.floor, math.ceil, math.trunc][mode](x)
    if not -(1 << (bits - 1)) <= r < (1 << (bits - 1)):
        return 1 << (bits - 1)
    return r & ((1 << bits) - 1)


def _rint(x: float) -> int:
    return int(np.rint(x))


# ---- mask registers --------------------------------------------------------------------

_KBITS = {"b": 8, "w": 16, "d": 32, "q": 64}


@pattern(r"kmov(b|w|d|q)")
def _kmov(v, d, s):
    bits = _KBITS[s]
    dst, src = d.ops
    val = int.from_bytes(v.value(d, src, bits // 8), "little") & ((1 << bits) - 1)
    if dst.kind == "reg" and not re.fullmatch(r"k[0-7]", dst.reg):
        v.set_gpr(dst.reg, val, max(dst.size, 4))
    else:
        v.put(d, dst, val.to_bytes(8, "little")[:bits // 8] if dst.kind == "mem"
              else val.to_bytes(8, "little"))


@pattern(r"k(and|andn|or|xor|xnor|add)(b|w|d|q)")
def _klogic(v, d, op, s):
    bits = _KBITS[s]
    full = (1 << bits) - 1
    dst, a, b = d.ops
    x, y = v.k[int(a.reg[1])] & full, v.k[int(b.reg[1])] & full
    r = {"and": x & y, "andn": ~x & y, "or": x | y, "xor": x ^ y, "xnor": ~(x ^ y),
         "add": x + y}[op] & full
    v.set_k(int(dst.reg[1]), r)


@pattern(r"knot(b|w|d|q)")
def _knot(v, d, s):
    full = (1 << _KBITS[s]) - 1
    dst, a = d.ops
    v.set_k(int(dst.reg[1]), ~v.k[int(a.reg[1])] & full)


@pattern(r"kshift(l|r)(b|w|d|q)")
def _kshift(v, d, lr, s):
    full = (1 << _KBITS[s]) - 1
    dst, a, imm = d.ops
    x = v.k[int(a.reg[1])] & full
    n = imm.imm & 0xFF
    r = 0 if n >= _KBITS[s] else ((x << n) if lr == "l" else (x >> n)) & full
    v.set_k(int(dst.reg[1]), r)


@pattern(r"k(or)?test(b|w|d|q)")
def _ktest(v, d, ortest, s):
    full = (1 << _KBITS[s]) - 1
    a, b = d.ops
    x, y = v.k[int(a.reg[1])] & full, v.k[int(b.reg[1])] & full
    if ortest:
        v.set_flags(ZF=int(x | y == 0), CF=int(x | y == full))
    else:
        v.set_flags(ZF=int(x & y == 0), CF=int(~x & y & full == 0))


@pattern(r"kunpck(bw|wd|dq)")
def _kunpck(v, d, s):
    half = {"bw": 8, "wd": 16, "dq": 32}[s]
    full = (1 << half) - 1
    dst, a, b = d.ops
    v.set_k(int(dst.reg[1]), ((v.k[int(a.reg[1])] & full) << half) | (v.k[int(b.reg[1])] & full))
