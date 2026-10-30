M = (1 << 64) - 1


def s(v):
    return v - (1 << 64) if v >> 63 else v


def expect(a, b):
    sa, sb = s(a), s(b)
    tq = abs(sa) // abs(sb) * (1 if (sa < 0) == (sb < 0) else -1)
    tr = sa - tq * sb
    return {"r8": tq & M, "r9": tr & M, "rax": (sa // sb) & M, "rdx": (sa % sb) & M}


def generate(rng, count, ctx):
    tests = []
    for i in range(count):
        a = rng.choice([rng.getrandbits(64), rng.randrange(-1000, 1000) & M, 1 << 63])
        b = rng.choice([rng.getrandbits(64), rng.randrange(1, 50), (-rng.randrange(1, 50)) & M])
        if s(b) == 0 or (a == 1 << 63 and s(b) == -1):
            b = 3
        tests.append({"name": f"random {i}", "regs": {"rdi": a, "rsi": b},
                      "expect": {"regs": expect(a, b)}})
    return tests
