import struct

GUARD = 16


def case(name, src, pal, rng, hidden=False, budget=True):
    n = len(src)
    want = struct.pack(f"<{n}I", *[pal[b] for b in reversed(src)])
    guard = rng.randbytes(4 * GUARD)
    t = {"name": name, "hidden": hidden,
         "regs": {"rdi": "@sprite", "rsi": "@screen", "rdx": n, "rcx": "@palette"},
         "mem": [{"sym": "sprite", "hex": bytes(src).hex()},
                 {"sym": "palette", "hex": struct.pack("<256I", *pal).hex()},
                 {"sym": "screen", "hex": (bytes(4 * n) + guard).hex()}],
         "inject": {"cpu": "avx2", "warm": [{"sym": "sprite", "size": max(n, 1)},
                                            {"sym": "palette", "size": 1024},
                                            {"sym": "screen", "size": 4 * n + 64}]},
         "expect": {"mem": [{"sym": "screen", "hex": (want + guard).hex()}],
                    "per": [max(n, 1), "pixel"]}}
    if budget:
        t["expect"]["max_cycles"] = int(0.8 * n) + 500
    return t


def palette(rng):
    return [rng.getrandbits(32) for _ in range(256)]


def fixed_tests(ctx):
    import random
    rng = random.Random(60)
    pal = palette(rng)
    return [case("8 pixels", [1, 2, 3, 4, 5, 6, 7, 8], pal, rng, budget=False),
            case("11 pixels", [rng.randrange(256) for _ in range(11)], pal, rng, budget=False),
            case("a 3000-pixel row", [rng.randrange(256) for _ in range(3000)], pal, rng)]


def generate(rng, count, ctx):
    pal = palette(rng)
    out = [case("nothing", [], pal, rng, True, False), case("one", [255], pal, rng, True, False)]
    for i in range(count):
        n = rng.randrange(2000, 16000)
        out.append(case(f"{n} pixels", [rng.randrange(256) for _ in range(n)], palette(rng), rng, True))
    return out


def audit(build):
    from ring.checks import disassemble
    mns = {mn for _, mn, _ in disassemble(build)}
    return [("looks colours up with vpgatherdd", "vpgatherdd" in mns, ""),
            ("reverses lanes with vpermd", "vpermd" in mns, "")]
