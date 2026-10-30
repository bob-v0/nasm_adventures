import math
import struct
from decimal import Decimal, getcontext
from fractions import Fraction

getcontext().prec = 80


def bits(x: float) -> int:
    return struct.unpack("<Q", struct.pack("<d", x))[0]


def solve(a, b, c):
    """(count, roots) for a·t² + b·t + c = 0, exactly (then rounded to doubles)."""
    if any(math.isnan(v) for v in (a, b, c)):
        return -1, []
    A, B, C = (Fraction(v) for v in (a, b, c))
    d = B * B - 4 * A * C
    if d < 0:
        return 0, []
    if d == 0:
        return 1, [float(-B / (2 * A))]
    s = Decimal(d.numerator) / Decimal(d.denominator)
    s = s.sqrt()
    da, db = Decimal(a), Decimal(b)
    r = sorted([(-db - s) / (2 * da), (-db + s) / (2 * da)])
    return 2, [float(x) for x in r]


def case(name, a, b, c, hidden=False):
    n, roots = solve(a, b, c)
    return {"name": name, "hidden": hidden,
            "regs": {"xmm0": bits(a), "xmm1": bits(b), "xmm2": bits(c), "rdi": "@hits"},
            "expect": {"check": True, "n": n, "roots": roots, "abc": [a, b, c]}}


def check(test, m):
    e = test.expect
    got = m.reg("rax")
    got = got - (1 << 64) if got >> 63 else got
    if got != e["n"]:
        what = {-1: "-1 (an input is NaN)", 0: "0 (no hit)", 1: "1 (touches)", 2: "2"}[e["n"]]
        return [f"a, b, c = {e['abc']}: expected {what} in rax, got {got}"]
    vals = struct.unpack("<2d", m.read(m.build.symbols["hits"], 16))[:e["n"]]
    for i, (g, w) in enumerate(zip(vals, e["roots"])):
        if not abs(g - w) <= 1e-12 * abs(w) and g != w:
            return [f"a, b, c = {e['abc']}: hits[{i}]: expected {w!r}, got {g!r}"
                    + (f" (relative error {abs(g - w) / abs(w):.1e})" if w else "")]
    return []


def _well_conditioned(rng):
    while True:
        a = rng.choice([-1, 1]) * rng.uniform(0.1, 10)
        b = rng.uniform(-20, 20)
        c = rng.uniform(-10, 10)
        d = b * b - 4 * a * c
        if abs(d) > 0.5 * (b * b + abs(4 * a * c)):
            return a, b, c


def fixed_tests(ctx):
    import random
    rng = random.Random(68)
    return [case("ray through the middle", 1.0, -6.0, 5.0), case("a miss", 1.0, 1.0, 1.0),
            case("grazing exactly", 1.0, 2.0, 1.0), case("negative a", -2.0, 3.0, 2.0),
            *[case(f"random {i}", *_well_conditioned(rng)) for i in range(3)],
            case("a tiny sphere far away", 1.0, 1e9, 1.0)]


def generate(rng, count, ctx):
    out = [case("far away, other side", 2.0, -3e8, 0.5, True),
           case("far, negative a", -1.0, 4e7, 3.0, True),
           case("b = 0", 1.0, 0.0, -4.0, True), case("c = 0", 1.0, 3.0, 0.0, True),
           case("NaN in the scene", 1.0, math.nan, 1.0, True),
           case("NaN a", math.nan, 1.0, 1.0, True), case("NaN c", 1.0, 2.0, math.nan, True),
           case("grazing at 3", 1.0, -6.0, 9.0, True)]
    for i in range(count):
        out.append(case(f"random {i}", *_well_conditioned(rng), True))
    for i in range(4):
        a, c = rng.uniform(0.5, 2), rng.uniform(0.5, 2)
        out.append(case(f"far {i}", a, rng.choice([-1, 1]) * 10 ** rng.uniform(6, 12), c, True))
    return out


def witness_test(w, ctx):
    if set(w) != {"a", "b", "c"} or not all(isinstance(v, str) for v in w.values()):
        raise ValueError('the witness is three numbers, as strings: '
                         '`;! witness a = "1", b = "2", c = "3"`')
    try:
        a, b, c = (float(w[k]) for k in "abc")
    except ValueError as e:
        raise ValueError(f"not a number: {e}")
    if a == 0 or math.isinf(a) or math.isinf(b) or math.isinf(c):
        raise ValueError("a must be nonzero, and none of them infinite")
    if not any(math.isnan(v) for v in (a, b, c)):
        d = Fraction(b) ** 2 - 4 * Fraction(a) * Fraction(c)
        if d != 0 and abs(d) < Fraction(1, 2) * (Fraction(b) ** 2 + abs(4 * Fraction(a) * Fraction(c))):
            raise ValueError("pick a case where b² and 4ac aren't close (a nearly grazing ray "
                             "is hard for any formula): the bug is elsewhere")
    return case("witness", a, b, c)
