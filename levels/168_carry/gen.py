M = (1 << 64) - 1
M128 = (1 << 128) - 1


def expect(alo, ahi, blo, bhi):
    a, b = ahi << 64 | alo, bhi << 64 | blo
    s, d = (a + b) & M128, (a - b) & M128
    return {"regs": {"r8": s & M, "r9": s >> 64, "r10": d & M, "r11": d >> 64},
            "flags": {"CF": int(a < b)}}


def generate(rng, count, ctx):
    tests = []
    for i in range(count):
        vals = [rng.choice([rng.getrandbits(64), M, 0, 1]) for _ in range(4)]
        tests.append({"name": f"random {i}",
                      "regs": dict(zip(["rdi", "rsi", "rdx", "rcx"], vals)),
                      "expect": expect(*vals)})
    return tests
