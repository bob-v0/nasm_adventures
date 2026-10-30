import struct
from fractions import Fraction


def f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


def case(name, a, b, hidden=False, budget=True):
    n = len(a)
    exact = sum(Fraction(x) * Fraction(y) for x, y in zip(a, b))
    scale = sum(abs(x * y) for x, y in zip(a, b))
    t = {"name": name, "hidden": hidden, "regs": {"rdi": "@va", "rsi": "@vb", "rdx": n},
         "mem": [{"sym": "va", "hex": struct.pack(f"<{n}f", *a).hex()},
                 {"sym": "vb", "hex": struct.pack(f"<{n}f", *b).hex()}] if n else [],
         "inject": {"warm": [{"sym": "va", "size": 4 * n}, {"sym": "vb", "size": 4 * n}]},
         "expect": {"check": True, "dot": float(exact), "tolerance": 1e-4 * scale + 1e-30,
                    "per": [max(n, 1), "element"]}}
    if budget:
        t["expect"]["max_cycles"] = int(0.6 * n) + 800
    return t


def check(test, m):
    got = struct.unpack("<f", struct.pack("<I", m.reg("xmm0") & 0xFFFFFFFF))[0]
    want, tol = test.expect["dot"], test.expect["tolerance"]
    if not abs(got - want) <= tol:
        return [f"expected {want!r} (as a float, give or take {tol:.2g}), got {got!r} in xmm0"]
    return []


def vec(rng, n, lo=-1.0, hi=1.0):
    return [f32(rng.uniform(lo, hi)) for _ in range(n)]


def fixed_tests(ctx):
    import random
    rng = random.Random(63)
    return [case("(1, 2, 3, 4) · (5, 6, 7, 8)", [1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0], budget=False),
            case("7 elements", vec(rng, 7), vec(rng, 7), budget=False),
            case("2000 elements", vec(rng, 2000), vec(rng, 2000))]


def generate(rng, count, ctx):
    out = [case("nothing", [], [], True, False), case("one", [3.0], [-2.5], True, False),
           case("19 elements", vec(rng, 19), vec(rng, 19), True, False)]
    for i in range(count):
        n = rng.randrange(3000, 20000)
        out.append(case(f"{n} elements", vec(rng, n, -100, 100), vec(rng, n), True))
    return out
