import math
import struct

INDEFINITE = 0x8000000000000000


def bits(x: float) -> int:
    return struct.unpack("<Q", struct.pack("<d", x))[0]


def expected(b: int) -> int:
    x = struct.unpack("<d", struct.pack("<Q", b))[0]
    if not math.isfinite(x):
        return INDEFINITE
    t = math.trunc(x)
    if not -(1 << 63) <= t < (1 << 63):
        return INDEFINITE
    return t & ((1 << 64) - 1)


def case(name, b, hidden=False):
    return {"name": name, "hidden": hidden, "regs": {"rdi": b},
            "expect": {"regs": {"rax": expected(b)}}}


def fixed_tests(ctx):
    return [case("1.0", bits(1.0)), case("-2.75", bits(-2.75)), case("123456.789", bits(123456.789)),
            case("0.0", 0), case("0.5", bits(0.5)), case("2^52 + 1", bits(2.0 ** 52 + 1)),
            case("1e18", bits(1e18)), case("1e19 (too big)", bits(1e19)),
            case("infinity", bits(math.inf)), case("NaN", 0x7FF8000000000000)]


def generate(rng, count, ctx):
    out = [case("-0.0", 1 << 63, True), case("smallest denormal", 1, True),
           case("-0.999", bits(-0.999), True), case("-2^63", bits(-2.0 ** 63), True),
           case("2^63", bits(2.0 ** 63), True), case("largest below 2^63", bits(2.0 ** 63) - 1, True),
           case("-infinity", bits(-math.inf), True), case("NaN with a payload", 0xFFF0000000001234, True),
           case("largest double", bits(1.7976931348623157e308), True)]
    for i in range(count):
        e = rng.randint(1023 - 3, 1023 + 66)
        b = (rng.getrandbits(1) << 63) | (e << 52) | rng.getrandbits(52)
        out.append(case(f"random {i}", b, True))
    return out


def audit(build):
    from ring.checks import disassemble
    fp = sorted({mn for _, mn, ops in disassemble(build)
                 if mn.startswith(("f", "cvt")) or any(r in ops for r in ("xmm", "ymm", "zmm", "st("))})
    return [("integer instructions only (no x87, SSE or AVX)", not fp,
             f"found: {', '.join(fp)}" if fp else "")]
