import struct


def sound(n, rng):
    """Loud samples, then a long quiet tail (after the first 500)."""
    return [rng.uniform(-1, 1) if i < 500 else rng.uniform(-1e-9, 1e-9) for i in range(n)]


def expected(xs):
    y, out = 0.0, []
    for x in xs:
        y = y * 0.5 + x * 1e-300
        out.append(y)
    return out


def case(name, n, rng, hidden=False):
    xs = sound(n, rng)
    return {"name": name, "hidden": hidden, "regs": {"rdi": "@samples", "rsi": "@smoothed", "rdx": n},
            "mem": [{"sym": "samples", "hex": struct.pack(f"<{n}d", *xs).hex()}] if n else [],
            "expect": {"check": True, "out": expected(xs), "per": [max(n, 1), "sample"],
                       "max_cycles": 12 * n + 1500}}


def check(test, m):
    want = test.expect["out"]
    n = len(want)
    got = struct.unpack(f"<{n}d", m.read(m.build.symbols["smoothed"], 8 * n)) if n else ()
    for i, (g, w) in enumerate(zip(got, want)):
        if abs(g - w) > 1e-300 and abs(g - w) > 1e-12 * abs(w):
            return [f"out[{i}]: expected {w!r}, got {g!r}"]
    return []


def fixed_tests(ctx):
    import random
    rng = random.Random(93)
    return [case("500 samples", 500, rng), case("1000 samples", 1000, rng)]


def generate(rng, count, ctx):
    return [case("nothing", 0, rng, True), case("3000 samples", 3000, rng, True),
            case("4000 samples", 4000, rng, True)]


def witness_test(w, ctx):
    import random
    if set(w) != {"n"} or not isinstance(w["n"], int) or not 1 <= w["n"] <= 4096:
        raise ValueError("the witness is an input size from 1 to 4096: `;! witness n = 1234`")
    return case("witness", w["n"], random.Random(1))
