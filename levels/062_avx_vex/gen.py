import struct

BUDGET = {"avx2": 0.42, "avx512": 0.42, "avx": 0.42, "sse4.2": 0.8}
NAMES = {"avx2": "an AVX2 CPU", "avx512": "an AVX-512 CPU", "avx": "an AVX CPU without AVX2 or FMA",
         "sse4.2": "an old CPU without AVX"}


def f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


def case(name, y, x, a, cpu, hidden=False, budget=True):
    n = len(y)
    want = [yy + a * xx for yy, xx in zip(y, x)]
    t = {"name": f"{name} on {NAMES[cpu]}", "hidden": hidden,
         "regs": {"rdi": "@vy", "rsi": "@vx", "rdx": n,
                  "xmm0": struct.unpack("<I", struct.pack("<f", a))[0]},
         "mem": [{"sym": "vy", "hex": struct.pack(f"<{n}f", *y).hex()},
                 {"sym": "vx", "hex": struct.pack(f"<{n}f", *x).hex()}] if n else [],
         "inject": {"cpu": cpu, "warm": [{"sym": "vy", "size": 4 * n}, {"sym": "vx", "size": 4 * n}]},
         "expect": {"check": True, "y": want, "scale": [abs(yy) + abs(a * xx) for yy, xx in zip(y, x)],
                    "per": [max(n, 1), "element"]}}
    if budget:
        t["expect"]["max_cycles"] = int(BUDGET[cpu] * n) + 400
    return t


def check(test, m):
    want = test.expect["y"]
    n = len(want)
    got = struct.unpack(f"<{n}f", m.read(m.build.symbols["vy"], 4 * n)) if n else ()
    for i, (g, w, s) in enumerate(zip(got, want, test.expect["scale"])):
        if not abs(g - w) <= 1e-6 * s + 1e-30:
            return [f"y[{i}]: expected {w!r}, got {g!r}"]
    if m.vector is not None and m.vector.dirty_upper:
        return ["the function returned with dirty upper ymm halves: vzeroupper before ret "
                "(the caller's SSE code would pay for them)"]
    return []


def vec(rng, n):
    return [f32(rng.uniform(-10, 10)) for _ in range(n)]


def fixed_tests(ctx):
    import random
    rng = random.Random(62)
    small = (vec(rng, 11), vec(rng, 11))
    big = (vec(rng, 4000), vec(rng, 4000))
    return [case("11 elements", *small, 2.0, "avx2", budget=False),
            case("11 elements", *small, 2.0, "sse4.2", budget=False),
            case("4000 elements", *big, -0.5, "avx2"),
            case("4000 elements", *big, -0.5, "sse4.2")]


def generate(rng, count, ctx):
    out = [case("nothing", [], [], 1.0, "avx2", True, False),
           case("3 elements", vec(rng, 3), vec(rng, 3), 3.0, "avx", True, False)]
    for i in range(count):
        n = rng.randrange(3000, 20000)
        y, x = vec(rng, n), vec(rng, n)
        a = f32(rng.uniform(-4, 4))
        for cpu in ("avx2", "avx", "sse4.2", "avx512"):
            out.append(case(f"{n} elements", y, x, a, cpu, True))
    return out
