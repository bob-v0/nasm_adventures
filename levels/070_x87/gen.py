import math
import struct

MOVES = {"movsd", "movq", "movapd", "movaps", "movups", "movupd", "movdqa", "movdqu", "movlpd",
         "movhpd"}


def bits(x: float) -> int:
    return struct.unpack("<Q", struct.pack("<d", x))[0]


def double(b: int) -> float:
    return struct.unpack("<d", struct.pack("<Q", b & (2 ** 64 - 1)))[0]


def case(name, x, y, a, hidden=False):
    c, s = math.cos(a), math.sin(a)
    xp, yp = x * c - y * s, x * s + y * c
    return {"name": name, "hidden": hidden,
            "regs": {"xmm0": bits(x), "xmm1": bits(y), "xmm2": bits(a)},
            "expect": {"check": True, "x": xp, "y": yp, "floor": math.floor(math.hypot(xp, yp)),
                       "scale": max(1.0, abs(x) + abs(y))}}


def check(test, m):
    from unicorn import x86_const as X
    e = test.expect
    out = []
    for reg, want in (("xmm0", e["x"]), ("xmm1", e["y"])):
        got = double(m.reg(reg))
        if not abs(got - want) <= 1e-9 * e["scale"]:
            out.append(f"{reg}: expected {want!r}, got {got!r}")
    if m.reg("rax") != e["floor"]:
        out.append(f"rax: expected floor(length) = {e['floor']}, got {m.reg('rax'):#x}")
    cw = m.uc.reg_read(X.UC_X86_REG_FPCW) & 0xFFFF
    if cw != 0x037F:
        out.append(f"the x87 control word is {cw:#06x} at the return; it must be restored "
                   "to 0x037f (save it with fnstcw first, fldcw it back after)")
    top = m.uc.reg_read(X.UC_X86_REG_FPSW) >> 11 & 7
    if top != 0:
        n = 8 - top
        out.append(f"the x87 stack isn't empty at the return: {n} value(s) left on it "
                   if n <= 4 else f"the x87 stack is off by {top}: more pops than pushes")
    return out


def _ok(x, y, a):
    c, s = math.cos(a), math.sin(a)
    length = math.hypot(x * c - y * s, x * s + y * c)
    return abs(length - round(length)) > 1e-6


def fixed_tests(ctx):
    return [case("3-4-5, no rotation", 3.0, 4.0, 0.0), case("(1, 0) by 30 degrees", 1.0, 0.0, math.pi / 6),
            case("(10, -2.5) by 2 radians", 10.0, -2.5, 2.0)]


def generate(rng, count, ctx):
    out = [case("(0, 0)", 0.0, 0.0, 1.0, True), case("(-7, 24) unrotated", -7.0, 24.0, 0.0, True)]
    while len(out) < count + 2:
        x, y, a = rng.uniform(-1000, 1000), rng.uniform(-1000, 1000), rng.uniform(-10, 10)
        if _ok(x, y, a):
            out.append(case(f"random {len(out)}", x, y, a, True))
    return out


def audit(build):
    from ring.checks import disassemble
    ins = disassemble(build)
    sse = sorted({mn for _, mn, ops in ins if "xmm" in ops and mn not in MOVES})
    trig = any(mn in ("fsincos", "fsin", "fcos") for _, mn, _ in ins)
    return [("the arithmetic is x87 (xmm registers only to move values in and out)", not sse,
             f"found: {', '.join(sse)}" if sse else ""),
            ("uses fsincos (or fsin and fcos)", trig, "")]
