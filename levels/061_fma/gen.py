import math
import struct

LO, HI = -87.3, 88.7
MAX_ULP = 2


def f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


def fbits(x):
    return struct.unpack("<I", struct.pack("<f", x))[0]


def case(name, xs, hidden=False, budget=True):
    n = len(xs)
    want = [fbits(f32(math.exp(x))) for x in xs]
    t = {"name": name, "hidden": hidden, "regs": {"rdi": "@xs", "rsi": "@ys", "rdx": n},
         "mem": [{"sym": "xs", "hex": struct.pack(f"<{n}f", *xs).hex()},
                 {"sym": "ys", "hex": bytes(4 * n + 64).hex()}],
         "inject": {"cpu": "avx2", "warm": [{"sym": "xs", "size": 4 * n}, {"sym": "ys", "size": 4 * n}]},
         "expect": {"check": True, "want": want, "xs": xs, "per": [max(n, 1), "element"]}}
    if budget:
        t["expect"]["max_cycles"] = int(1.0 * n) + 600
    return t


def check(test, m):
    want, xs = test.expect["want"], test.expect["xs"]
    n = len(want)
    got = struct.unpack(f"<{n + 16}I", m.read(m.build.symbols["ys"], 4 * n + 64))
    for i, (g, w) in enumerate(zip(got, want)):
        if abs(g - w) > MAX_ULP:
            gf = struct.unpack("<f", struct.pack("<I", g))[0]
            wf = struct.unpack("<f", struct.pack("<I", w))[0]
            return [f"exp({xs[i]!r}): expected {wf!r}, got {gf!r}: {abs(g - w)} ULPs away "
                    f"(at most {MAX_ULP})"]
    if any(got[n:]):
        return [f"wrote past the end: ys[{n + next(i for i, v in enumerate(got[n:]) if v)}]"]
    if m.vector is not None and m.vector.dirty_upper:
        return ["returned with dirty upper ymm halves: vzeroupper before ret"]
    return []


def fixed_tests(ctx):
    import random
    rng = random.Random(61)
    return [case("0, 1, -1, 2, 0.5, -0.5, 10, -10", [0.0, 1.0, -1.0, 2.0, 0.5, -0.5, 10.0, -10.0], budget=False),
            case("13 values", [f32(rng.uniform(-5, 5)) for _ in range(13)], budget=False),
            case("2000 values", [f32(rng.uniform(LO, HI)) for _ in range(2000)])]


def generate(rng, count, ctx):
    edges = [LO, HI, f32(math.log(2) / 2), -f32(math.log(2) / 2), 1e-7, -1e-7, 88.0, -87.0,
             f32(math.log(3)), 44.36]
    out = [case("nothing", [], True, False), case("edges", [f32(x) for x in edges], True, False),
           case("one", [3.0], True, False)]
    for i in range(count):
        n = rng.randrange(3000, 16000)
        out.append(case(f"{n} values", [f32(rng.uniform(LO, HI)) for _ in range(n)], True))
    out.append(case("near zero", [f32(rng.uniform(-0.01, 0.01)) for _ in range(1001)], True))
    return out


def audit(build):
    from ring.checks import disassemble
    fma = any(mn.startswith(("vfmadd", "vfnmadd", "vfmsub", "vfnmsub")) for _, mn, _ in disassemble(build))
    return [("uses FMA (vfmadd...)", fma, "")]
