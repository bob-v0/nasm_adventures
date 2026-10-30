M = (1 << 64) - 1


def expect(r, g, b, lo, hi, n):
    v = ((hi << 64 | lo) << n) & ((1 << 128) - 1)
    return {"rax": (r >> 3) << 11 | (g >> 2) << 5 | (b >> 3), "r8": v & M, "r9": v >> 64}


def generate(rng, count, ctx):
    tests = []
    for i in range(count):
        r, g, b = (rng.randrange(256) for _ in range(3))
        lo, hi = rng.getrandbits(64), rng.getrandbits(64)
        n = rng.choice([0, 1, 63, 64, 65, 127, rng.randrange(128)])
        tests.append({"name": f"random {i}",
                      "regs": {"rdi": r, "rsi": g, "rdx": b, "r10": lo, "r11": hi, "rcx": n},
                      "expect": {"regs": expect(r, g, b, lo, hi, n)}})
    return tests
