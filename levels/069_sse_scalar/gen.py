import math
import struct
from fractions import Fraction

MODES = {0: "to nearest", 1: "down", 2: "up", 3: "toward zero"}


def bits(x: float) -> int:
    return struct.unpack("<Q", struct.pack("<d", x))[0]


def expected(x: float, mode: int = 0) -> str:
    if math.isnan(x):
        return "nan"
    sign = "-" if math.copysign(1, x) < 0 else ""
    if math.isinf(x):
        return sign + "inf"
    a = abs(x)
    if mode == 0:
        n = round(a * 1000.0)           # an IEEE multiply, then ties to even
    else:
        exact = Fraction(a) * 1000      # (directed modes: the product's rounding can't
        n = math.floor(exact) if mode in (1, 3) else math.ceil(exact)   # change the result)
    return f"{sign}{n // 1000}.{n % 1000:03d}"


def case(name, x, hidden=False, mode=0):
    t = {"name": name, "hidden": hidden, "regs": {"xmm0": bits(x), "rdi": "@text"},
         "expect": {"check": True, "text": expected(x, mode)}}
    if mode:
        t["regs"]["mxcsr"] = 0x1F80 | mode << 13
        t["expect"]["mode"] = MODES[mode]
    return t


def check(test, m):
    want = test.expect["text"]
    n = m.reg("rax")
    got = m.read(m.build.symbols["text"], min(n, 64)).decode("latin-1") if n <= 64 else None
    if got != want:
        mode = f" (MXCSR rounding: {test.expect['mode']})" if "mode" in test.expect else ""
        return [f"expected {want!r}{mode}, got " + (repr(got) if got is not None else
                                                   f"a length of {n} (rax)")]
    if m.reg("mxcsr") != test.regs.get("mxcsr", 0x1F80):
        return ["MXCSR changed: it's the caller's; leave it as it was"]
    return []


def fixed_tests(ctx):
    return [case("3.25", 3.25), case("-12.5", -12.5), case("0.1", 0.1), case("1234567.891", 1234567.891),
            case("0.0", 0.0), case("a tie: 0.0625", 0.0625), case("NaN", math.nan),
            case("-infinity", -math.inf)]


def generate(rng, count, ctx):
    out = [case("-0.0", -0.0, True), case("-0.0001", -0.0001, True), case("infinity", math.inf, True),
           case("tie: 1.0625", 1.0625, True), case("tie: 2.0005 (not quite)", 2.0005, True),
           case("999.9996", 999.9996, True), case("0.0005", 0.0005, True),
           case("1e11", 1e11, True), case("-NaN", -math.nan, True),
           case("0.0019 rounding down", 0.0019, True, mode=1),
           case("-2.0001 rounding up", -2.0001, True, mode=2),
           case("7.7777 toward zero", 7.7777, True, mode=3)]
    for i in range(count):
        x = rng.choice([rng.uniform(-10, 10), rng.uniform(-1e6, 1e6), rng.uniform(-1e11, 1e11),
                        rng.randint(-99999, 99999) / 8])
        out.append(case(f"random {i}", x, True, mode=rng.choice([0, 0, 0, 1, 2, 3])))
    return out
