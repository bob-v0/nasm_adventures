M = (1 << 64) - 1


def s(v):
    return v - (1 << 64) if v >> 63 else v


def clamp(x, lo, hi):
    return min(max(x, lo), hi)


def generate(rng, count, ctx):
    tests = []
    for i in range(count):
        lo = rng.randrange(0, 1 << 62)
        hi = rng.randrange(lo, 1 << 63)
        x = rng.choice([rng.getrandbits(64), rng.randrange(lo, hi + 1), lo, hi, lo - 1, hi + 1,
                        (-rng.randrange(1, 1000)) & M])
        tests.append({"name": f"random {i}", "regs": {"rdi": x, "rsi": lo, "rdx": hi},
                      "expect": {"regs": {"rax": clamp(s(x), lo, hi) & M, "rbx": clamp(x, lo, hi)}}})
    return tests
